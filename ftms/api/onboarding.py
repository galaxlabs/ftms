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

    company = frappe.db.get_value("Transportation Company", {"company_name": company_name}, "name")
    if not company:
        company_domain = _default_domain(domain)
        if not company_domain:
            frappe.throw(_("No Transportation Domain is configured. Create one before public signup."))
        company_doc = frappe.get_doc({
            "doctype": "Transportation Company",
            "company_code": _unique_code("Transportation Company", "company_code", company_name),
            "company_name": company_name,
            "domain": company_domain,
            "email": email,
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
            "status": "Active",
            "approved_by": frappe.session.user if frappe.session.user != "Guest" else "Administrator",
            "approved_on": now_datetime(),
        })
        link_doc.insert(ignore_permissions=True)

    frappe.db.commit()
    return {
        "status": "ok",
        "user": user_doc.name,
        "company": company,
        "company_name": company_name,
        "role": "Company Admin",
        "link": link_doc.name,
    }


@frappe.whitelist()
def get_status():
    user = frappe.session.user
    if user == "Guest":
        return {"onboarded": False, "user_type": None}

    profile = frappe.db.get_value("User", user, ["user_type", "onboarded"], as_dict=True)
    if not profile:
        return {"onboarded": False, "user_type": None}

    return {
        "onboarded": bool(profile.get("onboarded")),
        "user_type": profile.get("user_type"),
    }


@frappe.whitelist()
def set_user_type(user_type):
    valid_types = ["Captain", "Passenger", "Company Admin", "Dispatcher", "Accountant"]
    if user_type not in valid_types:
        frappe.throw(_("Invalid user type. Must be one of: {0}").format(", ".join(valid_types)))

    user = frappe.session.user
    frappe.db.set_value("User", user, "user_type", user_type)
    return {"status": "ok", "user_type": user_type}


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
