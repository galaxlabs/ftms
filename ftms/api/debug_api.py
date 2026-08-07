import frappe


@frappe.whitelist(allow_guest=True, methods=["POST", "GET"])
def debug_echo_headers():
    """Diagnostic: echo request headers so we can see what the browser sends."""
    import json

    headers = {}
    keys = [
        "Expect", "Content-Type", "Authorization", "X-Requested-With",
        "Origin", "Content-Length", "Referer", "User-Agent", "Accept",
    ]
    for key in keys:
        val = frappe.get_request_header(key)
        if val:
            headers[key] = val[:200]
    body = frappe.request.get_data(as_text=True)[:500]
    return {
        "headers": headers,
        "body": body,
        "method": frappe.request.method,
        "protocol": frappe.request.environ.get("SERVER_PROTOCOL", ""),
    }
