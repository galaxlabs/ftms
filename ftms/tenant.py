from __future__ import annotations

import frappe
from frappe import _


SYSTEM_USERS = {"Administrator", "Guest"}


def _current_user(user=None):
	return user or frappe.session.user


def is_system_user(user=None):
	return _current_user(user) == "Administrator"


def is_guest(user=None):
	return _current_user(user) in (None, "Guest")


def get_user_companies(user=None):
	user = _current_user(user)
	if not user or user == "Guest":
		return []
	return frappe.get_all(
		"User Company Link",
		filters={"user": user, "status": "Active"},
		fields=["name", "company", "role", "is_owner", "status"],
		order_by="modified desc",
	)


def get_user_company(user=None):
	rows = get_user_companies(user=user)
	return rows[0].get("company") if rows else None


def has_company_access(company, user=None):
	if not company:
		return False
	if is_system_user(user):
		return True
	return any(row.get("company") == company for row in get_user_companies(user=user))


def require_company_access(company, user=None):
	user = _current_user(user)
	if not company:
		frappe.throw(_("Company is required."))
	if is_system_user(user):
		return company
	if is_guest(user) or not has_company_access(company, user=user):
		frappe.throw(_("Not permitted for this company."), frappe.PermissionError)
	return company


def set_company_from_user(doc, fieldname="company"):
	company = doc.get(fieldname)
	if company:
		return require_company_access(company)
	company = get_user_company()
	if company:
		doc.set(fieldname, company)
		return company
	return None


def resolve_company(company=None, user=None, allow_missing=False):
	user = _current_user(user)
	if company:
		return require_company_access(company, user=user)
	company = get_user_company(user=user)
	if company:
		return company
	if allow_missing:
		return None
	frappe.throw(_("Company is required."))


def require_company(doc, fieldname="company"):
	company = set_company_from_user(doc, fieldname=fieldname)
	if not company:
		frappe.throw(_("Company is required."))
	return company


def company_filters(company=None, user=None):
	user = _current_user(user)
	company = resolve_company(company=company, user=user, allow_missing=True)
	if company:
		return {"company": company}
	if is_guest(user):
		return {"company": "__guest_no_company_access__"}
	return {"company": "__no_company_access__"}
