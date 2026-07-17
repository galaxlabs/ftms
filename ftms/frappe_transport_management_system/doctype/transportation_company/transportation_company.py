from __future__ import annotations

import frappe
from frappe.model.document import Document


class TransportationCompany(Document):
    def validate(self):
        if self.enable_zatca_e_invoicing and self.zatca_phase == "ZATCA Phase 2":
            if not self.production_csid:
                frappe.msgprint("Production CSID is required for ZATCA Phase 2", indicator="orange")
            if not self.zatca_environment:
                frappe.msgprint("ZATCA Environment is required for ZATCA Phase 2", indicator="orange")
