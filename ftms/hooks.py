from . import __version__ as app_version

app_name = "ftms"
app_title = "FTMS"
app_publisher = "Galaxy Labs"
app_description = "Unified transport, trip, fleet, and route management for Frappe"
app_email = "galaxylab2020@gmail.com"
app_license = "MIT"

app_include_js = [
    "/assets/ftms/js/ftms_address.js"
]
app_include_css = [
    "/assets/ftms/css/fonts.css",
]

after_request = [
    "ftms.cors.add_cors_headers",
]

auth_hooks = [
    "ftms.firebase_auth.authenticate",
]

override_doctype_class = {
    "Address": "ftms.overrides.address.CustomAddress",
    "Trip": "ftms.transport_system.doctype.trip.trip.Trip",
    "Trip Booking": "ftms.transport_system.doctype.trip_booking.trip_booking.TripBooking",
}

before_migrate = "ftms.setup.install.before_migrate"
after_install = "ftms.setup.install.after_install"
after_migrate = "ftms.setup.install.after_migrate"

doctype_js = {
    "Address": "public/js/address.js",
}

override_doctype_dashboards = {
    "Vehicle": "ftms.transport_system.doctype.vehicle.vehicle_dashboard.get_data",
    "Route": "ftms.transport_system.doctype.route.route_dashboard.get_data",
    "Trip": "ftms.transport_system.doctype.trip.trip_dashboard.get_data",
    "Trip Booking": "ftms.transport_system.doctype.trip_booking.trip_booking_dashboard.get_data",
    "Trip Invoice": "ftms.transport_system.doctype.trip_invoice.trip_invoice_dashboard.get_data",
}

doc_events = {
    "Company": {
        "after_insert": ["ftms.accounts.utils.auto_setup_accounts", "ftms.printing.letterhead.sync_letterhead"],
        "on_update": "ftms.printing.letterhead.sync_letterhead",
    },
    "User Company Link": {
        "after_insert": "ftms.subscriptions.utils.create_subscription_on_link",
    },
    "Trip": {
        "validate": ["ftms.api.permissions.validate_user_access", "ftms.subscriptions.utils.enforce_subscription"],
        "on_update": ["ftms.commissions.engine.accrue_commissions", "ftms.realtime.publish_document_update"],
    },
    "Trip Invoice": {
        "validate": ["ftms.api.permissions.validate_user_access", "ftms.subscriptions.utils.enforce_subscription", "ftms.zatca.trip_adapter.validate_trip_invoice"],
        "on_submit": "ftms.zatca.trip_adapter.on_submit_trip_invoice",
    },
    "Trip Booking": {
        "validate": ["ftms.api.permissions.validate_user_access", "ftms.subscriptions.utils.enforce_subscription"],
        "on_update": "ftms.realtime.publish_document_update",
    },
    "Booking Offer": {"on_update": "ftms.realtime.publish_document_update"},
    "Payment Transaction": {"on_update": "ftms.realtime.publish_document_update"},
    "User Subscription": {"on_update": "ftms.realtime.publish_document_update"},
    "Notification Event": {
        "after_insert": "ftms.realtime.publish_document_update",
        "on_update": "ftms.realtime.publish_document_update",
    },
    "Vehicle": {
        "validate": "ftms.api.permissions.validate_user_access",
    },
    "Route": {
        "validate": "ftms.api.permissions.validate_user_access",
    },
    "Trip Expense": {
        "validate": "ftms.api.permissions.validate_user_access",
    },
    "Vehicle Assignment": {
        "validate": "ftms.api.permissions.validate_user_access",
    },
}

scheduler_events = {
    "daily": [
        "ftms.subscriptions.utils.daily_subscription_sync",
        "ftms.commissions.engine.daily_commission_summary",
        "ftms.api.vehicle.mark_due_service_records",
        "ftms.notifications.service.dispatch_queued_notifications",
    ],
    "hourly": [
        "ftms.subscriptions.utils.hourly_trial_check",
        "ftms.maintenance.expire_company_invitations",
        "ftms.maintenance.retry_failed_notifications",
    ],
    "weekly": [
        "ftms.maintenance.cleanup_old_notifications",
    ],
}

has_permission = {
    "Trip": "ftms.api.permissions.has_permission",
    "Trip Invoice": "ftms.api.permissions.has_permission",
    "Trip Booking": "ftms.api.permissions.has_permission",
    "Vehicle": "ftms.api.permissions.has_permission",
    "Route": "ftms.api.permissions.has_permission",
    "Trip Expense": "ftms.api.permissions.has_permission",
    "Vehicle Assignment": "ftms.api.permissions.has_permission",
}

get_permission_query_conditions = {
    "Trip": "ftms.api.permissions.get_permission_query_conditions_for_trip",
    "Trip Invoice": "ftms.api.permissions.get_permission_query_conditions_for_trip_invoice",
    "Trip Booking": "ftms.api.permissions.get_permission_query_conditions_for_trip_booking",
    "Vehicle": "ftms.api.permissions.get_permission_query_conditions_for_vehicle",
    "Route": "ftms.api.permissions.get_permission_query_conditions_for_route",
    "Trip Expense": "ftms.api.permissions.get_permission_query_conditions_for_trip_expense",
    "Vehicle Assignment": "ftms.api.permissions.get_permission_query_conditions_for_vehicle_assignment",
}

fixtures = [
    {"dt": "Vehicle Category", "filters": [["is_active", "=", 1]]},
    {"dt": "Vehicle Type", "filters": [["is_active", "=", 1]]},
    {"dt": "Vehicle Make", "filters": [["is_active", "=", 1]]},
    {"dt": "Vehicle Model", "filters": [["is_active", "=", 1]]},
    {"dt": "ZATCA Environment", "filters": [["name", "in", ["FATOORA Portal", "Simulation Portal", "Sandbox Portal"]]]},
    {"dt": "Print Format", "filters": [["module", "=", "Transport System"]]},
]

zatca_invoice_adapters = {
    "Trip Invoice": "ftms.zatca.trip_adapter.get_adapter",
}

default_print_format = {
    "Trip Invoice": "Trip Invoice KSA",
}

website_route_rules = [
    {"from_route": "/trip/<uuid>", "to_route": "/trip"},
]

guest_methods = [
    "ftms.api.config.get_client_config",
    "ftms.api.config.get_document_format",
    "ftms.api.config.validate_document",
    "ftms.api.payment.payment_webhook",
    "ftms.api.maps.list_ksa_places",
    "ftms.api.maps.search_ksa_places",
    "ftms.country.id_format.get_country_list",
    "ftms.country.id_format.get_document_types",
    "ftms.country.id_format.get_document_format",
    "ftms.country.id_format.validate_document_number",
    "ftms.country.id_format.get_country_info",
    "ftms.country.registry.get_country_info",
    "ftms.country.registry.get_country_info_by_name",
    "ftms.country.registry.get_language_by_country_name",
    "ftms.country.registry.geocode_city",
]
