from __future__ import annotations

import base64
import json
import re
import urllib.request

import frappe
from frappe import _
from frappe.utils import nowdate

GATEWAY_URL = "http://127.0.0.1:8181"
INSTANCE = "ftms-driver"
LANG_CHOICES = {"1": "en", "2": "ur", "3": "ar"}

WELCOME = "Welcome to Al Haramain Taxi.\nالحرمین ٹیکسی میں خوش آمدید۔"
HELP = "How can I help you? Reply 1 to create a trip from passenger documents.\nمیں آپ کی کیا مدد کر سکتا ہوں؟ مسافروں کی دستاویز سے ٹرپ بنانے کے لیے 1 لکھیں۔"
LANG_MENU = "Choose your language: 1 = English, 2 = اردو, 3 = العربية"
NOT_CAPTAIN = "Your number is not registered as a captain. / آپ کا نمبر رجسٹرڈ کپتان نہیں ہے۔"

TEXT = {
	"ask_count": {
		"en": "How many passengers are in this trip? Reply with the number.",
		"ur": "اس ٹرپ میں کتنے مسافر ہیں؟ تعداد لکھیں۔",
		"ar": "كم عدد الركاب في هذه الرحلة؟ اكتب العدد.",
	},
	"send_photos": {
		"en": "Send one document photo per passenger. When all are sent, reply 'done'.",
		"ur": "ہر مسافر کی دستاویز کی ایک تصویر بھیجیں۔ سب بھیج دیں تو 'done' لکھیں۔",
		"ar": "أرسل صورة وثيقة واحدة لكل راكب. عند الانتهاء اكتب 'done'.",
	},
	"photo_received": {
		"en": "Photo received. Unique passengers so far: {count}.",
		"ur": "تصویر وصول ہو گئی۔ اب تک {count} منفرد مسافر ملے۔",
		"ar": "تم استلام الصورة. عدد الركاب الفريدين حتى الآن: {count}.",
	},
	"need_more": {
		"en": "You said {expected} passengers, but {count} unique passengers were found. Please send the photos of the remaining {missing}, then reply 'done'.",
		"ur": "آپ نے {expected} مسافر بتائے، لیکن {count} منفرد مسافر ملے۔ باقی {missing} مسافروں کی تصاویر بھیجیں، پھر 'done' لکھیں۔",
		"ar": "ذكرت {expected} راكبًا، لكن وجدت {count} راكبًا فريدًا. أرسل صور {missing} المتبقين ثم اكتب 'done'.",
	},
	"more_than_expected": {
		"en": "You said {expected} passengers, but {count} unique passengers were found. Reply 'ok' to continue with {count}, or reply with the correct number.",
		"ur": "آپ نے {expected} مسافر بتائے، لیکن {count} منفرد مسافر ملے۔ {count} کے ساتھ جاری رکھنے کے لیے 'ok' لکھیں، یا درست تعداد لکھیں۔",
		"ar": "ذكرت {expected} راكبًا، لكن وجدت {count} راكبًا فريدًا. اكتب 'ok' للمتابعة بـ {count}، أو اكتب العدد الصحيح.",
	},
	"dupes_note": {
		"en": "{dupes} duplicate photo(s) were counted once.",
		"ur": "{dupes} ڈپلیکیٹ تصویر ایک شمار کی گئی۔",
		"ar": "تم احتساب {dupes} صورة مكررة مرة واحدة.",
	},
	"count_confirmed": {
		"en": "Confirmed: {count} passengers. Reply with the route number:",
		"ur": "تعداد درست ہے: {count} مسافر۔ روٹ کا نمبر لکھیں:",
		"ar": "تم التأكيد: {count} راكبًا. اكتب رقم المسار:",
	},
	"no_routes": {
		"en": "No routes are set up for your company.",
		"ur": "آپ کی کمپنی کے لیے کوئی روٹ نہیں بنا۔",
		"ar": "لا توجد مسارات مسجلة لشركتك.",
	},
	"trip_created": {
		"en": "Trip {trip} created with {count} passengers. The trip sheet PDF is attached.",
		"ur": "ٹرپ {trip} بن گیا، {count} مسافر۔ ٹرپ شیٹ کی PDF منسلک ہے۔",
		"ar": "تم إنشاء الرحلة {trip} بـ {count} راكبًا. ملف PDF لكشف الرحلة مرفق.",
	},
	"extraction_failed": {
		"en": "Could not read this photo. Send a clearer photo.",
		"ur": "یہ تصویر پڑھی نہیں جا سکی۔ زیادہ واضح تصویر بھیجیں۔",
		"ar": "تعذر قراءة هذه الصورة. أرسل صورة أوضح.",
	},
	"expect_number": {
		"en": "Please reply with a number.",
		"ur": "براہ کرم تعداد (نمبر) لکھیں۔",
		"ar": "اكتب رقمًا من فضلك.",
	},
	"expect_photo": {
		"en": "Send a passenger document photo, or reply 'done' when finished.",
		"ur": "مسافر کی دستاویز کی تصویر بھیجیں، یا ختم ہونے پر 'done' لکھیں۔",
		"ar": "أرسل صورة وثيقة راكب، أو اكتب 'done' عند الانتهاء.",
	},
	"invalid_option": {
		"en": "Please reply with a valid option.",
		"ur": "براہ کرم درست آپشن لکھیں۔",
		"ar": "اكتب خيارًا صحيحًا من فضلك.",
	},
	"route_invalid": {
		"en": "Reply with a route number from the list.",
		"ur": "فہرست سے روٹ کا نمبر لکھیں۔",
		"ar": "اكتب رقم المسار من القائمة.",
	},
	"trip_failed": {
		"en": "The trip could not be created. Please contact the office.",
		"ur": "ٹرپ نہیں بن سکا۔ براہ کرم دفتر سے رابطہ کریں۔",
		"ar": "تعذر إنشاء الرحلة. يرجى التواصل مع المكتب.",
	},
	"finished": {
		"en": "Trip finished. Reply 'new' to start another trip.",
		"ur": "ٹرپ مکمل ہو گیا۔ نیا ٹرپ شروع کرنے کے لیے 'new' لکھیں۔",
		"ar": "انتهت الرحلة. اكتب 'new' لبدء رحلة جديدة.",
	},
}


