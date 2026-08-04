from __future__ import annotations

import frappe

from ftms.config.service import (
    get_app_config as resolve_app_config,
    get_client_config as resolve_client_config,
    get_document_format as resolve_document_format,
    get_kashf_config,
    validate_configured_document,
)
from ftms.security import rate_limit


@frappe.whitelist(allow_guest=True)
def get_app_config(include_private=0):
    """Mobile app configuration. Only Firebase client keys are returned; payment
    webhook secrets and server-side Maps keys are never exposed."""
    rate_limit("get_app_config", limit=60, seconds=60)
    return resolve_app_config(include_private=bool(include_private))


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


@frappe.whitelist()
def get_kashf_template(service_type=None, country=None):
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)
    return get_kashf_config(service_type=service_type, country=country)
