from __future__ import annotations

import frappe

from ftms.document_ai import service


@frappe.whitelist(methods=["POST"])
def extract_attachment(attachment_action_id, file_url, target_doctype, target_name):
	return service.extract_attachment(attachment_action_id, file_url, target_doctype, target_name)


@frappe.whitelist(methods=["POST"])
def confirm_extraction(extraction, confirmed_values, corrections=None):
	return service.confirm_extraction(extraction, confirmed_values, corrections)
