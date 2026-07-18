from __future__ import annotations

import frappe
from frappe import _


def sync_letterhead(company_doc, method=None):
    if not frappe.db.exists("DocType", "Letterhead"):
        return
    if not company_doc.enable_print_branding:
        return

    letterhead_name = _("Letterhead - {0}").format(company_doc.company_code)
    existing = frappe.db.exists("Letterhead", letterhead_name)

    header_html = _build_header_html(company_doc)
    footer_text = company_doc.footer_text or company_doc.company_name

    if existing:
        letterhead = frappe.get_doc("Letterhead", existing)
        letterhead.image = company_doc.logo
        letterhead.header = header_html
        letterhead.footer = footer_text
        letterhead.save(ignore_permissions=True)
    else:
        letterhead = frappe.get_doc({
            "doctype": "Letterhead",
            "letterhead_name": letterhead_name,
            "image": company_doc.logo,
            "header": header_html,
            "footer": footer_text,
            "is_default": 0,
        })
        letterhead.insert(ignore_permissions=True)

    if company_doc.get("__print_letterhead") != letterhead_name:
        frappe.db.set_value("Transportation Company", company_doc.name,
                           "__print_letterhead", letterhead_name, update_modified=False)

    return letterhead_name


def get_letterhead(company_code):
    """Return the letterhead name for a given company code."""
    return _("Letterhead - {0}").format(company_code)


def _build_header_html(company):
    """Build a branded header HTML block."""
    lines = [f"<h3 style='margin:0;'>{company.company_name}</h3>"]
    if company.company_name_ar:
        lines.append(f"<div style='direction:rtl;'>{company.company_name_ar}</div>")
    lines.append(f"<div>VAT: {company.vat_no or ''} | CR: {company.cr_no or ''}</div>")
    if company.address:
        lines.append(f"<div style='font-size:9pt;'>{company.address}</div>")
    if company.phone:
        lines.append(f"<div style='font-size:9pt;'>Tel: {company.phone}</div>")
    return "<br>".join(lines)


def sync_all_letterheads():
    """Sync all companies that have print branding enabled."""
    companies = frappe.get_all("Transportation Company",
        filters={"enable_print_branding": 1},
        fields=["name"],
    )
    for c in companies:
        doc = frappe.get_doc("Transportation Company", c.name)
        sync_letterhead(doc)
    frappe.db.commit()
