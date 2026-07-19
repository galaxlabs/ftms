from __future__ import annotations

import uuid

import frappe
from frappe import _
from frappe.model.document import Document


class ProductionCSID(Document):
	def validate(self):
		if not self.production_csid_name:
			self.production_csid_name = f"PCSID-{frappe.generate_hash(length=8)}"
		if not self.status:
			self.status = "Pending"

	def on_trash(self):
		frappe.throw(_("Production CSID records cannot be deleted. Revoke instead."))


