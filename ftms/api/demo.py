from __future__ import annotations

import frappe

from ftms.utils.demo_data import seed_demo_transport_cycle


@frappe.whitelist()
def seed_transport_demo(company, route=None):
	return seed_demo_transport_cycle(company=company, route=route)
