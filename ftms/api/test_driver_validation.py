from datetime import date
from unittest import TestCase

from ftms.api.driver_validation import (
	nearest_city,
	validate_coordinates,
	validate_future_date,
	validate_model_year,
	validate_saudi_identity,
)


class TestDriverValidation(TestCase):
	def test_saudi_identity_prefix_and_length(self):
		self.assertEqual(validate_saudi_identity("National ID", "1234567890"), "1234567890")
		self.assertEqual(validate_saudi_identity("Iqama", "2345678901"), "2345678901")
		with self.assertRaisesRegex(ValueError, "start with 2"):
			validate_saudi_identity("Iqama", "1234567890")

	def test_dates_must_be_strictly_future(self):
		with self.assertRaisesRegex(ValueError, "future"):
			validate_future_date("2026-08-15", "Expiry", date(2026, 8, 15))
		self.assertEqual(
			validate_future_date("2026-08-16", "Expiry", date(2026, 8, 15)),
			date(2026, 8, 16),
		)

	def test_coordinates_and_nearest_city(self):
		latitude, longitude = validate_coordinates(24.72, 46.68)
		city, distance = nearest_city(
			latitude,
			longitude,
			[
				{"name": "Jeddah", "latitude": 21.54, "longitude": 39.17},
				{"name": "Riyadh", "latitude": 24.71, "longitude": 46.67},
			],
		)
		self.assertEqual(city["name"], "Riyadh")
		self.assertLess(distance, 2)
		with self.assertRaisesRegex(ValueError, "Saudi Arabia"):
			validate_coordinates(40, 46)

	def test_model_year_honors_catalog_range(self):
		self.assertEqual(validate_model_year(2024, 2020, 2025, current_year=2026), 2024)
		with self.assertRaisesRegex(ValueError, "2020 or newer"):
			validate_model_year(2019, 2020, 2025, current_year=2026)
