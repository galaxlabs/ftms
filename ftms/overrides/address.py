import frappe
from frappe.contacts.doctype.address.address import Address as CoreAddress

class CustomAddress(CoreAddress):
    def get_display(self):
        if self.country == "Saudi Arabia":
            parts = []
            sn = self.get("street_name", "")
            bn = self.get("building_no", "")
            if bn or sn:
                parts.append(" ".join(filter(None, [bn, sn])))
            if self.get("district"):
                parts.append(self.district)
            city_line = " ".join(filter(None, [self.city, self.pincode]))
            if city_line:
                parts.append(city_line)
            if self.get("additional_no"):
                parts.append(self.additional_no)
            return "\n".join(parts) if parts else super().get_display()
        return super().get_display()

def after_insert(doc, method=None):
    _create_linked(doc)

def on_update(doc, method=None):
    _create_linked(doc)

def _create_linked(doc):
    for link in doc.links:
        if link.link_doctype in ("Customer", "Supplier", "Branch", "Staff", "Bank"):
            address_name = frappe.db.get_value("Dynamic Link", {
                "link_doctype": link.link_doctype,
                "link_name": link.link_name,
                "parenttype": "Address"
            }, "parent")
            if not address_name:
                continue
            addr = frappe.get_doc("Address", address_name)
            addr.flags.ignore_permissions = True
            addr.save()
