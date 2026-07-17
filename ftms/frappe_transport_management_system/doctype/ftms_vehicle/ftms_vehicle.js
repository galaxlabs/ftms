frappe.ui.form.on("FTMS Vehicle", {
  vehicle_make(frm) {
    frm.set_query("vehicle_model", { filters: { vehicle_make: frm.doc.vehicle_make } });
  },
});
