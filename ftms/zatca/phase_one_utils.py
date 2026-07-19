import base64
import hashlib

import frappe

def generate_phase_one_qr(sales_invoice):
    seller_name = sales_invoice.company
    vat_number = ""
    company_doc = frappe.get_doc("Company", sales_invoice.company)
    if company_doc:
        vat_number = company_doc.vat_no or ""
    timestamp = sales_invoice.posting_date.strftime("%Y-%m-%dT%H:%M:%SZ") if sales_invoice.posting_date else ""
    total = float(sales_invoice.grand_total or 0)
    vat_total = float(sales_invoice.vat_amount or 0)

    tlv = _build_tlv(seller_name, vat_number, timestamp, total, vat_total)
    return base64.b64encode(tlv).decode("utf-8")

def _build_tlv(seller_name, vat_number, timestamp, total, vat_total):
    tlv_data = b""
    tlv_data += _tlv_tag(1, seller_name.encode("utf-8"))
    tlv_data += _tlv_tag(2, vat_number.encode("utf-8"))
    tlv_data += _tlv_tag(3, timestamp.encode("utf-8"))
    tlv_data += _tlv_tag(4, str(total).encode("utf-8"))
    tlv_data += _tlv_tag(5, str(vat_total).encode("utf-8"))
    return tlv_data

def _tlv_tag(tag, value):
    length = len(value)
    return bytes([tag]) + bytes([length]) + value
