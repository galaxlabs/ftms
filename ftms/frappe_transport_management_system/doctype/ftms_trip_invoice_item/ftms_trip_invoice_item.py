from frappe.model.document import Document
from frappe.utils import flt


class FTMSTripInvoiceItem(Document):
	def validate(self):
		self.qty = flt(self.qty or 1)
		self.rate = flt(self.rate or 0)
		self.amount = flt(self.qty * self.rate)
		self.vat_rate = flt(self.vat_rate or 0)
		self.vat_amount = flt(self.amount * self.vat_rate / 100)
		self.total_amount = flt(self.amount + self.vat_amount)
