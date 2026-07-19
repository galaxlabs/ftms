from __future__ import annotations

import frappe

from ftms.tenant import company_filters, resolve_company


@frappe.whitelist()
def list_expenses(company=None, limit=50):
	filters = company_filters(company=company)
	return frappe.get_all(
		"Trip Expense",
		filters=filters,
		fields=[
			"name", "company", "trip", "captain_user", "vehicle", "expense_date", "status",
			"expense_type", "supplier_name", "supplier_vat_no", "invoice_no",
			"net_amount", "vat_amount", "total_amount", "receipt_validation_status",
			"company_name_match", "ocr_company_name", "ocr_company_name_ar", "ocr_invoice_no",
			"ocr_total_amount", "ocr_vat_amount", "attachment", "approved_by", "approved_on", "paid_on",
		],
		order_by="expense_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_expense(name, company=None):
	doc = frappe.get_doc("Trip Expense", name)
	resolved_company = resolve_company(company=company, allow_missing=True)
	if resolved_company and doc.company != resolved_company:
		frappe.throw("Not permitted for this company")
	return doc.as_dict()
