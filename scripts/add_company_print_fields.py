import frappe, os
os.chdir("/home/dg/dev-b/sites")
frappe.init(site="ftms.galaxylabs.online")
frappe.connect()

fields = [
    ("print_font_en", "Print Font (English)", "Data", "Ubuntu", "company_description"),
    ("print_font_ar", "Print Font (Arabic)", "Data", "Cairo", "print_font_en"),
    ("print_header_size_en", "Header Font Size EN (px)", "Int", 16, "print_font_ar"),
    ("print_header_size_ar", "Header Font Size AR (px)", "Int", 22, "print_header_size_en"),
    ("print_body_size", "Body Font Size (px)", "Int", 11, "print_header_size_ar"),
    ("print_table_header_bg", "Table Header BG Color", "Data", "#07417b", "print_body_size"),
]

for fn, label, ft, default, after in fields:
    if frappe.db.exists("Custom Field", {"dt": "Company", "fieldname": fn}):
        print(f"Exists: {fn}")
        continue
    cf = frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "Company",
        "fieldname": fn,
        "label": label,
        "fieldtype": ft,
        "default": default,
        "insert_after": after,
    })
    cf.insert(ignore_permissions=True)
    print(f"Added: {fn}")

frappe.db.commit()
frappe.db.close()
print("Done")
