from __future__ import annotations

import frappe
from frappe import _


def get_user_company(user=None):
	user = user or frappe.session.user
	if not user:
		return None
	rows = frappe.get_all(
		"User Company Link",
		filters={"user": user, "status": "Active"},
		fields=["company"],
		order_by="modified desc",
		limit=1,
	)
	return rows[0].company if rows else None


def set_company_from_user(doc, fieldname="company"):
	company = doc.get(fieldname)
	if company:
		return company
	company = get_user_company()
	if company:
		doc.set(fieldname, company)
		return company
	return None


def resolve_company(company=None, user=None, allow_missing=False):
	if company:
		return company
	company = get_user_company(user=user)
	if company or allow_missing:
		return company
	frappe.throw(_("Company is required."))


def require_company(doc, fieldname="company"):
	company = set_company_from_user(doc, fieldname=fieldname)
	if not company:
		frappe.throw(_("Company is required."))
	return company


def company_filters(company=None, user=None):
	company = resolve_company(company=company, user=user, allow_missing=True)
	return {"company": company} if company else {}
