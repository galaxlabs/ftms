from unittest import TestCase

from ftms.api.driver_auth import normalize_mobile, validate_signup_values


class TestDriverAuthHelpers(TestCase):
	def test_normalizes_saudi_mobile(self):
		self.assertEqual(normalize_mobile("055 123 4567"), "+966551234567")
		self.assertEqual(normalize_mobile("+966551234567"), "+966551234567")

	def test_requires_matching_password_and_full_name(self):
		with self.assertRaisesRegex(ValueError, "do not match"):
			validate_signup_values("driver@example.com", "one", "two", "Test Driver", "+966551234567")
		with self.assertRaisesRegex(ValueError, "Full name"):
			validate_signup_values("driver@example.com", "one", "one", "X", "+966551234567")

	def test_returns_normalized_safe_identity(self):
		self.assertEqual(
			validate_signup_values(
				" DRIVER@Example.com ", "password", "password", " Test   Driver ", "0551234567"
			),
			("driver@example.com", "Test Driver", "+966551234567"),
		)
