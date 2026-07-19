from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import today

from ftms.tenant import company_filters, get_user_company, resolve_company


@frappe.whitelist(allow_guest=True)
def list_trips(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Trip",
		filters=filters,
		fields=["name", "company", "trip_title", "trip_date", "route", "vehicle", "trip_status"],
		order_by="trip_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_trip(name, company=None):
	doc = frappe.get_doc("Trip", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and doc.company != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()


@frappe.whitelist()
def create_trip(trip_title, route, trip_date=None, vehicle=None, assigned_captain_user=None):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)

	resolved_company = get_user_company()
	if not resolved_company:
		frappe.throw(_("Company is required."))

	doc = frappe.get_doc({
		"doctype": "Trip",
		"company": resolved_company,
		"trip_title": trip_title,
		"trip_date": trip_date or today(),
		"route": route,
		"vehicle": vehicle,
		"assigned_captain_user": assigned_captain_user,
		"trip_status": "Scheduled",
	})
	doc.insert()
	return {
		"name": doc.name,
		"trip_title": doc.trip_title,
		"trip_date": doc.trip_date,
		"route": doc.route,
		"vehicle": doc.vehicle,
		"trip_status": doc.trip_status,
		"company": doc.company,
	}
