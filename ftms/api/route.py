from __future__ import annotations

import frappe

from ftms.tenant import company_filters, resolve_company


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
def get_route(name, company=None):
	doc = frappe.get_doc("Route", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and doc.company != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()
