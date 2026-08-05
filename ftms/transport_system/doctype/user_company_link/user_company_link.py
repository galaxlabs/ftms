from frappe.model.document import Document

from ftms.user_roles import assign_business_role, remove_business_role_if_unused


class UserCompanyLink(Document):
	def after_insert(self):
		self._sync_user_role()

	def on_update(self):
		self._sync_user_role()

	def _sync_user_role(self):
		if self.status == "Active" and self.user and self.role:
			assign_business_role(self.user, self.role, onboarded=True)
		previous = self.get_doc_before_save()
		if previous and (
			previous.user != self.user
			or previous.role != self.role
			or (previous.status == "Active" and self.status != "Active")
		):
			remove_business_role_if_unused(previous.user, previous.role)
