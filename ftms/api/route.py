from __future__ import annotations

import frappe

from ftms.tenant import company_filters, get_user_company, resolve_company


@frappe.whitelist(allow_guest=True)
def list_routes(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Route",
		filters=filters,
		fields=[
			"name",
			"company",
			"route_title",
			"route_code",
			"source",
			"destination",
			"distance_km",
			"estimated_duration_minutes",
			"status",
		],
		order_by="modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def create_route(source, destination, company=None, route_title=None, route_code=None, status="Active"):
	resolved_company = get_user_company()
	if not resolved_company:
		frappe.throw("Company is required.")
	if company and company != resolved_company:
		frappe.throw("Not permitted for this company", frappe.PermissionError)
	doc = frappe.get_doc(
		{
			"doctype": "Route",
			"company": resolved_company,
			"route_title": route_title,
			"route_code": route_code,
			"source": source,
			"destination": destination,
			"status": status or "Active",
		}
	)
	doc.insert(ignore_permissions=True)
	return {
		"name": doc.name,
		"company": doc.company,
		"route_title": doc.route_title,
		"route_code": doc.route_code,
		"source": doc.source,
		"destination": doc.destination,
		"distance_km": doc.distance_km,
		"estimated_duration_minutes": doc.estimated_duration_minutes,
		"status": doc.status,
	}


@frappe.whitelist()
def get_route(name, company=None):
	doc = frappe.get_doc("Route", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and doc.company != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()
