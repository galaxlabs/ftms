from __future__ import annotations

import hashlib
import re

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, today

from ftms.document_ai.openai_vision import DocumentAIProviderError, extract_image
from ftms.document_ai.service import _image_from_data_url
from ftms.document_ai.service import _settings as _ai_settings
from ftms.security import rate_limit

DOCTYPE = "User Subscription"

RECEIPT_SCHEMA = {
	"type": "object",
	"additionalProperties": False,
	"properties": {
		"amount": {"type": ["number", "null"]},
		"currency": {"type": ["string", "null"]},
		"payment_date": {"type": ["string", "null"]},
		"payer_name": {"type": ["string", "null"]},
		"account_no": {"type": ["string", "null"]},
		"bank_name": {"type": ["string", "null"]},
		"payment_method": {"type": ["string", "null"]},
		"reference_no": {"type": ["string", "null"]},
		"receiver_name": {"type": ["string", "null"]},
		"receiver_account": {"type": ["string", "null"]},
		"confidence": {"type": ["number", "null"]},
	},
	"required": [
		"amount", "currency", "payment_date", "payer_name", "account_no", "bank_name",
		"payment_method", "reference_no", "receiver_name", "receiver_account", "confidence",
	],
}

RECEIPT_PROMPT = (
	"You read a payment receipt or transfer screenshot (bank app, EasyPaisa or similar) "
	"for a transport subscription. Return only the requested fields. Use YYYY-MM-DD for dates. "
	"Copy the payer name, sender account or wallet number, receiver account and reference number "
	"exactly as shown. Use null for anything not visible. confidence is between 0 and 1."
)


def _tokens(value):
	return {t for t in re.sub(r"[^a-zA-Z0-9 ]", " ", str(value or "").lower()).split() if len(t) > 2}


def _account_key(value):
	key = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
	if key.startswith("0092"):
		key = key[4:]
	if key.startswith("92") and len(key) == 12:
		key = "0" + key[2:]
	return key


def _lines(value):
	return [part.strip() for part in re.split(r"[\n,;]+", str(value or "")) if part.strip()]


def evaluate_receipt(data, *, expected_amount, holder_name, whitelisted_accounts, used_references,
		receiver_accounts, min_confidence):
	"""Return the reasons a receipt cannot be approved automatically. Empty list means approve."""
	issues = []
	amount = flt(data.get("amount"))
	if amount <= 0:
		issues.append("amount not readable")
	elif amount + 0.01 < flt(expected_amount):
		issues.append("amount below due")

	holder_tokens = _tokens(holder_name)
	payer_tokens = _tokens(data.get("payer_name"))
	if not payer_tokens:
		issues.append("payer name not readable")
	else:
		needed = 2 if len(holder_tokens) >= 2 else 1
		if len(holder_tokens & payer_tokens) < needed:
			issues.append("payer name does not match account holder")

	account = _account_key(data.get("account_no"))
	whitelist = {_account_key(a) for a in whitelisted_accounts if a}
	if not account:
		issues.append("sender account not readable")
	elif whitelist and account not in whitelist:
		issues.append("sender account is not registered for this user")

	reference = str(data.get("reference_no") or "").strip().upper()
	if not reference:
		issues.append("reference not readable")
	elif reference in {str(r).strip().upper() for r in used_references if r}:
		issues.append("reference already used")

	if receiver_accounts:
		allowed = {_account_key(a) for a in receiver_accounts if a}
		if _account_key(data.get("receiver_account")) not in allowed:
			issues.append("receiver account does not match company account")

	if flt(data.get("confidence")) < flt(min_confidence):
		issues.append("low AI confidence")
	return issues


def _require_user():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)
	return user


def _unpaid_period(user):
	names = frappe.get_all(DOCTYPE, filters={"user": user}, pluck="name", order_by="modified desc", limit=1)
	if not names:
		return None, None
	sub = frappe.get_doc(DOCTYPE, names[0])
	period = next((p for p in sub.periods if not p.paid), None)
	return sub, period


def _used_references():
	return frappe.get_all(
		"Subscription Period",
		filters={"receipt_reference": ["is", "set"]},
		pluck="receipt_reference",
	)


def _user_accounts(user):
	return _lines(frappe.db.get_value("User", user, "ftms_payment_accounts") or "")


def _save_user_accounts(user, accounts):
	frappe.db.set_value(
		"User", user, "ftms_payment_accounts", "\n".join(sorted(set(accounts))), update_modified=False
	)


