from __future__ import annotations

import frappe
from frappe.model.document import Document


class CommissionEntry(Document):
    def before_save(self):
        if not self.employee_name:
            emp = frappe.db.get_value("Employee", self.employee, "employee_name")
            self.employee_name = emp
