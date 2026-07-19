import frappe
from frappe import _

SYSTEM_USERS = {"Administrator", "Guest"}


def validate_user_access(doc, method):
    """Enforce data isolation: user must be linked to the document's company."""
    user = frappe.session.user
    if user in SYSTEM_USERS:
        return
    if not doc.meta.has_field("company"):
        return
    link = get_active_link(user)
    if not link:
        frappe.throw(_("No active company link. Contact your company admin."))
    doc_company = doc.get("company")
    if doc_company and doc_company != link.company:
        frappe.throw(_("Permission denied for company: {0}").format(doc_company))


def get_permission_query_conditions(user):
    """Filter list queries by user's company."""
    if user in SYSTEM_USERS:
        return ""
    link = get_active_link(user)
    if not link:
        return "1=0"
    return f"(`tabTrip`.`company` = {frappe.db.escape(link.company)})"


def get_permission_query_conditions_for_company_doc(user, doctype):
    if user in SYSTEM_USERS:
        return ""
    link = get_active_link(user)
    if not link:
        return "1=0"
    return f"(`tab{doctype}`.`company` = {frappe.db.escape(link.company)})"


def get_permission_query_conditions_for_trip(user):
    if user in SYSTEM_USERS:
        return ""
    link = get_active_link(user)
    if not link:
        return "1=0"
    company = frappe.db.escape(link.company)
    if link.role == "Captain":
        return f"(`tabTrip`.`company` = {company} AND `tabTrip`.`assigned_captain_user` = {frappe.db.escape(user)})"
    return f"(`tabTrip`.`company` = {company})"


def get_permission_query_conditions_for_vehicle(user):
    if user in SYSTEM_USERS:
        return ""
    link = get_active_link(user)
    if not link:
        return "1=0"
    company = frappe.db.escape(link.company)
    if link.role == "Captain":
        return f"(`tabVehicle`.`company` = {company} AND `tabVehicle`.`assigned_captain_user` = {frappe.db.escape(user)})"
    return f"(`tabVehicle`.`company` = {company})"


def get_permission_query_conditions_for_trip_expense(user):
    if user in SYSTEM_USERS:
        return ""
    link = get_active_link(user)
    if not link:
        return "1=0"
    company = frappe.db.escape(link.company)
    if link.role == "Captain":
        return f"(`tabTrip Expense`.`company` = {company} AND `tabTrip Expense`.`captain_user` = {frappe.db.escape(user)})"
    return f"(`tabTrip Expense`.`company` = {company})"


def get_permission_query_conditions_for_vehicle_assignment(user):
    if user in SYSTEM_USERS:
        return ""
    link = get_active_link(user)
    if not link:
        return "1=0"
    company = frappe.db.escape(link.company)
    if link.role == "Captain":
        return f"(`tabVehicle Assignment`.`company` = {company} AND `tabVehicle Assignment`.`captain_user` = {frappe.db.escape(user)})"
    return f"(`tabVehicle Assignment`.`company` = {company})"


def get_permission_query_conditions_for_trip_invoice(user):
    if user in SYSTEM_USERS:
        return ""
    link = get_active_link(user)
    if not link:
        return "1=0"
    company = frappe.db.escape(link.company)
    if link.role == "Captain":
        return f"(`tabTrip Invoice`.`company` = {company} AND EXISTS (SELECT 1 FROM `tabTrip` WHERE `tabTrip`.`name` = `tabTrip Invoice`.`trip` AND `tabTrip`.`assigned_captain_user` = {frappe.db.escape(user)}))"
    return f"(`tabTrip Invoice`.`company` = {company})"


def get_permission_query_conditions_for_trip_booking(user):
    if user in SYSTEM_USERS:
        return ""
    link = get_active_link(user)
    if not link:
        return "1=0"
    company = frappe.db.escape(link.company)
    if link.role == "Captain":
        return f"(`tabTrip Booking`.`company` = {company} AND EXISTS (SELECT 1 FROM `tabTrip` WHERE `tabTrip`.`name` = `tabTrip Booking`.`trip` AND `tabTrip`.`assigned_captain_user` = {frappe.db.escape(user)}))"
    return f"(`tabTrip Booking`.`company` = {company})"


def get_permission_query_conditions_for_route(user):
    """Routes may not have company — allow access via user link."""
    if user in SYSTEM_USERS:
        return ""
    link = get_active_link(user)
    if not link:
        return "1=0"
    if link.role == "Captain":
        return f"EXISTS (SELECT 1 FROM `tabTrip` WHERE `tabTrip`.`route` = `tabRoute`.`name` AND `tabTrip`.`company` = {frappe.db.escape(link.company)} AND `tabTrip`.`assigned_captain_user` = {frappe.db.escape(user)})"
    return f"(`tabRoute`.`company` = {frappe.db.escape(link.company)})"


def has_permission(doc, ptype, user):
    """Check document-level access based on company link and role."""
    if user in SYSTEM_USERS:
        return True
    link = get_active_link(user)
    if not link:
        return False
    if doc.get("company") and doc.company != link.company:
        return False
    if link.role == "Viewer" and ptype in ("create", "write", "delete", "submit", "cancel", "amend"):
        return False
    if link.role == "Captain":
        if ptype in ("delete", "submit", "cancel", "amend"):
            return False
        if doc.doctype == "Trip" and doc.get("assigned_captain_user") != user:
            return False
        if doc.doctype == "Vehicle" and doc.get("assigned_captain_user") != user:
            return False
        if doc.doctype == "Trip Expense" and doc.get("captain_user") != user:
            return False
        if doc.doctype == "Vehicle Assignment" and doc.get("captain_user") != user:
            return False
        if doc.doctype in ("Trip Invoice", "Trip Booking") and doc.get("trip"):
            assigned = frappe.db.get_value("Trip", doc.trip, "assigned_captain_user")
            if assigned != user:
                return False
        if ptype in ("write",) and doc.get("owner") and doc.owner != user:
            return False
    return True


@frappe.whitelist()
def get_linked_company():
    user = frappe.session.user
    link = get_active_link(user)
    if link:
        company_name = frappe.db.get_value("Company", link.company, "company_name")
        return {"company": link.company, "company_name": company_name, "role": link.role}
    return {"company": None, "role": None}


def get_active_link(user=None):
    user = user or frappe.session.user
    if not user:
        return None
    links = frappe.get_all(
        "User Company Link",
        filters={"user": user, "status": "Active"},
        fields=["company", "role"],
        order_by="modified desc",
        limit=1,
    )
    return links[0] if links else None
