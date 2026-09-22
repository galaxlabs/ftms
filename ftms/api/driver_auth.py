from __future__ import annotations

import hashlib
import re

import frappe
from frappe import _
from frappe.utils import validate_email_address
from frappe.utils.password_strength import test_password_strength

from ftms.security import rate_limit
from ftms.user_roles import assign_business_role


def normalize_email(email):
	email = (email or "").strip().lower()
	if not email or not validate_email_address(email):
		raise ValueError("A valid email is required")
	return email


def normalize_mobile(mobile_no):
	digits = re.sub(r"\D", "", str(mobile_no or ""))
	if digits.startswith("966"):
		digits = digits[3:]
	if digits.startswith("0"):
		digits = digits[1:]
	if not re.fullmatch(r"5\d{8}", digits):
		raise ValueError("A valid Saudi mobile number is required")
	return f"+966{digits}"


def validate_signup_values(email, password, confirm_password, full_name, mobile_no):
	email = normalize_email(email)
	full_name = re.sub(r"\s+", " ", (full_name or "").strip())
	if len(full_name) < 2 or len(full_name) > 140:
		raise ValueError("Full name must be between 2 and 140 characters")
	mobile_no = normalize_mobile(mobile_no)
	if not password:
		raise ValueError("Password is required")
	if password != confirm_password:
		raise ValueError("Password and confirm password do not match")
	return email, full_name, mobile_no


def _rate_limit_signup(email):
	rate_limit("signup_driver_ip", limit=5, seconds=3600)
	rate_limit(
		"signup_driver_email",
		limit=5,
		seconds=3600,
		identity=hashlib.sha256(email.encode("utf-8")).hexdigest(),
	)
	device_id = (frappe.get_request_header("X-Device-ID") or "").strip()
	if device_id:
		rate_limit(
			"signup_driver_device",
			limit=5,
			seconds=3600,
			identity=hashlib.sha256(device_id.encode("utf-8")).hexdigest(),
		)


def _identity_exists(email, mobile_no):
	return bool(
		frappe.db.exists("User", email)
		or frappe.db.exists("User", {"mobile_no": mobile_no})
		or frappe.db.exists("Captain Profile", {"mobile_no": mobile_no})
	)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def signup_driver(email, password, confirm_password, full_name, mobile_no):
	try:
		email, full_name, mobile_no = validate_signup_values(
			email, password, confirm_password, full_name, mobile_no
		)
	except ValueError as exc:
		frappe.throw(_(str(exc)))
	_rate_limit_signup(email)
	if _identity_exists(email, mobile_no):
		frappe.throw(_("An account with these details cannot be created"))

	if len(password) > 128:
		frappe.throw(_("Password exceeds the maximum allowed length"))
	if frappe.get_system_settings("enable_password_policy"):
		strength = test_password_strength(password, user_inputs=[email, full_name, mobile_no])
		minimum_score = int(frappe.get_system_settings("minimum_password_score") or 2)
		if not strength.get("score") or strength["score"] < minimum_score:
			frappe.throw(_("Password does not meet the configured password policy"))
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": full_name,
			"mobile_no": mobile_no,
			"enabled": 1,
			"user_type": "System User",
			"send_welcome_email": 0,
			"new_password": password,
		}
	)
	try:
		user.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		frappe.throw(_("An account with these details cannot be created"))
	assign_business_role(email, "Captain", onboarded=False)
	assign_business_role(email, "Driver", onboarded=False)
	profile = frappe.get_doc(
		{
			"doctype": "Captain Profile",
			"user": email,
			"full_name": full_name,
			"mobile_no": mobile_no,
			"status": "Pending",
			"verification_status": "Incomplete",
		}
	)
	profile.insert(ignore_permissions=True)
	roles = sorted({row.role for row in frappe.get_doc("User", email).roles} & {"Captain", "Driver"})
	frappe.db.commit()
	return {
		"status": "success",
		"user": {"email": email, "full_name": full_name, "mobile_no": mobile_no, "user_type": "System User"},
		"profile": {
			"name": profile.name,
			"status": profile.status,
			"verification_status": profile.verification_status,
		},
		"roles": roles,
	}
