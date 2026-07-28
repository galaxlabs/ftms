from __future__ import annotations

import frappe


def create_google_social_login_key(client_id: str, client_secret: str):
    """Create or update a Google Social Login Key for FTMS.
    Run via: bench --site ftms.galaxylabs.online execute ftms.setup.setup_google_oauth.create_google_social_login_key --args "'<client_id>','<client_secret>'"
    """
    provider = "Google"
    site_url = frappe.utils.get_url()

    if frappe.db.exists("Social Login Key", provider):
        doc = frappe.get_doc("Social Login Key", provider)
        if doc.client_id != client_id or doc.client_secret != client_secret:
            doc.client_id = client_id
            doc.client_secret = client_secret
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            return {"status": "ok", "action": "updated", "provider": provider}
        return {"status": "ok", "action": "unchanged", "provider": provider}

    doc = frappe.get_doc({
        "doctype": "Social Login Key",
        "provider_name": provider,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_url": f"{site_url}/api/method/frappe.integrations.oauth2_logins.login_via_{provider.lower()}",
        "authorize_url": "https://accounts.google.com/o/oauth2/auth",
        "access_token_url": "https://accounts.google.com/o/oauth2/token",
        "client_request_type": "POST",
        "api_endpoint": "https://www.googleapis.com/oauth2/v2/userinfo",
        "auth_url_data": "client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope=email+profile",
        "enable_social_login": 1,
        "social_login_provider": "Custom",
        "custom_base_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "user_id_property": "email",
        "email_property": "email",
        "first_name_property": "given_name",
        "last_name_property": "family_name",
        "icon": "google",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "ok", "action": "created", "provider": provider}


def remove_google_social_login_key():
    """Disable and remove Google Social Login Key.
    Run via: bench --site ftms.galaxylabs.online execute ftms.setup.setup_google_oauth.remove_google_social_login_key
    """
    if frappe.db.exists("Social Login Key", "Google"):
        doc = frappe.get_doc("Social Login Key", "Google")
        doc.enable_social_login = 0
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"status": "ok", "action": "disabled"}
    return {"status": "ok", "action": "not_found"}
