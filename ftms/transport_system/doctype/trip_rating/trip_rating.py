from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class TripRating(Document):
	def before_insert(self):
		self.rating_key = f"{self.trip}:{self.rater_user}:{self.rating_type}"

	def validate(self):
		try:
			score = int(self.rating)
		except (TypeError, ValueError):
			score = 0
		if not 1 <= score <= 5:
			frappe.throw(_("Rating must be between 1 and 5"))
		if self.rater_user == self.rated_user:
			frappe.throw(_("A user cannot rate themselves"))
		trip_status = frappe.db.get_value("Trip", self.trip, "trip_status")
		if trip_status != "Completed":
			frappe.throw(_("Ratings are available only after trip completion"))
