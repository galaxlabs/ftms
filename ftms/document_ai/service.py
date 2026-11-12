from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import base64
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

from ftms.api.driver_validation import validate_future_date, validate_saudi_identity
from ftms.document_ai.comparison import compare_extraction, mask_comparisons, normalize_value
from ftms.document_ai.openai_vision import DocumentAIProviderError, extract_image
from ftms.document_ai.registry import get_action, normalize_result
from ftms.security import rate_limit

ALLOWED_IMAGE_TYPES = {
	".jpg": "image/jpeg",
	".jpeg": "image/jpeg",
	".png": "image/png",
	".webp": "image/webp",
}

PASSENGER_EXTRACTION_SCHEMA = {
	"type": "object",
	"additionalProperties": False,
	"properties": {
		"passengers": {
			"type": "array",
			"items": {
				"type": "object",
				"additionalProperties": False,
				"properties": {
					"passenger_name": {"type": ["string", "null"]},
					"document_number": {"type": ["string", "null"]},
					"document_type": {"type": ["string", "null"]},
					"nationality": {"type": ["string", "null"]},
					"confidence": {"type": ["number", "null"]},
				},
				"required": ["passenger_name", "document_number", "document_type", "nationality", "confidence"],
			},
		},
	},
	"required": ["passengers"],
}

PASSENGER_EXTRACTION_PROMPT = """You are extracting passenger manifest rows from a travel document image.
Extract only passenger/person information visible in the supplied image.
Return JSON with key passengers.
Each passenger must include passenger_name, document_number, document_type, nationality, and confidence.
Use null for unreadable values. Do not guess. Do not include company names, route names, instructions, or unrelated text."""


def _require_user():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)
	return user


def _settings():
	doc = frappe.get_single("Integration Settings")
	if not cint(doc.document_ai_enabled):
		frappe.throw(_("Document AI is disabled"))
	if doc.document_ai_provider != "OpenAI":
		frappe.throw(_("The configured document AI provider is not supported"))
	api_key = doc.get_password("openai_api_key", raise_exception=False)
	if not api_key:
		frappe.throw(_("Document AI is enabled but the OpenAI API key is not configured"))
	return {
		"api_key": api_key,
		"model": doc.openai_vision_model or "gpt-4.1-mini",
		"timeout": min(max(cint(doc.document_ai_timeout_seconds) or 45, 1), 120),
		"max_file_bytes": min(max(cint(doc.document_ai_max_file_bytes) or 10 * 1024 * 1024, 1024), 25 * 1024 * 1024),
		"review_confidence": min(max(flt(doc.document_ai_review_confidence) or 0.7, 0), 1),
	}


def _image_from_data_url(file_data, mime_type=None, max_file_bytes=None):
	value = str(file_data or "")
	if not value:
		frappe.throw(_("Document image data is required"))
	if value.startswith("data:"):
		header, _, payload = value.partition(",")
		mime_type = mime_type or header.split(";", 1)[0].replace("data:", "")
	else:
		payload = value
	mime_type = (mime_type or "image/jpeg").lower()
	if mime_type not in ALLOWED_IMAGE_TYPES.values():
		frappe.throw(_("Only JPG, PNG, and WebP passenger document images are supported"))
	try:
		content = base64.b64decode(payload, validate=True)
	except Exception:
		frappe.throw(_("Invalid base64 document image"))
	if not content:
		frappe.throw(_("Document image is empty"))
	if max_file_bytes and len(content) > max_file_bytes:
		frappe.throw(_("The document image exceeds the configured file-size limit"))
	return content, mime_type


def extract_passenger_document(file_data, mime_type=None):
	user = _require_user()
	rate_limit("passenger_document_ai_user", limit=20, seconds=3600, identity=user)
	settings = _settings()
	content, mime_type = _image_from_data_url(file_data, mime_type=mime_type, max_file_bytes=settings["max_file_bytes"])
	file_hash = hashlib.sha256(content).hexdigest()
	rate_limit("passenger_document_ai_file", limit=3, seconds=3600, identity=f"{user}:{file_hash}")
	try:
		result = extract_image(
			api_key=settings["api_key"],
			model=settings["model"],
			prompt=PASSENGER_EXTRACTION_PROMPT,
			schema=PASSENGER_EXTRACTION_SCHEMA,
			command="extract_passenger_manifest",
			image_bytes=content,
			mime_type=mime_type,
			timeout=settings["timeout"],
		)
	except (DocumentAIProviderError, ValueError) as exc:
		frappe.throw(_("Passenger document extraction failed: {0}").format(str(exc)))
	passengers = []
	for row in result.get("passengers") or []:
		passenger = {
			"passenger_name": normalize_value(row.get("passenger_name")),
			"document_number": normalize_value(row.get("document_number")),
			"document_type": normalize_value(row.get("document_type")),
			"nationality": normalize_value(row.get("nationality")),
			"confidence": flt(row.get("confidence")),
		}
		if any(passenger.get(key) for key in ("passenger_name", "document_number", "nationality")):
			passengers.append(passenger)
	return {"status": "success", "passengers": passengers, "provider": "OpenAI", "model": settings["model"]}


