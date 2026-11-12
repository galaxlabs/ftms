import frappe
from frappe.tests.utils import FrappeTestCase

from ftms.api.driver_registration import (
	get_my_kashf,
	list_my_trips,
	resolve_scanned_trip,
	seed_demo_data,
	transition_my_trip,
)


class TestDriverOwnership(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Transportation Domain", {}):
			self.skipTest("Transportation Domain is required for driver seed integration tests")
		self.seed = seed_demo_data()["data"]

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_each_seed_captain_only_lists_and_resolves_own_trip(self):
		captains = [row for row in self.seed["users"] if row["role"] == "Captain"]
		self.assertEqual(len(captains), 3)
		for captain in captains:
			frappe.set_user(captain["email"])
			trips = list_my_trips()["data"]["trips"]
			self.assertEqual(len(trips), 1)
			self.assertEqual(trips[0]["company"]["name"], captain["company"])
			resolved = resolve_scanned_trip(trips[0]["trip_code"])["data"]["trip"]
			self.assertEqual(resolved["name"], trips[0]["name"])

	def test_foreign_trip_and_kashf_are_not_resolvable(self):
		captains = [row for row in self.seed["users"] if row["role"] == "Captain"]
		own_user = captains[0]["email"]
		foreign_company = captains[1]["company"]
		foreign_trip = frappe.db.get_value("Trip", {"company": foreign_company}, ["name", "trip_code"], as_dict=True)
		foreign_kashf = frappe.db.get_value("Vehicle Inspection Log", {"company": foreign_company}, "name")
		frappe.set_user(own_user)
		with self.assertRaises(frappe.PermissionError):
			resolve_scanned_trip(foreign_trip.trip_code)
		with self.assertRaises(frappe.PermissionError):
			transition_my_trip(foreign_trip.trip_code, "depart")
		with self.assertRaises(frappe.PermissionError):
			get_my_kashf(foreign_kashf)
