from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import now_datetime, random_string


def _make_code(value, fallback):
    code = re.sub(r"[^A-Z0-9]+", "-", (value or fallback).upper()).strip("-")
    return (code or fallback)[:24]


def _unique_code(doctype, fieldname, seed):
    base = _make_code(seed, "FTMS")
    code = base
    counter = 1
    while frappe.db.exists(doctype, {fieldname: code}):
        suffix = f"-{counter}"
        code = f"{base[:24 - len(suffix)]}{suffix}"
        counter += 1
    return code


def _default_domain(domain=None):
    if domain and frappe.db.exists("Transportation Domain", domain):
        return domain
    existing = frappe.db.get_value("Transportation Domain", {"is_active": 1}, "name")
    if existing:
        return existing
    return frappe.db.get_value("Transportation Domain", {}, "name")


def _send_reset_password_email(user_doc):
    try:
        user_doc.reset_password(send_email=True)
        return True, None
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "FTMS signup reset password email failed")
        return False, str(exc)


@frappe.whitelist(allow_guest=True)
def signup_user(email, password, confirm_password, username=None, first_name=None, last_name=None):
    """Create only a login user. Company/captain onboarding happens after login."""
    email = (email or "").strip().lower()
    username = (username or email).strip()
    first_name = (first_name or username or email).strip()
    last_name = (last_name or "").strip()

    if not email or "@" not in email:
        frappe.throw(_("A valid email is required"))
    if not password:
        frappe.throw(_("Password is required"))
    if password != confirm_password:
        frappe.throw(_("Password and confirm password do not match"))
    if frappe.db.exists("User", email):
        frappe.throw(_("A user with this email already exists"))

    user_doc = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "enabled": 1,
        "send_welcome_email": 0,
        "new_password": password,
    })
    user_doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "ok", "user": user_doc.name, "message": "User created. Login to continue onboarding."}


@frappe.whitelist(allow_guest=True)
def signup(company_name, email, username=None, first_name=None, last_name=None, domain=None):
    """Public onboarding: create a company admin user and active company link."""
    company_name = (company_name or "").strip()
    email = (email or "").strip().lower()
    username = (username or email).strip()
    first_name = (first_name or username or email).strip()
    last_name = (last_name or "").strip()

    if not company_name:
        frappe.throw(_("Company name is required"))
    if not email or "@" not in email:
        frappe.throw(_("A valid email is required"))

    company = frappe.db.get_value("Company", {"company_name": company_name}, "name")
    if company:
        frappe.throw(_("This company already exists. Request an invitation or join approval instead of creating a new owner."))
    if not company:
        company_domain = _default_domain(domain)
        if not company_domain:
            frappe.throw(_("No Transportation Domain is configured. Create one before public signup."))
        company_doc = frappe.get_doc({
            "doctype": "Company",
            "company_code": _unique_code("Company", "company_code", company_name),
            "company_name": company_name,
            "domain": company_domain,
            "email": email,
            "owner_user": email,
            "onboarding_status": "Draft",
            "status": "Active",
            "blacklisted": 0,
        })
        company_doc.insert(ignore_permissions=True)
        company = company_doc.name

    if frappe.db.exists("User", email):
        user_doc = frappe.get_doc("User", email)
        if first_name and user_doc.first_name != first_name:
            user_doc.first_name = first_name
        if last_name and user_doc.last_name != last_name:
            user_doc.last_name = last_name
        user_doc.enabled = 1
        user_doc.save(ignore_permissions=True)
    else:
        user_doc = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "enabled": 1,
            "send_welcome_email": 0,
            "new_password": random_string(18),
        })
        user_doc.insert(ignore_permissions=True)

    link = frappe.db.get_value("User Company Link", {"user": email, "company": company}, "name")
    if link:
        link_doc = frappe.get_doc("User Company Link", link)
        link_doc.role = "Company Admin"
        link_doc.is_owner = 1
        link_doc.joined_via = link_doc.joined_via or "Signup"
        link_doc.status = "Active"
        link_doc.approved_by = frappe.session.user if frappe.session.user != "Guest" else "Administrator"
        link_doc.approved_on = now_datetime()
        link_doc.save(ignore_permissions=True)
    else:
        link_doc = frappe.get_doc({
            "doctype": "User Company Link",
            "link_code": _unique_code("User Company Link", "link_code", f"{company}-{email}"),
            "user": email,
            "company": company,
            "role": "Company Admin",
            "is_owner": 1,
            "joined_via": "Signup",
            "status": "Active",
            "approved_by": frappe.session.user if frappe.session.user != "Guest" else "Administrator",
            "approved_on": now_datetime(),
        })
        link_doc.insert(ignore_permissions=True)

    reset_email_sent, reset_email_error = _send_reset_password_email(user_doc)

    frappe.db.commit()
    return {
        "status": "ok",
        "user": user_doc.name,
        "company": company,
        "company_name": company_name,
        "role": "Company Admin",
        "link": link_doc.name,
        "reset_email_sent": reset_email_sent,
        "reset_email_error": reset_email_error,
    }


