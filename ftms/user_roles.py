from __future__ import annotations

import frappe


BUSINESS_ROLES = {
	"Accountant",
	"Captain",
	"Company Admin",
	"Customer Company",
	"Dispatcher",
	"Partner",
	"Passenger",
	"Viewer",
}

DESK_ROLES = BUSINESS_ROLES - {"Passenger"}


def ensure_role(role):
	if role not in BUSINESS_ROLES:
		frappe.throw(f"Unsupported FTMS role: {role}")
	if not frappe.db.exists("Role", role):
		frappe.get_doc({
			"doctype": "Role",
			"role_name": role,
			"desk_access": int(role in DESK_ROLES),
		}).insert(ignore_permissions=True)


def assign_business_role(user, role, onboarded=None, replace=False):
	"""Assign an FTMS business role without misusing Frappe's User Type link."""
	if not user or user == "Guest":
		return
	ensure_role(role)
	user_type = "System User" if role in DESK_ROLES else "Website User"
	frappe.db.set_value("User", user, "user_type", user_type, update_modified=False)
	user_doc = frappe.get_doc("User", user)
	if replace:
		user_doc.roles = [
			row for row in user_doc.roles
			if row.role not in BUSINESS_ROLES or row.role == role
		]
	if role not in {row.role for row in user_doc.roles}:
		user_doc.append("roles", {"role": role})
	if onboarded is not None:
		user_doc.onboarded = int(bool(onboarded))
	user_doc.save(ignore_permissions=True)


def remove_business_role_if_unused(user, role):
	if not user or role not in BUSINESS_ROLES:
		return
	if frappe.db.exists(
		"User Company Link",
		{"user": user, "role": role, "status": "Active"},
	):
		return
	if role == "Captain" and frappe.db.exists("Captain Profile", {"user": user}):
		return
	if role == "Partner" and frappe.db.exists("Partner Profile", {"user": user}):
		return
	user_doc = frappe.get_doc("User", user)
	user_doc.roles = [row for row in user_doc.roles if row.role != role]
	remaining_roles = {row.role for row in user_doc.roles}
	has_desk_role = bool(
		frappe.get_all(
			"Role",
			filters={"name": ("in", tuple(remaining_roles)), "desk_access": 1},
			limit_page_length=1,
		)
	) if remaining_roles else False
	user_doc.user_type = "System User" if has_desk_role else "Website User"
	user_doc.save(ignore_permissions=True)


def get_business_role(user):
	roles = set(frappe.get_roles(user)) & BUSINESS_ROLES
	for preferred in (
		"Captain",
		"Partner",
		"Customer Company",
		"Company Admin",
		"Dispatcher",
		"Accountant",
		"Passenger",
		"Viewer",
	):
		if preferred in roles:
			return preferred
	return None
