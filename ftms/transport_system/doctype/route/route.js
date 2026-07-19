frappe.ui.form.on("Route", {
  source(frm) {
    frm.trigger("set_route_title");
  },

  destination(frm) {
    frm.trigger("set_route_title");
  },

  set_route_title(frm) {
    if (!frm.doc.route_title && frm.doc.source && frm.doc.destination) {
      frm.set_value("route_title", `${frm.doc.source} to ${frm.doc.destination}`);
    }
  },
});
