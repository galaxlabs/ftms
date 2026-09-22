from unittest import TestCase

from ftms.document_ai.comparison import compare_extraction, normalize_value
from ftms.document_ai.openai_vision import parse_chat_completion
from ftms.document_ai.registry import (
	ACTION_IDS,
	UNTRUSTED_CONTENT_INSTRUCTION,
	ComparisonRule,
	get_action,
	normalize_result,
)


class TestDocumentAIRegistry(TestCase):
	def test_exact_action_ids_and_prompt_isolation(self):
		self.assertEqual(
			set(ACTION_IDS),
			{
				"captain.id_document",
				"captain.license_document",
				"captain.driver_card_document",
				"vehicle.vehicle_card_document",
				"vehicle.vehicle_ownership_document",
			},
		)
		identity = get_action("captain.id_document")
		licence = get_action("captain.license_document")
		self.assertIn(UNTRUSTED_CONTENT_INSTRUCTION, identity.prompt)
		self.assertNotIn("license_number", identity.schema["properties"])
		self.assertNotIn("identity_number", licence.schema["properties"])
		self.assertNotEqual(identity.command, licence.command)

	def test_unknown_action_is_rejected(self):
		with self.assertRaisesRegex(ValueError, "Unsupported"):
			get_action("captain.free_form_prompt")

	def test_result_normalization_drops_unknown_fields(self):
		action = get_action("captain.license_document")
		result = normalize_result(
			action,
			{
				"license_number": " 123-456 ",
				"confidence": {"license_number": 1.4},
				"warnings": [" review "],
				"identity_number": "must be dropped",
			},
		)
		self.assertEqual(result["license_number"], "123-456")
		self.assertEqual(result["confidence"]["license_number"], 1)
		self.assertNotIn("identity_number", result)


class TestDocumentAIComparison(TestCase):
	def test_authoritative_normalization(self):
		self.assertEqual(normalize_value("١٢٣-٤٥٦", "number"), "123456")
		self.assertEqual(normalize_value("  Ahmed   Ali ", "name"), "AHMED ALI")
		self.assertEqual(normalize_value("2029/4/3", "date"), "2029-04-03")

	def test_blocking_mismatch_and_missing_states(self):
		rules = (
			ComparisonRule("holder", "full_name", "Holder", "name", True, True),
			ComparisonRule("number", "license_no", "Number", "number", True),
		)
		result = compare_extraction(
			{"holder": "Ahmed Ali", "number": None, "extra": "value"},
			{"full_name": "Mohammed Ali", "license_no": "123"},
			rules,
		)
		self.assertEqual(result["comparison_status"], "Blocked Mismatch")
		self.assertEqual([row["status"] for row in result["comparisons"]], ["Unmatched", "Missing Source", "Not Compared"])

	def test_exact_match(self):
		rules = (ComparisonRule("number", "number", "Number", "number", True, True),)
		result = compare_extraction({"number": "١٢٣-٤٥٦"}, {"number": "123456"}, rules)
		self.assertEqual(result["comparison_status"], "Exact Match")


class TestOpenAIParsing(TestCase):
	def test_parses_schema_json_without_sdk(self):
		payload = {"choices": [{"message": {"content": "```json\n{\"field\": \"value\"}\n```"}}]}
		self.assertEqual(parse_chat_completion(payload), {"field": "value"})
