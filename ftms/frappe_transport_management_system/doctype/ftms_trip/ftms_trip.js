frappe.ui.form.on("FTMS Trip", {
  route(frm) {
    if (frm.doc.route && !frm.doc.trip_title) {
      frm.set_value("trip_title", frm.doc.route);
    }
  },

  driver(frm) {
    if (frm.doc.route && frm.doc.driver && frm.doc.trip_title === frm.doc.route || frm.doc.trip_title === `${frm.doc.route} - `) {
      frm.set_value("trip_title", `${frm.doc.route} - ${frm.doc.driver}`);
    }
  },

  refresh(frm) {
    frm.trigger("update_passenger_count");
  },

  update_passenger_count(frm) {
    if (frm.doc.passengers) {
      frm.set_value("passenger_count", frm.doc.passengers.length);
    }
  },
});

frappe.ui.form.on("FTMS Trip Passenger", {
  passengers_add(frm) {
    frm.trigger("update_passenger_count");
  },
  passengers_remove(frm) {
    frm.trigger("update_passenger_count");
  },
});
