import frappe
from frappe import _

from ftms.accounts.api.reports import trial_balance, profit_and_loss, balance_sheet
from ftms.accounts.utils import setup_chart_of_accounts, get_unpaid_invoices

@frappe.whitelist()
def setup_accounts(company):
    return setup_chart_of_accounts(company)

@frappe.whitelist()
def get_trial_balance(from_date, to_date, company=None):
    return trial_balance(from_date, to_date, company)

@frappe.whitelist()
def get_profit_and_loss(from_date, to_date, company=None):
    return profit_and_loss(from_date, to_date, company)

@frappe.whitelist()
def get_balance_sheet(from_date, to_date, company=None):
    return balance_sheet(from_date, to_date, company)

@frappe.whitelist()
def get_unpaid_customer_invoices(customer):
    return get_unpaid_invoices("Customer", customer)

@frappe.whitelist()
def get_unpaid_supplier_invoices(supplier):
    return get_unpaid_invoices("Supplier", supplier)
