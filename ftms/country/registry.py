import frappe
import requests as http_requests

def get_country_data():
    return {
        "SA": {
            "country_name": "Saudi Arabia",
            "alpha_2": "SA",
            "alpha_3": "SAU",
            "official_name": "المملكة العربية السعودية",
            "language": "Arabic",
            "currency": "SAR",
            "currency_name": "Saudi riyal",
            "currency_symbol": "﷼",
            "timezones": ["Asia/Riyadh"],
            "phone_code": "+966",
            "capital": "Riyadh",
            "region": "Asia",
            "subregion": "Western Asia",
            "tld": ".sa"
        }
    }

@frappe.whitelist()
def get_country_info(alpha_2):
    data = get_country_data()
    return data.get(alpha_2.upper(), {})

@frappe.whitelist()
def get_country_info_by_name(country_name):
    for code, info in get_country_data().items():
        if info["country_name"].lower() == country_name.lower():
            return info
    return {}

@frappe.whitelist()
def get_language_by_country_name(country_name):
    if country_name == "Saudi Arabia":
        return "Arabic"
    return "English"

@frappe.whitelist()
def geocode_city(city, state=None, country=None):
    query_parts = [city]
    if state:
        query_parts.append(state)
    if country:
        query_parts.append(country)
    q = ", ".join(query_parts)
    try:
        resp = http_requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 1},
            headers={"User-Agent": "FTMS/1.0"},
            timeout=10,
        )
        data = resp.json()
        if data:
            return {"latitude": data[0]["lat"], "longitude": data[0]["lon"]}
    except Exception:
        pass
    return None
