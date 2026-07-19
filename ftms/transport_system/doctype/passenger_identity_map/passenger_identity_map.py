from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname


def _clean(value):
	if not value:
		return ""
	return re.sub(r"\s+", " ", str(value)).strip()


class PassengerIdentityMap(Document):
	def before_insert(self):
		if not self.identity_code:
			self.identity_code = make_autoname("PID-.#####")

	def validate(self):
		self.passenger_name = _clean(self.passenger_name)
		self.passenger_name_ar = _clean(self.passenger_name_ar)
		self.mobile_no = _clean(self.mobile_no)
		self.email = _clean(self.email)
		self.firebase_uid = _clean(self.firebase_uid)
		self.auth_provider = _clean(self.auth_provider or "Other") or "Other"
		self.status = _clean(self.status or "Active") or "Active"
		self.is_active = 1 if self.status == "Active" else 0

		if not self.identity_title:
			parts = [self.passenger_name, self.mobile_no, self.firebase_uid]
			self.identity_title = " | ".join(part for part in parts if part) or self.identity_code
