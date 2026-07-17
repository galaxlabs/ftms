import frappe
from frappe import _

_VAT_TEMPLATE_AVAILABLE = None

def _vat_template_available():
    global _VAT_TEMPLATE_AVAILABLE
    if _VAT_TEMPLATE_AVAILABLE is None:
        try:
            import frappe
            frappe.db.sql("SELECT COUNT(*) FROM `tabSales Taxes and Charges Template` LIMIT 1")
            _VAT_TEMPLATE_AVAILABLE = True
        except Exception:
            _VAT_TEMPLATE_AVAILABLE = False
    return _VAT_TEMPLATE_AVAILABLE

def validate_trip_invoice(doc, method):
    if doc.enable_zatca and _vat_template_available():
        if not doc.vat_template:
            frappe.throw("VAT Template must be provided when ZATCA E-Invoicing is enabled.")

def on_submit_trip_invoice(doc, method):
    if doc.enable_zatca:
        from ftms.zatca.clearence_util import generate_einvoice
        generate_einvoice(doc, submit_now=True)

def get_customer_type(doc):
    if doc.customer:
        customer = frappe.get_doc("Customer", doc.customer)
        return customer.customer_type
    return "Individual"

def get_customer_name(doc):
    return doc.customer or "Walk-in Customer"

def get_taxes_and_charges(doc):
    return doc.vat_template

def get_posting_date(doc):
    return doc.invoice_date

def get_posting_time(doc):
    return doc.get("posting_time") or "12:00:00"

def get_is_return(doc):
    return False

def get_is_debit_note(doc):
    return False

def get_taxes(doc):
    return doc.get("items", [])

def get_company(doc):
    return doc.company

def get_is_zatca_test(doc):
    return doc.is_zatca_test

def get_compliance_csid(doc):
    return doc.compliance_csid

def set_zatca_fields(doc, invoice_data, response_json, payload, status, zatca_status_field):
    doc.invoice_type = invoice_data["invoice_type"]
    doc.invoice_hash = payload.get("invoiceHash")
    doc.invoice_unique_identifier = invoice_data["uuid"]
    doc.invoice_icv = invoice_data["invoice_counter"]
    doc.zatca_submit_status = status
    doc.zatca_submit_time = frappe.utils.now_datetime()
    doc.seller_name = invoice_data["seller"].get("organizationName")
    doc.seller_vat = invoice_data["seller"].get("vatNumber")
    doc.buyer_name = invoice_data["buyer"].get("organizationName")
    doc.buyer_vat = invoice_data["buyer"].get("vatNumber")

def clear_zatca_fields(doc, status, validation_results):
    doc.zatca_submit_status = status
    doc.validation_results = validation_results