def _t(lang, key, **kwargs):
	text = TEXT[key].get(lang) or TEXT[key]["en"]
	return text.format(**kwargs)


def _gateway(path, payload=None):
	headers = {"apikey": frappe.conf.get("evolution_api_key") or "", "Content-Type": "application/json"}
	data = json.dumps(payload).encode("utf-8") if payload is not None else None
	req = urllib.request.Request(GATEWAY_URL + path, data=data, method="POST", headers=headers)
	with urllib.request.urlopen(req, timeout=60) as response:
		return json.loads(response.read().decode("utf-8") or "{}")


def _digits(value):
	return re.sub(r"\D", "", str(value or ""))


def _trace(phone, step, outcome="Info", detail=""):
	"""One row per bot step in WhatsApp Bot Event, so a stopped flow can be located. Never breaks the bot."""
	try:
		frappe.get_doc({
			"doctype": "WhatsApp Bot Event",
			"event_time": frappe.utils.now_datetime(),
			"phone": phone,
			"step": step,
			"outcome": outcome,
			"detail": str(detail or "")[:500],
		}).insert(ignore_permissions=True)
	except Exception:
		pass


def _send(phone, text):
	try:
		_gateway(f"/message/sendText/{INSTANCE}", {"number": phone, "text": text})
		_trace(phone, "reply_sent", "OK", text[:120])
	except Exception:
		frappe.log_error(frappe.get_traceback(), "WhatsApp send failed")
		_trace(phone, "reply_failed", "Error", "gateway send failed")


def _send_pdf(phone, pdf_bytes, filename, caption):
	try:
		_gateway(
			f"/message/sendMedia/{INSTANCE}",
			{
				"number": phone,
				"mediatype": "document",
				"mimetype": "application/pdf",
				"caption": caption,
				"media": base64.b64encode(pdf_bytes).decode("ascii"),
				"fileName": filename,
			},
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "WhatsApp PDF send failed")
		_send(phone, caption)


COUNTRY_NAMES = {
	"باكستان": "Pakistan", "پاکستان": "Pakistan",
	"الهند": "India", "الہند": "India", "بھارت": "India",
	"بنغلاديش": "Bangladesh", "بنگلہ دیش": "Bangladesh",
	"مصر": "Egypt", "اندونيسيا": "Indonesia", "إندونيسيا": "Indonesia",
	"سوريا": "Syria", "اليمن": "Yemen", "افغانستان": "Afghanistan",
	"السعودية": "Saudi Arabia", "سعودي عربيہ": "Saudi Arabia", "سعودی عرب": "Saudi Arabia",
	"نيبال": "Nepal", "سريلانكا": "Sri Lanka", "الفلبين": "Philippines",
	"ايران": "Iran", "إيران": "Iran", "تركيا": "Turkey", "الأردن": "Jordan",
}


