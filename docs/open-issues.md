# Open Issues To Resume

Last updated: 2026-05-11

This file captures the remaining issues found in the senior-engineer review. Use this as the next work queue when coming back to the project.

## Critical

### 1. Production API Routing Is Broken

`VITE_API_URL=/api` plus frontend calls like `/api/v1/services` produces `/api/api/v1/services`.

This was verified directly with Axios. The doubled path returns `404`.

References:

- `frontend/src/lib/api.ts` line 3
- `frontend/src/hooks/useSlotWebSocket.ts` line 33
- `.env.prod.example` line 33
- `docker-compose.prod.yml` line 84

What to fix:

- Decide whether `VITE_API_URL` means API origin only or full API prefix.
- Make frontend URL construction consistent for HTTP and WebSocket calls.
- Add a production-config test so `/api/api/v1/...` cannot come back.

### 2. Email Verification Is Implemented But Not Enforced

Users can register, auto-login, and book without verifying email.

If the business relies on email reminders, password recovery, and booking trust, this is a real issue.

References:

- `frontend/src/context/AuthContext.tsx` line 48
- `backend/app/core/dependencies.py` line 82
- `backend/app/api/v1/endpoints/auth.py` line 81

What to fix:

- Decide the policy: block booking until email is verified, or allow booking but visibly warn.
- If enforcing, add a verified-customer dependency for booking/hold/reschedule routes.
- Update frontend registration flow so users understand they need to verify.
- Add tests for unverified versus verified booking behavior.

## High Priority

### 3. Admin-Created Dates And Times Use The Admin Browser Timezone

Manual bookings, waitlist conversion, and staff blocked times use `new Date(...).toISOString()`.

If the salon timezone differs from the admin device timezone, bookings can be stored at the wrong time.

References:

- `frontend/src/pages/admin/AdminBookingsPage.tsx` line 155
- `frontend/src/pages/admin/AdminWaitlistPage.tsx` line 80
- `frontend/src/pages/admin/AdminStaffPage.tsx` line 52

What to fix:

- Treat admin-entered date/time as salon-local time.
- Add a helper that converts salon-local date/time into the correct UTC instant.
- Use that helper in admin booking, waitlist booking, and staff blocked time forms.
- Add tests for an admin browser timezone that differs from `SALON_TIMEZONE`.

### 4. Waitlist Is Admin-Only

Backend and admin UI support waitlist, but customers cannot join a waitlist when no slots are available.

If waitlist is meant to serve customers, a customer endpoint and customer UI are missing.

References:

- `backend/app/api/v1/endpoints/admin.py` line 560
- `frontend/src/pages/admin/AdminWaitlistPage.tsx` line 30

What to fix:

- Decide whether customer waitlist is needed for launch.
- If yes, add customer-facing waitlist endpoint.
- Add UI on the booking page when no slots are available.
- Let customers choose service, optional stylist, preferred date, and notes.
- Add admin visibility into customer-created waitlist entries.

### 5. Frontend Logout Bypasses Backend Logout

The backend has a logout endpoint, but frontend logout only clears `localStorage`.

That means refresh/access token blacklist logic is unused during normal logout.

References:

- `backend/app/api/v1/endpoints/auth.py` line 182
- `frontend/src/context/AuthContext.tsx` line 52

What to fix:

- Update frontend logout to call `POST /api/v1/auth/logout`.
- Send the current refresh token in the body.
- Keep local token clearing as fallback even if the network call fails.
- Add tests for refresh token blacklist behavior after logout.

### 6. Tests Do Not Cover The App Like Users Use It

Service tests are good, and the DB constraint integration test is valuable. But there are no FastAPI route tests for full auth/booking/admin flows, and no browser/e2e tests.

This is why the production `/api/api/v1` issue survived.

References:

- `.github/workflows/ci.yml` line 70

What to fix:

- Add FastAPI route tests for:
  - register/login/refresh/logout
  - customer hold and booking
  - customer cancel/reschedule
  - admin booking creation
  - admin waitlist conversion
  - audit history access
- Add at least one frontend smoke/e2e test for the customer booking flow.
- Add a production URL construction test or production build smoke test.

## Medium Priority

### 7. Audit Trail Backend Is Richer Than The UI

Backend stores previous/new values, but admin only sees action, role, and timestamp.

For disputes or debugging, that is not enough.

References:

- `backend/app/schemas/booking.py` line 113
- `frontend/src/pages/admin/AdminBookingsPage.tsx` line 490

What to fix:

- Add an expandable audit detail view.
- Show previous values and new values in readable form.
- Include actor information when available.

### 8. Booking Notes Are Captured But Not Surfaced Well

Notes can matter in a barber workflow. They are stored, but the admin booking list does not make them visible/useful.

References:

- `backend/app/schemas/booking.py` line 78
- `frontend/src/pages/admin/AdminBookingsPage.tsx` line 433

What to fix:

- Show booking notes in the admin booking list or details panel.
- Include notes in booking history if notes are changed later.
- Consider making notes visible in customer booking confirmation.

### 9. Validation Needs Tightening

Service update can accept bad values unless DB/app behavior catches it later.

Business hours update should explicitly reject `close_time <= open_time`.

Blocked dates should warn or block if confirmed bookings already exist that day.

References:

- `backend/app/schemas/service.py` line 21
- `backend/app/schemas/business.py` line 7
- `backend/app/api/v1/endpoints/admin.py` line 173

What to fix:

- Add validators for service update duration and price.
- Add business hours range validation.
- Add blocked-date conflict behavior for existing confirmed bookings.
- Add tests for invalid service updates, invalid hours, and blocked-date conflicts.

### 10. Production Scaling Assumptions Are Single-Instance

WebSockets are in-memory, and reminders run in-process.

This is acceptable for the first single-EC2 deployment with one backend process. It is not acceptable for multiple backend replicas without Redis pub/sub and a dedicated worker.

References:

- `backend/app/core/websocket_manager.py` line 8
- `backend/app/workers/reminders.py` line 132

What to fix:

- For first launch, document that production must run one backend process/container.
- Before horizontal scaling:
  - Move WebSocket broadcasts to Redis pub/sub.
  - Move reminders to a dedicated worker process.
  - Add operational monitoring for reminder failures.

