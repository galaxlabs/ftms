import base64
import hashlib
import xml.etree.ElementTree as ET

import frappe

def validate_sales_invoice(doc, method):
    if not doc.taxes_and_charges:
        frappe.throw("Sales Taxes and Charges Template must be provided.")
    if doc.is_return and (not doc.return_against and not doc.custom_cn_ref):
        frappe.throw("Go to credit note details and fetch return invoices")

def get_buyer_information(customer_name):
    customer = frappe.get_doc("Customer", customer_name)
    if customer.customer_type == "Company":
        address = frappe.get_doc("Address", customer.customer_primary_address)
        if not address:
            frappe.throw("Customer must have a primary address")
        if not customer.custom_vat_number and not customer.custom_registration_scheme:
            frappe.throw("Either VAT Number or Registration Scheme/Number required for Company")
        return {
            "organizationName": customer.customer_name,
            "vatNumber": customer.custom_vat_number,
            "registrationScheme": _get_registration_scheme_code(customer.custom_registration_scheme),
            "registrationNumber": customer.custom_registration_number,
            "streetName": address.address_line1,
            "buildingNumber": address.address_line2,
            "citySubdivisionName": address.city,
            "cityName": address.county,
            "postalZone": address.pincode,
            "countryCode": _get_country_code(address.country),
        }
    elif customer.customer_type == "Individual":
        return {"organizationName": customer.customer_name}
    return {}

def get_seller_information(csr_settings):
    return {
        "organizationName": csr_settings.csrorganizationname,
        "vatNumber": csr_settings.csrorganizationidentifier,
        "streetName": csr_settings.street_name,
        "buildingNumber": csr_settings.building_number,
        "citySubdivisionName": csr_settings.city_subdivision_name,
        "cityName": csr_settings.city_name,
        "postalZone": csr_settings.postal_zone,
        "countryCode": "SA",
        "registrationScheme": _get_registration_scheme_code(csr_settings.registration_scheme),
        "registrationNumber": csr_settings.registration_number,
    }

def _get_country_code(country_name):
    code = frappe.get_value("Country", filters={"name": country_name}, fieldname="code")
    return code.upper() if code else "SA"

def _get_registration_scheme_code(scheme):
    if not scheme:
        return ""
    start = scheme.find("(")
    end = scheme.find(")")
    if start != -1 and end != -1:
        return scheme[start + 1:end]
    return ""

def generate_invoice_payload_from_xml(xml_content):
    namespaces = {
        "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
        "sig": "urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2",
        "sac": "urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2",
        "xades": "http://uri.etsi.org/01903/v1.3.2#",
        "ds": "http://www.w3.org/2000/09/xmldsig#",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }
    root = ET.fromstring(xml_content)
    digest = root.find(".//ds:SignedInfo/ds:Reference/ds:DigestValue", namespaces)
    if digest is None or not digest.text:
        raise Exception("DigestValue not found in XML")
    uuid_el = root.find("cbc:UUID", namespaces)
    if uuid_el is None or not uuid_el.text:
        raise Exception("UUID not found in XML")
    return {
        "uuid": uuid_el.text.strip(),
        "invoiceHash": digest.text.strip(),
        "invoice": base64.b64encode(xml_content).decode("utf-8"),
    }

def extract_canonical_xml(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        namespaces = {
            "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }
        for ext_elem in root.findall(".//ext:UBLExtensions", namespaces):
            root.remove(ext_elem)
        for sig_elem in root.findall(".//cac:Signature", namespaces):
            root.remove(sig_elem)
        for doc_ref in root.findall(".//cac:AdditionalDocumentReference", namespaces):
            id_node = doc_ref.find(".//cbc:ID", namespaces)
            if id_node is not None and id_node.text == "QR":
                root.remove(doc_ref)
        return ET.tostring(root, encoding="unicode")
    except Exception:
        return None

def generate_invoice_hash(xml_file=None):
    content = None
    if xml_file:
        content = extract_canonical_xml(xml_file)
    if not content or str(content).strip() == "":
        content = "0"
    return base64.b64encode(hashlib.sha256(content.encode("utf-8")).digest()).decode("utf-8")
