import base64
import textwrap
import uuid
from datetime import datetime, timedelta

import frappe
from cryptography import x509
from cryptography.hazmat._oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.bindings._rust import ObjectIdentifier
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from frappe import _
from frappe.utils import add_months, get_datetime, get_site_path

try:
    import asn1
except ImportError:
    asn1 = None

try:
    import qrcode
    import numpy as np
    from PIL import Image
except ImportError:
    qrcode = None

def generate_private_keys():
    private_key = ec.generate_private_key(ec.SECP256K1(), backend=default_backend())
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return private_key_pem.decode("utf-8")

def build_csr(doc):
    private_key_pem = generate_private_keys()
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"), password=None, backend=default_backend()
    )
    csr_values = {
        "csr.common.name": doc.csrcommonname,
        "csr.serial.number": doc.csrserialnumber,
        "csr.organization.identifier": doc.csrorganizationidentifier,
        "csr.organization.unit.name": doc.csrorganizationunitname,
        "csr.organization.name": doc.csrorganizationname,
        "csr.country.name": doc.csrcountryname,
        "csr.invoice.type": doc.csrinvoicetype,
        "csr.location.address": doc.csrlocationaddress,
        "csr.industry.business.category": doc.csrindustrybusinesscategory,
    }
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, csr_values["csr.country.name"]),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, csr_values["csr.organization.unit.name"]),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, csr_values["csr.organization.name"]),
        x509.NameAttribute(NameOID.COMMON_NAME, csr_values["csr.common.name"]),
    ])
    custom_oid = ObjectIdentifier("1.3.6.1.4.1.311.20.2")
    oid_value = _get_oid_value(doc.zatca_environment)
    custom_extension = x509.UnrecognizedExtension(
        custom_oid, _encode_custom_oid_value(oid_value)
    ) if asn1 else None
    alt_name = x509.SubjectAlternativeName([
        x509.DirectoryName(x509.Name([
            x509.NameAttribute(NameOID.SURNAME, csr_values["csr.serial.number"]),
            x509.NameAttribute(NameOID.USER_ID, csr_values["csr.organization.identifier"]),
            x509.NameAttribute(NameOID.TITLE, csr_values["csr.invoice.type"]),
            x509.NameAttribute(ObjectIdentifier("2.5.4.26"), csr_values["csr.location.address"]),
            x509.NameAttribute(NameOID.BUSINESS_CATEGORY, csr_values["csr.industry.business.category"]),
        ]))
    ])
    builder = x509.CertificateSigningRequestBuilder()
    builder = builder.subject_name(subject)
    if custom_extension:
        builder = builder.add_extension(custom_extension, False)
    builder = builder.add_extension(alt_name, False)
    csr = builder.sign(private_key, hashes.SHA256(), default_backend())
    csr_pem = csr.public_bytes(serialization.Encoding.PEM)
    base64csr = base64.b64encode(csr_pem).decode("utf-8")
    return _save_csr(doc, private_key_pem, base64csr, csr_pem)

def _get_oid_value(environment):
    if environment == "Sandbox Portal":
        return "TESTZATCA-Code-Signing"
    elif environment == "Simulation Portal":
        return "PREZATCA-Code-Signing"
    return "ZATCA-Code-Signing"

def _encode_custom_oid_value(custom_string):
    encoder = asn1.Encoder()
    encoder.start()
    encoder.write(custom_string, asn1.Numbers.UTF8String)
    return encoder.output()

def _save_csr(doc, private_key_pem, base64csr, csr_pem):
    import re
    pem_str = private_key_pem.replace("\n", "")
    base64_key = re.search(
        r"-----BEGIN EC PRIVATE KEY-----(.*?)-----END EC PRIVATE KEY-----",
        pem_str,
    ).group(1).strip()
    doc.private_key = base64_key
    doc.private_key_pem_format = _format_pem(private_key_pem, "EC PRIVATE KEY")
    doc.csr = base64csr.strip()
    doc.csr_pem_format = csr_pem.decode("utf-8")
    doc.csr_generated = 1
    doc.save(ignore_permissions=True)
    return base64csr

