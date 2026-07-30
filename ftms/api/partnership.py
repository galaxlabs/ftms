from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime, today

from ftms.api.membership import _require_company_admin
from ftms.tenant import has_company_access, resolve_company


def _require_party_access(company):
	if not has_company_access(company):
		frappe.throw(_("You are not permitted for this company"), frappe.PermissionError)


@frappe.whitelist()
def create_partnership(provider_company, partnership_type, customer_company=None, service_types=None, operating_cities=None, commission_rate=0, start_date=None, end_date=None, capacity_notes=None):
	customer_company = resolve_company(company=customer_company)
	_require_company_admin(customer_company)
	if provider_company == customer_company:
		frappe.throw(_("Customer and provider companies must be different"))
	if not frappe.db.exists("Company", {"name": provider_company, "status": "Active", "blacklisted": 0}):
		frappe.throw(_("Provider company is not active"))
	if frappe.db.exists("Partnership", {"customer_company": customer_company, "provider_company": provider_company, "status": ["in", ("Proposed", "Under Review", "Approved", "Active")]}):
		frappe.throw(_("An active partnership already exists between these companies"))
	doc = frappe.get_doc({
		"doctype": "Partnership",
		"customer_company": customer_company,
		"provider_company": provider_company,
		"partnership_type": partnership_type,
		"service_types": service_types,
		"operating_cities": operating_cities,
		"commission_rate": commission_rate,
		"start_date": start_date,
		"end_date": end_date,
		"capacity_notes": capacity_notes,
		"status": "Proposed",
		"requested_by": frappe.session.user,
	})
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def list_partnerships(company=None, status=None, limit=50):
	company = resolve_company(company=company)
	filters = {"customer_company": company}
	rows = frappe.get_all("Partnership", filters=filters, fields="*", order_by="modified desc", limit_page_length=int(limit))
	provider_rows = frappe.get_all("Partnership", filters={"provider_company": company, **({"status": status} if status else {})}, fields="*", order_by="modified desc", limit_page_length=int(limit))
	if status:
		rows = [row for row in rows if row.status == status]
	return rows + [row for row in provider_rows if row.name not in {item.name for item in rows}]


@frappe.whitelist()
def transition_partnership(name, action, notes=None):
	doc = frappe.get_doc("Partnership", name)
	if has_company_access(doc.customer_company):
		_require_company_admin(doc.customer_company)
	else:
		_require_company_admin(doc.provider_company)
	transitions = {
		"review": ("Proposed", "Under Review"),
		"approve": (("Under Review", "Approved"), "Active"),
		"suspend": (("Active", "Approved"), "Suspended"),
		"terminate": (("Active", "Suspended", "Approved"), "Terminated"),
	}
	if action not in transitions:
		frappe.throw(_("Invalid partnership action"))
	allowed, target = transitions[action]
	allowed = (allowed,) if isinstance(allowed, str) else allowed
	if doc.status not in allowed:
		frappe.throw(_("Partnership cannot transition from {0}").format(doc.status))
	doc.status = target
	if notes:
		doc.capacity_notes = f"{doc.capacity_notes or ''}\n{notes}".strip()
	if target == "Active":
		doc.approved_by = frappe.session.user
		doc.approved_on = now_datetime()
	doc.save(ignore_permissions=True)
	return {"name": doc.name, "status": doc.status}


def create_agreement_for_booking(booking, trip, provider_company):
	if not booking.company or not provider_company:
		return None
	partnership = frappe.db.get_value(
		"Partnership",
		{"customer_company": booking.company, "provider_company": provider_company, "status": "Active"},
		"name",
	)
	if not partnership or booking.agreement:
		return None
	template = frappe.db.get_value("Agreement Template", {"enabled": 1, "service_type": booking.service_type}, ["name", "terms_body", "cancellation_policy", "waiting_policy", "payment_terms"], as_dict=True)
	if not template:
		template = frappe.db.get_value("Agreement Template", {"enabled": 1}, ["name", "terms_body", "cancellation_policy", "waiting_policy", "payment_terms"], as_dict=True)
	fee = float(booking.platform_fee_amount or 0)
	agreement = frappe.get_doc({
		"doctype": "Agreement",
		"agreement_title": booking.booking_title or f"Transport Agreement {booking.name}",
		"customer_company": booking.company,
		"provider_company": provider_company,
		"service_type": booking.service_type,
		"status": "Sent to Provider",
		"agreement_template": template.name if template else None,
		"order": booking.name,
		"trip": trip.name,
		"start_date": booking.booking_date or today(),
		"currency": "SAR",
		"agreed_amount": booking.fare_amount or booking.quoted_fare or 0,
		"platform_commission": fee,
		"provider_settlement": max(float(booking.fare_amount or 0) - fee, 0),
		"cancellation_policy": template.cancellation_policy if template else None,
		"waiting_policy": template.waiting_policy if template else None,
		"payment_terms": template.payment_terms if template else None,
	})
	agreement.insert(ignore_permissions=True)
	booking.db_set("agreement", agreement.name)
	return agreement


@frappe.whitelist()
def accept_agreement(name):
	doc = frappe.get_doc("Agreement", name)
	user = frappe.session.user
	if not has_company_access(doc.customer_company, user=user) and not has_company_access(doc.provider_company, user=user):
		frappe.throw(_("You are not permitted to accept this agreement"), frappe.PermissionError)
	if has_company_access(doc.customer_company, user=user):
		doc.customer_accepted_by = user
		doc.customer_accepted_on = now_datetime()
	if has_company_access(doc.provider_company, user=user):
		doc.provider_accepted_by = user
		doc.provider_accepted_on = now_datetime()
	if doc.customer_accepted_by and doc.provider_accepted_by:
		doc.status = "Active"
	else:
		doc.status = "Accepted"
	doc.save(ignore_permissions=True)
	return {"name": doc.name, "status": doc.status}
