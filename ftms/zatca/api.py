import frappe
from frappe import _

from ftms.zatca.utils import build_csr, get_certificate_and_public_key, generate_private_keys

@frappe.whitelist()
def generate_csr(doc_name):
    doc = frappe.get_doc("Zatca CSR Settings", doc_name)
    return build_csr(doc)

@frappe.whitelist()
def get_zatca_status(company):
    company_doc = frappe.get_doc("Company", company)
    status = {
        "zatca_enabled": company_doc.enable_zatca_e_invoicing,
        "zatca_phase": company_doc.zatca_phase,
        "has_production_csid": bool(company_doc.production_csid),
        "has_compliance_csid": bool(company_doc.compliance_csid),
    }
    if company_doc.production_csid:
        prod = frappe.get_doc("Production CSID", company_doc.production_csid)
        status["production_csid_expiry"] = str(prod.expiry_date) if prod.expiry_date else None
    return status

@frappe.whitelist()
def get_certificate_and_key(binary_security_token, created_on):
    return get_certificate_and_public_key(binary_security_token, created_on)

@frappe.whitelist()
def onboard_zatca(company):
    company_doc = frappe.get_doc("Company", company)
    if not company_doc.enable_zatca_e_invoicing:
        frappe.throw("Enable ZATCA E-Invoicing first")
    if company_doc.zatca_phase != "ZATCA Phase 2":
        frappe.throw("Set ZATCA Phase to Phase 2 first")
    return {"message": "ZATCA onboarding initiated", "company": company}

@frappe.whitelist()
def delete_test_invoices():
    test_invoices = frappe.get_all("Sales Invoice", filters={"custom_is_zatca_test": 1}, fields=["name"])
    for inv in test_invoices:
        try:
            doc = frappe.get_doc("Sales Invoice", inv.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Sales Invoice", inv.name, force=1)
        except Exception:
            pass
    return {"message": f"Deleted {len(test_invoices)} test invoices"}
