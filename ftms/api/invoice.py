from __future__ import annotations

import frappe

from ftms.tenant import company_filters, resolve_company


@frappe.whitelist()
def list_invoices(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"FTMS Trip Invoice",
		filters=filters,
		fields=["name", "company", "trip", "customer", "invoice_date", "status", "grand_total", "vat_amount"],
		order_by="invoice_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_invoice(name, company=None):
	doc = frappe.get_doc("FTMS Trip Invoice", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and getattr(doc, "company", None) != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()
