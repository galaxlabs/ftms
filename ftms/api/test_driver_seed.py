from unittest import TestCase

from ftms.api.driver_helpers import get_demo_seed_specs


class TestDriverSeedInvariants(TestCase):
	def test_seed_specs_are_distinct_test_records_without_credentials(self):
		specs = get_demo_seed_specs()
		companies = specs["companies"]
		users = specs["users"]
		self.assertEqual(len(companies), 3)
		self.assertEqual(len(users), 5)
		self.assertEqual(len({row[0] for row in companies}), 3)
		self.assertEqual(len({row[1] for row in companies}), 3)
		self.assertEqual(len({row[3] for row in companies}), 3)
		self.assertTrue(all(row[0].startswith("TEST-") and row[1].startswith("TEST ") for row in companies))
		self.assertTrue(all(len(row) == 5 and "password" not in " ".join(map(str, row)).lower() for row in users))
		captain_companies = {row[2] for row in users if row[3] == "Captain"}
		self.assertEqual(captain_companies, {0, 1, 2})
