from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


class SubscriptionAgreement(Document):
	def validate(self):
		self.billing_period_months = max(cint(self.billing_period_months) or 1, 1)
		self.active_days = cint(self.active_days) or self.billing_period_months * 30
		self.active_hours_per_day = flt(self.active_hours_per_day) or 8
		self.total_active_hours = flt(self.active_days) * flt(self.active_hours_per_day)
		self.calculated_period_amount = calculate_amount(self)


def calculate_amount(doc):
	vehicle_count = get_vehicle_count(doc.company, doc.vehicle_count_source, doc.manual_vehicle_count)
	minimum_vehicles = max(cint(doc.minimum_vehicles) or 0, 0)
	billable_vehicles = max(vehicle_count, minimum_vehicles)
	billing_basis = doc.billing_basis or "Per Vehicle Per Month"

	if billing_basis == "Fixed Period Amount":
		return flt(doc.fixed_period_amount)

	if billing_basis == "Manual":
		return flt(doc.calculated_period_amount or doc.fixed_period_amount)

	return flt(doc.price_per_vehicle_per_month) * billable_vehicles * max(cint(doc.billing_period_months) or 1, 1)


def get_vehicle_count(company, source=None, manual_vehicle_count=None):
	if source == "Manual":
		return cint(manual_vehicle_count)
	if not company:
		return 0
	rows = frappe.db.sql(
		"""
		select count(*)
		from `tabVehicle`
		where company = %s and coalesce(status, '') not in ('Inactive', 'Suspended', 'Sold')
		""",
		(company,),
	)
	return cint(rows[0][0]) if rows else 0
