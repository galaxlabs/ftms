from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, getdate


def _clean_text(value):
	if not value:
		return ""
	return re.sub(r"\s+", " ", str(value)).strip()


class TripPricingRule(Document):
	def before_insert(self):
		if not self.rule_code:
			self.rule_code = make_autoname("TPR-.#####")

	def validate(self):
		self.service_type = _clean_text(self.service_type)
		self.notes = _clean_text(self.notes)
		self.status = _clean_text(self.status or "Active") or "Active"
		self.is_active = 1 if self.status == "Active" else 0
		self.rule_title = " | ".join(
			value for value in [self.base_company, self.route, self.vehicle_type, self.trip_type] if value
		)

		if not self.base_company:
			frappe.throw(_("Base Company is required."))
		if not self.currency:
			frappe.throw(_("Currency is required."))
		if not self.effective_from:
			frappe.throw(_("Effective From is required."))
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero."))
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))
