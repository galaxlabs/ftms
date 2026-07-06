import frappe
from frappe.model.document import Document
from frappe.utils import flt


class Trip(Document):
	def validate(self):
		self.set_trip_title()
		self.set_trip_code()
		self.update_passenger_count()
		self.update_available_seats()
		self.calculate_per_passenger_value()

	def on_update(self):
		if self.trip_status in {"Arrived", "Completed"}:
			self.auto_generate_trip_invoices()

	def set_trip_title(self):
		if not self.trip_title and self.route and self.driver:
			self.trip_title = f"{self.route} - {self.driver}"
		elif not self.trip_title and self.route:
			self.trip_title = self.route

	def set_trip_code(self):
		if not self.trip_code and self.trip_title:
			self.trip_code = self.trip_title

	def update_available_seats(self):
		if self.seat_capacity and self.passenger_count:
			self.available_seats = self.seat_capacity - self.passenger_count
		elif self.seat_capacity:
			self.available_seats = self.seat_capacity

	def update_passenger_count(self):
		self.passenger_count = len(self.passengers or [])

	def calculate_per_passenger_value(self):
		count = len(self.passengers or [])
		if count > 0 and flt(self.trip_value):
			self.per_passenger_value = flt(self.trip_value) / count
		elif count == 0:
			self.per_passenger_value = 0

	def auto_generate_trip_invoices(self):
		passengers = self.passengers or []
		if not passengers:
			return

		count = len(passengers)
		base = flt(self.trip_value) / count if count else 0
		vat_rate = flt(self.vat_rate or 15)

		for row in passengers:
			if frappe.db.exists("Trip Invoice", {"trip": self.name, "passenger_row": row.name}):
				continue

			from_loc = self.from_location or ""
			to_loc = self.to_location or ""
			item_title = f"Trip {from_loc} - {to_loc}".strip()
			inv = frappe.new_doc("Trip Invoice")
			inv.trip = self.name
			inv.invoice_scope = "Passenger"
			inv.passenger_row = row.name
			inv.allocated_passenger_count = 1
			inv.customer = row.passenger_name or "Walk-in Customer"
			inv.invoice_passenger_name = row.passenger_name
			inv.invoice_passenger_mobile = row.mobile_no
			inv.trip_route = self.route
			inv.from_location = self.from_location
			inv.to_location = self.to_location
			inv.distance = self.distance_km
			inv.trip_value = base
			inv.vat_mode = self.vat_mode or "Included"
			inv.vat_rate = vat_rate
			inv.append("items", {
				"source_type": "Trip Route",
				"trip": self.name,
				"route": self.route,
				"item_name": item_title,
				"description": item_title,
				"qty": 1,
				"rate": base,
				"vat_rate": vat_rate,
			})
			inv.insert(ignore_permissions=True)

		first_invoice = frappe.db.get_value("Trip Invoice", {"trip": self.name}, "name")
		if first_invoice and self.trip_invoice != first_invoice:
			self.db_set("trip_invoice", first_invoice, update_modified=False)
