from __future__ import annotations

import frappe
from frappe import _


def _client_ip():
	return getattr(frappe.local, "request_ip", None) or "unknown"


def rate_limit(scope, *, limit=30, seconds=60, identity=None):
	"""Atomic, site-scoped fixed-window limiter for public endpoints."""
	identity = identity or _client_ip()
	cache = frappe.cache()
	key = cache.make_key(f"ftms:rate_limit:{scope}:{identity}")
	count = cache.eval(
		"""
		local count = redis.call('INCR', KEYS[1])
		if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
		return count
		""",
		1,
		key,
		seconds,
	)
	if int(count) > limit:
		frappe.throw(_("Too many requests. Please try again later."), frappe.RateLimitExceededError)
