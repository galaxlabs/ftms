from __future__ import annotations

import hashlib
import hmac
import json
import urllib.parse

import frappe
import http.client
from frappe import _

from ftms.config.service import get_integration_settings


MOYASAR_BASE = "api.moyasar.com"
MOYASAR_VERSION = "v1"
MOYASAR_API = f"/{MOYASAR_VERSION}"


def _api_key():
	"""Moyasser secret API key for server-to-server calls."""
	return frappe.get_site_config().get("moyasser_secret_key") or ""


def _publishable_key():
	"""Moyasser client-side publishable key (passed to Flutter/WEB)."""
	return get_integration_settings().get("payment_public_key") or ""


def _webhook_secret():
	"""Webhook secret for verifying incoming callbacks."""
	return get_integration_settings(include_private=True).get("payment_webhook_secret") or ""


def create_payment(amount, currency="SAR", description=None, user=None, company=None, metadata=None):
	"""Create a Moyaaser payment invoice and return the payment URL + ID."""
	api_key = _api_key()
	if not api_key:
		frappe.throw(_("Moyasser payment gateway is not configured"))

	body = {
		"amount": int(float(amount) * 100),  # halalas
		"currency": currency or "SAR",
		"description": description or "RideKSA Wallet Top-up",
	}
	if metadata:
		body["metadata"] = metadata
	if user:
		body["metadata"] = dict(body.get("metadata") or {})
		body["metadata"]["frappe_user"] = user
	if company:
		body["metadata"] = dict(body.get("metadata") or {})
		body["metadata"]["company"] = company

	body_bytes = json.dumps(body).encode("utf-8")
	conn = http.client.HTTPSConnection(MOYASAR_BASE, timeout=30)
	conn.request(
		"POST",
		f"{MOYASAR_API}/payments",
		body=body_bytes,
		headers={
			"Authorization": _basic_auth(api_key),
			"Content-Type": "application/json",
		},
	)
	response = conn.getresponse()
	raw = response.read().decode("utf-8")
	conn.close()

	if response.status not in (200, 201):
		frappe.log_error(
			f"Moyarger create-payment {response.status}: {raw}",
			"Moyasser Payment Error",
		)
		frappe.throw(_("Failed to create payment. Please try again."))

	result = json.loads(raw)
	payment_id = result.get("id")
	payment_url = result.get("source", {}).get("transaction_url") or result.get("url") or ""
	if not payment_id:
		frappe.throw(_("No payment ID returned by Moyasser"))

	return {
		"payment_id": payment_id,
		"payment_url": payment_url,
		"amount": float(amount),
		"currency": currency,
		"status": result.get("status"),
	}


def verify_webhook_signature(raw_body, signature_header):
	"""Verify the Moyasser webhook signature using HMAC-SHA256."""
	secret = _webhook_secret()
	if not secret or not signature_header:
		return False
	expected = hmac.new(
		secret.encode("utf-8"),
		raw_body if isinstance(raw_body, bytes) else raw_body.encode("utf-8"),
		hashlib.sha256,
	).hexdigest()
	return hmac.compare_digest(expected, signature_header)


def get_payment_status(payment_id):
	"""Retrieve a payment's current status from Moyasser."""
	api_key = _api_key()
	if not api_key or not payment_id:
		return None
	conn = http.client.HTTPSConnection(MOYASAR_BASE, timeout=15)
	conn.request(
		"GET",
		f"{MOYASAR_API}/payments/{urllib.parse.quote(str(payment_id))}",
		headers={"Authorization": _basic_auth(api_key)},
	)
	response = conn.getresponse()
	raw = response.read().decode("utf-8")
	conn.close()
	if response.status != 200:
		return None
	return json.loads(raw)


def list_payment_methods():
	"""Return available payment method options for the Flutter client."""
	return {
		"provider": "moyasar",
		"currency": "SAR",
		"publishable_key": _publishable_key(),
		"methods": ["creditcard", "applepay", "mada"],
	}


def _basic_auth(api_key):
	import base64
	creds = base64.b64encode(f"{api_key}:".encode()).decode()
	return f"Basic {creds}"


def configuration():
	"""Return Moyasser client-side configuration for the Flutter app."""
	return {
		"payment_provider": "moyaser",
		"publishable_key": _publishable_key(),
		"currency": "SAR",
	}
