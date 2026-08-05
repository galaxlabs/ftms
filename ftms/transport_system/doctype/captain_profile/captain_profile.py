import frappe
from frappe.model.document import Document


class CaptainProfile(Document):
	def _can_change_approval_status(self):
		if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
			return True
		if not self.current_company:
			return False
		link = frappe.db.get_value(
			"User Company Link",
			{"user": frappe.session.user, "company": self.current_company, "status": "Active"},
			["role", "is_owner"],
			as_dict=True,
		)
		return bool(link and (link.is_owner or link.role == "Company Admin"))

	def validate(self):
		status_changed = (self.is_new() and self.status != "Pending") or (
			not self.is_new() and self.has_value_changed("status")
		)
		if status_changed and not self._can_change_approval_status():
			frappe.throw("Only a System Manager or company administrator can change captain approval status", frappe.PermissionError)
		if self.user and not self.full_name:
			self.full_name = frappe.db.get_value("User", self.user, "full_name") or self.user
		if self.iqama_no and not self.national_id:
			self.national_id = self.iqama_no

	def after_insert(self):
		"""Auto-create User and Employee when a Captain Profile is created."""
		self._sync_user()
		self._sync_employee()

	def on_update(self):
		"""Sync User and Employee on every save."""
		self._sync_user()
		self._sync_employee()

	def _sync_user(self):
		"""Create or update the linked User record based on this Captain Profile."""
		if not self.user:
			return
		if frappe.db.exists("User", self.user):
			user_doc = frappe.get_doc("User", self.user)
		else:
			user_doc = frappe.get_doc({
				"doctype": "User",
				"email": self.user,
				"first_name": self.full_name or self.user,
				"enabled": 1,
				"user_type": "System User",
				"send_welcome_email": 0,
			})

		changed = False
		if self.full_name and user_doc.first_name != self.full_name:
			user_doc.first_name = self.full_name
			changed = True
		if self.mobile_no and user_doc.mobile_no != self.mobile_no:
			user_doc.mobile_no = self.mobile_no
			changed = True

		has_captain = frappe.db.exists("Has Role", {"parent": self.user, "role": "Captain"})
		if not has_captain:
			user_doc.add_roles("Captain")
			changed = True

		if changed or user_doc.is_new():
			user_doc.save(ignore_permissions=True)

	def _sync_employee(self):
		"""Create or update an Employee record for this captain."""
		if not self.user or not self.full_name:
			return
		existing = frappe.db.get_value("Employee", {"email": self.user}, "name")
		if existing:
			emp = frappe.get_doc("Employee", existing)
		else:
			emp = frappe.get_doc({
				"doctype": "Employee",
				"email": self.user,
				"employee_name": self.full_name,
				"status": "Active" if self.status == "Active" else "Inactive",
				"enabled": 1,
				"is_employee": 1,
			})

		changed = False
		if self.full_name and emp.employee_name != self.full_name:
			emp.employee_name = self.full_name
			changed = True
		if self.mobile_no and emp.mobile_no != self.mobile_no:
			emp.mobile_no = self.mobile_no
			changed = True
		if self.nationality and emp.nationality != self.nationality:
			emp.nationality = self.nationality
			changed = True
		if self.status == "Active" and emp.status != "Active":
			emp.status = "Active"
			emp.enabled = 1
			changed = True
		elif self.status != "Active" and emp.status == "Active":
			emp.status = "Inactive"
			emp.enabled = 0
			changed = True

		if changed or emp.is_new():
			emp.flags.ignore_mandatory = True
			emp.save(ignore_permissions=True)
