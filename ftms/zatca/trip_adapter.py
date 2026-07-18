from __future__ import annotations

import frappe
from frappe import _


def validate_trip_invoice(doc, method=None):
	if not doc.company:
		return

	company_doc = frappe.get_cached_doc("Transportation Company", doc.company)
	if not company_doc.enable_zatca_e_invoicing:
		return

	if company_doc.zatca_phase == "ZATCA Phase 2":
		if not company_doc.production_csid:
			frappe.throw(_(
				"ZATCA Phase 2 requires a Production CSID. Complete onboarding for company {0} first."
			).format(doc.company))
		csid = frappe.get_doc("Production CSID", company_doc.production_csid)
		if csid.status != "Active":
			frappe.throw(_("Production CSID for {0} is not active").format(doc.company))

	_validate_vat_fields(doc, company_doc)


def on_submit_trip_invoice(doc, method=None):
	if not doc.company:
		return

	company_doc = frappe.get_cached_doc("Transportation Company", doc.company)
	if not company_doc.enable_zatca_e_invoicing:
		return

	from ftms.zatca.clearance import submit_to_zatca

	try:
		result = submit_to_zatca(doc.name)
		doc.zatca_submit_status = result.get("status")
	except Exception as e:
		frappe.log_error(
			f"ZATCA submission failed for {doc.name}: {e}",
			"ZATCA Submission Error",
		)
		doc.zatca_submit_status = "Failed"
		doc.zatca_error = str(e)


def _validate_vat_fields(doc, company_doc):
	missing = []
	if not company_doc.vat_no:
		missing.append("VAT No")
	if not company_doc.cr_no:
		missing.append("CR No")
	if not company_doc.company_name:
		missing.append("Company Name")
	if missing:
		frappe.throw(_(
			"ZATCA E-Invoicing requires: {0}. Update company {1} first."
		).format(", ".join(missing), doc.company))