@frappe.whitelist()
def register_transportation_company(company_name, domain=None, legal_name=None, vat_no=None, tax_id=None, cr_no=None, address=None, phone=None, email=None):
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Login is required"), frappe.PermissionError)
    company_name = (company_name or "").strip()
    if not company_name:
        frappe.throw(_("Company name is required"))
    if frappe.db.exists("User Company Link", {"user": user, "status": "Active"}):
        frappe.throw(_("User is already linked to a company"))
    if frappe.db.exists("Captain Profile", {"user": user}):
        frappe.throw(_("Captain profile already exists. A captain must join a company by request or invitation."))

    company_domain = _default_domain(domain)
    if not company_domain:
        frappe.throw(_("No Transportation Domain is configured. Create one before company onboarding."))
    company_doc = frappe.get_doc({
        "doctype": "Company",
        "company_code": _unique_code("Company", "company_code", company_name),
        "company_name": company_name,
        "legal_name": legal_name,
        "domain": company_domain,
        "vat_no": vat_no,
        "tax_id": tax_id,
        "cr_no": cr_no,
        "address": address,
        "phone": phone,
        "email": email or user,
        "owner_user": user,
        "onboarding_status": "Draft",
        "status": "Active",
        "blacklisted": 0,
    })
    company_doc.insert(ignore_permissions=True)

    link_doc = frappe.get_doc({
        "doctype": "User Company Link",
        "link_code": _unique_code("User Company Link", "link_code", f"{company_doc.name}-{user}"),
        "user": user,
        "company": company_doc.name,
        "role": "Company Admin",
        "is_owner": 1,
        "joined_via": "Signup",
        "status": "Active",
        "approved_by": user,
        "approved_on": now_datetime(),
    })
    link_doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "ok", "company": company_doc.name, "link": link_doc.name}


