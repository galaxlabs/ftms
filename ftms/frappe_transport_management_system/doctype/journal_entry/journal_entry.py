from __future__ import annotations

import frappe
from frappe.model.document import Document


class JournalEntry(Document):
    def validate(self):
        self.calculate_totals()
        if abs(self.total_debit - self.total_credit) > 0.01:
            frappe.throw("Debit and Credit totals must be equal.")

    def calculate_totals(self):
        self.total_debit = sum((r.debit or 0) for r in self.accounts)
        self.total_credit = sum((r.credit or 0) for r in self.accounts)

    def before_submit(self):
        self.validate_against_voucher()
        self.make_gl_entries()

    def on_submit(self):
        frappe.db.set_value("Journal Entry", self.name, "status", "Submitted")

    def before_cancel(self):
        self.cancel_gl_entries()

    def on_cancel(self):
        frappe.db.set_value("Journal Entry", self.name, "status", "Cancelled")

    def make_gl_entries(self):
        for row in self.accounts:
            gle = frappe.get_doc({
                "doctype": "GL Entry",
                "account": row.account,
                "debit": row.debit or 0,
                "credit": row.credit or 0,
                "posting_date": self.posting_date,
                "company": self.company,
                "voucher_type": "Journal Entry",
                "voucher_no": self.name,
                "voucher_detail_no": row.name,
                "fiscal_year": self.get_fiscal_year(),
                "remarks": self.title or "",
            })
            gle.flags.ignore_permissions = True
            gle.insert()

    def cancel_gl_entries(self):
        existing = frappe.db.get_all("GL Entry",
            filters={"voucher_type": "Journal Entry", "voucher_no": self.name, "is_cancelled": 0})
        for gle in existing:
            frappe.db.set_value("GL Entry", gle.name, "is_cancelled", 1)

    def validate_against_voucher(self):
        pass

    def get_fiscal_year(self):
        from frappe.utils import get_fiscal_year
        return get_fiscal_year(self.posting_date)[0]

    def get_balance(self):
        return self.total_debit - self.total_credit