def _format_pem(pem_str, key_type):
    pem_str = pem_str.strip()
    raw = pem_str.replace(f"-----BEGIN {key_type}-----", "")
    raw = raw.replace(f"-----END {key_type}-----", "")
    raw = raw.replace("\n", "").strip()
    wrapped = "\n".join(textwrap.wrap(raw, 64))
    return f"-----BEGIN {key_type}-----\n{wrapped}\n-----END {key_type}-----\n"

def get_certificate_and_public_key(binary_security_token, created_on):
    certificate_data = base64.b64decode(binary_security_token).decode("utf-8")
    cert_base64 = f"""
    -----BEGIN CERTIFICATE-----
    {certificate_data.strip()}
    -----END CERTIFICATE-----
    """
    cert = x509.load_pem_x509_certificate(cert_base64.encode(), default_backend())
    public_key = cert.public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    created_dt = get_datetime(created_on)
    expiry_dt = add_months(created_dt, 12)
    return {
        "certificate": certificate_data,
        "public_key": public_key_pem,
        "expiry_date": expiry_dt.strftime("%Y-%m-%d %H:%M:%S"),
    }

def get_pem_details(invoice):
    production_csid = get_prod_csid(invoice)
    compliance_csid = frappe.get_doc("Compliance CSID", production_csid.compliance_csid)
    csr_settings = frappe.get_doc("Zatca CSR Settings", compliance_csid.csr_settings)
    private_key = csr_settings.private_key_pem_format
    public_key = _clean_pem(production_csid.public_key, "PUBLIC KEY")
    certificate = (production_csid.certificate or "").strip().replace("\n", "")
    return {"private_key": private_key, "public_key": public_key, "certificate": certificate}

def get_prod_csid(invoice):
    company_doc = frappe.get_doc("Transportation Company", invoice.company)
    prod_csid = frappe.get_doc("Production CSID", company_doc.production_csid)
    return prod_csid

def get_previous_invoice_counter(production_csid):
    latest_transaction = frappe.get_all(
        "Zatca Transactions",
        filters={"production_csid": production_csid},
        fields=["invoice_icv"],
        order_by="transaction_time desc",
        limit_page_length=1,
    )
    if latest_transaction:
        return latest_transaction[0].invoice_icv
    return 0

def get_previous_invoice_hash(production_csid):
    latest_transaction = frappe.get_all(
        "Zatca Transactions",
        filters={"production_csid": production_csid},
        fields=["invoice_hash"],
        order_by="transaction_time desc",
        limit_page_length=1,
    )
    if latest_transaction:
        return latest_transaction[0].invoice_hash
    return "NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ=="

def get_qr_code(data):
    if not qrcode:
        frappe.throw("qrcode package is required for QR generation")
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_array = np.array(img)
    img_pil = Image.fromarray(img_array)
    bytes_list = []
    img_pil.save(_BytesIOEncoder(bytes_list), format="PNG")
    return "data:image/png;base64," + base64.b64encode(b"".join(bytes_list)).decode("utf-8")

class _BytesIOEncoder:
    def __init__(self, byte_list):
        self.byte_list = byte_list
    def write(self, b):
        self.byte_list.append(b)

def _clean_pem(pem_key, keyword):
    if not pem_key:
        return ""
    return "".join(line for line in pem_key.strip().splitlines() if keyword not in line)

