frappe.ui.form.on("FTMS Trip Booking", {
  refresh(frm) {
    frm.trigger("update_counts");
  },

  update_counts(frm) {
    if (frm.doc.passengers) {
      frm.set_value("passenger_count", frm.doc.passengers.length);
    }
  },
});

frappe.ui.form.on("FTMS Trip Passenger", {
  passengers_add(frm) {
    frm.trigger("update_counts");
  },
  passengers_remove(frm) {
    frm.trigger("update_counts");
  },
});
