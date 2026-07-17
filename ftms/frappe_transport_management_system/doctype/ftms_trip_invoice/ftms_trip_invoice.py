import frappe

from frappe.model.document import Document
from frappe.utils import flt

from ftms.tenant import require_company


class FTMSTripInvoice(Document):
	def validate(self):
		require_company(self)
		if not self.company and self.trip:
			self.company = frappe.db.get_value("FTMS Trip", self.trip, "company")
		self.update_totals()

	def update_totals(self):
		net_total = 0
		vat_total = 0
		for row in self.items or []:
			row.qty = flt(row.qty or 1)
			row.rate = flt(row.rate or 0)
			row.amount = flt(row.qty * row.rate)
			row.vat_rate = flt(row.vat_rate or self.vat_rate or 0)
			row.vat_amount = flt(row.amount * row.vat_rate / 100)
			row.total_amount = flt(row.amount + row.vat_amount)
			net_total += row.amount
			vat_total += row.vat_amount

		if not self.trip_value and self.trip:
			self.trip_value = flt(frappe.db.get_value("FTMS Trip", self.trip, "trip_value") or 0)

		if not self.items and self.trip_value:
			pass

		self.net_total = flt(net_total or self.trip_value or 0)
		self.vat_amount = flt(vat_total)
		self.grand_total = flt(self.net_total + self.vat_amount)

		if self.rounding_difference is None:
			self.rounding_difference = flt(self.grand_total - (self.net_total + self.vat_amount))
