import frappe
from frappe.utils import nowdate, today

@frappe.whitelist()
def setup_chart_of_accounts(company):
    if not company:
        return
    accounts = [
        {"account_name": "Assets", "parent_account": None, "is_group": 1, "root_type": "Asset"},
        {"account_name": "Current Assets", "parent_account": "Assets", "is_group": 1, "root_type": "Asset"},
        {"account_name": "Cash", "parent_account": "Current Assets", "is_group": 0, "account_type": "Cash", "root_type": "Asset"},
        {"account_name": "Bank", "parent_account": "Current Assets", "is_group": 0, "account_type": "Bank", "root_type": "Asset"},
        {"account_name": "Debtors", "parent_account": "Current Assets", "is_group": 0, "account_type": "Receivable", "root_type": "Asset"},
        {"account_name": "Stock Assets", "parent_account": "Current Assets", "is_group": 0, "account_type": "Stock", "root_type": "Asset"},
        {"account_name": "Fixed Assets", "parent_account": "Assets", "is_group": 1, "root_type": "Asset"},
        {"account_name": "Vehicles", "parent_account": "Fixed Assets", "is_group": 0, "account_type": "Fixed Asset", "root_type": "Asset"},
        {"account_name": "Liabilities", "parent_account": None, "is_group": 1, "root_type": "Liability"},
        {"account_name": "Current Liabilities", "parent_account": "Liabilities", "is_group": 1, "root_type": "Liability"},
        {"account_name": "Creditors", "parent_account": "Current Liabilities", "is_group": 0, "account_type": "Payable", "root_type": "Liability"},
        {"account_name": "VAT Payable", "parent_account": "Current Liabilities", "is_group": 0, "account_type": "Tax", "root_type": "Liability"},
        {"account_name": "Accrued Expenses", "parent_account": "Current Liabilities", "is_group": 0, "root_type": "Liability"},
        {"account_name": "VAT Input", "parent_account": "Current Assets", "is_group": 0, "account_type": "Tax", "root_type": "Asset"},
        {"account_name": "Income", "parent_account": None, "is_group": 1, "root_type": "Income"},
        {"account_name": "Transport Revenue", "parent_account": "Income", "is_group": 0, "account_type": "Income Account", "root_type": "Income"},
        {"account_name": "Service Income", "parent_account": "Income", "is_group": 0, "account_type": "Income Account", "root_type": "Income"},
        {"account_name": "Expenses", "parent_account": None, "is_group": 1, "root_type": "Expense"},
        {"account_name": "Fuel Expenses", "parent_account": "Expenses", "is_group": 0, "account_type": "Expense Account", "root_type": "Expense"},
        {"account_name": "Vehicle Maintenance", "parent_account": "Expenses", "is_group": 0, "account_type": "Expense Account", "root_type": "Expense"},
        {"account_name": "Salaries", "parent_account": "Expenses", "is_group": 0, "account_type": "Expense Account", "root_type": "Expense"},
        {"account_name": "Rent", "parent_account": "Expenses", "is_group": 0, "account_type": "Expense Account", "root_type": "Expense"},
        {"account_name": "Utilities", "parent_account": "Expenses", "is_group": 0, "account_type": "Expense Account", "root_type": "Expense"},
        {"account_name": "Other Expenses", "parent_account": "Expenses", "is_group": 0, "account_type": "Expense Account", "root_type": "Expense"},
        {"account_name": "Equity", "parent_account": None, "is_group": 1, "account_type": "Equity", "root_type": "Equity"},
        {"account_name": "Opening Balance", "parent_account": "Equity", "is_group": 0, "account_type": "Equity", "root_type": "Equity"},
        {"account_name": "Retained Earnings", "parent_account": "Equity", "is_group": 0, "account_type": "Equity", "root_type": "Equity"},
    ]

    name_map = {}
    created = []
    for acc in accounts:
        pname = acc["account_name"]
        existing = frappe.db.get_value("Account", {"account_name": pname, "company": company})
        if existing:
            name_map[pname] = existing
            continue
        parent = None
        if acc["parent_account"]:
            parent = name_map.get(acc["parent_account"])
        doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": pname,
            "parent_account": parent,
            "is_group": acc["is_group"],
            "account_type": acc.get("account_type"),
            "company": company,
            "root_type": acc["root_type"],
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        name_map[pname] = doc.name
        created.append(doc.name)

    def _get(name):
        return name_map.get(name)

    frappe.db.set_value("Company", company, "default_cash_account", _get("Cash"))
    frappe.db.set_value("Company", company, "default_receivable_account", _get("Debtors"))
    frappe.db.set_value("Company", company, "default_payable_account", _get("Creditors"))
    frappe.db.set_value("Company", company, "default_income_account", _get("Transport Revenue"))
    frappe.db.set_value("Company", company, "default_expense_account", _get("Other Expenses"))
    frappe.db.set_value("Company", company, "vat_output_account", _get("VAT Payable"))
    frappe.db.set_value("Company", company, "vat_input_account", _get("VAT Input"))

    frappe.db.commit()
    return "Created " + str(len(created)) + " accounts for " + company

