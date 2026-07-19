from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class CommissionPayout(Document):
    def before_save(self):
        self._update_totals()

    def before_submit(self):
        self._validate_entries()
        self.status = "Paid"
        self.payment_date = self.payment_date or today()
        self._mark_entries_paid()

    def before_cancel(self):
        self._unmark_entries()
        self.status = "Draft"

    def _update_totals(self):
        total = 0
        for row in self.entries:
            entry = frappe.get_cached_value("Commission Entry", row.commission_entry, "amount")
            row.amount = entry or 0
            total += row.amount
        self.total_entries = len(self.entries)
        self.total_amount = total

    def _validate_entries(self):
        for row in self.entries:
            status = frappe.get_cached_value("Commission Entry", row.commission_entry, "status")
            if status == "Paid":
                frappe.throw(_("Commission Entry {0} is already paid").format(row.commission_entry))

    def _mark_entries_paid(self):
        for row in self.entries:
            frappe.db.set_value("Commission Entry", row.commission_entry, {
                "status": "Paid",
                "payout": self.name,
                "payout_date": self.payment_date or today(),
            })

    def _unmark_entries(self):
        for row in self.entries:
            frappe.db.set_value("Commission Entry", row.commission_entry, {
                "status": "Payable",
                "payout": None,
                "payout_date": None,
            })
