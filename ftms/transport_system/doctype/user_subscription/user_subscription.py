from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, get_last_day, getdate, today

MONTHLY_GRACE_DAYS = 5


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
        from ftms.subscriptions.utils import get_agreement_terms
        terms = get_agreement_terms(self.company)
        active_days = terms.active_days
        hours_per_day = terms.active_hours_per_day
        monthly_fee = terms.amount
        new_end = add_days(today_date, active_days)

        self.append("periods", {
            "period_start": str(today_date),
            "period_end": str(new_end),
            "subscription_agreement": terms.agreement,
            "agreement_type": terms.agreement_type,
            "billing_period_months": terms.billing_period_months,
            "vehicle_count": terms.vehicle_count,
            "active_days": active_days,
            "active_hours_per_day": hours_per_day,
            "amount": monthly_fee,
            "paid": 0,
        })
        self.subscription_agreement = terms.agreement
        self.agreement_type = terms.agreement_type
        self.status = "Overdue"
        self.active_days_used = 0
        self.active_days_remaining = 0
        self.active_hours_used = 0
        self.active_hours_per_day = hours_per_day
        self.active_hours_limit = 0
        self.active_hours_remaining = 0
        self.rollover_days = 0

    def mark_paid(self, invoice=None):
        """Mark current unpaid period as paid and activate."""
        if self.status not in ("Overdue", "Read Only"):
            frappe.throw(_("Subscription is not overdue."))
        periods = [p for p in self.periods if not p.paid]
        if not periods:
            frappe.throw(_("No unpaid periods found."))
        period = periods[0]
        period.paid = 1
        period.payment_date = str(today())
        if invoice:
            period.invoice = invoice
            period.payment_transaction = invoice
        self.current_period_start = str(getdate())
        self.current_period_end = period.period_end
        active_days = period.active_days or 30
        hours_per_day = period.active_hours_per_day or 8
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

    def _has_paid_period(self):
        return any(p.paid for p in self.periods)

    def ensure_current_month_period(self):
        """Monthly cycle: one unpaid period per calendar month, once the subscription has paid before."""
        if not self._has_paid_period():
            return False
        today_date = getdate()
        for p in self.periods:
            if p.period_start and getdate(p.period_start).year == today_date.year \
                    and getdate(p.period_start).month == today_date.month:
                return False
        from ftms.subscriptions.utils import get_agreement_terms
        terms = get_agreement_terms(self.company)
        month_start = getdate(today_date.replace(day=1))
        self.append("periods", {
            "period_start": str(month_start),
            "period_end": str(get_last_day(month_start)),
            "subscription_agreement": terms.agreement,
            "agreement_type": terms.agreement_type,
            "billing_period_months": 1,
            "vehicle_count": terms.vehicle_count,
            "active_days": terms.active_days,
            "active_hours_per_day": terms.active_hours_per_day,
            "amount": terms.amount,
            "paid": 0,
        })
        return True

    def apply_monthly_lock(self):
        """An unpaid month still open after its 5-day grace locks the account (Active -> Read Only)."""
        if self.status != "Active" or not self._has_paid_period():
            return False
        today_date = getdate()
        overdue = [
            p for p in self.periods
            if not p.paid and p.period_end and add_days(getdate(p.period_end), MONTHLY_GRACE_DAYS) < today_date
        ]
        if not overdue:
            return False
        self.status = "Read Only"
        self.is_online = 0
        return True

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
