from __future__ import annotations

from frappe.model.dashboard import Dashboard


def get_data(data=None):
    return Dashboard(
        transactions=[
            {"label": "Trips", "items": ["Trip"]},
            {"label": "Inspections", "items": ["Vehicle Inspection Log"]},
        ]
    ).data
