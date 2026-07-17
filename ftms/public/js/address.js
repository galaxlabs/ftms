frappe.ui.form.on("Address", {
    refresh: function(frm) {
        toggle_zatca(frm);
    },
    country: function(frm) {
        toggle_zatca(frm);
    }
});

function toggle_zatca(frm) {
    var sa = frm.doc.country === 'Saudi Arabia';
    frm.set_df_property('address_line1', 'hidden', sa ? 1 : 0);
    frm.set_df_property('address_line2', 'hidden', sa ? 1 : 0);
}
