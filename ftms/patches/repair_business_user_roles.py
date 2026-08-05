import frappe

from ftms.user_roles import BUSINESS_ROLES, assign_business_role


LEGACY_SELF_SELECTED_ROLES = ("Captain", "Customer Company", "Partner", "Passenger")


def execute():
	assignments = {}
	for row in frappe.get_all(
		"User Company Link",
		filters={"status": "Active", "role": ("in", tuple(BUSINESS_ROLES))},
		fields=["user", "role"],
	):
		if row.user:
			assignments.setdefault(row.user, set()).add(row.role)

	for row in frappe.get_all(
		"User",
		filters={"user_type": ("in", LEGACY_SELF_SELECTED_ROLES)},
		fields=["name", "user_type"],
	):
		assignments.setdefault(row.name, set()).add(row.user_type)

	for user, roles in assignments.items():
		for role in roles:
			assign_business_role(user, role)
