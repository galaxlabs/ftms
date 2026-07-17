import frappe

@frappe.whitelist()
def trial_balance(from_date, to_date, company=None):
    filters = {"posting_date": ["between", [from_date, to_date]], "is_cancelled": 0}
    if company:
        filters["company"] = company
    entries = frappe.db.get_all("GL Entry",
        filters=filters,
        fields=["account", "sum(debit) as total_debit", "sum(credit) as total_credit"],
        group_by="account"
    )
    result = []
    for e in entries:
        balance = e.total_debit - e.total_credit
        result.append({
            "account": e.account,
            "debit": e.total_debit,
            "credit": e.total_credit,
            "balance": balance
        })
    return result

@frappe.whitelist()
def profit_and_loss(from_date, to_date, company=None):
    filters = {"posting_date": ["between", [from_date, to_date]], "is_cancelled": 0}
    if company:
        filters["company"] = company
    income_accounts = frappe.db.get_all("Account", filters={"root_type": "Income"}, pluck="name")
    expense_accounts = frappe.db.get_all("Account", filters={"root_type": "Expense"}, pluck="name")
    total_income = 0
    total_expense = 0
    income_details = []
    expense_details = []
    for acc in income_accounts:
        f = dict(filters, account=acc)
        bal = frappe.db.get_value("GL Entry", f, "sum(credit) - sum(debit)")
        if bal:
            total_income += bal
            income_details.append({"account": acc, "amount": bal})
    for acc in expense_accounts:
        f = dict(filters, account=acc)
        bal = frappe.db.get_value("GL Entry", f, "sum(debit) - sum(credit)")
        if bal:
            total_expense += bal
            expense_details.append({"account": acc, "amount": bal})
    return {
        "income": income_details,
        "total_income": total_income,
        "expenses": expense_details,
        "total_expense": total_expense,
        "net_profit": total_income - total_expense
    }

@frappe.whitelist()
def balance_sheet(from_date, to_date, company=None):
    filters = {"posting_date": ["<=", to_date], "is_cancelled": 0}
    if company:
        filters["company"] = company
    asset_accounts = frappe.db.get_all("Account", filters={"root_type": "Asset"}, pluck="name")
    liability_accounts = frappe.db.get_all("Account", filters={"root_type": "Liability"}, pluck="name")
    equity_accounts = frappe.db.get_all("Account", filters={"root_type": "Equity"}, pluck="name")
    return {
        "assets": _get_balances(asset_accounts, filters),
        "liabilities": _get_balances(liability_accounts, filters),
        "equity": _get_balances(equity_accounts, filters),
    }

def _get_balances(accounts, filters):
    result = []
    for acc in accounts:
        f = dict(filters, account=acc)
        debit = frappe.db.get_value("GL Entry", f, "sum(debit)") or 0
        credit = frappe.db.get_value("GL Entry", f, "sum(credit)") or 0
        result.append({"account": acc, "balance": debit - credit})
    return result