def auto_setup_accounts(doc, method=None):
    if method != "after_insert":
        return
    setup_chart_of_accounts(doc.name)

def calc_line_amounts(doc):
    for field in ("items",):
        if doc.meta.has_field(field):
            for row in doc.get(field, []):
                row.amount = (row.qty or 0) * (row.rate or 0)
            if doc.meta.has_field("total"):
                doc.total = sum((r.amount or 0) for r in doc.get(field, []))

def calc_vat(doc):
    if not doc.meta.has_field("vat_amount"):
        return
    net = 0
    vat = 0
    for row in doc.get("items", []):
        amt = row.amount or 0
        vr = (row.get("vat_rate") or 0)
        net += amt
        vat += amt * vr / 100.0
    doc.vat_amount = vat
    if doc.meta.has_field("grand_total"):
        doc.grand_total = net + vat if doc.vat_type == "Exclusive" else net
    if doc.meta.has_field("total"):
        doc.total = net

@frappe.whitelist()
def get_unpaid_invoices(party_type, party):
    doctype = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"
    if not frappe.db.exists("DocType", doctype):
        return []
    party_field = "customer" if party_type == "Customer" else "supplier"
    return frappe.db.get_all(doctype,
        filters={"docstatus": 1, "outstanding": [">", 0], party_field: party},
        fields=["name", "posting_date", "total", "outstanding"],
        order_by="posting_date"
    )

def update_outstanding_from_payments(doc, method=None):
    if method == "on_submit":
        for ref in doc.references:
            inv = frappe.get_doc(ref.reference_type, ref.reference_name)
            gt = inv.grand_total or inv.total or 0
            new_outstanding = max(0, (inv.outstanding or gt) - (ref.allocated or 0))
            new_paid = (inv.paid_amount or 0) + (ref.allocated or 0)
            frappe.db.set_value(ref.reference_type, ref.reference_name, {
                "outstanding": new_outstanding,
                "paid_amount": new_paid,
                "balance": new_outstanding - new_paid,
                "status": "Paid" if new_outstanding <= 0 else "Submitted"
            })
    elif method == "on_cancel":
        for ref in doc.references:
            inv = frappe.get_doc(ref.reference_type, ref.reference_name)
            new_outstanding = (inv.outstanding or 0) + (ref.allocated or 0)
            new_paid = max(0, (inv.paid_amount or 0) - (ref.allocated or 0))
            frappe.db.set_value(ref.reference_type, ref.reference_name, {
                "outstanding": new_outstanding,
                "paid_amount": new_paid,
                "balance": new_outstanding - new_paid,
                "status": "Submitted"
            })
