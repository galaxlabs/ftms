from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class Vehicle(Document):
	def validate(self):
		self.set_vehicle_code()
		self.set_passenger_capacity()
		self.validate_catalog_dependencies()
		self.validate_identity_uniqueness()
		self.validate_required_documents()

	def validate_catalog_dependencies(self):
		if not self.vehicle_model:
			return
		model = frappe.db.get_value(
			"Vehicle Model",
			self.vehicle_model,
			["vehicle_make", "vehicle_type", "vehicle_category"],
			as_dict=True,
		)
		if not model:
			frappe.throw(_("Selected vehicle model does not exist"))
		if self.vehicle_make and model.vehicle_make != self.vehicle_make:
			frappe.throw(_("Selected model does not belong to the selected make"))
		if self.vehicle_type and model.vehicle_type != self.vehicle_type:
			frappe.throw(_("Selected model does not belong to the selected vehicle type"))
		self.vehicle_make = model.vehicle_make
		self.vehicle_type = model.vehicle_type

	def validate_identity_uniqueness(self):
		for fieldname, label in (("plate_no", "plate number"), ("chassis_no", "chassis number")):
			value = self.get(fieldname)
			if value and frappe.db.exists(
				"Vehicle",
				{"company": self.company, fieldname: value, "name": ("!=", self.name)},
			):
				frappe.throw(_("This {0} is already registered for the company").format(label))

	def validate_required_documents(self):
		requirements = frappe.get_all(
			"Vehicle Document Requirement",
			filters={"vehicle_type": self.vehicle_type, "enabled": 1, "mandatory": 1, "blocks_assignment": 1},
			fields="*",
		)
		for requirement in requirements:
			values = self._document_values(requirement.document_type)
			if requirement.requires_number and not values.get("number"):
				frappe.throw(_("{0}: document number is required").format(requirement.requirement_name))
			if requirement.requires_expiry:
				expiry = values.get("expiry")
				if not expiry:
					frappe.throw(_("{0}: expiry date is required").format(requirement.requirement_name))
				if getdate(expiry) < getdate(today()):
					frappe.throw(_("{0}: document is expired").format(requirement.requirement_name))
			if requirement.requires_attachment and not values.get("attachment"):
				frappe.throw(_("{0}: attachment is required").format(requirement.requirement_name))

	def _document_values(self, document_type):
		legacy = {
			"Registration": (self.registration_no, self.registration_expiry_date, self.registration_document),
			"Insurance": (None, self.insurance_expiry_date, self.insurance_document),
			"Operation Card": (self.operation_card_no, self.operation_card_expiry_date, self.operation_card_document),
		}
		if document_type in legacy:
			number, expiry, attachment = legacy[document_type]
			return {"number": number, "expiry": expiry, "attachment": attachment}
		for row in self.documents or []:
			if (row.document_type or "").casefold() == document_type.casefold():
				return {"number": row.document_number, "expiry": row.expiry_date, "attachment": row.attachment}
		return {}

	def set_vehicle_code(self):
		"""Use a stable, readable identifier instead of a manually entered name."""
		if not self.plate_no:
			return
		company_code = frappe.db.get_value("Company", self.company, "company_code") if self.company else None
		company_code = company_code or self.company or "CAPTAIN"
		company_abbr = re.sub(r"[^A-Z0-9]", "", str(company_code).upper())[:3] or "CAP"
		parts = [company_abbr, self.plate_no, self.vehicle_model, self.vehicle_make]
		base = "-".join(
			re.sub(r"[^A-Z0-9]+", "-", str(part or "").upper()).strip("-")
			for part in parts
			if part
		)
		if not base:
			return
		code = base[:140]
		counter = 2
		while frappe.db.exists("Vehicle", {"vehicle_code": code, "name": ("!=", self.name or "")}):
			suffix = f"-{counter}"
			code = f"{base[:140 - len(suffix)]}{suffix}"
			counter += 1
		self.vehicle_code = code
		self.vehicle_name = code

	def set_passenger_capacity(self):
		if self.seat_capacity and not self.passenger_capacity:
			self.passenger_capacity = self.seat_capacity
		if self.passenger_capacity and not self.seat_capacity:
			self.seat_capacity = self.passenger_capacity
