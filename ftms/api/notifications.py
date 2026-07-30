from __future__ import annotations

import frappe
from frappe import _


@frappe.whitelist()
def list_my_notifications(limit=50):
	if frappe.session.user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	return frappe.get_all(
		"Notification Event",
		filters={"recipient_user": frappe.session.user},
		fields=["name", "event_type", "title", "message", "channel", "status", "reference_doctype", "reference_name", "created_at"],
		order_by="created_at desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def mark_read(name):
	if frappe.session.user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	doc = frappe.get_doc("Notification Event", name)
	if doc.recipient_user != frappe.session.user:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	doc.db_set("status", "Read")
	return {"name": name, "status": "Read"}