def _get_owned_target(action, target_doctype, target_name, user):
	if target_doctype not in action.target_doctypes:
		frappe.throw(_("This target type is not allowed for the attachment action"), frappe.PermissionError)
	target = frappe.get_doc(target_doctype, target_name)
	if target_doctype == "Captain Profile":
		owned = target.user == user
	else:
		owned = user in (target.owner_captain_user, target.assigned_captain_user)
	if not owned:
		frappe.throw(_("You do not own the selected target record"), frappe.PermissionError)
	return target


def _get_owned_private_file(file_url, target, user, max_file_bytes):
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(_("The selected file does not exist"))
	file_doc = frappe.get_doc("File", file_name)
	if file_doc.owner != user:
		frappe.throw(_("You do not own the selected file"), frappe.PermissionError)
	if not cint(file_doc.is_private) or not str(file_doc.file_url or "").startswith("/private/files/"):
		frappe.throw(_("Document extraction requires a private file"))
	if file_doc.attached_to_doctype and (
		file_doc.attached_to_doctype != target.doctype or file_doc.attached_to_name != target.name
	):
		frappe.throw(_("The selected file is attached to another record"), frappe.PermissionError)
	extension = Path(file_doc.file_name or file_doc.file_url).suffix.lower()
	if extension == ".pdf":
		frappe.throw(_("PDF extraction is not supported in the first release; upload a JPG, PNG, or WebP image"))
	if extension not in ALLOWED_IMAGE_TYPES:
		frappe.throw(_("Unsupported document file type; upload a JPG, PNG, or WebP image"))
	mime_type = (mimetypes.guess_type(file_doc.file_name or file_doc.file_url or "")[0] or "").lower()
	if mime_type not in ALLOWED_IMAGE_TYPES.values():
		frappe.throw(_("The file MIME type does not match a supported document image"))
	path = file_doc.get_full_path()
	file_size = cint(file_doc.file_size) or os.path.getsize(path)
	if file_size <= 0 or file_size > max_file_bytes:
		frappe.throw(_("The document image exceeds the configured file-size limit"))
	with open(path, "rb") as handle:
		content = handle.read(max_file_bytes + 1)
	if len(content) > max_file_bytes:
		frappe.throw(_("The document image exceeds the configured file-size limit"))
	if not _matches_image_signature(content, extension):
		frappe.throw(_("The file content does not match its image type"))
	return file_doc, content, ALLOWED_IMAGE_TYPES[extension]


def _matches_image_signature(content, extension):
	if extension in (".jpg", ".jpeg"):
		return content.startswith(b"\xff\xd8\xff")
	if extension == ".png":
		return content.startswith(b"\x89PNG\r\n\x1a\n")
	if extension == ".webp":
		return len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
	return False


def _comparison_target(target):
	data = target.as_dict()
	if target.doctype != "Vehicle":
		return data
	if target.company:
		company = frappe.db.get_value("Company", target.company, ["legal_name", "company_name", "cr_no"], as_dict=True)
		data["__owner_name"] = company.legal_name or company.company_name if company else None
		data["__company_cr_number"] = company.cr_no if company else None
	elif target.owner_captain_user:
		data["__owner_name"] = frappe.db.get_value("Captain Profile", {"user": target.owner_captain_user}, "full_name")
	return data


def _overall_confidence(result):
	values = [float(value) for value in (result.get("confidence") or {}).values()]
	return sum(values) / len(values) if values else 0


