from __future__ import annotations

import frappe
from frappe.model.document import Document


class TransportationCompany(Document):
    def validate(self):
        if self.onboarding_status in ("ZATCA Ready", "Active"):
            required = {
                "legal_name": "Legal Name",
                "vat_no": "VAT No",
                "cr_no": "CR No",
                "address": "Address",
                "phone": "Phone",
                "email": "Email",
            }
            missing = [label for field, label in required.items() if not self.get(field)]
            if missing:
                frappe.throw("Complete company profile before activating: " + ", ".join(missing))

        if self.enable_zatca_e_invoicing and self.zatca_phase == "ZATCA Phase 2":
            if not self.production_csid:
                frappe.msgprint("Production CSID is required for ZATCA Phase 2", indicator="orange")
            if not self.zatca_environment:
                frappe.msgprint("ZATCA Environment is required for ZATCA Phase 2", indicator="orange")
