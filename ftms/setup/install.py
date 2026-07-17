from __future__ import annotations

import frappe

def after_install():
    ensure_settings()
    create_custom_fields()

def after_migrate():
    ensure_settings()
    sync_customizations()
    create_custom_fields()

def ensure_settings():
    if not frappe.db.exists("Transport Settings", "Transport Settings"):
        frappe.get_doc({"doctype": "Transport Settings"}).insert(ignore_permissions=True)
    if not frappe.db.exists("Tenant Policy", "Tenant Policy"):
        frappe.get_doc({"doctype": "Tenant Policy", "domain": ""}).insert(ignore_permissions=True)

def sync_customizations():
    from frappe.modules.utils import sync_customizations
    sync_customizations("ftms")

def create_custom_fields():
    custom_fields = [
        {"dt": "Address", "fieldname": "sb_location", "fieldtype": "Section Break", "label": "Location & Map", "insert_after": "email_id"},
        {"dt": "Address", "fieldname": "latitude", "fieldtype": "Float", "label": "Latitude", "insert_after": "sb_location"},
        {"dt": "Address", "fieldname": "longitude", "fieldtype": "Float", "label": "Longitude", "insert_after": "latitude"},
        {"dt": "Address", "fieldname": "map_view", "fieldtype": "HTML", "label": "Map View", "insert_after": "longitude", "read_only": 1},
        {"dt": "Address", "fieldname": "sb_zatca", "fieldtype": "Section Break", "label": "Saudi Address (ZATCA)", "insert_after": "map_view"},
        {"dt": "Address", "fieldname": "building_no", "fieldtype": "Data", "label": "Building Number", "insert_after": "sb_zatca", "length": 4},
        {"dt": "Address", "fieldname": "street_name", "fieldtype": "Data", "label": "Street Name", "insert_after": "building_no"},
        {"dt": "Address", "fieldname": "district", "fieldtype": "Data", "label": "District", "insert_after": "street_name"},
        {"dt": "Address", "fieldname": "additional_no", "fieldtype": "Data", "label": "Additional Number", "insert_after": "district"},
        {"dt": "Sales Invoice", "fieldname": "sb_zatca", "fieldtype": "Section Break", "label": "ZATCA E-Invoicing", "insert_after": "taxes_and_charges"},
        {"dt": "Sales Invoice", "fieldname": "custom_is_zatca_test", "fieldtype": "Check", "label": "Is ZATCA Test Invoice", "insert_after": "sb_zatca"},
        {"dt": "Sales Invoice", "fieldname": "custom_compliance", "fieldtype": "Link", "label": "Compliance CSID", "options": "Compliance CSID", "insert_after": "custom_is_zatca_test"},
        {"dt": "Sales Invoice", "fieldname": "custom_zatca_submit_status", "fieldtype": "Data", "label": "ZATCA Submit Status", "read_only": 1, "insert_after": "custom_compliance"},
        {"dt": "Sales Invoice", "fieldname": "custom_invoice_type", "fieldtype": "Data", "label": "ZATCA Invoice Type", "read_only": 1, "insert_after": "custom_zatca_submit_status"},
        {"dt": "Sales Invoice", "fieldname": "custom_invoice_hash", "fieldtype": "Data", "label": "ZATCA Invoice Hash", "read_only": 1, "insert_after": "custom_invoice_type"},
        {"dt": "Sales Invoice", "fieldname": "custom_invoice_unique_identifier", "fieldtype": "Data", "label": "ZATCA Invoice UUID", "read_only": 1, "insert_after": "custom_invoice_hash"},
        {"dt": "Sales Invoice", "fieldname": "custom_invoice_icv", "fieldtype": "Int", "label": "ZATCA ICV", "read_only": 1, "insert_after": "custom_invoice_unique_identifier"},
        {"dt": "Sales Invoice", "fieldname": "custom_zatca_submit_time", "fieldtype": "Datetime", "label": "ZATCA Submit Time", "read_only": 1, "insert_after": "custom_invoice_icv"},
        {"dt": "Sales Invoice", "fieldname": "custom_seller_name", "fieldtype": "Data", "label": "ZATCA Seller Name", "read_only": 1, "insert_after": "custom_zatca_submit_time"},
        {"dt": "Sales Invoice", "fieldname": "custom_seller_vat", "fieldtype": "Data", "label": "ZATCA Seller VAT", "read_only": 1, "insert_after": "custom_seller_name"},
        {"dt": "Sales Invoice", "fieldname": "custom_buyer_name", "fieldtype": "Data", "label": "ZATCA Buyer Name", "read_only": 1, "insert_after": "custom_seller_vat"},
        {"dt": "Sales Invoice", "fieldname": "custom_buyer_vat", "fieldtype": "Data", "label": "ZATCA Buyer VAT", "read_only": 1, "insert_after": "custom_buyer_name"},
        {"dt": "Sales Invoice", "fieldname": "custom_invoice_xml", "fieldtype": "Code", "label": "ZATCA Invoice XML", "read_only": 1, "insert_after": "custom_buyer_vat"},
        {"dt": "Sales Invoice", "fieldname": "custom_invoice_qr_code", "fieldtype": "Code", "label": "ZATCA QR Code", "read_only": 1, "insert_after": "custom_invoice_xml"},
        {"dt": "Sales Invoice", "fieldname": "custom_validation_results", "fieldtype": "Long Text", "label": "ZATCA Validation Results", "read_only": 1, "insert_after": "custom_invoice_qr_code"},
    ]
    for cf in custom_fields:
        dt = cf.pop("dt")
        fieldname = cf["fieldname"]
        if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
            existing = frappe.get_doc("Custom Field", {"dt": dt, "fieldname": fieldname})
            existing.update(cf)
            existing.save()
        else:
            doc = frappe.get_doc({"doctype": "Custom Field", "dt": dt, **cf})
            doc.insert(ignore_links=True)
    frappe.db.commit()