def _receiver_accounts():
	return _lines(frappe.db.get_single_value("Integration Settings", "payment_receiver_accounts") or "")


def _file_name(file_name, mime_type):
	name = (file_name or "payment-receipt").strip() or "payment-receipt"
	if "." not in name:
		name += {"image/png": ".png", "image/webp": ".webp"}.get(mime_type, ".jpg")
	return name


@frappe.whitelist()
def upload_receipt(file_data=None, file_name=None, receipt_note=None):
	"""Upload a payment screenshot for the current unpaid period. AI reads and matches it;
	a clean match activates the subscription without manual approval."""
	user = _require_user()
	rate_limit("subscription_receipt_user", limit=10, seconds=3600, identity=user)
	sub, period = _unpaid_period(user)
	if not sub or not period:
		frappe.throw(_("No unpaid subscription period found"))
	if not file_data:
		frappe.throw(_("Receipt file is required"))

	settings = _ai_settings()
	content, mime_type = _image_from_data_url(file_data, max_file_bytes=settings["max_file_bytes"])
	file_hash = hashlib.sha256(content).hexdigest()
	rate_limit("subscription_receipt_file", limit=3, seconds=3600, identity=f"{user}:{file_hash}")

	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": _file_name(file_name, mime_type),
		"content": content,
		"attached_to_doctype": DOCTYPE,
		"attached_to_name": sub.name,
		"is_private": 1,
	}).insert(ignore_permissions=True)

	period.receipt = file_doc.file_url
	period.receipt_uploaded_on = now_datetime()
	period.receipt_note = receipt_note or ""
	period.receipt_status = "Receipt Uploaded"

	try:
		data = extract_image(
			api_key=settings["api_key"],
			model=settings["model"],
			prompt=RECEIPT_PROMPT,
			schema=RECEIPT_SCHEMA,
			command="extract_subscription_receipt",
			image_bytes=content,
			mime_type=mime_type,
			timeout=settings["timeout"],
		)
	except (DocumentAIProviderError, ValueError) as exc:
		period.receipt_status = "Needs Review"
		period.receipt_match_note = f"AI reading failed: {str(exc)[:200]}"
		sub.save(ignore_permissions=True)
		return {"status": period.receipt_status, "issues": [period.receipt_match_note], "period": period.name}

	holder = frappe.db.get_value("User", user, "full_name") or user
	issues = evaluate_receipt(
		data,
		expected_amount=period.amount,
		holder_name=holder,
		whitelisted_accounts=_user_accounts(user),
		used_references=_used_references(),
		receiver_accounts=_receiver_accounts(),
		min_confidence=settings["review_confidence"],
	)

	period.receipt_ai_json = frappe.as_json(data)
	period.receipt_amount = flt(data.get("amount"))
	period.receipt_payer_name = data.get("payer_name") or ""
	period.receipt_account_no = data.get("account_no") or ""
	period.receipt_reference = str(data.get("reference_no") or "").strip()
	period.receipt_payment_method = data.get("payment_method") or ""
	period.receipt_match_note = ", ".join(issues) if issues else "Matched: amount, payer name, account, reference"

	if issues:
		period.receipt_status = "Needs Review"
		sub.save(ignore_permissions=True)
		return {"status": period.receipt_status, "issues": issues, "period": period.name}

	account = _account_key(data.get("account_no"))
	known = _user_accounts(user)
	if account and account not in {_account_key(a) for a in known}:
		_save_user_accounts(user, known + [account])

	period.receipt_status = "Auto Approved"
	sub.save(ignore_permissions=True)
	if sub.status in ("Overdue", "Read Only"):
		sub.status = "Overdue"
		sub.save(ignore_permissions=True)
		sub.mark_paid()
	else:
		period.paid = 1
		period.payment_date = today()
		sub.last_payment_date = today()
		sub.save(ignore_permissions=True)
	return {"status": period.receipt_status, "issues": [], "period": period.name}


@frappe.whitelist()
def get_receipt_status():
	user = _require_user()
	_, period = _unpaid_period(user)
	if not period:
		return {"status": "none"}
	return {
		"period": period.name,
		"amount_due": flt(period.amount),
		"receipt_status": period.receipt_status or "",
		"match_note": period.receipt_match_note or "",
		"receipt_uploaded_on": str(period.receipt_uploaded_on or ""),
	}