def _country(value):
	"""Map OCR nationality text to a valid Country name, or None."""
	text = (value or "").strip()
	if not text:
		return None
	name = COUNTRY_NAMES.get(text, text)
	if frappe.db.exists("Country", name):
		return name
	return None


CHROME_BINARIES = ("/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/snap/bin/chromium")


def _render_pdf_with_chrome(html):
	"""Render print HTML with headless Chrome (modern CSS and Arabic shaping)."""
	import os
	import subprocess
	import tempfile

	binary = next((b for b in CHROME_BINARIES if os.path.exists(b)), None)
	if not binary:
		raise RuntimeError("Chrome is not installed")
	font_css = "<style>*{font-family: 'Ubuntu', 'Amiri', sans-serif !important;}</style>"
	if "</head>" in html:
		html = html.replace("</head>", font_css + "</head>", 1)
	else:
		html = font_css + html
	with tempfile.TemporaryDirectory() as tmp:
		src = os.path.join(tmp, "trip.html")
		out = os.path.join(tmp, "trip.pdf")
		with open(src, "w", encoding="utf-8") as fh:
			fh.write(html)
		subprocess.run(
			[
				binary, "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
				"--no-pdf-header-footer", f"--print-to-pdf={out}", "file://" + src,
			],
			check=True, timeout=120, capture_output=True,
		)
		with open(out, "rb") as fh:
			return fh.read()


def _trip_pdf(trip_name):
	if not frappe.db.get_value("Trip", trip_name, "qr_code"):
		from ftms.api.trip import generate_qr
		generate_qr(trip_name)
	html = frappe.get_print("Trip", trip_name, print_format="Trip Contract", as_pdf=False)
	try:
		return _render_pdf_with_chrome(html)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Chrome PDF render failed; using wkhtmltopdf")
		return frappe.get_print("Trip", trip_name, print_format="Trip Contract", as_pdf=True)


def _find_captain(phone):
	tail = _digits(phone)[-9:]
	if len(tail) < 9:
		return None
	rows = frappe.get_all(
		"Captain Profile",
		filters={"mobile_no": ["like", f"%{tail}"]},
		fields=["name", "user", "mobile_no", "current_company"],
		limit=20,
	)
	for row in rows:
		if _digits(row.mobile_no)[-9:] == tail and row.user:
			return row
	return None


def _text_of(message):
	if message.get("conversation"):
		return message["conversation"]
	return (message.get("extendedTextMessage") or {}).get("text") or ""


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
	if ((payload.get("data") or {}).get("key") or {}).get("fromMe"):
		return {"ok": True, "ignored": "from_me"}

	frappe.enqueue(
		"ftms.api.whatsapp.process_message",
		queue="short",
		timeout=900,
		payload=payload,
		enqueue_after_commit=False,
	)
	return {"ok": True, "queued": True}


def process_message(payload):
	data = payload.get("data") or {}
	key = data.get("key") or {}
	sender = key.get("remoteJidAlt") or key.get("remoteJid") or ""
	# Group and broadcast chats are not part of the captain flow.
	if sender.endswith("@g.us") or sender.endswith("@broadcast") or key.get("remoteJid", "").endswith("@g.us"):
		return
	phone = _digits(sender.split("@")[0])
	if not phone:
		return
	# One message at a time per phone: parallel workers were saving the same session.
	with frappe.cache().lock(f"wa_session_lock:{phone}", timeout=180):
		_process_message(payload)


def _process_message(payload):
	data = payload.get("data") or {}
	key = data.get("key") or {}
	message_id = key.get("id") or ""
	sender = key.get("remoteJidAlt") or key.get("remoteJid") or ""
	phone = _digits(sender.split("@")[0])
	if not phone:
		return
	if message_id and frappe.db.exists("WhatsApp Message Log", message_id):
		return

	message = data.get("message") or {}
	text = _text_of(message).strip()
	kind = "image" if "imageMessage" in message else ("text" if text else "other")
	_log_message(message_id, phone, kind, text)
	_trace(phone, "received", "Info", f"kind={kind}")

	captain = _find_captain(phone)
	if not captain:
		# Numbers that are not captains get no reply.
		_trace(phone, "ignored_not_captain", "Info", "no captain profile for this number")
		return

	session = _get_session(phone, captain)
	_trace(phone, "session", "Info", f"state={session.state or 'Start'}")
	if kind == "image":
		_handle_image(session, phone, key, message)
	else:
		_handle_text(session, phone, text.lower())


