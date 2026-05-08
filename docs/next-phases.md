# Next Engineering Phases

This branch is a parking place for the remaining product and production gaps.
Do not treat this as an implementation branch yet; split focused work branches
from `main` when starting each phase.

## Phase A: Payments, Deposits, and No-Show Policy

- Decide provider: Stripe is the likely default.
- Add deposit/payment intent flow for customer bookings.
- Store payment state on bookings.
- Define refund/cancellation/no-show rules.
- Add admin visibility into payment/deposit status.
- Add tests for successful payment, failed payment, cancellation, and no-show paths.

## Phase B: Account Recovery and Email Verification

- Add email verification tokens and verified email state.
- Add password reset request and reset confirmation flow.
- Add rate limits for auth recovery endpoints.
- Add frontend screens for verify/reset flows.
- Add notification templates and tests.

## Phase C: Audit Trail

- Add booking audit event model.
- Record create, reschedule, cancel, complete, no-show, staff changes, and admin actions.
- Expose admin booking history in the UI.
- Include actor, previous values, new values, timestamp, and source.

## Phase D: Manual Admin Booking, Walk-Ins, and Waitlist

- Add admin booking creation that can choose customer, service, staff, and time.
- Add lightweight walk-in customer flow.
- Add waitlist model for service/date/staff preferences.
- Add admin controls to convert waitlist entries into bookings.
- Keep overlap, staff schedule, hold, and no-show rules consistent with customer bookings.

## Phase E: CI Pipeline

- Add GitHub Actions for backend tests, frontend build, and Docker compose config validation.
- Cache Python and Node dependencies.
- Run migrations against Postgres service in CI.
- Block PR merge on failing checks.

## Phase F: Real Deployment Edge

- Choose deployment target.
- Add reverse proxy/TLS strategy.
- Separate health and readiness endpoints.
- Decide secrets management and production environment injection.
- Document deploy, rollback, and migration process.

## Phase G: Frontend Bundle Splitting

- Inspect current Vite bundle composition.
- Add route-level lazy loading for admin/customer pages.
- Consider manual chunks for large shared libraries.
- Keep build passing and verify no visible loading regressions.
