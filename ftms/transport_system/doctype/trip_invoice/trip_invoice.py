from frappe.utils import flt
from frappe.model.document import Document


class TripInvoice(Document):
	def validate(self):
		self.set_customer_fallback()
		self.calculate_item_totals()
		self.calculate_totals()

	def set_customer_fallback(self):
		if not self.customer:
			self.customer = self.invoice_passenger_name or "Walk-in Customer"

	def calculate_item_totals(self):
		for d in self.items or []:
			qty = flt(d.qty or 1)
			rate = flt(d.rate)
			d.amount = qty * rate
			d.vat_amount = d.amount * flt(d.vat_rate or self.vat_rate or 0) / 100
			d.total_amount = d.amount + d.vat_amount
			if not d.item_name and self.from_location and self.to_location:
				d.item_name = f"Trip {self.from_location} - {self.to_location}"
			if not d.description:
				d.description = d.item_name

	def calculate_totals(self):
		self.net_total = sum(flt(d.amount) for d in (self.items or []))
		self.vat_amount = sum(flt(d.vat_amount) for d in (self.items or []))
		self.grand_total = flt(self.net_total) + flt(self.vat_amount)
