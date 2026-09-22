import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

PRIVILEGED_ROLES = {"System Manager"}


def _is_system_reviewer(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or bool(PRIVILEGED_ROLES.intersection(frappe.get_roles(user)))


def _is_company_reviewer(company, user=None):
    user = user or frappe.session.user
    if _is_system_reviewer(user):
        return True
    if not company:
        return False
    link = frappe.db.get_value(
        "User Company Link",
        {"user": user, "company": company, "status": "Active"},
        ["role", "is_owner"],
        as_dict=True,
    )
    return bool(link and (link.is_owner or link.role == "Company Admin"))


def get_permission_query_conditions(user):
    if _is_system_reviewer(user):
        return ""
    reviewer_links = frappe.get_all(
        "User Company Link",
        filters={"user": user, "status": "Active"},
        or_filters={"role": "Company Admin", "is_owner": 1},
        fields=["company"],
    )
    conditions = [f"`tabVehicle Inspection Log`.`captain_user` = {frappe.db.escape(user)}"]
    companies = [link.company for link in reviewer_links]
    if companies:
        escaped = ", ".join(frappe.db.escape(company) for company in companies)
        conditions.append(f"`tabVehicle Inspection Log`.`company` IN ({escaped})")
    return f"({' OR '.join(conditions)})"


def has_permission(doc, ptype, user):
    if _is_system_reviewer(user):
        return True
    if doc.captain_user == user:
        return ptype not in ("delete", "share", "export", "submit", "cancel", "amend")
    return _is_company_reviewer(doc.company, user) and ptype in ("read", "write", "print", "email")


def _get_master_checklist():
    return frappe.get_all(
        "Vehicle Inspection Checklist Item",
        filters={"is_active": 1},
        fields=["name", "category", "sort_order", "item"],
        order_by="category asc, sort_order asc, creation asc",
    )


@frappe.whitelist()
def get_checklist_rows():
    rows = []
    for m in _get_master_checklist():
        rows.append(
            {
                "section": m.category or "",
                "item_en": m.name,            # Link to master doc
                "category": m.category or "",
                "item": m.item or "",
                "sort_order": m.sort_order or 0,
                "status": "Sound | سليم",
            }
        )
    return rows


class VehicleInspectionLog(Document):
    def validate(self):
        self._validate_locked_record()
        self._validate_vehicle_scope()
        self._validate_trip_scope()
        if self.status == "Submitted" and not self.submitted_on:
            self.submitted_on = now_datetime()

    def before_insert(self):
        # If user already has rows, don't overwrite
        if self.items:
            return

        # only auto-fill if checkbox enabled
        if int(self.auto_fill_checklist or 0) != 1:
            return

        for r in get_checklist_rows():
            row = self.append("items", {})
            row.section = r["section"]
            row.item_en = r["item_en"]      # ✅ correct child fieldname
            row.category = r["category"]
            row.item = r["item"]
            row.sort_order = r["sort_order"]
            row.status = r["status"]

    def after_insert(self):
        if self.inspection_no != self.name:
            self.db_set("inspection_no", self.name, update_modified=False)

    def _validate_locked_record(self):
        previous = self.get_doc_before_save()
        if previous and previous.status != "Draft" and not _is_company_reviewer(previous.company):
            frappe.throw(_("Submitted inspections can only be changed by an authorized reviewer"), frappe.PermissionError)
        if not _is_company_reviewer(self.company):
            if self.status not in ("Draft", "Submitted"):
                frappe.throw(_("Captains may only draft or submit an inspection"), frappe.PermissionError)
            if self.captain_user and self.captain_user != frappe.session.user:
                frappe.throw(_("You may only create your own inspection"), frappe.PermissionError)

    def _validate_vehicle_scope(self):
        if not self.vehicle:
            return
        vehicle = frappe.db.get_value(
            "Vehicle",
            self.vehicle,
            ["company", "owner_captain_user", "assigned_captain_user", "vehicle_type"],
            as_dict=True,
        )
        if not vehicle:
            frappe.throw(_("Selected vehicle does not exist"))
        captain_user = self.captain_user or frappe.session.user
        if not _is_system_reviewer() and captain_user not in (
            vehicle.owner_captain_user,
            vehicle.assigned_captain_user,
        ):
            frappe.throw(_("The vehicle is not owned by or assigned to this captain"), frappe.PermissionError)
        if self.company and self.company != vehicle.company:
            frappe.throw(_("Inspection company must match the vehicle company"), frappe.PermissionError)
        if vehicle.company:
            if not frappe.db.exists(
                "User Company Link",
                {"user": captain_user, "company": vehicle.company, "status": "Active"},
            ) and not _is_system_reviewer():
                frappe.throw(_("Captain has no active membership in the vehicle company"), frappe.PermissionError)
            self.company = vehicle.company
        elif self.company:
            frappe.throw(_("A privately owned vehicle cannot be inspected under another company"), frappe.PermissionError)
        self.captain_user = captain_user
        self.vehicle_type = vehicle.vehicle_type

    def _validate_trip_scope(self):
        if not self.trip:
            if self.route:
                route_company = frappe.db.get_value("Route", self.route, "company")
                if route_company != self.company:
                    frappe.throw(_("Inspection route must belong to the inspection company"), frappe.PermissionError)
            return
        trip = frappe.db.get_value(
            "Trip",
            self.trip,
            ["company", "route", "vehicle", "assigned_captain_user"],
            as_dict=True,
        )
        if not trip:
            frappe.throw(_("Selected trip does not exist"))
        if trip.assigned_captain_user != self.captain_user:
            frappe.throw(_("Kashf trip must be assigned to this captain"), frappe.PermissionError)
        if trip.company != self.company:
            frappe.throw(_("Kashf trip and vehicle companies must match"), frappe.PermissionError)
        if trip.vehicle != self.vehicle:
            frappe.throw(_("Kashf vehicle must match the assigned trip vehicle"), frappe.PermissionError)
        self.route = trip.route
