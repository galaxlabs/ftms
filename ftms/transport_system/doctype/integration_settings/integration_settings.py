import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


class IntegrationSettings(Document):
	def validate(self):
		if self.document_ai_provider and self.document_ai_provider != "OpenAI":
			frappe.throw("Only the OpenAI document AI provider is supported")
		if cint(self.document_ai_timeout_seconds) < 1 or cint(self.document_ai_timeout_seconds) > 120:
			frappe.throw("Document AI timeout must be between 1 and 120 seconds")
		if cint(self.document_ai_max_file_bytes) < 1024 or cint(self.document_ai_max_file_bytes) > 25 * 1024 * 1024:
			frappe.throw("Document AI maximum file size must be between 1 KB and 25 MB")
		high = flt(self.document_ai_high_confidence)
		review = flt(self.document_ai_review_confidence)
		if not 0 <= review <= high <= 1:
			frappe.throw("Document AI confidence thresholds must satisfy 0 <= review <= high <= 1")