def _log_message(message_id, phone, kind, text):
	from frappe.exceptions import DuplicateEntryError

	name = message_id or frappe.generate_hash(length=20)
	try:
		frappe.get_doc({
			"doctype": "WhatsApp Message Log",
			"message_id": name,
			"phone": phone,
			"kind": kind,
			"body": text[:5000],
		}).insert(ignore_permissions=True)
	except DuplicateEntryError:
		frappe.db.rollback()


def _get_session(phone, captain):
	if frappe.db.exists("WhatsApp Session", phone):
		session = frappe.get_doc("WhatsApp Session", phone)
	else:
		session = frappe.get_doc({"doctype": "WhatsApp Session", "phone": phone, "state": "Start"})
		session.insert(ignore_permissions=True)
	session.captain = captain.name
	return session


def _save(session):
	session.save(ignore_permissions=True)


def _load_photos(session):
	try:
		rows = json.loads(session.photos or "[]")
	except ValueError:
		rows = []
	return rows if isinstance(rows, list) else []


def _unique(rows):
	seen = {}
	for row in rows:
		key = (row.get("document_number") or row.get("passenger_name") or "").strip().lower()
		if key and key not in seen:
			seen[key] = row
	return list(seen.values())


def _reset(session):
	session.state = "Help"
	session.language = "en"
	session.expected_count = 0
	session.photos = "[]"
	session.trip = None
	_save(session)


NEW_TRIP_WORDS = {"new", "نیو", "نیا", "نئی", "نیا ٹرپ", "نیا ٹرپ شروع"}


def _handle_text(session, phone, text):
	lang = session.language or "en"
	state = session.state or "Start"

	if text.strip() in NEW_TRIP_WORDS:
		_reset(session)
		_send(phone, WELCOME + "\n\n" + HELP)
		return

	if state == "Start":
		session.state = "Help"
		_save(session)
		_send(phone, WELCOME + "\n\n" + HELP)
		return

	if state == "Help":
		if text == "1":
			session.state = "Language"
			_save(session)
			_send(phone, LANG_MENU)
		else:
			_send(phone, HELP)
		return

	if state == "Language":
		if text in LANG_CHOICES:
			session.language = LANG_CHOICES[text]
			session.state = "Count"
			_save(session)
			_send(phone, _t(session.language, "ask_count"))
		else:
			_send(phone, LANG_MENU)
		return

	if state == "Count":
		if text.isdigit() and 1 <= int(text) <= 300:
			session.expected_count = int(text)
			session.state = "Photos"
			_save(session)
			_send(phone, _t(lang, "send_photos"))
		else:
			_send(phone, _t(lang, "expect_number"))
		return

	if state == "Photos":
		if text == "done":
			_reconcile(session, phone)
		else:
			_send(phone, _t(lang, "expect_photo"))
		return

	if state == "ConfirmMore":
		if text == "ok":
			_confirm_route_menu(session, phone)
		elif text.isdigit() and 1 <= int(text) <= 300:
			session.expected_count = int(text)
			_save(session)
			_reconcile(session, phone)
		else:
			_send(phone, _t(lang, "invalid_option"))
		return

	if state == "Route":
		_handle_route_choice(session, phone, text)
		return

	if state == "Done":
		_send(phone, _t(lang, "finished"))


def _reconcile(session, phone):
	lang = session.language or "en"
	rows = _load_photos(session)
	unique = _unique(rows)
	dupes = len(rows) - len(unique)
	expected = session.expected_count or 0
	count = len(unique)

	if count < expected:
		session.state = "Photos"
		_save(session)
		_send(phone, _t(lang, "need_more", expected=expected, count=count, missing=expected - count))
		return

	if count > expected:
		session.state = "ConfirmMore"
		_save(session)
		_send(phone, _t(lang, "more_than_expected", expected=expected, count=count))
		return

	if dupes:
		_send(phone, _t(lang, "dupes_note", dupes=dupes))
	_confirm_route_menu(session, phone)


