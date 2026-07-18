from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ZATCAEnvironment(Document):
	def validate(self):
		_require_url(self.compliance_csid_api, "Compliance CSID API")
		_require_url(self.production_csid_api, "Production CSID API")
		_require_url(self.invoice_clearance_api, "Invoice Clearance API")
		_require_url(self.invoice_reporting_api, "Invoice Reporting API")


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


class ComplianceCSID(Document):
	def validate(self):
		if not self.compliance_csid_name:
			self.compliance_csid_name = f"CCSID-{frappe.generate_hash(length=8)}"
		if not self.status:
			self.status = "Pending"

	def on_trash(self):
		frappe.throw(_("Compliance CSID records cannot be deleted. Revoke instead."))


class ProductionCSID(Document):
	def validate(self):
		if not self.production_csid_name:
			self.production_csid_name = f"PCSID-{frappe.generate_hash(length=8)}"
		if not self.status:
			self.status = "Pending"

	def on_trash(self):
		frappe.throw(_("Production CSID records cannot be deleted. Revoke instead."))


class ZatcaTransactions(Document):
	def validate(self):
		if not self.transaction_date:
			self.transaction_date = frappe.utils.now_datetime()


def _require_url(value, label):
	if not value or not value.startswith(("http://", "https://")):
		frappe.throw(_("{0} must be a valid URL starting with http:// or https://").format(label))


def _generate_serial_number():
	import uuid
	return "1-FTMS|2-V15|3-" + str(uuid.uuid4())
