from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, today

from ftms.tenant import company_filters, resolve_company


def _rule_matches(rule, route, distance_km, vehicle=None):
	if vehicle and rule.vehicle and rule.vehicle != vehicle:
		return False
	if not vehicle and rule.vehicle:
		return False
	if route and rule.route and rule.route != route:
		return False
	if rule.distance_min_km and distance_km < rule.distance_min_km:
		return False
	if rule.distance_max_km and distance_km > rule.distance_max_km:
		return False
	if rule.valid_from and getdate(rule.valid_from) > getdate(today()):
		return False
	if rule.valid_until and getdate(rule.valid_until) < getdate(today()):
		return False
	return True


def _resolve_rule(company, vehicle_type, route=None, distance_km=0, vehicle=None, rule_name=None):
	filters = {"company": company, "vehicle_type": vehicle_type, "is_active": 1}
	if rule_name:
		filters["name"] = rule_name
	rules = frappe.get_all(
		"Pricing Rule",
		filters=filters,
		fields="*",
		order_by="modified desc",
	)
	matches = [rule for rule in rules if _rule_matches(rule, route, distance_km, vehicle=vehicle)]
	if not matches:
		return None
	return sorted(
		matches,
		key=lambda rule: (
			1 if vehicle and rule.vehicle == vehicle else 0,
			1 if route and rule.route == route else 0,
			1 if rule.distance_min_km or rule.distance_max_km else 0,
		),
		reverse=True,
	)[0]


def calculate_quote(company, vehicle_type, route=None, distance_km=None, passenger_count=1, vehicle=None, rule_name=None):
	"""Calculate a bounded quote using distance, demand, and available supply."""
	if not company or not vehicle_type:
		return None
	if distance_km is None and route:
		distance_km = frappe.db.get_value("Route", route, "distance_km")
	distance_km = max(float(distance_km or 0), 0)
	passenger_count = max(int(passenger_count or 1), 1)
	rule = _resolve_rule(company, vehicle_type, route, distance_km, vehicle=vehicle, rule_name=rule_name)
	if not rule:
		return None

	demand_filters = {
		"company": company,
		"vehicle_type": vehicle_type,
		"negotiation_status": "Awaiting Offers",
		"booking_status": ("!=", "Cancelled"),
	}
	demand_count = frappe.db.count("Trip Booking", filters=demand_filters)
	supply_count = frappe.db.count(
		"Vehicle",
		filters={
			"company": company,
			"vehicle_type": vehicle_type,
			"is_active": 1,
			"status": "Active",
		},
	)
	demand_index = demand_count / max(supply_count, 1)
	supply_index = supply_count / max(demand_count, 1)
	demand_adjustment = min(
		max(demand_index - 1, 0) * float(rule.demand_weight or 0) / 100,
		float(rule.demand_surge_cap or 0) / 100,
	)
	supply_adjustment = min(
		max(supply_index - 1, 0) * float(rule.supply_weight or 0) / 100,
		float(rule.supply_discount_cap or 0) / 100,
	)
	base_fare = (
		float(rule.base_fare or 0)
		+ distance_km * float(rule.per_km_rate or 0)
		+ passenger_count * float(rule.per_passenger_rate or 0)
	)
	market_fare = base_fare * (1 + demand_adjustment - supply_adjustment)
	minimum = float(rule.min_fare or 0)
	maximum = float(rule.max_fare or 0)
	final_fare = max(market_fare, minimum)
	if maximum:
		final_fare = min(final_fare, maximum)
	return {
		"pricing_rule": rule.name,
		"vehicle": rule.vehicle,
		"distance_km": round(distance_km, 2),
		"base_fare": round(base_fare, 2),
		"demand_count": demand_count,
		"supply_count": supply_count,
		"demand_index": round(demand_index, 4),
		"supply_index": round(supply_index, 4),
		"demand_adjustment": round(demand_adjustment, 4),
		"supply_adjustment": round(supply_adjustment, 4),
		"minimum_fare": round(minimum, 2),
		"maximum_fare": round(maximum, 2),
		"final_fare": round(final_fare, 2),
	}


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
		fields=["name", "rule_name", "vehicle_type", "vehicle", "base_fare", "per_km_rate",
				"per_passenger_rate", "min_fare", "max_fare", "route", "distance_min_km",
				"distance_max_km", "demand_weight", "supply_weight", "is_active"],
		order_by="rule_name asc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_price_quote(vehicle_type, route=None, distance_km=None, passenger_count=1, vehicle=None, company=None, pricing_rule=None):
	company = resolve_company(company=company)
	quote = calculate_quote(
		company,
		vehicle_type,
		route=route,
		distance_km=distance_km,
		passenger_count=passenger_count,
		vehicle=vehicle,
		rule_name=pricing_rule,
	)
	if not quote:
		frappe.throw(_("No active pricing rule matches this vehicle, route, and distance"))
	return quote
