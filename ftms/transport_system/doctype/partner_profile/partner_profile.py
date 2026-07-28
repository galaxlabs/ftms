from __future__ import annotations

import frappe
from frappe.model.document import Document


class PartnerProfile(Document):
    def before_insert(self):
        if self.company_name and not self.company:
            self._create_company()

    def _create_company(self):
        company_doc = frappe.get_doc({
            "doctype": "Company",
            "company_code": self._make_code(self.company_name),
            "company_name": self.company_name,
            "legal_name": self.legal_name,
            "company_name_ar": self.company_name_ar,
            "vat_no": self.vat_no,
            "tax_id": self.tax_id,
            "cr_no": self.cr_no,
            "phone": self.phone,
            "email": self.email or self.user,
            "address": self.address,
            "owner_user": self.user,
            "domain": self._default_domain(),
            "onboarding_status": "Profile Complete",
            "status": "Active",
        })
        company_doc.insert(ignore_permissions=True)
        self.company = company_doc.name
        self._create_user_link(company_doc.name)

    def _create_user_link(self, company_name):
        link = frappe.get_doc({
            "doctype": "User Company Link",
            "link_code": self._make_code(f"{company_name}-{self.user}"),
            "user": self.user,
            "company": company_name,
            "role": "Partner",
            "is_owner": 1,
            "joined_via": "Signup",
            "status": "Active",
            "approved_by": self.user,
            "approved_on": frappe.utils.now_datetime(),
        })
        link.insert(ignore_permissions=True)

    def _make_code(self, value):
        import re
        code = re.sub(r"[^A-Z0-9]+", "-", (value or "").upper()).strip("-")
        return (code or "PRT")[:24]

    def _default_domain(self):
        existing = frappe.db.get_value("Transportation Domain", {"is_active": 1}, "name")
        if existing:
            return existing
        return frappe.db.get_value("Transportation Domain", {}, "name")
