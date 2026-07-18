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
    return f"(`tab{{doctype}}`.`company` = {frappe.db.escape(link.company)})"


def get_permission_query_conditions_for_route(user):
    """Routes may not have company — allow access via user link."""
    if user in SYSTEM_USERS:
        return ""
    link = get_active_link(user)
    if not link:
        return "1=0"
    return "1=1"


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
        if ptype in ("write",) and doc.get("owner") and doc.owner != user:
            return False
    return True


@frappe.whitelist()
def get_linked_company():
    user = frappe.session.user
    link = get_active_link(user)
    if link:
        company_name = frappe.db.get_value("Transportation Company", link.company, "company_name")
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
