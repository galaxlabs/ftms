import frappe
from frappe.model.document import Document


def _default_domain():
	"""Fallback Transportation Domain for auto-created companies."""
	d = frappe.db.get_single_value("Transport Settings", "default_domain") or frappe.db.exists("Transportation Domain", "FTMS")
	return d or "FTMS"


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
		"""Auto-create User, Company, and Employee when a Captain Profile is created."""
		self._sync_user()
		self._sync_company()
		self._sync_employee()

	def on_update(self):
		"""Sync User, Company, and Employee on every save."""
		self._sync_user()
		self._sync_company()
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

	def _sync_company(self):
		"""Auto-create a Company from captain's company_name + company_tax_id + company_name_ar.
		If the company already exists (by tax_id or name), link to it.
		"""
		if not self.company_name or not self.company_tax_id:
			return

		# Check if company exists by tax_id or name
		existing = None
		if self.company_tax_id:
			existing = frappe.db.exists("Company", {"tax_id": self.company_tax_id})
		if not existing and self.company_name:
			existing = frappe.db.exists("Company", {"company_name": self.company_name})

		if existing:
			company_name = existing
		else:
			code = (self.company_tax_id or self.company_name or "NEW")[:8].upper().replace(" ", "")
			doc = frappe.get_doc({
				"doctype": "Company",
				"company_name": self.company_name,
				"company_code": code,
				"tax_id": self.company_tax_id,
				"company_name_ar": self.company_name_ar,
				"domain": _default_domain(),
				"owner_user": self.user,
				"status": "Active",
				"customer_enabled": 1,
			})
			doc.flags.ignore_mandatory = True
			doc.insert(ignore_permissions=True)
			company_name = doc.name

		if self.current_company != company_name:
			self.db_set("current_company", company_name)

	def _sync_employee(self):
		"""Create or update an Employee record for this captain.
		Skips if no company is assigned on the Captain Profile.
		"""
		if not self.user or not self.full_name:
			return
		if not self.current_company:
			return

		existing = frappe.db.get_value("Employee", {"email": self.user}, "name")
		if existing:
			emp = frappe.get_doc("Employee", existing)
		else:
			emp = frappe.get_doc({
				"doctype": "Employee",
				"email": self.user,
				"employee_name": self.full_name,
				"company": self.current_company,
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
		if self.current_company and emp.company != self.current_company:
			emp.company = self.current_company
			changed = True

		if changed or emp.is_new():
			emp.flags.ignore_mandatory = True
			emp.save(ignore_permissions=True)
