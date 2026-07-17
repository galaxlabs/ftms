from . import __version__ as app_version

app_name = "ftms"
app_title = "Frappe Transport Management System"
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

override_doctype_class = {
    "Address": "ftms.overrides.address.CustomAddress",
}

after_install = "ftms.setup.install.after_install"
after_migrate = "ftms.setup.install.after_migrate"

doctype_js = {
    "Address": "public/js/address.js",
}

override_doctype_dashboards = {
    "Vehicle": "ftms.frappe_transport_management_system.doctype.vehicle.vehicle_dashboard.get_data",
    "Route": "ftms.frappe_transport_management_system.doctype.route.route_dashboard.get_data",
    "Trip": "ftms.frappe_transport_management_system.doctype.trip.trip_dashboard.get_data",
    "Trip Booking": "ftms.frappe_transport_management_system.doctype.trip_booking.trip_booking_dashboard.get_data",
    "Trip Invoice": "ftms.frappe_transport_management_system.doctype.trip_invoice.trip_invoice_dashboard.get_data",
}

doc_events = {
    "Transportation Company": {
        "after_insert": "ftms.accounts.utils.auto_setup_accounts",
    },
    "Trip Invoice": {
        "validate": "ftms.zatca.trip_adapter.validate_trip_invoice",
        "on_submit": "ftms.zatca.trip_adapter.on_submit_trip_invoice",
    },
}

fixtures = [
    {"dt": "Print Format", "filters": [["module", "=", "Frappe Transport Management System"]]},
]
