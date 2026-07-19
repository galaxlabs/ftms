from __future__ import annotations

import uuid

import frappe
from frappe import _
from frappe.model.document import Document


class ComplianceCSID(Document):
	def validate(self):
		if not self.compliance_csid_name:
			self.compliance_csid_name = f"CCSID-{frappe.generate_hash(length=8)}"
		if not self.status:
			self.status = "Pending"

	def on_trash(self):
		frappe.throw(_("Compliance CSID records cannot be deleted. Revoke instead."))