def get_address(sales_invoice_doc):
    if sales_invoice_doc.custom_is_zatca_test:
        compliance_csid = frappe.get_doc("Compliance CSID", sales_invoice_doc.custom_compliance)
    else:
        production_csid = get_prod_csid(sales_invoice_doc)
        compliance_csid = frappe.get_doc("Compliance CSID", production_csid.compliance_csid)
    csr_settings = frappe.get_doc("Zatca CSR Settings", compliance_csid.csr_settings)
    company_address = {
        "address_line1": str(csr_settings.street_name or ""),
        "address_line2": str(csr_settings.building_number or ""),
        "city": str(csr_settings.city_name or ""),
        "pincode": str(csr_settings.postal_zone or ""),
        "state": str(csr_settings.city_subdivision_name or ""),
        "country": "Saudi Arabia",
        "registration_name": str(csr_settings.csrorganizationname or ""),
        "company_tax_id": str(csr_settings.csrorganizationidentifier or ""),
    }
    customer_doc = frappe.get_doc("Customer", sales_invoice_doc.customer)
    address_name = None
    if customer_doc.customer_primary_address:
        address_name = customer_doc.customer_primary_address
    else:
        customer_link = frappe.get_all("Dynamic Link",
            filters={"link_doctype": "Customer", "link_name": sales_invoice_doc.customer, "parenttype": "Address"},
            fields=["parent"], limit=1)
        if customer_link:
            address_name = customer_link[0].parent
    if address_name:
        address_fields = ["address_line1", "address_line2", "city", "pincode", "state", "country"]
        customer_address = frappe.get_value("Address", address_name, address_fields, as_dict=True)
    else:
        customer_address = {}
    return company_address, customer_address

def get_zatca_tax_category_details(invoice_doc):
    if not invoice_doc.taxes or not invoice_doc.taxes_and_charges:
        return {"category": "Standard Rate", "rate": 15.0, "code": "S",
                "exemption_reason_code": None, "exemption_reason_text": None}
    template = frappe.get_doc("Sales Taxes and Charges Template", invoice_doc.taxes_and_charges)
    tax_type = template.get("custom_tax_type", "Standard Rate")
    rate = template.get("tax_rate", 15.0)
    if template.taxes:
        rate = template.taxes[0].rate
    code_map = {"Standard Rate": "S", "Zero Rate": "Z", "Except Rate": "E"}
    reason_code = None
    reason_text = None
    if tax_type in ("Zero Rate", "Except Rate"):
        reason_field = f"custom_{tax_type.lower().replace(' ', '_')}_reason"
        reason_and_code = template.get(reason_field)
        if reason_and_code:
            reason_text, reason_code = reason_and_code.split("(", 1)
            reason_code = reason_code.rstrip(")")
            reason_text = reason_text.strip()
    return {
        "category": tax_type,
        "rate": rate,
        "code": code_map.get(tax_type, "O"),
        "exemption_reason_code": reason_code,
        "exemption_reason_text": reason_text,
    }

def time_formatter(posting_time):
    if isinstance(posting_time, str):
        try:
            return datetime.strptime(posting_time, "%H:%M:%S.%f").strftime("%H:%M:%S")
        except ValueError:
            return datetime.strptime(posting_time, "%H:%M:%S").strftime("%H:%M:%S")
    elif hasattr(posting_time, "strftime"):
        return posting_time.strftime("%H:%M:%S")
    elif isinstance(posting_time, timedelta):
        total_seconds = int(posting_time.total_seconds())
        return f"{total_seconds // 3600:02}:{(total_seconds % 3600) // 60:02}:{total_seconds % 60:02}"
    return "00:00:00"

def get_exemption_reason_map():
    return {
        "VATEX-SA-29": "Financial services mentioned in Article 29 of the VAT Regulations.",
        "VATEX-SA-30": "Real estate transactions mentioned in Article 30 of the VAT Regulations.",
        "VATEX-SA-32": "Export of goods.",
        "VATEX-SA-33": "Export of services.",
        "VATEX-SA-34-1": "The international transport of Goods.",
        "VATEX-SA-34-2": "International transport of passengers.",
        "VATEX-SA-35": "Medicines and medical equipment.",
        "VATEX-SA-36": "Qualifying metals.",
        "VATEX-SA-EDU": "Private education to citizen.",
        "VATEX-SA-HEA": "Private healthcare to citizen.",
        "VATEX-SA-OOS": "Free text reason to be provided by taxpayer.",
    }
