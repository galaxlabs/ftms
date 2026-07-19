from __future__ import annotations

import base64
import json

import frappe
from frappe import _

from ftms.zatca.signing import (
	_generate_icv,
	_get_invoice_type as _get_invoice_type_code,
	_get_last_pih,
	generate_invoice_xml,
	sign_invoice_xml,
)
from ftms.zatca.utils import (
	call_zatca_api,
	get_zatca_headers,
	log_transaction,
)


@frappe.whitelist()
def submit_to_zatca(invoice_name):
	invoice = frappe.get_doc("Trip Invoice", invoice_name)
	company = invoice.company

	if not invoice.docstatus == 1:
		frappe.throw(_("Invoice {0} must be submitted first").format(invoice_name))

	company_doc = frappe.get_doc("Company", company)
	if not company_doc.enable_zatca_e_invoicing:
		frappe.throw(_("ZATCA E-Invoicing is not enabled for company {0}").format(company))

	csid_settings = _get_active_csid(company_doc)
	headers = get_zatca_headers(company)
	urls = _get_urls(company_doc)

	invoice_counter = _generate_icv(company)
	pih = _get_last_pih(company)

	xml_string, uuid_str = generate_invoice_xml(
		invoice, company_doc, csid_settings, invoice_counter, pih
	)

	if csid_settings.get("private_key_pem"):
		signed_xml, digest = sign_invoice_xml(
			xml_string, csid_settings["private_key_pem"]
		)
	else:
		signed_xml, digest = xml_string, ""

	xml_b64 = base64.b64encode(signed_xml.encode("utf-8")).decode()

	invoice_type_code, invoice_type_name = _get_invoice_type_code(invoice)
	is_b2b = invoice_type_code == "388"

	api_url = urls["clearance"] if is_b2b else urls["reporting"]
	api_name = "Clearance" if is_b2b else "Reporting"

	payload = {"invoice": xml_b64}
	if is_b2b:
		payload["clearance_status"] = "Submitted"

	resp = call_zatca_api("POST", api_url, headers, payload, timeout=60)

	status = "Submitted"
	if resp.get("clearanceStatus") == "Cleared":
		status = "Cleared"
	elif resp.get("clearanceStatus") == "Rejected":
		status = "Rejected"
	elif resp.get("status") == "Submitted":
		status = "Submitted"

	invoice.db_set("zatca_submit_status", status)
	invoice.db_set("zatca_submit_time", frappe.utils.now_datetime())
	invoice.db_set("invoice_xml", signed_xml)

	log_transaction(
		company, "Trip Invoice", invoice.name,
		f"ZATCA {api_name}", status,
		request={"invoice": invoice.name, "counter": invoice_counter, "pih": pih},
		response=resp,
	)

	txn = frappe.get_doc(
		{
			"doctype": "Zatca Transactions",
			"company": company,
			"reference_doctype": "Trip Invoice",
			"reference_docname": invoice.name,
			"action": f"ZATCA {api_name}",
			"status": status,
			"invoice_id": invoice.name,
			"invoice_uuid": uuid_str,
			"invoice_hash": digest,
			"invoice_icv": invoice_counter,
			"previous_invoice_hash": pih,
			"request_body": json.dumps({"invoice": invoice.name}),
			"response_body": json.dumps(resp, ensure_ascii=False),
			"transaction_time": frappe.utils.now_datetime(),
		}
	)
	txn.insert(ignore_permissions=True)

	return {"status": status, "response": resp}


def _get_active_csid(company_doc):
	if company_doc.zatca_phase == "ZATCA Phase 2" and company_doc.production_csid:
		csid = frappe.get_doc("Production CSID", company_doc.production_csid)
		return {
			"binary_security_token": csid.binary_security_token,
			"secret": csid.secret,
			"private_key_pem": None,
		}
	if company_doc.compliance_csid:
		csid = frappe.get_doc("Compliance CSID", company_doc.compliance_csid)
		return {
			"binary_security_token": csid.binary_security_token,
			"secret": csid.secret,
			"private_key_pem": None,
		}
	frappe.throw(_("No active CSID for company {0}").format(company_doc.name))


def _get_urls(company_doc):
	if not company_doc.zatca_environment:
		frappe.throw(_("ZATCA Environment not set on company {0}").format(company_doc.name))
	env = frappe.get_doc("ZATCA Environment", company_doc.zatca_environment)
	return {
		"clearance": env.invoice_clearance_api,
		"reporting": env.invoice_reporting_api,
		"compliance_csid": env.compliance_csid_api,
		"production_csid": env.production_csid_api,
	}



