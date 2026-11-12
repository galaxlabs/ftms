from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import now_datetime

from ftms.api.membership import _require_company_admin
from ftms.tenant import get_user_company, is_system_user, resolve_company
from ftms.user_roles import assign_business_role


def _digits_only(value):
	return re.sub(r"\D", "", str(value or ""))


def _validate_captain_identity(id_document_type, identity_no):
	identity_no = _digits_only(identity_no)
	if not identity_no:
		return identity_no
	if not re.fullmatch(r"\d{10}", identity_no):
		frappe.throw(_("Saudi ID/Iqama must be exactly 10 digits"))
	if id_document_type == "Iqama" and not identity_no.startswith("2"):
		frappe.throw(_("Iqama number must start with 2"))
	if id_document_type == "National ID" and not identity_no.startswith("1"):
		frappe.throw(_("Saudi National ID must start with 1"))
	return identity_no


@frappe.whitelist()
def list_captains(company=None, limit=50):
	resolved_company = resolve_company(company=company, allow_missing=True)
	# Without a company, only platform admins may list captains across all companies.
	if not resolved_company and not is_system_user():
		return []
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
	if frappe.session.user != "Administrator" and doc.current_company != resolved_company:
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
	full_name = (full_name or "").strip()
	mobile_no = (mobile_no or "").strip()
	id_document_type = (id_document_type or "").strip()
	nationality = (nationality or "").strip()
	identity_no = _validate_captain_identity(id_document_type, iqama_no or national_id)
	if id_document_type == "Iqama":
		iqama_no = identity_no
		national_id = None
	elif id_document_type == "National ID":
		national_id = identity_no
		iqama_no = None
	license_no = (license_no or "").strip()
	city = (city or "").strip()
	address = (address or "").strip()
	missing = [label for label, value in (
		(_("Full name"), full_name),
		(_("Mobile number"), mobile_no),
		(_("ID document type"), id_document_type),
		(_("Nationality"), nationality),
		(_("Identity number"), identity_no),
		(_("Driving license number"), license_no),
		(_("License expiry date"), license_expiry_date),
		(_("City"), city),
		(_("Address"), address),
	) if not value]
	if missing:
		frappe.throw(_("Complete required captain details: {0}").format(", ".join(missing)))

	existing = frappe.db.get_value("Captain Profile", {"user": user}, "name")
	if existing:
		doc = frappe.get_doc("Captain Profile", existing)
	else:
		doc = frappe.get_doc({"doctype": "Captain Profile", "user": user, "status": "Pending"})

	doc.full_name = full_name
	doc.mobile_no = mobile_no
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
	assign_business_role(user, "Captain", onboarded=True)
	assign_business_role(user, "Driver", onboarded=True)
	frappe.db.commit()
	return {"status": "ok", "captain_profile": doc.name, "profile_status": doc.status, "is_new": not bool(existing)}


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
	_require_company_admin(doc.company, user=user)
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
	_require_company_admin(doc.company, user=user)
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


@frappe.whitelist()
def register_vehicle(
	vehicle_make=None, vehicle_model=None,
	plate_no=None, chassis_no=None,
	model_year=None, color=None,
	seat_capacity=None, fuel_type=None,
	operation_card_no=None, operation_card_expiry_date=None,
	registration_expiry_date=None, insurance_expiry_date=None,
	operation_card_document=None, registration_document=None,
	insurance_document=None,
):
	"""Register a vehicle under the captain's own name (no company required)."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)

	profile = frappe.db.get_value("Captain Profile", {"user": user}, "name")
	if not profile:
		frappe.throw(_("Create a captain profile before registering vehicles"))

	if chassis_no and frappe.db.exists("Vehicle", {"chassis_no": chassis_no}):
		frappe.throw(_("A vehicle with this chassis number already exists"))

	vehicle_code = _make_vehicle_code(chassis_no or plate_no or user, vehicle_make, vehicle_model)
	vehicle_name = f"{vehicle_make or 'VHC'} - {plate_no or vehicle_code}"

	doc = frappe.get_doc({
		"doctype": "Vehicle",
		"vehicle_code": vehicle_code,
		"vehicle_name": vehicle_name,
		"vehicle_make": vehicle_make,
		"vehicle_model": vehicle_model,
		"plate_no": plate_no,
		"chassis_no": chassis_no,
		"model_year": model_year,
		"color": color,
		"seat_capacity": seat_capacity,
		"fuel_type": fuel_type or "Petrol",
		"ownership_type": "Owned",
		"operation_card_no": operation_card_no,
		"operation_card_expiry_date": operation_card_expiry_date,
		"registration_expiry_date": registration_expiry_date,
		"insurance_expiry_date": insurance_expiry_date,
		"operation_card_document": operation_card_document,
		"registration_document": registration_document,
		"insurance_document": insurance_document,
		"assigned_captain_user": user,
		"status": "Active",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok", "vehicle": doc.name, "vehicle_code": vehicle_code}


@frappe.whitelist()
def lookup_company_by_tax_id(tax_id=None, vat_no=None):
	"""Auto-fetch company details by tax ID or VAT number."""
	if not tax_id and not vat_no:
		return None
	filters = {}
	if tax_id:
		filters["tax_id"] = tax_id
	if vat_no:
		filters["vat_no"] = vat_no
	company = frappe.db.get_value("Company", filters, [
		"name", "company_name", "legal_name", "company_name_ar",
		"vat_no", "tax_id", "cr_no", "phone", "email", "address",
	], as_dict=True)
	if company:
		company["found"] = True
	return company


def _make_vehicle_code(chassis_or_plate, make, model):
	import re
	parts = [re.sub(r"[^A-Z0-9]+", "-", (chassis_or_plate or "").upper())[:12]]
	if make:
		parts.append(re.sub(r"[^A-Z0-9]+", "-", make.upper())[:8])
	if model:
		parts.append(re.sub(r"[^A-Z0-9]+", "-", model.upper())[:8])
	return "-".join(parts)[:30]
