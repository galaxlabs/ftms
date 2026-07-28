import frappe

from ftms.country.registry import geocode_city as _geocode_city
from ftms.tenant import resolve_company


@frappe.whitelist(allow_guest=True)
def list_ksa_cities(limit=100):
    return frappe.get_all(
        "KSA City",
        fields=["name", "city_name", "city_name_ar", "region", "region_ar", "latitude", "longitude", "is_active"],
        order_by="city_name asc",
        limit_page_length=int(limit),
    )


@frappe.whitelist(allow_guest=True)
def list_ksa_regions():
    cities = frappe.get_all("KSA City", fields=["region", "region_ar"], distinct=1, order_by="region asc")
    return [{"region": c.region, "region_ar": c.region_ar} for c in cities]


@frappe.whitelist()
def geocode(address, city=None, state=None, country=None):
    return _geocode_city(address, state, country)


@frappe.whitelist()
def search_places(query, limit=5):
    import requests
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": limit},
            headers={"User-Agent": "FTMS/1.0"},
            timeout=10,
        )
        return resp.json()
    except Exception as e:
        frappe.log_error(f"Geocoding failed: {e}")
        return []
