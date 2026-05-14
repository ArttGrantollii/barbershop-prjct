# Open Issues Remediation Plan

Last updated: 2026-05-14

This file is the active engineering worklist for the senior-engineer review.
Work one phase at a time. Do not begin the next phase until the current phase's
implementation and verification gate are complete.

## Execution Rules

- Keep each phase narrowly scoped to the issue it is meant to close.
- Add or update tests in the same phase as the fix.
- Run the phase's verification gate before moving on.
- Update this file when a phase changes state.
- Prefer small, reviewable changes over broad refactors.

## Phase 1: Production API URL Construction

Status: Complete

Problem:

`VITE_API_URL=/api` plus frontend calls like `/api/v1/services` produces
`/api/api/v1/services` in the production build. This breaks HTTP calls,
refresh-token calls, and WebSocket slot updates behind the Caddy edge proxy.

References:

- `frontend/src/lib/api.ts`
- `frontend/src/hooks/useSlotWebSocket.ts`
- `.env.prod.example`
- `docker-compose.prod.yml`

Fix:

- Normalize `VITE_API_URL` before using it as an HTTP or WebSocket base.
- Support both local direct-backend config (`http://localhost:8000`) and
  production same-domain config (`/api`).
- Add a regression check that proves `/api` does not become `/api/api/v1`.

Verification gate:

- `cd frontend && npm.cmd run test:api-url`
- `cd frontend && npm.cmd run build`
- `docker compose exec backend python -m pytest`

Completed verification:

- 2026-05-14: `npm.cmd run test:api-url` passed.
- 2026-05-14: `npm.cmd run build` passed.
- 2026-05-14: `docker compose exec backend python -m pytest` passed, 58 tests.

## Phase 2: Email Verification Policy

Status: Complete

Problem:

Email verification tokens, pages, and user state exist, but unverified users can
still hold slots, create bookings, cancel, and reschedule. The product needs an
explicit policy.

Decision:

For launch, enforce verified email before customer booking mutations. Customers
may still view public services and availability before verification.

Fix:

- Add a verified-customer dependency on customer hold, book, and reschedule
  routes.
- Keep read-only booking views, hold release, and cancellation available to
  authenticated customers so cleanup and existing-appointment management remain
  possible.
- Keep admin actions independent from customer email verification.
- Update the customer-facing booking UX so unverified customers understand why
  booking controls are unavailable.
- Add backend tests for unverified versus verified customer behavior.

Verification gate:

- `docker compose exec backend python -m pytest`
- `cd frontend && npm.cmd run build`

Completed verification:

- 2026-05-14: `docker compose exec backend python -m pytest` passed, 61 tests.
- 2026-05-14: `npm.cmd run build` passed.

## Phase 3: Admin Salon-Timezone Input

Status: Complete

Problem:

Admin-created bookings, waitlist conversions, and staff blocked times convert
browser-local date/time input with `new Date(...).toISOString()`. If the admin
browser timezone differs from `SALON_TIMEZONE`, the stored UTC instant is wrong.

Fix:

- Add a frontend helper that converts salon-local date/time input to a UTC ISO
  instant.
- Use it in admin booking creation, waitlist booking, and staff blocked-time
  creation.
- Add tests for a browser timezone that differs from the salon timezone.

Verification gate:

- `cd frontend && npm.cmd run test:datetime`
- `cd frontend && npm.cmd run build`
- `docker compose exec backend python -m pytest`

Completed verification:

- 2026-05-14: `npm.cmd run test:datetime` passed.
- 2026-05-14: `npm.cmd run build` passed.
- 2026-05-14: `docker compose exec backend python -m pytest` passed, 61 tests.

## Phase 4: User-Path Test Coverage

Status: Complete

Problem:

Backend service tests are strong, but the app lacks route-level tests for full
auth/booking/admin flows and has no browser-level booking smoke test.

Fix:

- Add FastAPI route tests for register/login/refresh/logout, hold/book,
  cancel/reschedule, admin booking creation, waitlist conversion, and audit
  history access.
- Add one deterministic Playwright customer booking smoke test with mocked API
  responses. The backend route suite covers the API wiring; the browser smoke
  covers the frontend booking journey and production-style `/api` URL base.
