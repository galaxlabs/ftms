from __future__ import annotations

import frappe

def before_migrate():
    prohibit_erpnext()
    rename_transportation_company_doctype()

def after_install():
    prohibit_erpnext()
    ensure_settings()
    create_custom_fields()

def after_migrate():
    prohibit_erpnext()
    ensure_settings()
    sync_customizations()
    create_custom_fields()
    seed_existing_subscriptions()
    sync_print_branding()
    seed_ksa_cities()

def prohibit_erpnext():
    if "erpnext" in frappe.get_installed_apps():
        frappe.throw("FTMS is standalone and cannot be installed on a site with ERPNext.")

def rename_transportation_company_doctype():
    if not frappe.db.exists("DocType", "Transportation Company"):
        return
    if frappe.db.exists("DocType", "Company"):
        company_module = frappe.db.get_value("DocType", "Company", "module")
        if company_module not in {"Transport System", "FTMS"}:
            frappe.throw("Cannot rename Transportation Company to Company because another Company DocType already exists.")
        return
    if frappe.db.table_exists("Company"):
        frappe.throw("Cannot rename Transportation Company to Company because tabCompany already exists.")

    frappe.db.sql("UPDATE `tabDocType` SET name='Company', module='Transport System' WHERE name='Transportation Company'")
    frappe.db.sql("UPDATE `tabDocField` SET parent='Company' WHERE parent='Transportation Company'")
    frappe.db.sql("UPDATE `tabDocPerm` SET parent='Company' WHERE parent='Transportation Company'")
    frappe.db.sql("UPDATE `tabDocField` SET options='Company' WHERE options='Transportation Company'")
    frappe.db.sql("UPDATE `tabCustom Field` SET dt='Company' WHERE dt='Transportation Company'")
    frappe.db.sql("UPDATE `tabCustom Field` SET options='Company' WHERE options='Transportation Company'")
    frappe.db.sql("UPDATE `tabProperty Setter` SET doc_type='Company' WHERE doc_type='Transportation Company'")
    frappe.db.sql("UPDATE `tabProperty Setter` SET value='Company' WHERE value='Transportation Company'")
    frappe.db.sql("UPDATE `tabDocShare` SET share_doctype='Company' WHERE share_doctype='Transportation Company'")
    frappe.db.sql("RENAME TABLE `tabTransportation Company` TO `tabCompany`")
    frappe.clear_cache(doctype="Company")
    frappe.db.commit()

def sync_print_branding():
    from ftms.printing.letterhead import sync_all_letterheads
    sync_all_letterheads()

def seed_existing_subscriptions():
    """Create trial subscriptions for existing active User Company Links."""
    from ftms.subscriptions.utils import create_subscription_on_link
    links = frappe.get_all("User Company Link",
        filters={"status": "Active"},
        fields=["name", "user", "company"],
    )
    for link in links:
        existing = frappe.db.exists("User Subscription", {
            "user": link.user,
            "company": link.company,
        })
        if not existing:
            doc = frappe.get_doc("User Company Link", link.name)
            create_subscription_on_link(doc, None)
    if links:
        frappe.db.commit()

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
        {"dt": "User", "fieldname": "ftms_identity_section", "fieldtype": "Section Break", "label": "FTMS Identity", "insert_after": "mobile_no"},
        {"dt": "User", "fieldname": "ftms_id_document_type", "fieldtype": "Select", "label": "ID Document Type", "options": "National ID\nIqama\nPassport\nGCC ID\nOther", "insert_after": "ftms_identity_section"},
        {"dt": "User", "fieldname": "ftms_id_no", "fieldtype": "Data", "label": "ID No", "insert_after": "ftms_id_document_type"},
        {"dt": "User", "fieldname": "ftms_nationality", "fieldtype": "Data", "label": "Nationality", "insert_after": "ftms_id_no"},
        {"dt": "User", "fieldname": "ftms_id_expiry_date", "fieldtype": "Date", "label": "ID Expiry Date", "insert_after": "ftms_nationality"},
        {"dt": "User", "fieldname": "ftms_id_document", "fieldtype": "Attach", "label": "ID Document", "insert_after": "ftms_id_expiry_date"},
    ]
    for cf in custom_fields:
        dt = cf.pop("dt")
        if not frappe.db.exists("DocType", dt):
            continue
        fieldname = cf["fieldname"]
        if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
            existing = frappe.get_doc("Custom Field", {"dt": dt, "fieldname": fieldname})
            existing.update(cf)
            existing.save()
        else:
            doc = frappe.get_doc({"doctype": "Custom Field", "dt": dt, **cf})
            doc.insert(ignore_links=True)
    frappe.db.commit()


def seed_ksa_cities():
    from ftms.setup.seed_ksa_cities import seed
    seed()