def extract_attachment(attachment_action_id, file_url, target_doctype, target_name):
	user = _require_user()
	try:
		action = get_action(attachment_action_id)
	except ValueError as exc:
		frappe.throw(_(str(exc)))
	rate_limit("document_ai_user", limit=20, seconds=3600, identity=user)
	target = _get_owned_target(action, target_doctype, target_name, user)
	settings = _settings()
	file_doc, content, mime_type = _get_owned_private_file(file_url, target, user, settings["max_file_bytes"])
	file_hash = hashlib.sha256(content).hexdigest()
	rate_limit("document_ai_file_action", limit=3, seconds=3600, identity=f"{user}:{file_hash}:{action.action_id}")

	existing = frappe.db.get_value(
		"Document Extraction",
		{
			"attachment_action_id": action.action_id,
			"prompt_version": action.prompt_version,
			"file_hash": file_hash,
			"target_doctype": target_doctype,
			"target_name": target_name,
			"requested_by": user,
			"status": ("in", ("Needs Confirmation", "Confirmed")),
		},
		"name",
	)
	if existing:
		return extraction_response(frappe.get_doc("Document Extraction", existing), action)

	doc = frappe.get_doc(
		{
			"doctype": "Document Extraction",
			"attachment_action_id": action.action_id,
			"command": action.command,
			"prompt_version": action.prompt_version,
			"status": "Processing",
			"model_provider": "OpenAI",
			"model_name": settings["model"],
			"file": file_doc.name,
			"file_url": file_doc.file_url,
			"file_hash": file_hash,
			"target_doctype": target_doctype,
			"target_name": target_name,
			"company": target.get("company") or target.get("current_company"),
			"requested_by": user,
			"requested_on": now_datetime(),
		}
	)
	doc.flags.document_ai_service = True
	doc.insert(ignore_permissions=True)
	try:
		raw_result = extract_image(
			api_key=settings["api_key"],
			model=settings["model"],
			prompt=action.prompt,
			schema=action.schema,
			command=action.command,
			image_bytes=content,
			mime_type=mime_type,
			timeout=settings["timeout"],
		)
		result = normalize_result(action, raw_result)
		comparison = compare_extraction(
			result,
			_comparison_target(target),
			action.comparison_rules,
			result.get("confidence"),
			settings["review_confidence"],
		)
		doc.raw_result_json = json.dumps(raw_result, ensure_ascii=False)
		doc.normalized_result_json = json.dumps(result, ensure_ascii=False)
		doc.comparisons_json = json.dumps(comparison["comparisons"], ensure_ascii=False)
		doc.warnings_json = json.dumps(result.get("warnings") or [], ensure_ascii=False)
		doc.overall_confidence = _overall_confidence(result)
		doc.comparison_status = comparison["comparison_status"]
		doc.status = "Needs Confirmation"
		doc.save(ignore_permissions=True)
	except (DocumentAIProviderError, ValueError) as exc:
		doc.status = "Failed"
		doc.failure_reason = str(exc)[:500]
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(_("Document extraction failed: {0}").format(str(exc)))
	frappe.db.commit()
	return extraction_response(doc, action)


def extraction_response(doc, action=None):
	action = action or get_action(doc.attachment_action_id)
	values = json.loads(doc.normalized_result_json or "{}")
	comparisons = json.loads(doc.comparisons_json or "[]")
	return {
		"status": "success",
		"extraction": {
			"name": doc.name,
			"attachment_action_id": doc.attachment_action_id,
			"command": doc.command,
			"prompt_version": doc.prompt_version,
			"review_status": doc.status,
			"comparison_status": doc.comparison_status,
			"values": values,
			"comparisons": mask_comparisons(comparisons, action.sensitive_fields),
			"unmatched_count": sum(row.get("status") == "Unmatched" for row in comparisons),
			"blocking_count": sum(bool(row.get("blocking")) for row in comparisons),
			"warnings": json.loads(doc.warnings_json or "[]"),
			"overall_confidence": flt(doc.overall_confidence),
		},
	}


def confirm_extraction(extraction, confirmed_values, corrections=None):
	user = _require_user()
	doc = frappe.get_doc("Document Extraction", extraction)
	if doc.requested_by != user:
		frappe.throw(_("You do not own this extraction"), frappe.PermissionError)
	if doc.status != "Needs Confirmation":
		frappe.throw(_("Only an extraction awaiting confirmation can be confirmed"))
	if doc.comparison_status in ("Blocked Mismatch", "Unable to Compare"):
		frappe.throw(_("This extraction requires a rescan or manual review and cannot be confirmed"))
	action = get_action(doc.attachment_action_id)
	values = _parse_json_object(confirmed_values, "confirmed_values")
	unknown = set(values) - set(action.update_fields)
	if unknown:
		frappe.throw(_("Confirmed values contain fields not allowed for this attachment action"))
	target = _get_owned_target(action, doc.target_doctype, doc.target_name, user)
	updates = _validated_updates(action, target, values)
	for target_field, value in updates.items():
		target.set(target_field, value)
	attachment_field = _attachment_field_for_target(action, target, values)
	if attachment_field:
		target.set(attachment_field, doc.file_url)
	target.save(ignore_permissions=True)
	doc.corrections_json = json.dumps(_parse_json_object(corrections or {}, "corrections"), ensure_ascii=False)
	doc.confirmed_by = user
	doc.confirmed_on = now_datetime()
	doc.status = "Confirmed"
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"status": "success",
		"extraction": doc.name,
		"review_status": doc.status,
		"target": {"doctype": target.doctype, "name": target.name, "updated_fields": sorted(updates)},
	}


