import frappe
import requests as http_requests
from ftms.country.id_format import load_countries, find_country, get_id_format


@frappe.whitelist(allow_guest=True)
def get_country_info(alpha_2):
    country = find_country(alpha_2=alpha_2)
    if not country:
        return {}
    fmt = get_id_format(alpha_2)
    return {
        "country_name": country.get("country_name"),
        "alpha_2": country.get("alpha_2"),
        "alpha_3": country.get("alpha_3"),
        "official_name": country.get("official_name"),
        "native": country.get("native"),
        "language": country.get("language"),
        "currency": country.get("currency"),
        "currency_name": country.get("currency_name"),
        "currency_symbol": country.get("currency_symbol"),
        "timezones": country.get("timezones", []),
        "phone_code": country.get("phone_code"),
        "capital": country.get("capital"),
        "region": country.get("region"),
        "subregion": country.get("subregion"),
        "tld": country.get("tld"),
        "id_format": fmt.get("documents", {}).get("National ID"),
    }


@frappe.whitelist(allow_guest=True)
def get_country_info_by_name(country_name):
    country = find_country(country_name=country_name)
    if not country:
        return {}
    return get_country_info(alpha_2=country.get("alpha_2"))


@frappe.whitelist(allow_guest=True)
def get_language_by_country_name(country_name):
    country = find_country(country_name=country_name)
    return country.get("language", "English")


@frappe.whitelist(allow_guest=True)
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
