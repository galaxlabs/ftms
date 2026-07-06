import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class EmployeeTransportContract(Document):
	def validate(self):
		pass

	@frappe.whitelist()
	def generate_trip(self):
		if not self.is_active:
			frappe.throw("Cannot generate trip from an inactive contract")

		active_rows = [r for r in self.employees if r.is_active]
		if not active_rows:
			frappe.throw("No active passengers/employees in this contract")

		trip = frappe.new_doc("Trip")
		trip.trip_title = f"{self.route} - {self.shift_type} - {now_datetime().strftime('%Y-%m-%d')}"
		trip.route = self.route
		trip.trip_value = self.fixed_rate
		trip.transport_contract = self.name

		for row in active_rows:
			passenger = trip.append("passengers", {})
			if row.employee:
				passenger.passenger_name = row.employee
			else:
				passenger.passenger_name = row.passenger_name

		trip.passenger_count = len(active_rows)
		trip.insert(ignore_permissions=True)

		self.db_set("last_trip_generated", now_datetime())

		frappe.msgprint(f"Trip {trip.name} generated successfully")
		return trip.name