def _attachment_field_for_target(action, target, values):
	if action.action_id == "vehicle.vehicle_card_document" and target.doctype == "Vehicle":
		preferred = (
			"operation_card_document"
			if values.get("document_kind") == "Operation Card"
			else "registration_document"
		)
		return preferred if target.meta.has_field(preferred) else None
	for fieldname in action.attachment_fields:
		if target.meta.has_field(fieldname):
			return fieldname
	return None


def _parse_json_object(value, label):
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except json.JSONDecodeError:
			frappe.throw(_("{0} must be valid JSON").format(label))
	if not isinstance(value, dict):
		frappe.throw(_("{0} must be a JSON object").format(label))
	return value


def _validated_updates(action, target, values):
	updates = {}
	for source_field, value in values.items():
		target_field = action.update_fields[source_field]
		if not target.meta.has_field(target_field) or value in (None, ""):
			continue
		if target_field in (
			"id_expiry_date",
			"license_expiry_date",
			"driver_card_expiry_date",
			"registration_expiry_date",
			"operation_card_expiry_date",
		):
			try:
				value = validate_future_date(value, target.meta.get_label(target_field))
			except ValueError as exc:
				frappe.throw(_(str(exc)))
		if target_field in ("seat_capacity", "passenger_capacity", "model_year"):
			value = cint(value)
			if value <= 0:
				frappe.throw(_("{0} must be positive").format(target.meta.get_label(target_field)))
		updates[target_field] = value.strip() if isinstance(value, str) else value
	if action.action_id == "vehicle.vehicle_card_document" and values.get("expiry_date"):
		expiry_field = (
			"operation_card_expiry_date"
			if values.get("document_kind") == "Operation Card"
			else "registration_expiry_date"
		)
		try:
			updates[expiry_field] = validate_future_date(values["expiry_date"], target.meta.get_label(expiry_field))
		except ValueError as exc:
			frappe.throw(_(str(exc)))
	if action.action_id == "captain.id_document" and values.get("identity_number"):
		document_type = values.get("document_type")
		try:
			identity = validate_saudi_identity(document_type, values["identity_number"])
		except ValueError as exc:
			frappe.throw(_(str(exc)))
		updates["id_document_type"] = document_type
		updates["national_id"] = identity
		if document_type == "Iqama":
			updates["iqama_no"] = identity
			if values.get("expiry_date"):
				updates["iqama_expiry_date"] = getdate(values["expiry_date"])
	if target.doctype == "Captain Profile":
		_validate_captain_updates(target, updates)
	return updates


def _validate_captain_updates(target, updates):
	unique_fields = {
		"national_id": "Identity number",
		"iqama_no": "Iqama number",
		"license_no": "Driving licence number",
		"driver_card_no": "Driver-card number",
	}
	for fieldname, label in unique_fields.items():
		value = updates.get(fieldname)
		if value and frappe.db.exists(
			"Captain Profile", {fieldname: value, "name": ("!=", target.name)}
		):
			frappe.throw(_("{0} is already registered").format(label))
	if target.verification_status != "Verified":
		return
	kinds = {
		"full_name": "name",
		"national_id": "number",
		"iqama_no": "number",
		"license_no": "number",
		"driver_card_no": "number",
		"id_expiry_date": "date",
		"iqama_expiry_date": "date",
		"license_expiry_date": "date",
		"driver_card_expiry_date": "date",
	}
	for fieldname, value in updates.items():
		current = target.get(fieldname)
		if current in (None, ""):
			continue
		kind = kinds.get(fieldname, "text")
		if normalize_value(current, kind) != normalize_value(value, kind):
			frappe.throw(
				_("Verified Captain details cannot be overwritten by AI extraction; submit a profile correction request")
			)
