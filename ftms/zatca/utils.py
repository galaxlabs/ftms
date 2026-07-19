from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import frappe
import requests
from frappe import _


def get_zatca_headers(company):
	settings = _get_zatca_settings(company)
	if not settings.get("binary_security_token") or not settings.get("secret"):
		frappe.throw(_("ZATCA CSID not configured for company {0}").format(company))
	return {
		"Accept": "application/json",
		"Content-Type": "application/json",
		"Authorization": "Basic "
		+ base64.b64encode(
			f"{settings['binary_security_token']}:{settings['secret']}".encode()
		).decode(),
	}


def _get_zatca_settings(company):
	doc = frappe.get_doc("Company", company)
	env = None
	if doc.zatca_environment:
		env = frappe.get_doc("ZATCA Environment", doc.zatca_environment)
	if doc.zatca_phase == "ZATCA Phase 2" and doc.production_csid:
		csid = frappe.get_doc("Production CSID", doc.production_csid)
		return {
			"binary_security_token": csid.binary_security_token,
			"secret": csid.secret,
			"clearance_api": env.invoice_clearance_api if env else "",
			"reporting_api": env.invoice_reporting_api if env else "",
			"compliance_api": env.compliance_csid_api if env else "",
			"production_api": env.production_csid_api if env else "",
		}
	if doc.zatca_phase in ("ZATCA Phase 1", "ZATCA Phase 2") and doc.compliance_csid:
		csid = frappe.get_doc("Compliance CSID", doc.compliance_csid)
		return {
			"binary_security_token": csid.binary_security_token,
			"secret": csid.secret,
			"clearance_api": env.invoice_clearance_api if env else "",
			"reporting_api": env.invoice_reporting_api if env else "",
			"compliance_api": env.compliance_csid_api if env else "",
			"production_api": env.production_csid_api if env else "",
		}
	frappe.throw(_("No active CSID found for company {0}. Complete ZATCA onboarding first.").format(company))


def get_environment_urls(company):
	doc = frappe.get_doc("Company", company)
	if not doc.zatca_environment:
		frappe.throw(_("ZATCA Environment not set on company {0}").format(company))
	env = frappe.get_doc("ZATCA Environment", doc.zatca_environment)
	return {
		"compliance_csid": env.compliance_csid_api,
		"production_csid": env.production_csid_api,
		"clearance": env.invoice_clearance_api,
		"reporting": env.invoice_reporting_api,
	}


def call_zatca_api(method, url, headers, payload, timeout=30):
	try:
		resp = requests.request(method, url, headers=headers, json=payload, timeout=timeout)
		data = resp.json() if resp.text else {}
	except Exception as e:
		frappe.log_error(f"ZATCA API call failed: {e}", "ZATCA API Error")
		frappe.throw(_("ZATCA API communication failed: {0}").format(str(e)))
	if resp.status_code in (200, 201, 202):
		return data
	error_msg = data.get("errors", data.get("error", resp.text))
	frappe.log_error(
		f"ZATCA {resp.status_code}: {error_msg}\nURL: {url}",
		"ZATCA API Error",
	)
	frappe.throw(_("ZATCA API error ({0}): {1}").format(resp.status_code, error_msg))


def zatca_timestamp(dt=None):
	if dt is None:
		dt = datetime.now(timezone.utc)
	return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def log_transaction(company, doctype, docname, action, status, request=None, response=None):
	log = frappe.get_doc(
		{
			"doctype": "Zatca Transactions",
			"company": company,
			"reference_doctype": doctype,
			"reference_docname": docname,
			"action": action,
			"status": status,
			"request_body": json.dumps(request, ensure_ascii=False) if request else None,
			"response_body": json.dumps(response, ensure_ascii=False) if response else None,
			"transaction_time": frappe.utils.now_datetime(),
		}
	)
	log.insert(ignore_permissions=True)
	return log
