from frappe.model.document import Document


class Route(Document):
	def validate(self):
		if self.source and self.destination and not self.route_title:
			self.route_title = f"{self.source} to {self.destination}"

		if self.route_title and not self.route_name:
			self.route_name = self.route_title
