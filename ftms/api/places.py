from __future__ import annotations

import frappe
from frappe import _

from ftms.tenant import has_company_access, resolve_company


def _require_user():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)
    return user


@frappe.whitelist()
def save_place(title, latitude, longitude, source="Manual Pin", name_en=None, name_ar=None,
               address=None, place_type=None, google_place_id=None, region=None, city=None,
               company=None, notes=None):
    user = _require_user()
    company = resolve_company(company=company, allow_missing=True)
    if company and not has_company_access(company, user=user):
        frappe.throw(_("Not permitted for this company"), frappe.PermissionError)
    if source not in {"Google Places", "Manual Pin", "Local Registry"}:
        frappe.throw(_("Invalid place source"))
    latitude = float(latitude)
    longitude = float(longitude)
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        frappe.throw(_("Invalid coordinates"))
    doc = frappe.get_doc({
        "doctype": "Saved Place",
        "title": title,
        "user": user,
        "company": company,
        "source": source,
        "place_type": place_type,
        "google_place_id": google_place_id,
        "name_en": name_en or title,
        "name_ar": name_ar,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "region": region,
        "city": city,
        "notes": notes,
        "status": "Active",
    })
    doc.insert(ignore_permissions=True)
    return doc.as_dict()


@frappe.whitelist()
def list_saved_places(company=None, limit=100):
    user = _require_user()
    company = resolve_company(company=company, allow_missing=True)
    filters = {"user": user, "status": "Active"}
    if company:
        if not has_company_access(company, user=user):
            frappe.throw(_("Not permitted for this company"), frappe.PermissionError)
        filters["company"] = company
    return frappe.get_all(
        "Saved Place",
        filters=filters,
        fields=["name", "title", "source", "place_type", "google_place_id", "name_en", "name_ar", "address", "latitude", "longitude", "region", "city", "company", "notes"],
        order_by="modified desc",
        limit_page_length=int(limit or 100),
    )


@frappe.whitelist()
def archive_place(name):
    user = _require_user()
    doc = frappe.get_doc("Saved Place", name)
    if doc.user != user and not (doc.company and has_company_access(doc.company, user=user)):
        frappe.throw(_("Not permitted to archive this place"), frappe.PermissionError)
    doc.db_set("status", "Archived")
    return {"status": "Archived", "name": name}
