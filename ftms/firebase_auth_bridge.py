from __future__ import annotations

import json
import hashlib
import time
import urllib.error
import urllib.request

import frappe
from google.auth import jwt
from google.auth.transport.requests import Request
from google.oauth2 import id_token as google_id_token
from google.oauth2 import service_account


FIREBASE_AUDIENCE = (
	"https://identitytoolkit.googleapis.com/google.identity.identitytoolkit.v1.IdentityToolkit"
)


def create_custom_token(user):
	credentials, project_id = _credentials()
	uid = _firebase_uid(user, credentials, project_id)
	now = int(time.time())
	payload = {
		"iss": credentials.service_account_email,
		"sub": credentials.service_account_email,
		"aud": FIREBASE_AUDIENCE,
		"iat": now,
		"exp": now + 3600,
		"uid": uid,
	}
	token = jwt.encode(
		credentials.signer,
		payload,
		key_id=getattr(credentials.signer, "key_id", None),
	)
	return token.decode("utf-8") if isinstance(token, bytes) else token


def _allowed_firebase_project_ids():
	primary = frappe.db.get_single_value("Integration Settings", "firebase_project_id")
	extra = frappe.get_site_config().get("firebase_auth_project_ids") or []
	if isinstance(extra, str):
		extra = [extra]
	ids = []
	for pid in [primary, *extra]:
		pid = (pid or "").strip()
		if pid and pid not in ids:
			ids.append(pid)
	return ids


def verify_id_token(token):
	project_ids = _allowed_firebase_project_ids()
	if not project_ids:
		frappe.throw("Firebase project ID is not configured")
	for project_id in project_ids:
		try:
			claims = google_id_token.verify_firebase_token(token, Request(), audience=project_id)
		except ValueError:
			continue
		if (
			claims.get("aud") == project_id
			and claims.get("iss") == f"https://securetoken.google.com/{project_id}"
			and claims.get("sub")
		):
			return claims
	raise frappe.AuthenticationError("Invalid Firebase authentication token")


def _primary_project_id():
	return (frappe.db.get_single_value("Integration Settings", "firebase_project_id") or "").strip()


def _uid_map(user_name):
	if not frappe.get_meta("User").has_field("ftms_firebase_uids"):
		return {}
	raw = frappe.db.get_value("User", user_name, "ftms_firebase_uids")
	try:
		data = json.loads(raw) if raw else {}
	except ValueError:
		data = {}
	return data if isinstance(data, dict) else {}


def _uid_for_project(user_name, project_id):
	if project_id == _primary_project_id():
		return frappe.db.get_value("User", user_name, "ftms_firebase_uid")
	return _uid_map(user_name).get(project_id)


def _store_uid_for_project(user_name, project_id, uid):
	if project_id == _primary_project_id():
		frappe.db.set_value("User", user_name, "ftms_firebase_uid", uid, update_modified=False)
		return
	data = _uid_map(user_name)
	data[project_id] = uid
	frappe.db.set_value("User", user_name, "ftms_firebase_uids", json.dumps(data), update_modified=False)


def _find_user_by_uid(uid, project_id):
	if project_id == _primary_project_id():
		return frappe.db.get_value("User", {"ftms_firebase_uid": uid, "enabled": 1}, "name")
	if not frappe.get_meta("User").has_field("ftms_firebase_uids"):
		return None
	candidates = frappe.get_all(
		"User",
		filters={"enabled": 1, "ftms_firebase_uids": ["like", f'%"{uid}"%']},
		pluck="name",
		limit=20,
	)
	for name in candidates:
		if _uid_map(name).get(project_id) == uid:
			return name
	return None


def resolve_frappe_user(claims, create=False):
	uid = claims.get("sub") or claims.get("uid")
	project_id = claims.get("aud") or _primary_project_id()
	email = (claims.get("email") or "").strip().lower()
	if not uid:
		raise frappe.AuthenticationError("Firebase token has no user ID")

	mapped = _find_user_by_uid(uid, project_id)
	if mapped:
		return mapped
	phone = (claims.get("phone_number") or "").strip()
	if not email and phone and create:
		return _create_phone_user(uid, phone, project_id)
	if not email or claims.get("email_verified") is not True:
		raise frappe.AuthenticationError("Verified Firebase email is required to link this account")

	existing = frappe.db.get_value("User", {"name": email, "enabled": 1}, "name")
	if existing:
		frappe.db.sql("SELECT name FROM `tabUser` WHERE name=%s FOR UPDATE", existing)
		current_uid = _uid_for_project(existing, project_id)
		if current_uid and current_uid != uid:
			raise frappe.AuthenticationError("Firebase account does not match this Frappe user")
		_store_uid_for_project(existing, project_id, uid)
		return existing
	if not create:
		raise frappe.AuthenticationError("No enabled Frappe user matches this Firebase account")

	from frappe.utils import random_string
	from frappe.exceptions import DuplicateEntryError

	name = (claims.get("name") or "").strip()
	parts = name.split(" ", 1) if name else []
	user_fields = _project_uid_fields(uid, project_id)
	user_doc = frappe.get_doc({
		"doctype": "User",
		"email": email,
		"username": email.split("@", 1)[0],
		"first_name": parts[0][:140] if parts else email.split("@", 1)[0][:140],
		"last_name": parts[1].strip() if len(parts) > 1 else "",
		"enabled": 1,
		"send_welcome_email": 0,
		"new_password": random_string(24),
		"user_type": "Website User",
		**user_fields,
	})
	try:
		user_doc.insert(ignore_permissions=True)
	except DuplicateEntryError:
		frappe.db.rollback()
		existing = _find_user_by_uid(uid, project_id)
		if not existing:
			raise frappe.AuthenticationError("Firebase identity could not be linked")
		return existing
	return user_doc.name


