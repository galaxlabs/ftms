"""Standalone data fields for cross-doctype references.
Makes doctypes self-contained: each stores a reference name + a flag
rather than a hard Link that breaks when the target is deleted.
"""
from __future__ import annotations

import frappe


def set_trip_on_booking(booking_name, trip_name):
    """Write the trip reference on a Trip Booking as both Link and Data+Check."""
    frappe.db.set_value("Trip Booking", booking_name, "trip", trip_name)
    frappe.db.set_value("Trip Booking", booking_name, "trip_ref", trip_name)
    frappe.db.set_value("Trip Booking", booking_name, "has_trip", 1)


def set_booking_on_trip(trip_name, booking_name):
    """Write the booking reference on a Trip as both Link and Data+Check."""
    frappe.db.set_value("Trip", trip_name, "trip_booking", booking_name)
    frappe.db.set_value("Trip", trip_name, "booking_ref", booking_name)
    frappe.db.set_value("Trip", trip_name, "has_booking", 1)


def set_vehicle_on_booking_offer(offer_name, vehicle_name):
    frappe.db.set_value("Booking Offer", offer_name, "vehicle", vehicle_name)
    frappe.db.set_value("Booking Offer", offer_name, "vehicle_ref", vehicle_name)
    frappe.db.set_value("Booking Offer", offer_name, "has_vehicle", 1)
