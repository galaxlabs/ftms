from __future__ import annotations

import math
from datetime import date, datetime

SAUDI_LATITUDE_BOUNDS = (16.0, 33.0)
SAUDI_LONGITUDE_BOUNDS = (34.0, 56.0)


def validate_saudi_identity(document_type, value):
	digits = str(value or "").strip()
	prefix = {"National ID": "1", "Iqama": "2"}.get(str(document_type or "").strip())
	if not prefix:
		raise ValueError("ID document type must be National ID or Iqama")
	if len(digits) != 10 or not digits.isdigit() or not digits.startswith(prefix):
		raise ValueError(f"{document_type} must be exactly 10 digits and start with {prefix}")
	return digits


def validate_future_date(value, label, reference_date=None):
	if not value:
		raise ValueError(f"{label} is required")
	if isinstance(value, datetime):
		parsed = value.date()
	elif isinstance(value, date):
		parsed = value
	else:
		try:
			parsed = date.fromisoformat(str(value).strip())
		except ValueError:
			raise ValueError(f"{label} must use YYYY-MM-DD format")
	if parsed <= (reference_date or date.today()):
		raise ValueError(f"{label} must be in the future")
	return parsed


def validate_coordinates(latitude, longitude):
	try:
		latitude = float(latitude)
		longitude = float(longitude)
	except (TypeError, ValueError):
		raise ValueError("Latitude and longitude must be numeric")
	if not math.isfinite(latitude) or not math.isfinite(longitude):
		raise ValueError("Latitude and longitude must be finite")
	if not SAUDI_LATITUDE_BOUNDS[0] <= latitude <= SAUDI_LATITUDE_BOUNDS[1]:
		raise ValueError("Latitude is outside Saudi Arabia bounds")
	if not SAUDI_LONGITUDE_BOUNDS[0] <= longitude <= SAUDI_LONGITUDE_BOUNDS[1]:
		raise ValueError("Longitude is outside Saudi Arabia bounds")
	return latitude, longitude


def nearest_city(latitude, longitude, cities):
	closest = None
	closest_distance = math.inf
	for city in cities:
		city_latitude = city.get("latitude")
		city_longitude = city.get("longitude")
		if city_latitude is None or city_longitude is None:
			continue
		lat1, lat2 = math.radians(latitude), math.radians(float(city_latitude))
		delta_lat = lat2 - lat1
		delta_long = math.radians(float(city_longitude) - longitude)
		a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_long / 2) ** 2
		distance = 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
		if distance < closest_distance:
			closest = city
			closest_distance = distance
	if closest is None:
		raise ValueError("No active KSA city has coordinates")
	return closest, closest_distance


def validate_model_year(value, minimum=None, maximum=None, current_year=None):
	try:
		year = int(value)
	except (TypeError, ValueError):
		raise ValueError("Model year must be an integer")
	upper_bound = (current_year or date.today().year) + 1
	if year < 1980 or year > upper_bound:
		raise ValueError(f"Model year must be between 1980 and {upper_bound}")
	if minimum and year < int(minimum):
		raise ValueError(f"Model year must be {int(minimum)} or newer")
	if maximum and year > int(maximum):
		raise ValueError(f"Model year must be {int(maximum)} or older")
	return year
