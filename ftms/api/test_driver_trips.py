from unittest import TestCase

from ftms.api.driver_helpers import parse_trip_scan_value


class TestTripScanParsing(TestCase):
	UUID = "123e4567-e89b-12d3-a456-426614174000"

	def test_parses_name_and_code_as_references(self):
		self.assertEqual(parse_trip_scan_value("TRIP-2026-0001"), {"kind": "reference", "value": "TRIP-2026-0001"})
		self.assertEqual(parse_trip_scan_value("RKS-101"), {"kind": "reference", "value": "RKS-101"})

	def test_parses_public_uuid_and_url(self):
		expected = {"kind": "public_uuid", "value": self.UUID}
		self.assertEqual(parse_trip_scan_value(self.UUID.upper()), expected)
		self.assertEqual(parse_trip_scan_value(f"https://example.test/trip/{self.UUID}?source=qr"), expected)
		self.assertEqual(parse_trip_scan_value(f"/trip/{self.UUID}"), expected)

	def test_rejects_empty_or_unrelated_urls(self):
		with self.assertRaisesRegex(ValueError, "required"):
			parse_trip_scan_value(" ")
		with self.assertRaisesRegex(ValueError, "public trip URL"):
			parse_trip_scan_value(f"https://example.test/booking/{self.UUID}")