@frappe.whitelist()
def create_captain_profile(
    full_name=None, mobile_no=None, national_id=None, license_no=None,
    license_expiry_date=None, city=None, address=None,
    id_document_type=None, nationality=None, iqama_no=None,
    iqama_expiry_date=None, driver_card_no=None, driver_card_expiry_date=None,
    provider_name=None, provider_legal_name=None, provider_tax_id=None,
    provider_cr_no=None, provider_logo=None, provider_stamp=None,
    vehicle_card_document=None, vehicle_ownership_document=None,
):
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Login is required"), frappe.PermissionError)
    if frappe.db.exists("User Company Link", {"user": user, "status": "Active"}):
        frappe.throw(_("Company-linked users cannot create an independent captain profile"))
    if frappe.db.exists("Captain Profile", {"user": user}):
        frappe.throw(_("Captain profile already exists"))
    profile = frappe.get_doc({
        "doctype": "Captain Profile",
        "user": user,
        "full_name": full_name or frappe.db.get_value("User", user, "full_name") or user,
        "mobile_no": mobile_no,
        "id_document_type": id_document_type,
        "nationality": nationality,
        "iqama_no": iqama_no,
        "iqama_expiry_date": iqama_expiry_date,
        "national_id": national_id,
        "license_no": license_no,
        "license_expiry_date": license_expiry_date,
        "driver_card_no": driver_card_no,
        "driver_card_expiry_date": driver_card_expiry_date,
        "city": city,
        "address": address,
        "provider_name": provider_name,
        "provider_legal_name": provider_legal_name,
        "provider_tax_id": provider_tax_id,
        "provider_cr_no": provider_cr_no,
        "provider_logo": provider_logo,
        "provider_stamp": provider_stamp,
        "vehicle_card_document": vehicle_card_document,
        "vehicle_ownership_document": vehicle_ownership_document,
        "status": "Pending",
    })
    profile.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "ok", "captain_profile": profile.name}


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
def get_status():
    user = frappe.session.user
    if user == "Guest":
        return {"onboarded": False, "user_type": None, "available_roles": []}

    profile = frappe.db.get_value("User", user, ["user_type", "onboarded"], as_dict=True)
    if not profile:
        return {"onboarded": False, "user_type": None, "available_roles": ["Passenger", "Partner", "Captain"]}

    onboarded = bool(profile.get("onboarded"))
    user_type = profile.get("user_type")

    existing_partner = frappe.db.exists("Partner Profile", {"user": user})
    existing_captain = frappe.db.exists("Captain Profile", {"user": user})
    existing_company_link = frappe.db.exists("User Company Link", {"user": user, "status": "Active"})

    partner_profile = None
    if existing_partner:
        partner_profile = frappe.db.get_value("Partner Profile", {"user": user}, [
            "name", "partner_type", "service_contract_type", "company", "status",
            "company_name", "vat_no",
        ], as_dict=True)

    captain_profile = None
    if existing_captain:
        captain_profile = frappe.db.get_value("Captain Profile", {"user": user}, [
            "name", "full_name", "status", "current_company",
        ], as_dict=True)

    available_roles = []
    if not existing_partner and not existing_captain and not existing_company_link:
        available_roles = ["Passenger", "Partner", "Captain"]
    elif user_type == "Passenger":
        available_roles = ["Passenger"]
    elif user_type == "Partner":
        available_roles = ["Partner"]
    elif user_type == "Captain":
        available_roles = ["Captain"]

    return {
        "onboarded": onboarded,
        "user_type": user_type,
        "available_roles": available_roles,
        "partner_profile": partner_profile,
        "captain_profile": captain_profile,
    }


@frappe.whitelist()
def set_user_type(user_type):
    valid_types = ["Captain", "Passenger", "Company Admin", "Partner", "Dispatcher", "Accountant"]
    if user_type not in valid_types:
        frappe.throw(_("Invalid user type. Must be one of: {0}").format(", ".join(valid_types)))

    user = frappe.session.user
    frappe.db.set_value("User", user, "user_type", user_type)
    return {"status": "ok", "user_type": user_type}


@frappe.whitelist()
def set_role(role):
    """Set the user's intended role before onboarding begins."""
    valid_roles = ["Passenger", "Partner", "Captain"]
    if role not in valid_roles:
        frappe.throw(_("Invalid role. Must be one of: {0}").format(", ".join(valid_roles)))
    user = frappe.session.user
    frappe.db.set_value("User", user, "user_type", role)
    frappe.db.set_value("User", user, "onboarded", 0)
    return {"status": "ok", "role": role}


