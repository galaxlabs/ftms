from __future__ import annotations

import frappe


ALLOWED_ORIGINS = {
    "https://rideksa-web.celtcoksa.com",
    "https://rideksa-84949.web.app",
    "https://ftms-frontend-nine.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
}


def add_cors_headers(response):
    origin = frappe.request.headers.get("Origin") if frappe.request else None
    configured = frappe.conf.get("allow_cors")
    if configured == "*":
        allowed_origin = origin or "*"
    elif origin in ALLOWED_ORIGINS:
        allowed_origin = origin
    else:
        allowed_origin = None

    if allowed_origin:
        response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"

    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Frappe-CSRF-Token"
    response.headers["Access-Control-Max-Age"] = "86400"
    return response
