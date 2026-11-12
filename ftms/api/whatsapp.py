from __future__ import annotations

import json
import re
import urllib.request

import frappe
from frappe import _

GATEWAY_URL = "http://127.0.0.1:8181"
INSTANCE = "ftms-driver"


def _gateway(path, payload=None):
	headers = {"apikey": frappe.conf.get("evolution_api_key") or "", "Content-Type": "application/json"}
	data = json.dumps(payload).encode("utf-8") if payload is not None else None
	req = urllib.request.Request(GATEWAY_URL + path, data=data, method="POST", headers=headers)
	with urllib.request.urlopen(req, timeout=60) as response:
		return json.loads(response.read().decode("utf-8") or "{}")


def _digits(value):
	return re.sub(r"\D", "", str(value or ""))


def _send_text(phone, text):
	try:
		_gateway(f"/message/sendText/{INSTANCE}", {"number": phone, "text": text})
	except Exception:
		frappe.log_error(frappe.get_traceback(), "WhatsApp send failed")


def _find_captain(phone):
	tail = _digits(phone)[-9:]
	if len(tail) < 9:
		return None
	rows = frappe.get_all(
		"Captain Profile",
		filters={"mobile_no": ["like", f"%{tail}"]},
		fields=["name", "user", "mobile_no"],
		limit=20,
	)
	for row in rows:
		if _digits(row.mobile_no)[-9:] == tail and row.user:
			return row
	return None


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook():
	expected = frappe.conf.get("whatsapp_webhook_token")
	token = frappe.request.args.get("token")
	if not expected or token != expected:
		frappe.throw(_("Unauthorized"), frappe.PermissionError)

	payload = json.loads(frappe.request.get_data() or b"{}")
	event = str(payload.get("event") or "").upper().replace(".", "_")
	if event != "MESSAGES_UPSERT":
		return {"ok": True, "ignored": event}

	data = payload.get("data") or {}
	key = data.get("key") or {}
	if key.get("fromMe"):
		return {"ok": True, "ignored": "from_me"}

	phone = _digits((key.get("remoteJid") or "").split("@")[0])
	captain = _find_captain(phone)
	if not captain:
		_send_text(phone, "آپ کا نمبر رجسٹرڈ کپتانوں میں نہیں ہے۔ پہلے ایپ میں رجسٹریشن مکمل کریں۔")
		return {"ok": True, "ignored": "unknown_sender"}

	message = data.get("message") or {}
	if "imageMessage" in message:
		return _handle_image(phone, captain, key, message)

	_send_text(phone, "مسافر کی دستاویز کی واضح تصویر بھیجیں۔")
	return {"ok": True}


def _handle_image(phone, captain, key, message):
	from ftms.document_ai.service import extract_passenger_document

	media = _gateway(
		f"/chat/getBase64FromMediaMessage/{INSTANCE}",
		{"message": {"key": key, "message": message}, "convertToMp4": False},
	)
	b64 = media.get("base64") or ""
	mime = media.get("mimetype") or (message.get("imageMessage") or {}).get("mimetype") or "image/jpeg"
	if not b64:
		_send_text(phone, "تصویر حاصل نہیں ہو سکی۔ دوبارہ بھیجیں۔")
		return {"ok": True, "ignored": "no_media"}

	frappe.set_user(captain.user)
	try:
		result = extract_passenger_document(file_data=f"data:{mime};base64,{b64}", mime_type=mime)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "WhatsApp passenger extraction failed")
		_send_text(phone, "تصویر پڑھی نہیں جا سکی۔ زیادہ واضح تصویر بھیجیں۔")
		return {"ok": True, "ignored": "extraction_failed"}
	finally:
		frappe.set_user("Guest")

	passengers = result.get("passengers") or []
	if not passengers:
		_send_text(phone, "تصویر میں کوئی مسافر نہیں ملا۔")
		return {"ok": True, "passengers": 0}

	lines = [f"{index}. {p.get('passenger_name') or '-'} ({p.get('document_number') or '-'})" for index, p in enumerate(passengers, 1)]
	_send_text(phone, f"{len(passengers)} مسافر ملے:\n" + "\n".join(lines) + "\n\nٹرپ بنانے کا اگلا مرحلہ ابھی باقی ہے۔")
	return {"ok": True, "passengers": len(passengers)}
