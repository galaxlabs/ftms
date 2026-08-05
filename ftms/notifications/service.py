from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime


def emit_event(event_type, recipient_user, title, message, company=None,
			   reference_doctype=None, reference_name=None, channel="FCM", dedupe_key=None):
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
	frappe.enqueue(
		"ftms.notifications.service.dispatch_notification",
		event_name=doc.name,
		queue="short",
		enqueue_after_commit=True,
		job_id=f"notification-{doc.name}",
		deduplicate=True,
	)
	return doc.name


def dispatch_queued_notifications():
	"""Deliver a bounded fallback batch for jobs missed by the worker."""
	for name in frappe.get_all(
		"Notification Event",
		filters={"status": "Queued"},
		pluck="name",
		limit_page_length=100,
	):
		dispatch_notification(name)
	frappe.db.commit()


def dispatch_notification(event_name):
	frappe.db.sql(
		"SELECT name FROM `tabNotification Event` WHERE name=%s FOR UPDATE",
		event_name,
	)
	doc = frappe.get_doc("Notification Event", event_name)
	if doc.status != "Queued":
		return
	doc.attempt_count = int(doc.attempt_count or 0) + 1
	try:
		if doc.channel == "In App":
			pass
		elif doc.channel == "Email":
			email = frappe.db.get_value("User", doc.recipient_user, "email")
			if not email:
				raise ValueError("Recipient has no email address")
			frappe.sendmail(recipients=[email], subject=doc.title, message=doc.message)
		elif doc.channel == "FCM":
			from ftms.notifications.fcm import send_to_user

			result = send_to_user(
				doc.recipient_user,
				doc.title,
				doc.message,
				{"event_type": doc.event_type, "reference_doctype": doc.reference_doctype, "reference_name": doc.reference_name},
				failed_only=doc.attempt_count > 1,
			)
			if not result.get("configured"):
				raise RuntimeError("Firebase service account is not configured")
			if not result.get("tokens"):
				raise RuntimeError("Recipient has no active push token")
			if result.get("failed"):
				raise RuntimeError(result.get("error") or "Push delivery failed")
		else:
			raise RuntimeError(f"Unsupported notification channel: {doc.channel}")
		doc.status = "Sent"
		doc.sent_at = now_datetime()
		doc.next_retry_at = None
		doc.error_message = None
		doc.save(ignore_permissions=True)
	except Exception as exc:
		doc.status = "Failed"
		doc.error_message = str(exc)[:500]
		doc.next_retry_at = add_to_date(now_datetime(), minutes=min(2 ** int(doc.attempt_count or 1), 60))
		doc.save(ignore_permissions=True)
		frappe.log_error(frappe.get_traceback(), f"Notification delivery failed: {event_name}")
