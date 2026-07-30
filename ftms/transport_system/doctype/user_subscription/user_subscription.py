from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, today


class UserSubscription(Document):
    TRIAL_DAYS = 15
    PERIOD_DAYS = 30
    MONTHLY_FEE = 100

    def before_save(self):
        self._compute_status()

    def _compute_status(self):
        """Auto-compute status based on trial/period dates."""
        if self.status in ("Inactive",):
            return

        today_date = getdate()

        if self.status == "Trial":
            if self.trial_end and getdate(self.trial_end) < today_date:
                self.status = "Read Only"
            else:
                remaining = (getdate(self.trial_end) - today_date).days if self.trial_end else 0
                self.trial_days_left = max(remaining, 0)
            return

        if self.status == "Active":
            if self.active_hours_limit and (self.active_hours_remaining or 0) <= 0:
                self.status = "Read Only"

    def _auto_renew(self):
        """Create next period, mark as overdue until paid."""
        today_date = getdate()
        from ftms.subscriptions.utils import subscription_settings
        active_days, hours_per_day, monthly_fee = subscription_settings()
        new_end = add_days(today_date, active_days)

        self.append("periods", {
            "period_start": str(today_date),
            "period_end": str(new_end),
            "amount": monthly_fee,
            "paid": 0,
        })
        self.status = "Overdue"
        self.active_days_used = 0
        self.active_days_remaining = active_days
        self.active_hours_used = 0
        self.active_hours_per_day = hours_per_day
        self.active_hours_limit = active_days * hours_per_day
        self.active_hours_remaining = self.active_hours_limit
        self.rollover_days = 0

    def mark_paid(self, invoice=None):
        """Mark current unpaid period as paid and activate."""
        if self.status != "Overdue":
            frappe.throw(_("Subscription is not overdue."))
        periods = [p for p in self.periods if not p.paid]
        if not periods:
            frappe.throw(_("No unpaid periods found."))
        period = periods[0]
        period.paid = 1
        period.payment_date = str(today())
        if invoice:
            period.invoice = invoice
        self.current_period_start = str(getdate())
        self.current_period_end = period.period_end
        from ftms.subscriptions.utils import subscription_settings
        active_days, hours_per_day, _ = subscription_settings()
        self.active_hours_used = 0
        self.active_hours_per_day = hours_per_day
        self.active_hours_limit = active_days * hours_per_day
        self.active_hours_remaining = self.active_hours_limit
        self.active_days_used = 0
        self.active_days_remaining = active_days
        self.is_online = 1
        self.status = "Active"
        self.last_payment_date = str(today())
        self.last_invoice = invoice
        self.save(ignore_permissions=True)

    def renew(self):
        """Create a new subscription period (generates invoice)."""
        from ftms.subscriptions.utils import _create_renewal_invoice
        self._auto_renew()
        _create_renewal_invoice(self)
        self.save(ignore_permissions=True)

    def set_inactive(self):
        """Manually set subscription to inactive."""
        self.status = "Inactive"
        self.save(ignore_permissions=True)
