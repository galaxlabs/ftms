from __future__ import annotations

import frappe

from ftms.tenant import company_filters, resolve_company


@frappe.whitelist(allow_guest=True)
def overview(company=None):
	company = resolve_company(company=company, allow_missing=True)
	filters = company_filters(company=company)

	trip_count = frappe.db.count("Trip", filters=filters)
	booking_count = frappe.db.count("Trip Booking", filters=filters)
	invoice_where = ["1=1"]
	invoice_params = {}
	if company:
		invoice_where.append("company = %(company)s")
		invoice_params["company"] = company
	invoice_stats = frappe.db.sql(
		f"""
		SELECT COUNT(name) AS invoice_count, COALESCE(SUM(COALESCE(vat_amount, 0)), 0) AS vat_total
		FROM `tabTrip Invoice`
		WHERE {' AND '.join(invoice_where)}
		""",
		invoice_params,
		as_dict=True,
	)[0]
	invoice_count = int(invoice_stats.invoice_count or 0)
	vat_total = float(invoice_stats.vat_total or 0)

	return {
		"company": company,
		"cards": {
			"trips": trip_count,
			"bookings": booking_count,
			"invoices": invoice_count,
			"vat": round(vat_total, 2),
		},
		"activity": [
			{"label": f"Trips: {trip_count}", "time": "today"},
			{"label": f"Bookings: {booking_count}", "time": "today"},
			{"label": f"Invoices: {invoice_count}", "time": "today"},
		],
	}
