from __future__ import annotations

import frappe
from frappe import _

from ftms.tenant import get_user_company, resolve_company


@frappe.whitelist(allow_guest=True)
def list_companies(company=None, limit=100):
	if frappe.session.user == "Guest":
		filters = {"status": "Active", "blacklisted": 0}
		fields = ["name", "company_code", "company_name", "legal_name", "company_name_ar", "domain", "status"]
	else:
		active_company = get_user_company()
		if not active_company:
			return []
		if company and company != active_company:
			frappe.throw(_("Not permitted for this company"), frappe.PermissionError)
		filters = {"name": active_company}
		fields = ["name", "company_code", "company_name", "legal_name", "company_name_ar", "vat_no", "tax_id", "cr_no", "domain", "phone", "email", "status", "blacklisted"]
	return frappe.get_all(
		"Company",
		filters=filters,
		fields=fields,
		order_by="modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_company(name, company=None):
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and name != resolved_company:
		frappe.throw("Not permitted for this company")
	doc = frappe.get_doc("Company", name)
	return doc.as_dict()
