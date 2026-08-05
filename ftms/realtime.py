from __future__ import annotations

import frappe


STATUS_FIELDS = {
    "Trip": "trip_status",
    "Trip Booking": "booking_status",
    "Booking Offer": "status",
    "Payment Transaction": "status",
    "User Subscription": "status",
    "Notification Event": "status",
}


def publish_document_update(doc, method=None):
    """Publish a minimal update only to users related to the document."""
    payload = {
        "doctype": doc.doctype,
        "name": doc.name,
        "status": doc.get(STATUS_FIELDS.get(doc.doctype)),
        "modified": str(doc.modified or ""),
    }
    for user in _recipients(doc):
        frappe.publish_realtime(
            "ftms_update",
            payload,
            user=user,
            after_commit=True,
        )


def _recipients(doc):
    users = set()
    for fieldname in ("recipient_user", "user", "main_rider_user", "assigned_captain_user", "captain_user"):
        value = doc.get(fieldname)
        if value and value != "Guest":
            users.add(value)

    company = doc.get("company")
    booking_name = doc.get("booking") or doc.get("trip_booking")
    if doc.doctype == "Trip Booking":
        booking_name = doc.name
    elif doc.doctype == "Trip" and not booking_name:
        booking_name = frappe.db.get_value("Trip Booking", {"trip": doc.name}, "name")

    if booking_name:
        company = company or frappe.db.get_value("Trip Booking", booking_name, "company")
        rider = frappe.db.get_value("Trip Booking", booking_name, "main_rider_user")
        if rider:
            users.add(rider)
        users.update(
            frappe.get_all(
                "Trip Passenger",
                filters={"parent": booking_name, "user": ("is", "set")},
                pluck="user",
            )
        )

    company_roles = {
        "Trip": ("Company Admin", "Dispatcher"),
        "Trip Booking": ("Company Admin", "Dispatcher"),
        "Booking Offer": ("Company Admin", "Dispatcher"),
        "Payment Transaction": ("Company Admin", "Accountant"),
        "User Subscription": ("Company Admin", "Accountant"),
    }.get(doc.doctype)
    if company and company_roles:
        users.update(
            frappe.get_all(
                "User Company Link",
                filters={
                    "company": company,
                    "status": "Active",
                    "role": ("in", company_roles),
                },
                pluck="user",
            )
        )
    return {user for user in users if user and user != "Guest"}
