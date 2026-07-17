import frappe

from ftms.country.registry import geocode_city as _geocode_city

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
