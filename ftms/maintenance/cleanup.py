"""Auto-cleanup: remove old Umrah/Hajj bookings after 21 days, keep invoices for ZATCA."""
from __future__ import annotations

import frappe
from frappe.utils import add_days, today, getdate


EXPIRY_DAYS = 21
UMRAH_HAJJ_KEYWORDS = ["umrah", "hajj", "makkah", "madinah", "mecca", "medina"]


def _is_umrah_hajj(booking):
    """Detect Umrah/Hajj bookings by route, title, or service type."""
    text = " ".join([
        str(booking.get("route") or ""),
        str(booking.get("booking_title") or ""),
        str(booking.get("pickup_point") or ""),
        str(booking.get("drop_point") or ""),
    ]).lower()
    return any(kw in text for kw in UMRAH_HAJJ_KEYWORDS)


def _is_keep_type(booking):
    """Pick & drop and regular rides are kept. Umrah/Hajj are deleted."""
    service = str(booking.get("service_type") or "").lower()
    if service in ("pick_drop", "ride"):
        return True
    return False


def cleanup_old_bookings():
    """Delete Umrah/Hajj bookings older than EXPIRY_DAYS.
    Trip Invoices are preserved for ZATCA/tax compliance.
    Runs as a daily scheduled job.
    """
    cutoff = add_days(today(), -EXPIRY_DAYS)

    candidates = frappe.db.get_all(
        "Trip Booking",
        filters={
            "creation": ("<=", cutoff),
            "booking_status": ("in", ["Draft", "Confirmed", "Cancelled"]),
        },
        fields=["name", "route", "booking_title", "pickup_point", "drop_point",
                "service_type", "booking_date", "booking_status", "trip"],
        limit_page_length=500,
    )

    removed = 0
    for b in candidates:
        if _is_keep_type(b):
            continue
        if not _is_umrah_hajj(b):
            continue
        try:
            _force_delete_booking(b.name)
            removed += 1
        except Exception as e:
            frappe.log_error(
                f"Cleanup failed for {b.name}: {e}",
                "Booking Cleanup Error",
            )

    if removed:
        frappe.db.commit()
        frappe.log_error(
            f"Cleaned up {removed} expired Umrah/Hajj bookings older than {cutoff}",
            "Booking Cleanup",
        )

    return removed


def _force_delete_booking(booking_name):
    """Force-delete a booking and all linked children, bypassing validation."""
    booking = frappe.db.get_value(
        "Trip Booking", booking_name,
        ["name", "trip", "selected_captain", "selected_vehicle"], as_dict=True,
    )
    if not booking:
        return

    # Delete child passengers
    frappe.db.sql("DELETE FROM `tabTrip Passenger` WHERE parent=%s", booking_name)

    # Delete linked offers
    frappe.db.sql("DELETE FROM `tabBooking Offer` WHERE booking=%s", booking_name)

    # Delete linked penalties
    frappe.db.sql("DELETE FROM `tabPenalty Entry` WHERE booking=%s", booking_name)

    # Delete linked settlements (keep ledger/invoice intact)
    frappe.db.sql("DELETE FROM `tabSettlement` WHERE trip=%s", booking.trip)

    # Delete linked trip (but NOT trip invoice - keep for ZATCA)
    if booking.trip:
        frappe.db.sql("DELETE FROM `tabTrip Expense` WHERE trip=%s", booking.trip)
        frappe.db.sql("DELETE FROM `tabTrip Staff Assignment` WHERE parent=%s", booking.trip)
        frappe.db.sql("DELETE FROM `tabTrip Rating` WHERE trip=%s", booking.trip)
        frappe.db.sql("DELETE FROM `tabTrip` WHERE name=%s", booking.trip)

    # Delete the booking itself
    frappe.db.sql("DELETE FROM `tabTrip Booking` WHERE name=%s", booking_name)


def cleanup_old_trip_groups():
    """Delete abandoned trip groups (no usage in EXPIRY_DAYS)."""
    cutoff = add_days(today(), -EXPIRY_DAYS)
    groups = frappe.db.get_all(
        "Trip Group",
        filters={"modified": ("<=", cutoff), "times_used": 0},
        fields=["name"],
        limit_page_length=200,
    )
    for g in groups:
        frappe.db.sql("DELETE FROM `tabTrip Group Passenger` WHERE parent=%s", g.name)
        frappe.db.sql("DELETE FROM `tabTrip Group` WHERE name=%s", g.name)
    return len(groups)
