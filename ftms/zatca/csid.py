from __future__ import annotations

import frappe
from frappe import _

from ftms.zatca.utils import call_zatca_api, get_environment_urls, log_transaction


def _get_basic_auth(csr_settings_name):
	doc = frappe.get_doc("Zatca CSR Settings", csr_settings_name)
	if not doc.csr_generated or not doc.csr:
		frappe.throw(_("CSR not generated yet for {0}").format(csr_settings_name))
	return doc


@frappe.whitelist()
def onboard_compliance_csid(csr_settings_name, otp):
	csr_doc = _get_basic_auth(csr_settings_name)
	company = csr_doc.company
	urls = get_environment_urls(company)

	payload = {
		"csr": csr_doc.csr,
		"otp": otp,
	}

	resp = call_zatca_api(
		"POST",
		urls["compliance_csid"],
		{"Accept": "application/json", "Content-Type": "application/json"},
		payload,
		timeout=60,
	)

	if not resp.get("requestID") or not resp.get("binarySecurityToken"):
		frappe.throw(_("Compliance CSID response missing required fields: {0}").format(resp))

	compliance = frappe.get_doc(
		{
			"doctype": "Compliance CSID",
			"compliance_csid_name": f"CCSID-{csr_doc.csrorganizationidentifier}-{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S')}",
			"csr_settings": csr_settings_name,
			"status": "Active",
			"certificate": resp.get("certificate", ""),
			"public_key": resp.get("publicKey", ""),
			"binary_security_token": resp.get("binarySecurityToken", ""),
			"secret": resp.get("secret", ""),
			"expiry_date": resp.get("expiryDate"),
			"request_id": resp.get("requestID"),
		}
	)
	compliance.insert(ignore_permissions=True)

	company_doc = frappe.get_doc("Company", company)
	company_doc.compliance_csid = compliance.name
	company_doc.save(ignore_permissions=True)

	log_transaction(
		company, "Compliance CSID", compliance.name,
		"Compliance CSID Onboarding", "Success",
		request={"csr_settings": csr_settings_name, "otp": "***"},
		response=resp,
	)

	return {"compliance_csid": compliance.name, "request_id": compliance.request_id}


@frappe.whitelist()
def onboard_production_csid(compliance_csid_name, otp):
	compliance = frappe.get_doc("Compliance CSID", compliance_csid_name)
	if compliance.status != "Active":
		frappe.throw(_("Compliance CSID {0} is not active").format(compliance_csid_name))

	csr_doc = frappe.get_doc("Zatca CSR Settings", compliance.csr_settings)
	company = csr_doc.company
	urls = get_environment_urls(company)

	payload = {
		"compliance_request_id": compliance.request_id,
		"otp": otp,
	}

	resp = call_zatca_api(
		"POST",
		urls["production_csid"],
		{"Accept": "application/json", "Content-Type": "application/json"},
		payload,
		timeout=60,
	)

	if not resp.get("binarySecurityToken") or not resp.get("secret"):
		frappe.throw(_("Production CSID response missing required fields: {0}").format(resp))

	production = frappe.get_doc(
		{
			"doctype": "Production CSID",
			"production_csid_name": f"PCSID-{csr_doc.csrorganizationidentifier}-{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S')}",
			"compliance_csid": compliance_csid_name,
			"status": "Active",
			"certificate": resp.get("certificate", ""),
			"public_key": resp.get("publicKey", ""),
			"binary_security_token": resp.get("binarySecurityToken", ""),
			"secret": resp.get("secret", ""),
			"expiry_date": resp.get("expiryDate"),
			"request_id": resp.get("requestID"),
		}
	)
	production.insert(ignore_permissions=True)

	company_doc = frappe.get_doc("Company", company)
	company_doc.compliance_csid = compliance_csid_name
	company_doc.production_csid = production.name
	company_doc.save(ignore_permissions=True)

	compliance.db_set("status", "Onboarded")

	log_transaction(
		company, "Production CSID", production.name,
		"Production CSID Onboarding", "Success",
		request={"compliance_csid": compliance_csid_name, "otp": "***"},
		response=resp,
	)

	return {"production_csid": production.name, "request_id": production.request_id}


@frappe.whitelist()
def revoke_csid(production_csid_name):
	production = frappe.get_doc("Production CSID", production_csid_name)
	if production.status != "Active":
		frappe.throw(_("CSID {0} is not active").format(production_csid_name))
	production.db_set("status", "Revoked")
	return {"status": "Revoked"}


@frappe.whitelist()
def get_csid_status(company):
	doc = frappe.get_doc("Company", company)
	result = {
		"enable_zatca": doc.enable_zatca_e_invoicing,
		"phase": doc.zatca_phase,
		"environment": doc.zatca_environment,
		"compliance_csid": None,
		"production_csid": None,
	}
	if doc.compliance_csid:
		c = frappe.get_doc("Compliance CSID", doc.compliance_csid)
		result["compliance_csid"] = {
			"name": c.name,
			"status": c.status,
			"expiry_date": str(c.expiry_date) if c.expiry_date else None,
		}
	if doc.production_csid:
		p = frappe.get_doc("Production CSID", doc.production_csid)
		result["production_csid"] = {
			"name": p.name,
			"status": p.status,
			"expiry_date": str(p.expiry_date) if p.expiry_date else None,
		}
	return result
