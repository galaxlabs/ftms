import frappe
import requests

from ftms.country.registry import geocode_city as _geocode_city
from ftms.config.service import get_integration_settings
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


@frappe.whitelist(allow_guest=True)
def list_ksa_places(limit=100, featured_only=False):
    filters = {"enabled": 1}
    if str(featured_only).lower() in {"1", "true", "yes"}:
        filters["featured"] = 1
    return frappe.get_all(
        "KSA Place",
        filters=filters,
        fields=["name", "name_en", "name_ar", "place_type", "region", "city", "latitude", "longitude", "google_place_id", "featured"],
        order_by="featured desc, name_en asc",
        limit_page_length=int(limit or 100),
    )


@frappe.whitelist()
def geocode(address, city=None, state=None, country=None):
    return _geocode_city(address, state, country)


@frappe.whitelist()
def search_places(query, limit=5):
    return search_ksa_places(query=query, limit=limit)


def _local_ksa_places(query, limit=10):
    query = (query or "").strip()
    if not query:
        return []
    like = f"%{query}%"
    results = []
    if frappe.db.exists("DocType", "KSA Place"):
        rows = frappe.get_all(
            "KSA Place",
            filters={"enabled": 1},
            or_filters=[
                ["name_en", "like", like],
                ["name_ar", "like", like],
                ["search_aliases_en", "like", like],
                ["search_aliases_ar", "like", like],
            ],
            fields=["name", "name_en", "name_ar", "place_type", "region", "city", "latitude", "longitude", "google_place_id"],
            order_by="featured desc, name_en asc",
            limit_page_length=int(limit or 10),
        )
        results.extend([
            {
                "source": "local",
                "place_id": row.google_place_id or row.name,
                "name_en": row.name_en,
                "name_ar": row.name_ar,
                "display_name": row.name_en,
                "place_type": row.place_type,
                "region": row.region,
                "city": row.city,
                "latitude": row.latitude,
                "longitude": row.longitude,
            }
            for row in rows
        ])
    if frappe.db.exists("DocType", "KSA City"):
        cities = frappe.get_all(
            "KSA City",
            filters={"is_active": 1},
            or_filters=[["city_name", "like", like], ["city_name_ar", "like", like]],
            fields=["name", "city_name", "city_name_ar", "region", "latitude", "longitude"],
            order_by="city_name asc",
            limit_page_length=int(limit or 10),
        )
        results.extend([
            {
                "source": "local_city",
                "place_id": row.name,
                "name_en": row.city_name,
                "name_ar": row.city_name_ar,
                "display_name": row.city_name,
                "place_type": "City",
                "region": row.region,
                "latitude": row.latitude,
                "longitude": row.longitude,
            }
            for row in cities
        ])
    return results[: int(limit or 10)]


def _google_ksa_places(query, limit=10):
    settings = get_integration_settings(include_private=True)
    key = settings.get("maps_api_key")
    country_code = (settings.get("maps_country_restriction") or "SA").strip().upper()
    if not key or not query:
        return []

    rows = {}
    for language in ("en", "ar"):
        try:
            response = requests.get(
                "https://maps.googleapis.com/maps/api/place/autocomplete/json",
                params={
                    "input": query,
                    "components": f"country:{country_code.lower()}",
                    "language": language,
                    "types": "establishment|geocode",
                    "key": key,
                },
                headers={"User-Agent": "FTMS/1.0"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            frappe.log_error(frappe.get_traceback(), "KSA Google Places search failed")
            continue
        if data.get("status") not in {"OK", "ZERO_RESULTS"}:
            continue
        for prediction in (data.get("predictions") or [])[: int(limit or 10)]:
            place_id = prediction.get("place_id")
            if not place_id:
                continue
            row = rows.setdefault(place_id, {
                "source": "google",
                "place_id": place_id,
                "name_en": "",
                "name_ar": "",
                "display_name": prediction.get("description") or "",
                "place_type": (prediction.get("types") or ["Other"])[0],
                "latitude": None,
                "longitude": None,
            })
            text = (prediction.get("structured_formatting") or {}).get("main_text") or prediction.get("description") or ""
            row["name_ar" if language == "ar" else "name_en"] = text

    for place_id, row in list(rows.items())[: int(limit or 10)]:
        try:
            response = requests.get(
                "https://maps.googleapis.com/maps/api/place/details/json",
                params={"place_id": place_id, "fields": "geometry,address_component", "language": "en", "key": key},
                headers={"User-Agent": "FTMS/1.0"},
                timeout=10,
            )
            result = response.json().get("result") or {}
            location = ((result.get("geometry") or {}).get("location") or {})
            row["latitude"] = location.get("lat")
            row["longitude"] = location.get("lng")
        except Exception:
            continue
    return list(rows.values())


@frappe.whitelist(allow_guest=True)
def search_ksa_places(query, limit=10):
    """Search configured country places, returning Arabic and English labels."""
    query = (query or "").strip()
    if not query:
        return []
    local = _local_ksa_places(query, limit=limit)
    google = _google_ksa_places(query, limit=limit)
    merged = []
    seen = set()
    for row in google + local:
        key = row.get("place_id") or f"{row.get('name_en')}:{row.get('name_ar')}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
        if len(merged) >= int(limit or 10):
            break
    if merged:
        return merged
    try:
        settings = get_integration_settings()
        country_code = (settings.get("maps_country_restriction") or "SA").strip().lower()
        country_name = "Saudi Arabia" if country_code == "sa" else country_code.upper()
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{query}, {country_name}", "format": "json", "limit": limit, "countrycodes": country_code, "addressdetails": 1},
            headers={"User-Agent": "FTMS/1.0"},
            timeout=10,
        )
        return [
            {
                "source": "nominatim",
                "place_id": row.get("place_id"),
                "name_en": row.get("display_name", ""),
                "name_ar": row.get("display_name", ""),
                "display_name": row.get("display_name", ""),
                "place_type": row.get("type", "Other"),
                "latitude": row.get("lat"),
                "longitude": row.get("lon"),
            }
            for row in resp.json()
        ]
    except Exception as e:
        frappe.log_error(f"Geocoding failed: {e}")
        return []
