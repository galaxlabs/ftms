from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime

from ftms.tenant import get_user_company, resolve_company


@frappe.whitelist()
def list_captains(company=None, limit=50):
	resolved_company = resolve_company(company=company, allow_missing=True)
	filters = {}
	if resolved_company:
		filters["current_company"] = resolved_company
	return frappe.get_all(
		"Captain Profile",
		filters=filters,
		fields=[
			"name", "user", "full_name", "mobile_no", "status", "current_company",
			"id_document_type", "nationality", "iqama_no", "national_id",
			"license_no", "license_expiry_date", "driver_card_no", "driver_card_expiry_date",
			"city", "address", "id_document", "license_document", "driver_card_document",
		],
		order_by="modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_captain(name, company=None):
	doc = frappe.get_doc("Captain Profile", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and doc.current_company != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()


@frappe.whitelist()
def create_captain_profile(
	full_name=None, mobile_no=None,
	id_document_type=None, nationality=None,
	iqama_no=None, iqama_expiry_date=None,
	national_id=None,
	license_no=None, license_expiry_date=None,
	driver_card_no=None, driver_card_expiry_date=None,
	city=None, address=None,
	id_document=None, license_document=None, driver_card_document=None,
):
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)

	existing = frappe.db.get_value("Captain Profile", {"user": user}, "name")
	if existing:
		doc = frappe.get_doc("Captain Profile", existing)
	else:
		doc = frappe.get_doc({"doctype": "Captain Profile", "user": user, "status": "Pending"})

	doc.full_name = full_name or doc.full_name or frappe.db.get_value("User", user, "full_name") or user
	doc.mobile_no = mobile_no or doc.mobile_no
	if id_document_type:
		doc.id_document_type = id_document_type
	if nationality:
		doc.nationality = nationality
	if iqama_no:
		doc.iqama_no = iqama_no
	if iqama_expiry_date:
		doc.iqama_expiry_date = iqama_expiry_date
	if national_id:
		doc.national_id = national_id
	if license_no:
		doc.license_no = license_no
	if license_expiry_date:
		doc.license_expiry_date = license_expiry_date
	if driver_card_no:
		doc.driver_card_no = driver_card_no
	if driver_card_expiry_date:
		doc.driver_card_expiry_date = driver_card_expiry_date
	if city:
		doc.city = city
	if address:
		doc.address = address
	if id_document:
		doc.id_document = id_document
	if license_document:
		doc.license_document = license_document
	if driver_card_document:
		doc.driver_card_document = driver_card_document

	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok", "captain_profile": doc.name, "is_new": not bool(existing)}


@frappe.whitelist()
def request_join_company(company):
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)
	profile = frappe.db.get_value("Captain Profile", {"user": user}, "name")
	if not profile:
		frappe.throw(_("Create a captain profile before requesting to join a company"))
	if frappe.db.exists("Captain Join Request", {"captain_profile": profile, "company": company, "status": "Pending"}):
		frappe.throw(_("A pending join request already exists for this company"))
	request = frappe.get_doc({
		"doctype": "Captain Join Request",
		"captain_profile": profile,
		"company": company,
		"requested_by": user,
		"requested_on": now_datetime(),
		"status": "Pending",
	})
	request.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok", "join_request": request.name}


@frappe.whitelist()
def list_join_requests(company=None, status="Pending", limit=50):
	resolved_company = resolve_company(company=company)
	filters = {"company": resolved_company, "status": status}
	return frappe.get_all(
		"Captain Join Request",
		filters=filters,
		fields=[
			"name", "captain_profile", "company", "requested_by",
			"requested_on", "status", "approved_by", "approved_on", "notes",
		],
		order_by="requested_on desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def approve_join_request(name, notes=None):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)
	doc = frappe.get_doc("Captain Join Request", name)
	if doc.status != "Pending":
		frappe.throw(_("This request is already {0}").format(doc.status))
	doc.status = "Approved"
	doc.approved_by = user
	doc.approved_on = now_datetime()
	if notes:
		doc.notes = notes
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok", "join_request": doc.name}


@frappe.whitelist()
def reject_join_request(name, notes=None):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)
	doc = frappe.get_doc("Captain Join Request", name)
	if doc.status != "Pending":
		frappe.throw(_("This request is already {0}").format(doc.status))
	doc.status = "Rejected"
	doc.approved_by = user
	doc.approved_on = now_datetime()
	if notes:
		doc.notes = notes
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok", "join_request": doc.name}


@frappe.whitelist()
def get_my_profile():
	user = frappe.session.user
	if user == "Guest":
		return None
	profile = frappe.db.get_value("Captain Profile", {"user": user}, "name")
	if not profile:
		return None
	doc = frappe.get_doc("Captain Profile", profile)
	return doc.as_dict()
