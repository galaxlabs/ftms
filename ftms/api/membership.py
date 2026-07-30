from __future__ import annotations

import hashlib
import secrets

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime

from ftms.notifications.service import emit_event
from ftms.tenant import has_company_access, resolve_company


ADMIN_ROLES = {"Company Admin"}


def _require_company_admin(company, user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return
	if not has_company_access(company, user=user):
		frappe.throw(_("You are not permitted for this company"), frappe.PermissionError)
	link = frappe.db.get_value(
		"User Company Link",
		{"user": user, "company": company, "status": "Active"},
		["role", "is_owner"],
		as_dict=True,
	)
	if not link or (link.role not in ADMIN_ROLES and not link.is_owner):
		frappe.throw(_("Only a company owner or admin can manage memberships"), frappe.PermissionError)


def _token_hash(token):
	return hashlib.sha256(token.encode("utf-8")).hexdigest()


@frappe.whitelist()
def invite_member(company, invited_email, role, expires_in_hours=72):
	user = frappe.session.user
	_require_company_admin(company, user=user)
	if role not in {"Dispatcher", "Captain", "Passenger", "Accountant", "Viewer"}:
		frappe.throw(_("Invalid invitation role"))
	if frappe.db.exists("User", {"email": invited_email}):
		invited_user = frappe.db.get_value("User", {"email": invited_email}, "name")
	else:
		invited_user = None
	token = secrets.token_urlsafe(32)
	invitation = frappe.get_doc({
		"doctype": "Company Invitation",
		"company": company,
		"invited_email": invited_email,
		"invited_user": invited_user,
		"role": role,
		"token_hash": _token_hash(token),
		"expires_at": add_to_date(now_datetime(), hours=max(1, min(float(expires_in_hours or 72), 720))),
		"status": "Invited",
		"invited_by": user,
		"invited_at": now_datetime(),
	})
	invitation.insert(ignore_permissions=True)
	emit_event("Membership Invitation", invited_user, "Company invitation", f"You were invited to join {company}.", company=company, reference_doctype="Company Invitation", reference_name=invitation.name, dedupe_key=f"membership-invite:{invitation.name}")
	return {"invitation": invitation.name, "token": token, "expires_at": invitation.expires_at}


@frappe.whitelist()
def accept_invitation(token):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	invitation = frappe.db.get_value("Company Invitation", {"token_hash": _token_hash(token)}, "name")
	if not invitation:
		frappe.throw(_("Invitation is invalid or expired"), frappe.PermissionError)
	doc = frappe.get_doc("Company Invitation", invitation)
	if doc.status != "Invited" or doc.expires_at < now_datetime():
		if doc.status == "Invited":
			doc.db_set("status", "Expired")
		frappe.throw(_("Invitation is invalid or expired"), frappe.PermissionError)
	user_email = frappe.db.get_value("User", user, "email")
	if user_email and user_email.casefold() != doc.invited_email.casefold():
		frappe.throw(_("This invitation was issued to another email address"), frappe.PermissionError)
	link = frappe.db.get_value("User Company Link", {"user": user, "company": doc.company}, "name")
	if link:
		link_doc = frappe.get_doc("User Company Link", link)
		link_doc.role = doc.role
		link_doc.status = "Pending"
		link_doc.joined_via = "Invite"
		link_doc.save(ignore_permissions=True)
	else:
		link_doc = frappe.get_doc({
			"doctype": "User Company Link",
			"link_code": f"{doc.company}-{user}-{secrets.token_hex(4)}",
			"user": user,
			"company": doc.company,
			"role": doc.role,
			"joined_via": "Invite",
			"status": "Pending",
		})
		link_doc.insert(ignore_permissions=True)
	doc.status = "Accepted"
	doc.accepted_by = user
	doc.accepted_at = now_datetime()
	doc.save(ignore_permissions=True)
	return {"invitation": doc.name, "membership": link_doc.name, "status": link_doc.status}


@frappe.whitelist()
def approve_membership(link_name):
	user = frappe.session.user
	link = frappe.get_doc("User Company Link", link_name)
	_require_company_admin(link.company, user=user)
	if link.status != "Pending":
		frappe.throw(_("Membership is not pending"))
	link.status = "Active"
	link.approved_by = user
	link.approved_on = now_datetime()
	link.save(ignore_permissions=True)
	emit_event("Membership Approved", link.user, "Company membership approved", f"Your membership in {link.company} is active.", company=link.company, reference_doctype="User Company Link", reference_name=link.name, dedupe_key=f"membership-approved:{link.name}")
	return {"name": link.name, "status": link.status}


@frappe.whitelist()
def revoke_membership(link_name):
	user = frappe.session.user
	link = frappe.get_doc("User Company Link", link_name)
	_require_company_admin(link.company, user=user)
	if link.is_owner:
		frappe.throw(_("The company owner cannot be revoked"))
	link.status = "Revoked"
	link.save(ignore_permissions=True)
	return {"name": link.name, "status": link.status}


@frappe.whitelist()
def list_memberships(company=None, status=None, limit=100):
	company = resolve_company(company=company)
	_require_company_admin(company)
	filters = {"company": company}
	if status:
		filters["status"] = status
	return frappe.get_all("User Company Link", filters=filters, fields=["name", "user", "company", "role", "is_owner", "joined_via", "status", "approved_by", "approved_on"], order_by="modified desc", limit_page_length=int(limit))
