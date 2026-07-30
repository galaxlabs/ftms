from __future__ import annotations

import frappe

from ftms.config.service import (
    get_client_config as resolve_client_config,
    get_document_format as resolve_document_format,
    validate_configured_document,
)


@frappe.whitelist(allow_guest=True)
def get_client_config(country=None, platform=None, company=None):
    """Return safe configuration for Vue/Flutter clients; never return private secrets."""
    return resolve_client_config(
        user=frappe.session.user,
        company=company,
        country=country,
        platform=platform,
    )


@frappe.whitelist(allow_guest=True)
def get_document_format(country=None, document_type=None):
    if not country or not document_type:
        frappe.throw("Country and document type are required")
    return resolve_document_format(country, document_type) or {}


@frappe.whitelist(allow_guest=True)
def validate_document(country=None, document_type=None, value=None):
    if not country or not document_type:
        frappe.throw("Country and document type are required")
    return validate_configured_document(country, document_type, value)
