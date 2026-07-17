import base64
import hashlib
import xml.etree.ElementTree as ET

import frappe

def validate_sales_invoice(doc, method):
    taxes_field = doc.get("taxes_and_charges") or doc.get("vat_template")
    if not taxes_field:
        frappe.throw("Tax Template must be provided.")
    if doc.get("is_return") and (not doc.get("return_against") and not doc.get("custom_cn_ref")):
        frappe.throw("Go to credit note details and fetch return invoices")

def get_buyer_information(customer_name):
    if not customer_name or not frappe.db.exists("Customer", customer_name):
        return {"organizationName": customer_name or "Walk-in Customer"}
    customer = frappe.get_doc("Customer", customer_name)
    if customer.customer_type == "Company":
        address = None
        if customer.customer_primary_address:
            address = frappe.get_doc("Address", customer.customer_primary_address)
        return {
            "organizationName": customer.customer_name,
            "vatNumber": getattr(customer, "custom_vat_number", None),
            "registrationScheme": _get_registration_scheme_code(getattr(customer, "custom_registration_scheme", None)),
            "registrationNumber": getattr(customer, "custom_registration_number", None),
            "streetName": address.address_line1 if address else "",
            "buildingNumber": address.address_line2 if address else "",
            "citySubdivisionName": address.city if address else "",
            "cityName": address.county if address else "",
            "postalZone": address.pincode if address else "",
            "countryCode": _get_country_code(address.country) if address else "SA",
        }
    return {"organizationName": customer.customer_name}

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
