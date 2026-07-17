from __future__ import annotations

import frappe

from ftms.tenant import company_filters, resolve_company


@frappe.whitelist()
def list_trips(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Trip",
		filters=filters,
		fields=["name", "company", "trip_title", "trip_code", "trip_date", "trip_status", "route", "vehicle"],
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
