from __future__ import annotations

import uuid

import frappe
from frappe import _
from frappe.model.document import Document


def _generate_serial_number():
    return "1-FTMS|2-V15|3-" + str(uuid.uuid4())


class ZatcaCSRSettings(Document):
	def validate(self):
		self._validate_required()
		self._validate_address()
		if not self.csrserialnumber:
			self.csrserialnumber = _generate_serial_number()

	def _validate_required(self):
		required = {
			"csrcommonname": "Common Name",
			"csrorganizationidentifier": "Organization Identifier",
			"csrorganizationunitname": "Organization Unit Name",
			"csrorganizationname": "Organization Name",
			"csrlocationaddress": "Location Address",
			"csrindustrybusinesscategory": "Industry Business Category",
			"registration_number": "Registration Number",
		}
		for field, label in required.items():
			if not self.get(field):
				frappe.throw(_("{0} is required").format(label))

	def _validate_address(self):
		if not self.city_name:
			frappe.throw(_("City Name is required"))
		if not self.postal_zone:
			frappe.throw(_("Postal Zone is required"))
		if not self.building_number:
			frappe.throw(_("Building Number is required"))


