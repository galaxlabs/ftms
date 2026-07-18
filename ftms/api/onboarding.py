from __future__ import annotations

import frappe
from frappe import _


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
