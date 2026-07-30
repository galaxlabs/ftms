from __future__ import annotations

import frappe
from frappe.utils import now_datetime


def emit_event(event_type, recipient_user, title, message, company=None,
			   reference_doctype=None, reference_name=None, channel="In App", dedupe_key=None):
	if not recipient_user or recipient_user == "Guest":
		return None
	if dedupe_key and frappe.db.exists("Notification Event", {"dedupe_key": dedupe_key}):
		return frappe.db.get_value("Notification Event", {"dedupe_key": dedupe_key}, "name")
	doc = frappe.get_doc({
		"doctype": "Notification Event",
		"event_type": event_type,
		"recipient_user": recipient_user,
		"company": company,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"title": title,
		"message": message,
		"channel": channel,
		"status": "Queued",
		"dedupe_key": dedupe_key,
		"created_at": now_datetime(),
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def dispatch_queued_notifications():
	"""Deliver supported queued events; unsupported channels remain retryable."""
	for event in frappe.get_all(
		"Notification Event",
		filters={"status": "Queued"},
		fields=["name", "recipient_user", "title", "message", "channel"],
		limit_page_length=100,
	):
		doc = frappe.get_doc("Notification Event", event.name)
		try:
			if doc.channel == "In App":
				doc.status = "Sent"
				doc.sent_at = now_datetime()
			elif doc.channel == "Email":
				email = frappe.db.get_value("User", doc.recipient_user, "email")
				if not email:
					doc.error_message = "Recipient has no email address"
					doc.status = "Failed"
				else:
					frappe.sendmail(recipients=[email], subject=doc.title, message=doc.message)
					doc.status = "Sent"
					doc.sent_at = now_datetime()
			doc.save(ignore_permissions=True)
		except Exception as exc:
			doc.status = "Failed"
			doc.error_message = str(exc)[:500]
			doc.save(ignore_permissions=True)
	frappe.db.commit()
