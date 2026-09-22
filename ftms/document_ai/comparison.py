from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
ARABIC_PLATE_LETTERS = str.maketrans({"\u0627": "A", "\u0628": "B", "\u062d": "J", "\u062f": "D", "\u0631": "R", "\u0633": "S", "\u0635": "X", "\u0637": "T", "\u0639": "E", "\u0642": "G", "\u0643": "K", "\u0644": "L", "\u0645": "Z", "\u0646": "N", "\u0647": "H", "\u0648": "U", "\u0649": "V"})


def normalize_value(value, kind="text"):
	if value is None:
		return None
	if isinstance(value, (date, datetime)):
		return value.strftime("%Y-%m-%d")
	text = unicodedata.normalize("NFKC", str(value)).translate(ARABIC_DIGITS).strip()
	if not text:
		return None
	if kind == "date":
		match = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
		if not match:
			return text
		year, month, day = (int(part) for part in match.groups())
		try:
			return date(year, month, day).isoformat()
		except ValueError:
			return text
	if kind in ("number", "plate"):
		if kind == "plate":
			text = text.translate(ARABIC_PLATE_LETTERS)
		return re.sub(r"[^A-Z0-9]", "", text.upper()) or None
	if kind == "name":
		text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
		text = text.replace("\u0623", "\u0627").replace("\u0625", "\u0627").replace("\u0622", "\u0627").replace("\u0649", "\u064a")
	return re.sub(r"\s+", " ", text).strip().upper() or None


def compare_extraction(values, target, rules, confidence=None, unreadable_threshold=0.7):
	confidence = confidence or {}
	comparisons = []
	compared = set()
	for rule in rules:
		source = values.get(rule.source_field)
		target_value = target.get(rule.target_field) if hasattr(target, "get") else None
		source_normalized = normalize_value(source, rule.kind)
		target_normalized = normalize_value(target_value, rule.kind)
		field_confidence = confidence.get(rule.source_field)
		if source_normalized is None:
			status = "Missing Source"
		elif field_confidence is not None and float(field_confidence) < unreadable_threshold:
			status = "Unreadable"
		elif target_normalized is None:
			status = "Missing Target"
		elif source_normalized == target_normalized:
			status = "Match"
		else:
			status = "Unmatched"
		severity = "Blocking" if rule.blocking and status == "Unmatched" else ("Required" if rule.required else "Review")
		comparisons.append(
			{
				"field": rule.source_field,
				"label": rule.label,
				"source_value": source,
				"target_field": rule.target_field,
				"target_value": target_value,
				"normalized_source": source_normalized,
				"normalized_target": target_normalized,
				"status": status,
				"severity": severity,
				"blocking": severity == "Blocking",
				"message": _comparison_message(rule.label, status),
			}
		)
		compared.add(rule.source_field)
	for field, value in values.items():
		if field in compared or field in ("confidence", "warnings"):
			continue
		comparisons.append(
			{
				"field": field,
				"label": field.replace("_", " ").title(),
				"source_value": value,
				"target_field": None,
				"target_value": None,
				"normalized_source": normalize_value(value) if not isinstance(value, list) else value,
				"normalized_target": None,
				"status": "Not Compared",
				"severity": "Information",
				"blocking": False,
				"message": "No authoritative target comparison is configured for this field.",
			}
		)
	overall = overall_comparison_status(comparisons, rules)
	return {"comparisons": comparisons, "comparison_status": overall}


def overall_comparison_status(comparisons, rules):
	required = {rule.source_field for rule in rules if rule.required}
	if any(row["blocking"] and row["status"] == "Unmatched" for row in comparisons):
		return "Blocked Mismatch"
	if any(row["field"] in required and row["status"] in ("Missing Source", "Unreadable") for row in comparisons):
		return "Unable to Compare"
	if any(row["status"] in ("Unmatched", "Missing Target", "Missing Source", "Unreadable") for row in comparisons):
		return "Review Required"
	if required and all(row["status"] == "Match" for row in comparisons if row["field"] in required):
		return "Exact Match"
	return "Review Required"


def _comparison_message(label, status):
	messages = {
		"Match": f"{label} matches.",
		"Unmatched": f"{label} does not match the target record.",
		"Missing Source": f"{label} is missing from the document.",
		"Missing Target": f"{label} is not yet present on the target record.",
		"Unreadable": f"{label} could not be read with sufficient confidence.",
	}
	return messages[status]


def mask_value(value, visible=4):
	text = str(value or "")
	return f"{'*' * max(0, len(text) - visible)}{text[-visible:]}" if text else None


def mask_comparisons(comparisons, sensitive_fields):
	masked = []
	for comparison in comparisons:
		row = dict(comparison)
		if row["field"] in sensitive_fields:
			row["source_value"] = mask_value(row.get("source_value"))
			row["target_value"] = mask_value(row.get("target_value"))
			row.pop("normalized_source", None)
			row.pop("normalized_target", None)
		masked.append(row)
	return masked
