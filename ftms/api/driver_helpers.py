from __future__ import annotations

import uuid
from urllib.parse import unquote, urlparse


def parse_trip_scan_value(value):
	"""Parse a trip name/code, public UUID, or /trip/<uuid> URL without database access."""
	value = str(value or "").strip()
	if not value:
		raise ValueError("Trip scan value is required")
	parsed = urlparse(value)
	if parsed.scheme or parsed.netloc or value.startswith("/"):
		parts = [unquote(part).strip() for part in parsed.path.split("/") if part.strip()]
		if len(parts) < 2 or parts[-2].casefold() != "trip":
			raise ValueError("Scanned URL is not a public trip URL")
		value = parts[-1]
	if not value or len(value) > 140 or any(character.isspace() for character in value):
		raise ValueError("Invalid trip scan value")
	try:
		return {"kind": "public_uuid", "value": str(uuid.UUID(value))}
	except ValueError:
		return {"kind": "reference", "value": value}


def get_demo_seed_specs():
	"""Stable public identifiers for the idempotent TEST data set; never includes credentials."""
	companies = (
		("TEST-RKS-A", "TEST RideKSA Transport Provider", "TEST RideKSA Transport Provider LLC", "#165DFF", "TEST Provider A footer"),
		("TEST-RKS-B", "TEST RideKSA Fleet Owner", "TEST RideKSA Fleet Owner LLC", "#0F766E", "TEST Fleet Owner footer"),
		("TEST-RKS-C", "TEST RideKSA City Transport", "TEST RideKSA City Transport LLC", "#B45309", "TEST City Transport footer"),
	)
	users = (
		("test.rideksa.admin.a@example.com", "TEST Admin A", 0, "Company Admin", 1),
		("test.rideksa.captain.a@example.com", "TEST Captain A", 0, "Captain", 0),
		("test.rideksa.admin.b@example.com", "TEST Admin B", 1, "Company Admin", 1),
		("test.rideksa.captain.b@example.com", "TEST Captain B", 1, "Captain", 0),
		("test.rideksa.captain.c@example.com", "TEST Captain C", 2, "Captain", 0),
	)
	return {"companies": companies, "users": users}
