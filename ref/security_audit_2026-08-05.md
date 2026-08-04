# Security Audit - 2026-08-05

## Summary
- Public `allow_guest=True` endpoints found: 38.
- `ignore_permissions=True` calls found: 114.
- Immediate mitigations already pushed: rate limiting for app config, booking creation, guest group join and payment webhook; payment webhook signature verification already exists; mobile config no longer returns payment secrets or server-side Maps key.
- Remaining login/signup rate-limit changes are prepared locally but not pushed because `ftms/api/auth.py` and `ftms/api/onboarding.py` contain unrelated uncommitted changes that must be reviewed first.

## Highest-Risk Public Endpoints
- `ftms.api.auth.login_with_firebase`: public token exchange; add rate limit and token audience/package checks in production.
- `ftms.api.onboarding.signup_user`: public account creation; add rate limit, password policy and abuse logging.
- `ftms.api.onboarding.signup`: public company/admin onboarding; add rate limit, duplicate identity checks and approval workflow.
- `ftms.api.booking.create_booking`: public booking create; rate-limited, but should require an authenticated session for mobile-created bookings or a configured transport hub API key for server integrations.
- `ftms.api.booking.join_booking_group`: public guest join; rate-limited and signed-token protected, but should log abuse and optionally add CAPTCHA for public web links.
- `ftms.api.payment.payment_webhook`: public by design; rate-limited and HMAC-signature protected.
- Public list endpoints (`company`, `contract`, `dashboard`, `employee`, `invoice`, `route`, `vehicle`, `pricing_rule`): review whether each should remain public or require session/company access.

## `ignore_permissions=True` Remediation Plan
- Safe/setup contexts: setup/seed/demo/installation scripts may keep bypasses if not callable by public users.
- System service contexts: wallet, notifications, penalties, commissions, ZATCA should keep bypasses only behind explicit ownership/company checks in caller code.
- API contexts: every public or user-facing API using bypasses must have explicit session, ownership, company-access and field-level validation before insert/save.
- Recommended pattern: replace direct `insert(ignore_permissions=True)` in API modules with service functions that validate access, sanitize fields, then perform privileged writes internally.

## Next Actions
1. Isolate and review existing uncommitted backend changes in `auth.py`, `onboarding.py`, `pricing_rule.py`, `vehicle.py` and Vehicle doctype files.
2. Push login/signup rate limits only after unrelated backend changes are approved or separated.
3. Convert public list endpoints to authenticated/company-scoped endpoints unless needed by public landing pages.
4. Add tests for booking ownership, group join duplicate prevention, webhook signature failure and rate-limit lockout.
5. Add logging/monitoring for public endpoint failures and rate-limit hits.
