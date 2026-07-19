from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import today

from ftms.tenant import company_filters, get_user_company, resolve_company


@frappe.whitelist(allow_guest=True)
def list_invoices(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Trip Invoice",
		filters=filters,
		fields=["name", "company", "invoice_date", "customer", "vat_amount", "grand_total", "status"],
		order_by="invoice_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_invoice(name, company=None):
	doc = frappe.get_doc("Trip Invoice", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and doc.company != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()


@frappe.whitelist()
def create_invoice(customer, trip=None, invoice_date=None, fare_amount=None, vat_amount=None, grand_total=None):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)

	resolved_company = get_user_company()
	if not resolved_company:
		frappe.throw(_("Company is required."))

	doc = frappe.get_doc({
		"doctype": "Trip Invoice",
		"company": resolved_company,
		"customer": customer,
		"trip": trip,
		"invoice_date": invoice_date or today(),
		"fare_amount": fare_amount,
		"vat_amount": vat_amount,
		"grand_total": grand_total,
		"status": "Draft",
	})
	doc.insert(ignore_permissions=True)
	return {
		"name": doc.name,
		"customer": doc.customer,
		"invoice_date": doc.invoice_date,
		"grand_total": doc.grand_total,
		"status": doc.status,
		"company": doc.company,
	}
