from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


def _require_url(value, label):
    if not value or not value.startswith(("http://", "https://")):
        frappe.throw(_("{0} must be a valid URL").format(label))


class ZATCAEnvironment(Document):

	def validate(self):
		_require_url(self.compliance_csid_api, "Compliance CSID API")
		_require_url(self.production_csid_api, "Production CSID API")
		_require_url(self.invoice_clearance_api, "Invoice Clearance API")
		_require_url(self.invoice_reporting_api, "Invoice Reporting API")


