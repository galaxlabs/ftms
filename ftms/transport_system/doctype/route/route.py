from __future__ import annotations

import math

import frappe
from frappe.model.document import Document

from ftms.tenant import require_company


def haversine_km(lat1, lon1, lat2, lon2):
	R = 6371.0
	d_lat = math.radians(lat2 - lat1)
	d_lon = math.radians(lon2 - lon1)
	a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
	return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)


def city_lat_lng(city):
	vals = frappe.db.get_value("KSA City", city, ["latitude", "longitude"])
	if vals and vals[0] is not None and vals[1] is not None:
		return float(vals[0]), float(vals[1])
	return None


class Route(Document):
	def validate(self):
		require_company(self)
		if self.source and self.destination:
			if self.source == self.destination:
				frappe.throw("Source and Destination cannot be the same city.")
			if not self.route_title:
				src = frappe.db.get_value("KSA City", self.source, "city_name")
				dst = frappe.db.get_value("KSA City", self.destination, "city_name")
				self.route_title = f"{src} to {dst}"
			if not self.distance_km:
				src_coords = city_lat_lng(self.source)
				dst_coords = city_lat_lng(self.destination)
				if src_coords and dst_coords:
					self.distance_km = haversine_km(src_coords[0], src_coords[1], dst_coords[0], dst_coords[1])
		if self.route_title and not self.route_name:
			self.route_name = self.route_title