- Add the frontend smoke test to CI.

Verification gate:

- `docker compose exec backend python -m pytest`
- `cd frontend && npm.cmd run test:e2e`
- GitHub Actions runs the new frontend e2e command.

Completed verification:

- 2026-05-14: `docker compose exec backend python -m pytest` passed, 72 tests.
- 2026-05-14: `npm.cmd run test:e2e` passed, 1 browser smoke test.
- 2026-05-14: `npm.cmd run test:api-url` passed.
- 2026-05-14: `npm.cmd run test:datetime` passed.
- 2026-05-14: `npm.cmd run build` passed.

## Phase 5: Session Logout Correctness

Status: Complete

Problem:

The backend has refresh-token blacklist logic, but frontend logout currently
only clears local storage.

Fix:

- Call `POST /api/v1/auth/logout` with the current refresh token.
- Clear local state even if the network call fails.
- Add tests that prove a logged-out refresh token cannot be reused.

Verification gate:

- `docker compose exec backend python -m pytest`
- `cd frontend && npm.cmd run build`

Completed verification:

- 2026-05-15: `docker compose exec backend python -m pytest` passed, 72 tests.
- 2026-05-15: `npm.cmd run test:e2e` passed, 2 browser smoke tests.
- 2026-05-15: `npm.cmd run test:api-url` passed.
- 2026-05-15: `npm.cmd run test:datetime` passed.
- 2026-05-15: `npm.cmd run build` passed.

## Phase 6: Admin Operational Completeness

Status: Complete

Problem:

Several admin workflows are implemented but under-surfaced or under-validated:
audit details, booking notes, service update validation, business hours
validation, and blocked-date conflict behavior.

Fix:

- Show audit previous/new values in an expandable admin history view.
- Surface booking notes in admin booking details or list rows.
- Validate service update duration and price.
- Reject invalid business hours where `close_time <= open_time`.
- Warn or block when adding a blocked date that already has confirmed bookings.

Verification gate:

- `docker compose exec backend python -m pytest`
- Frontend test command added as needed for admin UI behavior.
- `cd frontend && npm.cmd run build`

Completed verification:

- 2026-05-15: `docker compose exec backend python -m pytest` passed, 75 tests.
- 2026-05-15: `npm.cmd run test:e2e` passed, 2 browser smoke tests.
- 2026-05-15: `npm.cmd run test:api-url` passed.
- 2026-05-15: `npm.cmd run test:datetime` passed.
- 2026-05-15: `npm.cmd run build` passed.

## Phase 7: Launch Operations And Scaling Boundary

Status: Complete

Problem:

The first production shape is intentionally single-host/single-backend, but the
code does not yet make that operational boundary obvious enough. WebSocket
broadcasts are in-memory, and the reminder loop runs in-process.

Fix:

- Document that production must run one backend process/container for launch.
- Add a deployment note that horizontal scaling requires Redis pub/sub for slot
  broadcasts and a dedicated reminder worker process.
- Move startup seed behavior into a deliberate one-shot seed command or data
  migration.

Verification gate:

- Documentation updated.
- `docker compose -f docker-compose.prod.yml config`
- `docker compose exec backend python -m pytest`

Completed verification:

- 2026-05-15: `docker compose exec backend python -m app.ops.seed` passed.
- 2026-05-15: `docker compose config --quiet` passed.
- 2026-05-15: `docker compose -f docker-compose.prod.yml config --quiet` passed with the local Docker config permission warning only.
- 2026-05-15: `docker compose exec backend python -m pytest` passed, 75 tests.
- 2026-05-15: `npm.cmd run test:e2e` passed, 2 browser smoke tests.
- 2026-05-15: `npm.cmd run test:api-url` passed.
- 2026-05-15: `npm.cmd run test:datetime` passed.
- 2026-05-15: `npm.cmd run build` passed.

## Deferred: Customer Waitlist

Status: Deferred product decision

Backend and admin UI support waitlist entries, but customers cannot join a
waitlist when no slots are available. This is a product-scope decision, not a
launch blocker unless customer waitlist is required for the first release.
