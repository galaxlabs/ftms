from __future__ import annotations

import frappe
from frappe import _

from ftms.tenant import company_filters, get_user_company, resolve_company


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


@frappe.whitelist()
def create_customer(customer_name, mobile_no=None, email=None, customer_name_ar=None):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)

	resolved_company = get_user_company()
	if not resolved_company:
		frappe.throw(_("Company is required."))

	doc = frappe.get_doc({
		"doctype": "Customer",
		"company": resolved_company,
		"customer_name": customer_name,
		"customer_name_ar": customer_name_ar,
		"mobile_no": mobile_no,
		"email": email,
		"status": "Active",
	})
	doc.insert(ignore_permissions=True)
	return {
		"name": doc.name,
		"customer_name": doc.customer_name,
		"customer_name_ar": doc.customer_name_ar,
		"mobile_no": doc.mobile_no,
		"email": doc.email,
		"company": doc.company,
		"status": doc.status,
	}
