import frappe
from frappe import _

from ftms.zatca.api import generate_csr, get_zatca_status, onboard_zatca, get_certificate_and_key, delete_test_invoices
from ftms.zatca.clearence_util import resend_einvoice, bulk_resend_einvoices
from ftms.zatca.utils import get_pem_details

@frappe.whitelist()
def generate_csr_endpoint(doc_name):
    return generate_csr(doc_name)

@frappe.whitelist()
def get_status(company):
    return get_zatca_status(company)

@frappe.whitelist()
def onboard(company):
    return onboard_zatca(company)

@frappe.whitelist()
def get_certificate(binary_security_token, created_on):
    return get_certificate_and_key(binary_security_token, created_on)

@frappe.whitelist()
def get_pem(invoice):
    return get_pem_details(invoice)

@frappe.whitelist()
def resend(invoice_name):
    if isinstance(invoice_name, str):
        doc = frappe.get_doc("Sales Invoice", invoice_name)
    return resend_einvoice(doc)

@frappe.whitelist()
def bulk_resend(invoice_names):
    return bulk_resend_einvoices(invoice_names)

@frappe.whitelist()
def delete_test():
    return delete_test_invoices()
