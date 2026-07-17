from __future__ import annotations

import frappe
from frappe.utils.pdf import get_pdf


@frappe.whitelist()
def trip_invoice_pdf(name, print_format=None):
	html = frappe.get_print("FTMS Trip Invoice", name, print_format=print_format)
	frappe.response.filename = f"{name}.pdf"
	frappe.response.filecontent = get_pdf(html)
	frappe.response.type = "download"
	return None


@frappe.whitelist()
def trip_manifest_pdf(name, print_format=None):
	html = frappe.get_print("FTMS Trip", name, print_format=print_format)
	frappe.response.filename = f"{name}-manifest.pdf"
	frappe.response.filecontent = get_pdf(html)
	frappe.response.type = "download"
	return None
