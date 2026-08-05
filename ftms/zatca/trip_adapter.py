from __future__ import annotations

import frappe
from frappe import _

from ftms.zatca.adapter import TripInvoiceAdapter


def validate_trip_invoice(doc, method=None):
    if not doc.company:
        return

    company_doc = frappe.get_cached_doc("Company", doc.company)
    if not company_doc.enable_zatca_e_invoicing:
        return

    if company_doc.zatca_phase == "ZATCA Phase 2":
        if not company_doc.production_csid:
            frappe.throw(_(
                "ZATCA Phase 2 requires a Production CSID. Complete onboarding for company {0} first."
            ).format(doc.company))
        csid = frappe.get_doc("Production CSID", company_doc.production_csid)
        if csid.status != "Active":
            frappe.throw(_("Production CSID for {0} is not active").format(doc.company))

    _validate_vat_fields(doc, company_doc)


def on_submit_trip_invoice(doc, method=None):
    if not doc.company:
        return

    company_doc = frappe.get_cached_doc("Company", doc.company)
    if not company_doc.enable_zatca_e_invoicing:
        return

    frappe.enqueue(
        "ftms.zatca.trip_adapter.submit_trip_invoice",
        invoice_name=doc.name,
        queue="short",
        timeout=120,
        enqueue_after_commit=True,
        job_id=f"zatca-trip-invoice-{doc.name}",
        deduplicate=True,
    )


def submit_trip_invoice(invoice_name):
    from ftms.zatca.clearance import submit_to_zatca

    try:
        result = submit_to_zatca(invoice_name, doctype="Trip Invoice")
        frappe.db.set_value(
            "Trip Invoice",
            invoice_name,
            {"zatca_submit_status": result.get("status"), "zatca_error": None},
        )
    except Exception as exc:
        frappe.db.set_value(
            "Trip Invoice",
            invoice_name,
            {"zatca_submit_status": "FAILED", "zatca_error": str(exc)[:1000]},
        )
        frappe.log_error(frappe.get_traceback(), f"ZATCA submission failed: {invoice_name}")
        return {"status": "FAILED", "error": str(exc)}
    return result


def _validate_vat_fields(doc, company_doc):
    missing = []
    if not company_doc.vat_no:
        missing.append("VAT No")
    if not company_doc.cr_no:
        missing.append("CR No")
    if not company_doc.company_name:
        missing.append("Company Name")
    if missing:
        frappe.throw(_(
            "ZATCA E-Invoicing requires: {0}. Update company {1} first."
        ).format(", ".join(missing), doc.company))


def get_adapter():
    return TripInvoiceAdapter()
