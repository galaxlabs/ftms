import frappe


@frappe.whitelist()
def generate_qr(trip_name):
	"""Generate QR code for public trip page."""
	trip = frappe.get_doc("Trip", trip_name)
	if not trip.public_uuid:
		import uuid
		trip.db_set("public_uuid", str(uuid.uuid4()))
		trip.reload()

	import pyqrcode
	public_url = f"{frappe.utils.get_url().rstrip('/')}/trip/{trip.public_uuid.lstrip('/')}"
	qr = pyqrcode.create(public_url)
	data_uri = "data:image/png;base64," + qr.png_as_base64_str(scale=6)
	trip.db_set("qr_code", data_uri)

	return {"qr_code": data_uri, "public_url": public_url, "uuid": trip.public_uuid}


@frappe.whitelist()
def get_public_url(trip_name):
	"""Get the public trip page URL for a trip."""
	uuid = frappe.db.get_value("Trip", trip_name, "public_uuid")
	if not uuid:
		import uuid as _uuid
		uuid = str(_uuid.uuid4())
		frappe.db.set_value("Trip", trip_name, "public_uuid", uuid)
	return {"url": f"{frappe.utils.get_url().rstrip('/')}/trip/{uuid.lstrip('/')}"}
