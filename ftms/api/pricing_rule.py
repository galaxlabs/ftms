from __future__ import annotations

import frappe

from ftms.tenant import company_filters


@frappe.whitelist(allow_guest=True)
def list_pricing_rules(company=None, limit=50):
	filters = company_filters(company=company)
	if filters:
		filters["is_active"] = 1
	else:
		filters = {"is_active": 1}
	return frappe.get_all(
		"Pricing Rule",
		filters=filters,
		fields=["name", "rule_name", "vehicle_type", "base_fare", "per_km_rate",
				"per_passenger_rate", "min_fare", "max_passengers", "is_active"],
		order_by="rule_name asc",
		limit_page_length=int(limit),
	)
