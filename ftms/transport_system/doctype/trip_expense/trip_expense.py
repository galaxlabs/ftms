import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class TripExpense(Document):
	def validate(self):
		if self.trip:
			trip = frappe.db.get_value("Trip", self.trip, ["company", "assigned_captain_user", "vehicle"], as_dict=True)
			if trip:
				if trip.company != self.company:
					frappe.throw("Trip must belong to the selected company")
				if not self.captain_user:
					self.captain_user = trip.assigned_captain_user
				if not self.vehicle:
					self.vehicle = trip.vehicle

		self.net_amount = flt(self.net_amount)
		self.vat_amount = flt(self.vat_amount)
		if not self.total_amount:
			self.total_amount = self.net_amount + self.vat_amount

		self.validate_receipt_company_match()

		if self.captain_user:
			active = frappe.db.exists("User Company Link", {"user": self.captain_user, "company": self.company, "role": "Captain", "status": "Active"})
			if not active:
				frappe.throw("Captain user must be active in the selected company")

	def before_save(self):
		if self.status == "Approved" and not self.approved_on:
			self.approved_by = self.approved_by or frappe.session.user
			self.approved_on = now_datetime()

	def validate_receipt_company_match(self):
		ocr_names = [self.get("ocr_company_name"), self.get("ocr_company_name_ar")]
		ocr_names = [normalize(value) for value in ocr_names if value]
		if not ocr_names:
			self.receipt_validation_status = self.receipt_validation_status or "Not Checked"
			return

		company = frappe.db.get_value("Company", self.company, ["company_name", "legal_name", "company_name_ar"], as_dict=True) or {}
		company_names = [normalize(value) for value in company.values() if value]
		matched = any(
			ocr_name in company_names or any(ocr_name in company_name or company_name in ocr_name for company_name in company_names)
			for ocr_name in ocr_names
		)
		self.company_name_match = 1 if matched else 0
		self.receipt_validation_status = "Matched" if matched else "Failed"
		if self.status == "Approved" and not matched:
			frappe.throw("Receipt OCR company name does not match the selected company.")


def normalize(value):
	return " ".join(str(value or "").casefold().split())
