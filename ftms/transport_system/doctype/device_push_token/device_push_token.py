from __future__ import annotations

import frappe
from frappe.model.document import Document


class DevicePushToken(Document):
    def validate(self):
        self.user = self.user or frappe.session.user
        if not self.user or self.user == "Guest":
            frappe.throw("A signed-in user is required")
        if not self.token:
            frappe.throw("Push token is required")
