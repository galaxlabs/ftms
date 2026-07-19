from __future__ import annotations

import frappe
from frappe import _

from ftms.tenant import company_filters, get_user_company, resolve_company


@frappe.whitelist(allow_guest=True)
def list_contracts(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Employee Transport Contract",
		filters=filters,
		fields=["name", "company", "contract_title", "route", "shift_type", "is_active"],
		order_by="modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_contract(name, company=None):
	doc = frappe.get_doc("Employee Transport Contract", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and doc.company != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()


@frappe.whitelist()
def create_contract(contract_title, route, shift_type=None, is_active=1):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)

	resolved_company = get_user_company()
	if not resolved_company:
		frappe.throw(_("Company is required."))

	doc = frappe.get_doc({
		"doctype": "Employee Transport Contract",
		"company": resolved_company,
		"contract_title": contract_title,
		"route": route,
		"shift_type": shift_type or "Morning",
		"is_active": int(is_active),
	})
	doc.insert()
	return {
		"name": doc.name,
		"contract_title": doc.contract_title,
		"route": doc.route,
		"shift_type": doc.shift_type,
		"is_active": doc.is_active,
		"company": doc.company,
	}
