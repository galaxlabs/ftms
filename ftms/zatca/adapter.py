from __future__ import annotations

import frappe


class InvoiceAdapter:
    """Base adapter interface for ZATCA invoicing.

    Each app that uses ZATCA implements a subclass and registers it via
    the `get_zatca_adapter` hook or by passing it explicitly.
    """

    def get_invoice(self, name: str):
        raise NotImplementedError

    def get_company(self, invoice) -> str:
        raise NotImplementedError

    def get_customer_name(self, invoice) -> str:
        raise NotImplementedError

    def get_items(self, invoice) -> list:
        raise NotImplementedError

    def get_invoice_type(self, invoice) -> str:
        raise NotImplementedError

    def is_return(self, invoice) -> bool:
        raise NotImplementedError

    def get_invoice_date(self, invoice):
        raise NotImplementedError

    def get_grand_total(self, invoice) -> float:
        raise NotImplementedError

    def get_net_total(self, invoice) -> float:
        raise NotImplementedError

    def get_vat_amount(self, invoice) -> float:
        raise NotImplementedError

    def get_vat_rate(self, invoice) -> float:
        raise NotImplementedError

    def save_zatca_data(self, invoice, data: dict):
        raise NotImplementedError


class TripInvoiceAdapter(InvoiceAdapter):
    """Adapter for FTMS Trip Invoice doctype."""

    def get_invoice(self, name: str):
        return frappe.get_doc("Trip Invoice", name)

    def get_company(self, invoice) -> str:
        return invoice.company

    def get_customer_name(self, invoice) -> str:
        return invoice.customer

    def get_items(self, invoice) -> list:
        return invoice.items or []

    def get_invoice_type(self, invoice) -> str:
        inv_type = getattr(invoice, "invoice_type", None)
        if inv_type == "Credit Note":
            return "credit_note"
        elif inv_type == "Debit Note":
            return "debit_note"
        return "invoice"

    def is_return(self, invoice) -> bool:
        return False

    def get_invoice_date(self, invoice):
        return invoice.invoice_date

    def get_grand_total(self, invoice) -> float:
        return invoice.grand_total or 0

    def get_net_total(self, invoice) -> float:
        return invoice.net_total or 0

    def get_vat_amount(self, invoice) -> float:
        return invoice.vat_amount or 0

    def get_vat_rate(self, invoice) -> float:
        return invoice.vat_rate or 15

    def save_zatca_data(self, invoice, data: dict):
        for key, value in data.items():
            if hasattr(invoice, key) or key in invoice.as_dict():
                invoice.set(key, value)
            else:
                prefixed = "custom_" + key
                if hasattr(invoice, prefixed) or prefixed in invoice.as_dict():
                    invoice.set(prefixed, value)
        invoice.save(ignore_permissions=True)


def get_adapter(doctype: str) -> InvoiceAdapter:
    """Resolve ZATCA adapter for a given doctype via hooks."""
    adapters = frappe.get_hooks("zatca_invoice_adapters") or {}
    if doctype in adapters:
        return frappe.get_attr(adapters[doctype])()
    if doctype == "Trip Invoice":
        return TripInvoiceAdapter()
    raise ValueError(f"No ZATCA adapter registered for {doctype}")


@frappe.whitelist()
def registered_adapters():
    return list(frappe.get_hooks("zatca_invoice_adapters").keys()) if frappe.get_hooks("zatca_invoice_adapters") else []
