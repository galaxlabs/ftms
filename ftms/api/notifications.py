from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime


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


@frappe.whitelist()
def register_device_token(token, platform="unknown", device_id=None):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	if not token:
		frappe.throw(_("Push token is required"))
	name = frappe.db.get_value("Device Push Token", {"token": token}, "name")
	if name:
		owner, active = frappe.db.get_value("Device Push Token", name, ["user", "active"])
		if owner != user and active:
			frappe.throw(_("This push token is already registered to another user"), frappe.PermissionError)
		frappe.db.set_value("Device Push Token", name, {
			"user": user,
			"platform": platform if platform in ("android", "web", "ios") else "unknown",
			"device_id": device_id,
			"active": 1,
			"last_seen_at": now_datetime(),
			"last_error": None,
		})
	else:
		doc = frappe.get_doc({
			"doctype": "Device Push Token",
			"user": user,
			"token": token,
			"platform": platform if platform in ("android", "web", "ios") else "unknown",
			"device_id": device_id,
			"active": 1,
			"last_seen_at": now_datetime(),
		})
		doc.insert(ignore_permissions=True)
		name = doc.name
	return {"name": name, "status": "Active"}


@frappe.whitelist()
def unregister_device_token(token):
	user = frappe.session.user
	name = frappe.db.get_value("Device Push Token", {"token": token, "user": user}, "name")
	if name:
		frappe.db.set_value("Device Push Token", name, "active", 0)
	return {"status": "ok"}
