from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class VehicleDocumentRequirement(Document):
	def validate(self):
		if not self.document_type:
			frappe.throw(_("Document type is required"))
