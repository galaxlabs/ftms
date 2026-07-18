from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

FLAT_COMMISSION_THRESHOLD = 200
FLAT_COMMISSION_AMOUNT = 5


def accrue_commissions(trip, method=None):
    """Auto-create commission entries when a trip is completed.

    Rules applied:
    1. Flat rate commission: 5 SAR for trips with value > 200 SAR
    2. Driver percentage commission (if driver_commission_amount > 0)
    """
    if trip.get_doc_before_save():
        old_status = trip._doc_before_save.trip_status
    else:
        old_status = None

    if trip.trip_status != "Completed" or old_status == "Completed":
        return

    if not trip.driver:
        return

    if frappe.db.exists("Commission Entry", {"trip": trip.name}):
        return

    trip_value = flt(trip.trip_value or 0)

    # Flat rate commission for qualifying trips
    if trip_value > FLAT_COMMISSION_THRESHOLD:
        _create_entry(
            employee=trip.driver,
            trip=trip.name,
            trip_value=trip_value,
            commission_type="Flat Rate",
            rate=str(FLAT_COMMISSION_AMOUNT),
            amount=FLAT_COMMISSION_AMOUNT,
            notes=_("Flat commission for trip over {0} SAR").format(FLAT_COMMISSION_THRESHOLD),
        )

    # Percentage-based driver commission
    driver_amount = flt(trip.driver_commission_amount or 0)
    if driver_amount > 0:
        _create_entry(
            employee=trip.driver,
            trip=trip.name,
            trip_value=trip_value,
            commission_type="Percentage",
            rate=_("{0}%").format(trip.driver_commission_rate or 0),
            amount=driver_amount,
            notes=_("Driver commission at {0}%").format(trip.driver_commission_rate or 0),
        )

    # Mark driver commission as Posted
    frappe.db.set_value("Trip", trip.name, "driver_commission_status", "Posted")


def _create_entry(employee, trip, trip_value, commission_type, rate, amount, notes=""):
    """Create a single Commission Entry."""
    entry = frappe.get_doc({
        "doctype": "Commission Entry",
        "employee": employee,
        "trip": trip,
        "trip_value": trip_value,
        "commission_type": commission_type,
        "rate": rate,
        "amount": amount,
        "status": "Payable",
        "notes": notes,
    })
    entry.insert(ignore_permissions=True)
    return entry


def daily_commission_summary():
    """Daily cron: generate a summary of pending/payable commissions per employee."""
    entries = frappe.db.sql("""
        SELECT employee, employee_name, status, COUNT(*) as count, SUM(amount) as total
        FROM `tabCommission Entry`
        WHERE status IN ("Pending", "Payable")
        GROUP BY employee, status
    """, as_dict=True)

    for row in entries:
        frappe.log_error(
            _("Commission Summary - {0}: {1} entries ({2}) = {3} SAR").format(
                row.employee_name or row.employee,
                row.count,
                row.status,
                flt(row.total),
            ),
            _("Daily Commission Summary"),
        )

    return entries


def get_employee_ledger(employee, from_date=None, to_date=None):
    """Return all commission entries for a given employee."""
    filters = {"employee": employee}
    if from_date:
        filters["creation"] = [">=", from_date]
    if to_date:
        filters.setdefault("creation", [])
        filters["creation"].append(["<=", to_date])

    entries = frappe.get_all(
        "Commission Entry",
        filters=filters,
        fields=["*"],
        order_by="creation desc",
    )
    totals = {"pending": 0, "payable": 0, "paid": 0}
    for e in entries:
        status = e.status
        if status in totals:
            totals[status] += flt(e.amount)

    return {"entries": entries, **totals}


def get_company_ledger(company, from_date=None, to_date=None):
    """Return commission entries grouped by employee for a company."""
    filters = {"company": company}
    if from_date:
        filters["creation"] = [">=", from_date]
    if to_date:
        filters.setdefault("creation", [])
        filters["creation"].append(["<=", to_date])

    entries = frappe.get_all(
        "Commission Entry",
        filters=filters,
        fields=["employee", "employee_name", "status", "SUM(amount) as total", "COUNT(*) as count"],
        group_by="employee, status",
        order_by="employee, status",
    )
    return entries