def _project_uid_fields(uid, project_id):
	if project_id == _primary_project_id():
		return {"ftms_firebase_uid": uid}
	return {"ftms_firebase_uids": json.dumps({project_id: uid})}


def _create_phone_user(uid, phone, project_id):
	from frappe.exceptions import DuplicateEntryError
	from frappe.utils import random_string

	email = f"firebase-phone-{hashlib.sha256(uid.encode('utf-8')).hexdigest()[:24]}@rideksa.local"
	try:
		frappe.get_doc({
			"doctype": "User",
			"email": email,
			"first_name": phone,
			"mobile_no": phone,
			"enabled": 1,
			"send_welcome_email": 0,
			"new_password": random_string(24),
			"user_type": "Website User",
			**_project_uid_fields(uid, project_id),
		}).insert(ignore_permissions=True)
	except DuplicateEntryError:
		frappe.db.rollback()
		existing = _find_user_by_uid(uid, project_id)
		if not existing:
			raise frappe.AuthenticationError("Firebase phone identity could not be linked")
		return existing
	return email


def _credentials():
	settings = frappe.get_single("Integration Settings")
	raw = settings.get_password("firebase_service_account_json", raise_exception=False)
	if not raw:
		frappe.throw("Firebase service account is not configured")
	info = json.loads(raw)
	credentials = service_account.Credentials.from_service_account_info(
		info,
		scopes=["https://www.googleapis.com/auth/identitytoolkit"],
	)
	credentials.refresh(Request())
	project_id = settings.firebase_project_id or info.get("project_id")
	if not project_id:
		frappe.throw("Firebase project ID is not configured")
	if info.get("project_id") != project_id:
		frappe.throw("Firebase service account belongs to a different project")
	return credentials, project_id


def _firebase_uid(user, credentials, project_id):
	meta = frappe.get_meta("User")
	if meta.has_field("ftms_firebase_uid"):
		uid = frappe.db.get_value("User", user, "ftms_firebase_uid")
		if uid:
			return uid

	uid = _lookup_firebase_uid(user, credentials, project_id)
	if not uid:
		uid = _create_firebase_user(user, credentials, project_id)
	if meta.has_field("ftms_firebase_uid"):
		frappe.db.set_value("User", user, "ftms_firebase_uid", uid, update_modified=False)
	return uid


def _lookup_firebase_uid(user, credentials, project_id):
	request = urllib.request.Request(
		f"https://identitytoolkit.googleapis.com/v1/projects/{project_id}/accounts:lookup",
		data=json.dumps({"email": [user]}).encode("utf-8"),
		method="POST",
		headers={
			"Authorization": f"Bearer {credentials.token}",
			"Content-Type": "application/json",
		},
	)
	with urllib.request.urlopen(request, timeout=20) as response:
		result = json.loads(response.read().decode("utf-8"))
	users = result.get("users") or []
	if users and users[0].get("localId"):
		return users[0]["localId"]
	return None


def backfill_firebase_uids():
	settings = frappe.get_single("Integration Settings")
	if not settings.get_password("firebase_service_account_json", raise_exception=False):
		return 0
	credentials, project_id = _credentials()
	updated = 0
	for user in frappe.get_all(
		"User",
		filters={"enabled": 1, "ftms_firebase_uid": ("is", "not set")},
		pluck="name",
	):
		if "@" not in user:
			continue
		uid = _lookup_firebase_uid(user, credentials, project_id)
		if uid:
			frappe.db.set_value("User", user, "ftms_firebase_uid", uid, update_modified=False)
			updated += 1
	return updated


def _create_firebase_user(user, credentials, project_id):
	uid = "ftms_" + hashlib.sha256(user.encode("utf-8")).hexdigest()[:40]
	request = urllib.request.Request(
		f"https://identitytoolkit.googleapis.com/v1/projects/{project_id}/accounts",
		data=json.dumps({
			"localId": uid,
			"email": user,
			"emailVerified": False,
			"disabled": False,
		}).encode("utf-8"),
		method="POST",
		headers={
			"Authorization": f"Bearer {credentials.token}",
			"Content-Type": "application/json",
		},
	)
	try:
		with urllib.request.urlopen(request, timeout=20) as response:
			result = json.loads(response.read().decode("utf-8"))
	except urllib.error.HTTPError as exc:
		frappe.log_error(
			exc.read().decode("utf-8", errors="replace")[:1000],
			"Firebase user provisioning failed",
		)
		raise
	if not result.get("localId"):
		frappe.throw("Firebase did not return a user ID")
	return result["localId"]
