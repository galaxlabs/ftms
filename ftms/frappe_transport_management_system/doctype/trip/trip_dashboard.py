from __future__ import annotations

from frappe.model.dashboard import Dashboard


def get_data(data=None):
    return Dashboard(
        transactions=[
            {"label": "Bookings", "items": ["Trip Booking"]},
            {"label": "Invoices", "items": ["Trip Invoice"]},
            {"label": "Passengers", "items": ["Trip Passenger"]},
            {"label": "Staff", "items": ["Trip Staff Assignment"]},
        ]
    ).data
