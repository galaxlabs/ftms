from __future__ import annotations

import frappe

from ftms.tenant import company_filters, resolve_company


@frappe.whitelist()
def list_customers(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Customer",
		filters=filters,
		fields=["name", "company", "customer_name", "customer_name_ar", "mobile_no", "email", "status"],
		order_by="modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_customer(name, company=None):
	doc = frappe.get_doc("Customer", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and getattr(doc, "company", None) != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()
