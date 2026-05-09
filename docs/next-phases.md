# Engineering Roadmap

## Completed Phases

The core launch-hardening phases below are implemented on `main` and covered by
local validation plus GitHub Actions CI.

### Phase A: Manual Admin Booking, Walk-Ins, and Waitlist

- Add admin booking creation that can choose customer, service, staff, and time.
- Add lightweight walk-in customer flow.
- Add waitlist model for service/date/staff preferences.
- Add admin controls to convert waitlist entries into bookings.
- Keep overlap, staff schedule, hold, and no-show rules consistent with customer bookings.

### Phase B: Audit Trail

- Add booking audit event model.
- Record create, reschedule, cancel, complete, no-show, staff changes, and admin actions.
- Expose admin booking history in the UI.
- Include actor, previous values, new values, timestamp, and source.

### Phase C: Account Recovery and Email Verification

- Add email verification tokens and verified email state.
- Add password reset request and reset confirmation flow.
- Add rate limits for auth recovery endpoints.
- Add frontend screens for verify/reset flows.
- Add notification templates and tests.

### Phase D: CI Pipeline

- Add GitHub Actions for backend tests, frontend build, and Docker compose config validation.
- Cache Python and Node dependencies.
- Run migrations against Postgres service in CI.
- Block PR merge on failing checks.

### Phase E: Real Deployment Edge

- Choose deployment target.
- Add reverse proxy/TLS strategy.
- Separate health and readiness endpoints.
- Decide secrets management and production environment injection.
- Document deploy, rollback, and migration process.

### Phase F: Frontend Bundle Splitting

- Inspect current Vite bundle composition.
- Add route-level lazy loading for admin/customer pages.
- Consider manual chunks for large shared libraries.
- Keep build passing and verify no visible loading regressions.

## Next Decision

- Run a full manual product smoke test against the local app or a staging host.
- Configure GitHub branch protection so CI checks are required before merging.
- Prepare production secrets, DNS, AWS host, and database backup process.

## Future Optional: Payments, Deposits, and No-Show Policy

Do not start this until the client explicitly wants online payment.

- Decide provider and payment rules only after confirming the business requirement.
- Add deposit/payment intent flow for customer bookings if needed.
- Store payment state on bookings if needed.
- Define refund/cancellation/no-show rules if needed.
- Add admin visibility into payment/deposit status if needed.
- Add tests for successful payment, failed payment, cancellation, and no-show paths if needed.
