from __future__ import annotations

import frappe
from frappe import _

from ftms.commissions.engine import get_employee_ledger, get_company_ledger


@frappe.whitelist()
def get_ledger(employee, from_date=None, to_date=None):
    """Return commission ledger for an employee/captain."""
    return get_employee_ledger(employee, from_date, to_date)


@frappe.whitelist()
def get_company_commissions(company, from_date=None, to_date=None):
    """Return commission summary by employee for a company."""
    return get_company_ledger(company, from_date, to_date)


@frappe.whitelist()
def get_summary(employee=None):
    """Return commission summary (pending/payable/paid totals)."""
    filters = {"status": ["in", ("Pending", "Payable")]}
    if employee:
        filters["employee"] = employee

    data = frappe.get_all(
        "Commission Entry",
        filters=filters,
        fields=["status", "SUM(amount) as total", "COUNT(*) as count"],
        group_by="status",
    )
    result = {"pending": 0, "payable": 0, "pending_count": 0, "payable_count": 0}
    for row in data:
        s = row.status.lower()
        result[s] = row.total or 0
        result[f"{s}_count"] = row.count or 0
    return result


@frappe.whitelist()
def list_payouts(employee=None, status=None):
    """List commission payouts."""
    filters = {}
    if employee:
        filters["employee"] = employee
    if status:
        filters["status"] = status
    return frappe.get_all(
        "Commission Payout",
        filters=filters,
        fields=["name", "employee", "employee_name", "from_date", "to_date",
                "total_amount", "total_entries", "status", "payment_date",
                "payment_method", "reference_no"],
        order_by="creation desc",
    )


@frappe.whitelist()
def create_payout(employee, company, from_date, to_date, commission_entries=None):
    """Create a payout for selected commission entries or all payable entries.

    If commission_entries is not provided, includes all Payable entries for the employee.
    """
    if commission_entries:
        entry_names = commission_entries
    else:
        entry_names = frappe.get_all(
            "Commission Entry",
            filters={
                "employee": employee,
                "status": "Payable",
                "trip_date": ["between", [from_date, to_date]],
            },
            pluck="name",
        )

    if not entry_names:
        frappe.throw(_("No payable commission entries found for this period."))

    payout = frappe.get_doc({
        "doctype": "Commission Payout",
        "employee": employee,
        "company": company,
        "from_date": from_date,
        "to_date": to_date,
        "entries": [{"commission_entry": name} for name in entry_names],
        "status": "Draft",
    })
    payout.insert(ignore_permissions=True)
    return {"name": payout.name, "total_amount": payout.total_amount, "entries": len(entry_names)}


@frappe.whitelist()
def submit_payout(name):
    """Submit/mark a payout as paid."""
    payout = frappe.get_doc("Commission Payout", name)
    payout.before_submit()
    payout.save(ignore_permissions=True)
    return {"status": payout.status, "name": payout.name}


@frappe.whitelist()
def cancel_payout(name):
    """Cancel a payout and unmark entries."""
    payout = frappe.get_doc("Commission Payout", name)
    payout.before_cancel()
    payout.save(ignore_permissions=True)
    return {"status": payout.status, "name": payout.name}