@frappe.whitelist()
def create_passenger_profile(full_name=None, mobile_no=None, nationality=None, id_document_type=None, id_number=None, id_expiry_date=None):
    """Create a passenger profile and mark onboarding complete."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Login is required"), frappe.PermissionError)

    from ftms.country.id_format import find_country, validate_document

    if id_document_type and id_number and nationality:
        country = find_country(country_name=nationality)
        if country.get("alpha_2"):
            result = validate_document(country["alpha_2"], id_document_type, id_number)
            if not result.get("valid"):
                frappe.throw(result.get("error") or "Invalid identity document format")

    frappe.db.set_value("User", user, {
        "user_type": "Passenger",
        "onboarded": 1,
        "mobile_no": mobile_no,
        "ftms_id_document_type": id_document_type,
        "ftms_id_no": id_number,
        "ftms_nationality": nationality,
        "ftms_id_expiry_date": id_expiry_date,
    })
    if full_name:
        frappe.db.set_value("User", user, "full_name", full_name)

    return {"status": "ok", "user": user, "role": "Passenger"}


@frappe.whitelist()
def create_partner_profile(
    partner_type=None, service_contract_type=None,
    company_name=None, legal_name=None, company_name_ar=None,
    vat_no=None, cr_no=None, tax_id=None, license_no=None,
    phone=None, email=None, address=None, city=None, country=None,
    full_name=None, mobile_no=None,
    partner_data=None,
):
    """Create a partner profile with company registration."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Login is required"), frappe.PermissionError)

    valid_types = ["Travel Agent", "Taxi Service", "Fleet Owner", "Rent A Car Service", "Service Contract"]
    if partner_type not in valid_types:
        frappe.throw(_("Invalid partner type"))

    if frappe.db.exists("Partner Profile", {"user": user}):
        frappe.throw(_("Partner profile already exists for this user"))
    if frappe.db.exists("User Company Link", {"user": user, "status": "Active"}):
        frappe.throw(_("User is already linked to a company"))

    domain = _default_domain()
    if not domain:
        frappe.throw(_("No Transportation Domain configured"))

    company_doc = frappe.get_doc({
        "doctype": "Company",
        "company_code": _unique_code("Company", "company_code", company_name or "Partner"),
        "company_name": company_name or f"{user}'s Company",
        "legal_name": legal_name,
        "company_name_ar": company_name_ar,
        "vat_no": vat_no,
        "tax_id": tax_id,
        "cr_no": cr_no,
        "phone": phone,
        "email": email or user,
        "address": address,
        "owner_user": user,
        "domain": domain,
        "onboarding_status": "Profile Complete",
        "status": "Active",
    })
    company_doc.insert(ignore_permissions=True)

    link_doc = frappe.get_doc({
        "doctype": "User Company Link",
        "link_code": _unique_code("User Company Link", "link_code", f"{company_doc.name}-{user}"),
        "user": user,
        "company": company_doc.name,
        "role": "Partner",
        "is_owner": 1,
        "joined_via": "Signup",
        "status": "Active",
        "approved_by": user,
        "approved_on": now_datetime(),
    })
    link_doc.insert(ignore_permissions=True)

    profile = frappe.get_doc({
        "doctype": "Partner Profile",
        "user": user,
        "full_name": full_name or frappe.db.get_value("User", user, "full_name") or user,
        "mobile_no": mobile_no,
        "partner_type": partner_type,
        "service_contract_type": service_contract_type if partner_type == "Service Contract" else None,
        "company": company_doc.name,
        "status": "Active",
        "company_name": company_name,
        "legal_name": legal_name,
        "company_name_ar": company_name_ar,
        "vat_no": vat_no,
        "cr_no": cr_no,
        "tax_id": tax_id,
        "license_no": license_no,
        "phone": phone,
        "email": email or user,
        "address": address,
        "city": city,
        "country": country,
        "partner_data": partner_data,
    })
    profile.insert(ignore_permissions=True)

    frappe.db.set_value("User", user, {"user_type": "Partner", "onboarded": 1})
    frappe.db.commit()

    return {
        "status": "ok",
        "profile": profile.name,
        "company": company_doc.name,
        "partner_type": partner_type,
    }


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
        "domain", "owner_user",
    ], as_dict=True)
    return company


@frappe.whitelist()
def complete():
    user = frappe.session.user
    frappe.db.set_value("User", user, "onboarded", 1)
    return {"status": "ok", "onboarded": True}


@frappe.whitelist()
def get_captain_profile():
    user = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user_id": user}, ["name", "employee_name", "phone", "vehicle_assigned"], as_dict=True)
    return {"has_profile": bool(employee), "profile": employee}


@frappe.whitelist()
def get_recent_rides(limit=10):
    user = frappe.session.user
    bookings = frappe.get_all("Trip Booking",
        filters={"passenger": user, "docstatus": 1},
        fields=["name", "trip", "booking_status", "from_location", "to_location", "scheduled_time"],
        order_by="creation desc",
        limit=limit,
    )
    return {"rides": bookings}
