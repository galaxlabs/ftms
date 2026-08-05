from __future__ import annotations

import frappe
from frappe.utils import add_days, now_datetime


def expire_company_invitations():
    names = frappe.get_all(
        "Company Invitation",
        filters={"status": "Invited", "expires_at": ("<", now_datetime())},
        pluck="name",
        limit_page_length=500,
    )
    for name in names:
        frappe.db.set_value("Company Invitation", name, "status", "Expired", update_modified=False)
    return len(names)


def retry_failed_notifications():
    """Retry a bounded batch of external notification deliveries."""
    retryable = frappe.get_all(
        "Notification Event",
        filters={
            "status": "Failed",
            "channel": ("in", ("Email", "FCM")),
            "attempt_count": ("<", 3),
            "next_retry_at": ("<=", now_datetime()),
        },
        pluck="name",
        order_by="modified asc",
        limit_page_length=50,
    )
    for name in retryable:
        frappe.db.set_value(
            "Notification Event",
            name,
            {"status": "Queued", "error_message": None, "next_retry_at": None},
            update_modified=False,
        )
    if retryable:
        from ftms.notifications.service import dispatch_notification

        for name in retryable:
            frappe.enqueue(
                dispatch_notification,
                event_name=name,
                queue="short",
                enqueue_after_commit=True,
                job_id=f"notification-retry-{name}",
                deduplicate=True,
            )
    return len(retryable)


def cleanup_old_notifications(days=90):
    cutoff = add_days(now_datetime(), -abs(int(days)))
    return frappe.db.delete(
        "Notification Event",
        {"status": ("in", ("Sent", "Read")), "modified": ("<", cutoff)},
    )
