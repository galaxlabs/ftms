from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


def _is_manager(user):
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def get_permission_query_conditions(user):
	if _is_manager(user):
		return ""
	return f"`tabDocument Extraction`.`requested_by` = {frappe.db.escape(user)}"


def has_permission(doc, ptype, user):
	if _is_manager(user):
		return True
	return doc.requested_by == user and ptype in ("read", "create")


class DocumentExtraction(Document):
	def before_insert(self):
		if not _is_manager(frappe.session.user):
			self.requested_by = frappe.session.user
		self.requested_by = self.requested_by or frappe.session.user
		self.requested_on = self.requested_on or now_datetime()
		if not _is_manager(frappe.session.user) and not self.flags.document_ai_service:
			action = __import__("ftms.document_ai.registry", fromlist=["get_action"]).get_action(
				self.attachment_action_id
			)
			self.command = action.command
			self.prompt_version = action.prompt_version
			self.status = "Queued"
			for fieldname in (
				"comparison_status", "model_provider", "model_name", "raw_result_json",
				"normalized_result_json", "comparisons_json", "warnings_json", "corrections_json",
				"confirmed_by", "confirmed_on", "reviewer", "reviewed_on", "failure_reason",
			):
				self.set(fieldname, None)

	def validate(self):
		from ftms.document_ai.registry import get_action

		action = get_action(self.attachment_action_id)
		if self.command != action.command or int(self.prompt_version or 0) != action.prompt_version:
			frappe.throw("Document extraction command or prompt version does not match the action")
		if self.target_doctype not in action.target_doctypes:
			frappe.throw("Document extraction target is not allowed for this action")
		previous = self.get_doc_before_save()
		if previous:
			for fieldname in (
				"attachment_action_id", "command", "prompt_version", "file", "file_url", "file_hash",
				"target_doctype", "target_name", "requested_by", "requested_on",
			):
				if self.has_value_changed(fieldname):
					frappe.throw(f"Document extraction audit field {fieldname} cannot be changed")