def _route_rows(session):
	company = frappe.db.get_value("Captain Profile", session.captain, "current_company")
	if not company:
		return []
	return frappe.get_all(
		"Route",
		filters={"company": company},
		fields=["name", "route_title", "route_name", "source", "destination"],
		order_by="name asc",
		limit=9,
	)


def _route_label(row):
	label = row.get("route_title") or row.get("route_name")
	if not label and (row.get("source") or row.get("destination")):
		label = f"{row.get('source') or ''} → {row.get('destination') or ''}"
	return label or row.get("name")


def _confirm_route_menu(session, phone):
	lang = session.language or "en"
	count = len(_unique(_load_photos(session)))
	routes = _route_rows(session)
	if not routes:
		_send(phone, _t(lang, "no_routes"))
		return
	session.state = "Route"
	_save(session)
	lines = [f"{index}. {_route_label(row)}" for index, row in enumerate(routes, 1)]
	_send(phone, _t(lang, "count_confirmed", count=count) + "\n" + "\n".join(lines))


def _handle_route_choice(session, phone, text):
	lang = session.language or "en"
	routes = _route_rows(session)
	if not (text.isdigit() and 1 <= int(text) <= len(routes)):
		_send(phone, _t(lang, "route_invalid"))
		return
	route = routes[int(text) - 1]
	unique = _unique(_load_photos(session))
	captain_user = frappe.db.get_value("Captain Profile", session.captain, "user")
	company = frappe.db.get_value("Captain Profile", session.captain, "current_company")

	from ftms.api.trip import create_trip_with_passengers

	frappe.set_user(captain_user)
	try:
		trip = create_trip_with_passengers(
			trip_title=f"WhatsApp {nowdate()} {_route_label(route)}",
			trip_date=nowdate(),
			route=route.get("name"),
			assigned_captain_user=captain_user,
			company=company,
			status="Draft",
			passengers=[
				{
					"passenger_name": r.get("passenger_name"),
					"document_number": r.get("document_number"),
					"document_type": r.get("document_type"),
					"nationality": _country(r.get("nationality")),
					"source": "OCR",
				}
				for r in unique
			],
			notes="Created from WhatsApp",
		)
		trip_name = trip.get("name") if isinstance(trip, dict) else trip
		pdf_bytes = _trip_pdf(trip_name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "WhatsApp trip creation failed")
		_trace(phone, "trip_failed", "Error", "create_trip_with_passengers or PDF failed")
		_send(phone, _t(lang, "trip_failed"))
		return
	finally:
		frappe.set_user("Administrator")

	session.trip = trip_name
	session.state = "Done"
	_save(session)
	_send_pdf(phone, pdf_bytes, f"{trip_name}.pdf", _t(lang, "trip_created", trip=trip_name, count=len(unique)))
	_trace(phone, "trip_created", "OK", trip_name)


def _handle_image(session, phone, key, message):
	lang = session.language or "en"
	if session.state != "Photos":
		_send(phone, HELP if session.state in ("Start", "Help") else _t(lang, "expect_photo"))
		return

	from ftms.document_ai.service import extract_passenger_document

	media = _gateway(
		f"/chat/getBase64FromMediaMessage/{INSTANCE}",
		{"message": {"key": key, "message": message}, "convertToMp4": False},
	)
	b64 = media.get("base64") or ""
	mime = media.get("mimetype") or (message.get("imageMessage") or {}).get("mimetype") or "image/jpeg"
	if not b64:
		_send(phone, _t(lang, "extraction_failed"))
		return

	captain_user = frappe.db.get_value("Captain Profile", session.captain, "user")
	frappe.set_user(captain_user)
	try:
		result = extract_passenger_document(file_data=f"data:{mime};base64,{b64}", mime_type=mime)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "WhatsApp passenger extraction failed")
		_send(phone, _t(lang, "extraction_failed"))
		return
	finally:
		frappe.set_user("Administrator")

	rows = _load_photos(session)
	for row in result.get("passengers") or []:
		if any(row.get(k) for k in ("passenger_name", "document_number")):
			rows.append(row)
	session.photos = json.dumps(rows, ensure_ascii=False)
	_save(session)
	_send(phone, _t(lang, "photo_received", count=len(_unique(rows))))
