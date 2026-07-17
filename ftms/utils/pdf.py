from __future__ import annotations

import frappe


def render_pdf(doctype, name, print_format=None, doc=None):
	if doc is None:
		doc = frappe.get_doc(doctype, name)
	html = frappe.get_print(doctype, name, print_format=print_format, doc=doc)
	return html
