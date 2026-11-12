import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate, flt


def _expiry_rows(doctype, name_field, owner_label, fields, owner_value):
	rows = []
	today = getdate(nowdate())
	limit = getdate(add_days(nowdate(), 30))
	meta = frappe.get_meta(doctype)
	valid = [(f, l) for f, l in fields if meta.has_field(f)]
	if not valid:
		return rows
	docs = frappe.get_all(doctype, filters=owner_value, fields=["name"] + [f for f, _l in valid], limit=50)
	for doc in docs:
		for fieldname, label in valid:
			expiry = doc.get(fieldname)
			if not expiry:
				continue
			expiry = getdate(expiry)
			if expiry <= limit:
				rows.append({
					"doctype": doctype,
					"name": doc.name,
					"owner": owner_label,
					"document": label,
					"expiry_date": str(expiry),
					"days_left": (expiry - today).days,
				})
	return rows


@frappe.whitelist()
def get_driver_home():
	"""Summary for the driver home screen: today's trips and earnings, and documents expiring within 30 days."""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Login is required"), frappe.PermissionError)

	today = nowdate()
	trips = frappe.get_all(
		"Trip",
		filters={"assigned_captain_user": user, "trip_date": today, "trip_status": "Completed"},
		fields=["name", "trip_value", "driver_commission_amount"],
		limit=500,
	)
	gross = sum(flt(t.trip_value) for t in trips)
	company_share = sum(flt(t.driver_commission_amount) for t in trips)

	expiring = []
	profile = frappe.db.get_value("Captain Profile", {"user": user}, "name")
	if profile:
		expiring += _expiry_rows(
			"Captain Profile", "name", "driver",
			[
				("iqama_expiry_date", "Iqama"),
				("license_expiry_date", "Driving license"),
				("driver_card_expiry_date", "Driver card"),
			],
			{"name": profile},
		)
	expiring += _expiry_rows(
		"Vehicle", "name", "vehicle",
		[
			("registration_expiry_date", "Vehicle registration"),
			("insurance_expiry_date", "Insurance"),
			("operation_card_expiry_date", "Operation card"),
		],
		{"assigned_captain_user": user},
	)
	expiring.sort(key=lambda r: r["days_left"])

	return {
		"trips_today": len(trips),
		"gross_today": round(gross, 2),
		"company_share_today": round(company_share, 2),
		"driver_share_today": round(gross - company_share, 2),
		"expiring_documents": expiring,
	}
