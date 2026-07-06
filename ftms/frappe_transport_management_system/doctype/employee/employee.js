frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (!frm.doc.status) {
			frm.set_value("status", "Active");
		}
	}
});
