frappe.ui.form.on("FTMS Employee Transport Contract", {
  refresh(frm) {
    if (!frm.is_new() && frm.doc.is_active) {
      frm.add_custom_button(__("Generate Trip"), () => {
        frappe.call({
          method: "frappe.client.call",
          args: {
            doctype: frm.doc.doctype,
            name: frm.doc.name,
            method: "generate_trip",
          },
          callback(r) {
            if (r.message) {
              frappe.show_alert({
                message: __("Trip {0} created", [r.message]),
                indicator: "green",
              });
              frm.reload_doc();
            }
          },
        });
      });
    }
  },
});
