from __future__ import annotations

import json
import time

import frappe
from frappe import _


def _client_ip():
    forwarded = frappe.get_request_header("X-Forwarded-For") or ""
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return getattr(frappe.local, "request_ip", None) or "unknown"


def rate_limit(scope, *, limit=30, seconds=60, identity=None):
    """Small fixed-window limiter for public endpoints."""
    identity = identity or _client_ip()
    key = f"ftms:rate_limit:{scope}:{identity}"
    now = int(time.time())
    cache = frappe.cache()
    raw = cache.get_value(key)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        bucket = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        bucket = {}

    reset_at = int(bucket.get("reset_at") or now + seconds)
    count = int(bucket.get("count") or 0)
    if now >= reset_at:
        reset_at = now + seconds
        count = 0
    if count >= limit:
        frappe.throw(_("Too many requests. Please try again later."), frappe.PermissionError)

    cache.set_value(
        key,
        json.dumps({"count": count + 1, "reset_at": reset_at}),
        expires_in_sec=max(reset_at - now, 1),
    )
