# Vendos Salon Project Documentation

Last reviewed: 2026-05-11

This document describes what the project currently implements, how the system is built technically, how it is validated, and what still needs attention before a real production launch.

## Product Scope

Vendos Salon is a full-stack booking system for a barber shop or salon. The current product supports customer accounts, service browsing, appointment booking, staff selection, admin booking management, walk-ins, waitlist management, booking history, email/SMS style notifications, and production-oriented Docker deployment.

Online payments, deposits, no-show fee enforcement, mobile app push notifications, and course/video selling are not implemented yet. Payments are intentionally parked until the client confirms that online payment is required.

## User Roles

### Customer

Customers can:

- Register an account.
- Log in and receive access/refresh tokens.
- View active services.
- Choose a service.
- Choose any available stylist or a specific stylist.
- Pick an available date and time.
- Hold a slot temporarily before confirming.
- Confirm a booking.
- View their own bookings.
- Cancel their own confirmed bookings, subject to the cancellation window.
- Reschedule their own confirmed bookings, subject to the reschedule/cancellation window.
- Update profile details.
- Change password.
- Request password reset.
- Verify email through a token link.

### Admin

Admins can:

- View dashboard metrics and today's schedule.
- Manage services.
- Activate/deactivate services.
- Delete services only when they have no booking history.
- Manage staff.
- Assign services to staff.
- Activate/deactivate staff.
- Delete staff only when they have no booking history.
- Configure staff-specific working hours.
- Configure staff-specific blocked times.
- Configure global business hours.
- Configure globally blocked dates.
- Search, filter, and paginate bookings.
- Create scheduled bookings manually.
- Record completed walk-ins.
- Cancel bookings.
- Reschedule bookings.
- Mark bookings completed.
- Mark past bookings as no-show.
- View booking audit history.
- Create waitlist entries.
- Cancel waitlist entries.
- Convert waitlist entries into confirmed bookings.

## Customer-Facing Features

### Public Home Page

The home page shows the salon brand experience, services, and calls to book an appointment.

Implemented in:

- `frontend/src/pages/HomePage.tsx`
- `frontend/src/components/layout/Navbar.tsx`

### Registration and Login

Customers can register with name, email, phone, and password. Login uses OAuth2 password form semantics on the backend and stores access and refresh tokens in the frontend.

Implemented in:

- `backend/app/api/v1/endpoints/auth.py`
- `backend/app/core/security.py`
- `backend/app/core/dependencies.py`
- `frontend/src/pages/RegisterPage.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/context/AuthContext.tsx`
- `frontend/src/lib/api.ts`

### Email Verification

The backend creates email verification tokens, stores hashed tokens, and sends a verification link through the configured notification backend.

Implemented in:

- `backend/app/services/account_service.py`
- `backend/app/db/models/user.py`
- `backend/app/db/repositories/account_token_repository.py`
- `backend/app/api/v1/endpoints/auth.py`
- `frontend/src/pages/VerifyEmailPage.tsx`

Important current behavior:

- Verification state exists.
- Verification links exist.
- The UI has a verification page.
- Booking/login is not currently blocked for unverified users.

### Password Reset

Customers can request a password reset link and reset their password using a token.

Implemented in:

- `backend/app/services/account_service.py`
- `backend/app/api/v1/endpoints/auth.py`
- `frontend/src/pages/ForgotPasswordPage.tsx`
- `frontend/src/pages/ResetPasswordPage.tsx`

### Profile and Password Change

Customers can update their profile and change password after re-entering the current password.

Implemented in:

- `backend/app/api/v1/endpoints/auth.py`
- `frontend/src/pages/ProfilePage.tsx`

### Booking Flow

The customer booking flow is a three-step process:

1. Select service.
2. Select stylist, date, and available time.
3. Confirm booking while the slot is temporarily held.

Implemented in:

- `frontend/src/pages/BookPage.tsx`
- `backend/app/api/v1/endpoints/services.py`
- `backend/app/api/v1/endpoints/staff.py`
- `backend/app/api/v1/endpoints/availability.py`
- `backend/app/api/v1/endpoints/bookings.py`
- `backend/app/services/availability_service.py`
- `backend/app/services/booking_service.py`

### Slot Holds

Before a customer confirms a booking, the backend creates a Redis-backed temporary hold. This prevents another customer from taking the same staff member and time while the first customer is confirming.

Implemented details:

- Slot holds are stored in Redis.
- Holds are scoped by staff ID and start time.
- Holds expire automatically after `SLOT_HOLD_TTL_SECONDS`.
- One user can hold only one slot at a time.
- Hold cleanup is best-effort from the frontend and guaranteed by Redis TTL.

Implemented in:

- `backend/app/services/booking_service.py`
- `backend/app/services/availability_service.py`
- `frontend/src/pages/BookPage.tsx`

### Live Slot Updates

The frontend uses WebSockets to update slot status when another customer holds, books, releases, cancels, or reschedules a slot.

Implemented in:

- `backend/app/api/v1/endpoints/ws.py`
- `backend/app/core/websocket_manager.py`
- `frontend/src/hooks/useSlotWebSocket.ts`

Current limitation:

- WebSocket room management is in-process. It works for one backend process. A multi-instance deployment would need shared pub/sub, usually Redis pub/sub.

### My Bookings

Customers can view their own bookings, cancel eligible bookings, and reschedule eligible bookings.

Implemented in:

- `backend/app/api/v1/endpoints/bookings.py`
- `backend/app/services/booking_service.py`
- `frontend/src/pages/MyBookingsPage.tsx`
- `frontend/src/components/RescheduleDialog.tsx`

## Admin Features

### Admin Dashboard

The dashboard shows aggregate booking metrics and today's confirmed schedule. Metrics are computed in the backend, not from a capped frontend booking page.

Implemented in:

- `backend/app/api/v1/endpoints/admin.py`
- `backend/app/db/repositories/booking_repository.py`
- `frontend/src/pages/admin/AdminDashboardPage.tsx`

Metrics include:

- Today's confirmed booking count.
- Today's expected revenue.
- Next seven days confirmed booking count.
- Total confirmed bookings.
- Total cancelled bookings.
- Today's schedule.

### Service Management

Admins can create, update, activate/deactivate, and delete services. Deletion is blocked when a service has existing booking history.

Implemented in:

- `backend/app/api/v1/endpoints/admin.py`
- `backend/app/schemas/service.py`
- `backend/app/db/models/service.py`
- `backend/app/db/repositories/service_repository.py`
- `frontend/src/pages/admin/AdminServicesPage.tsx`

### Staff Management

Admins can create, update, activate/deactivate, and delete staff. Staff can be assigned to services. Deletion is blocked when a staff member has existing booking history.

Implemented in:

- `backend/app/api/v1/endpoints/admin.py`
- `backend/app/schemas/staff.py`
- `backend/app/db/models/staff.py`
- `backend/app/db/repositories/staff_repository.py`
- `frontend/src/pages/admin/AdminStaffPage.tsx`

### Staff Working Hours

Staff can have their own weekly working hours. If no staff-specific hours are set, global business hours are used.

Implemented in:

- `backend/app/db/models/staff.py`
- `backend/app/db/repositories/staff_repository.py`
- `backend/app/api/v1/endpoints/admin.py`
- `frontend/src/pages/admin/AdminStaffPage.tsx`

### Staff Blocked Times

Admins can block specific time ranges for individual staff members. Availability and booking validation respect these blocks.

Implemented in:

- `backend/app/db/models/staff.py`
- `backend/app/services/availability_service.py`
- `backend/app/services/booking_service.py`
- `frontend/src/pages/admin/AdminStaffPage.tsx`

### Global Business Hours

Admins can set global open/close hours and closed days. These hours are used as fallback when staff-specific hours are not configured.

Implemented in:

- `backend/app/db/models/business.py`
- `backend/app/db/repositories/business_repository.py`
- `backend/app/api/v1/endpoints/admin.py`
- `frontend/src/pages/admin/AdminHoursPage.tsx`

### Blocked Dates

Admins can block full calendar dates, such as holidays. Availability and booking validation reject bookings on blocked dates.

Implemented in:

- `backend/app/db/models/business.py`
- `backend/app/db/repositories/business_repository.py`
- `backend/app/api/v1/endpoints/admin.py`
- `frontend/src/pages/admin/AdminBlockedDatesPage.tsx`

### Admin Booking Management

Admins can:

- List bookings with pagination.
- Filter by status.
- Search customer name, email, and phone.
- Filter by date range.
- Create confirmed bookings.
- Create completed walk-ins.
- Cancel bookings.
- Reschedule bookings.
- Complete bookings.
- Mark past confirmed bookings as no-show.
- View booking history.

Implemented in:

- `backend/app/api/v1/endpoints/admin.py`
- `backend/app/services/booking_service.py`
- `backend/app/db/repositories/booking_repository.py`
- `frontend/src/pages/admin/AdminBookingsPage.tsx`
- `frontend/src/components/RescheduleDialog.tsx`

### Walk-Ins

Admins can record completed walk-ins. Walk-ins are stored as bookings with status `completed`.

Implemented in:

- `backend/app/services/booking_service.py`
- `backend/app/api/v1/endpoints/admin.py`
- `frontend/src/pages/admin/AdminBookingsPage.tsx`

### Waitlist

Admins can create waitlist entries and convert them into bookings.

Implemented in:

- `backend/app/db/models/booking.py`
- `backend/app/db/repositories/waitlist_repository.py`
- `backend/app/schemas/waitlist.py`
- `backend/app/api/v1/endpoints/admin.py`
- `frontend/src/pages/admin/AdminWaitlistPage.tsx`

Current limitation:

- Waitlist is admin-only. Customers cannot currently join a waitlist from the booking page.

### Audit Trail

Booking audit events are recorded for important booking lifecycle actions.

Implemented actions include:

- Customer booking created.
- Admin booking created.
- Walk-in completed.
- Booking rescheduled.
- Booking cancelled.
- Booking completed.
- Booking marked no-show.
- Waitlist converted into booking.

Stored audit fields:

- Booking ID.
- Actor ID.
- Actor role.
- Action.
- Previous values.
- New values.
- Created timestamp.

Implemented in:

- `backend/app/db/models/booking.py`
- `backend/app/db/repositories/booking_audit_repository.py`
- `backend/app/services/audit_service.py`
- `backend/app/api/v1/endpoints/admin.py`
- `frontend/src/pages/admin/AdminBookingsPage.tsx`

Current limitation:

- The frontend only shows action, actor role, and timestamp. It does not yet show the previous/new values in a useful detail view.

## Booking Rules and Business Logic

### Staff Capacity

The system supports multiple staff members working at the same time. Two bookings can overlap if they are assigned to different staff members. Two confirmed bookings cannot overlap for the same staff member.

Enforced by:

- Application-level overlap checks.
- PostgreSQL exclusion constraint on `(staff_id, tstzrange(start_time, end_time))` for confirmed bookings.

Implemented in:

- `backend/alembic/versions/0004_multi_staff_capacity.py`
- `backend/app/db/repositories/booking_repository.py`
- `backend/app/services/booking_service.py`
- `backend/tests/integration/test_booking_capacity_db.py`

### Same-Day Customer Booking Limit

Customers cannot have more than one confirmed booking on the same salon-local day.

Implemented in:

- `backend/app/services/booking_service.py`
- `backend/app/db/repositories/booking_repository.py`

### Cancellation Window

Customers cannot cancel inside the configured cancellation window. Admins can cancel without this customer restriction.

Configured by:

- `CANCELLATION_WINDOW_HOURS`

Implemented in:

- `backend/app/services/booking_service.py`

### Cancellation Daily Limit

Customers have a daily cancellation limit. The counter is Redis-backed and rolls over based on the salon-local date.

Configured by:

- `CANCELLATION_LIMIT_PER_DAY`

Implemented in:

- `backend/app/services/booking_service.py`

### Rebooking Cooldown

After a customer cancels a slot, they cannot immediately rebook the same start time during the cooldown window.

Configured by:

- `SLOT_COOLDOWN_SECONDS`

Implemented in:

- `backend/app/services/booking_service.py`
- `backend/app/services/availability_service.py`

### Minimum Lead Time

The system can enforce minimum advance notice before a booking can be made or held.

Configured by:

- `MIN_LEAD_MINUTES`

Implemented in:

- `backend/app/services/booking_service.py`
- `backend/app/services/availability_service.py`

### No-Show Rules

Admins can mark a booking as no-show only when:

- The booking is currently confirmed.
- The booking start time has already passed.

Implemented in:

- `backend/app/api/v1/endpoints/admin.py`

## Notifications

The app has a notification abstraction with console and AWS backends.

Supported notification events:

- Booking confirmed.
- Booking cancelled.
- Booking reminder.
- Email verification.
- Password reset.

Implemented in:

- `backend/app/notifications/service.py`
- `backend/app/notifications/console.py`
- `backend/app/notifications/aws.py`
- `backend/app/notifications/schemas.py`

### AWS Notifications

AWS support currently uses:

- SES for email.
- SNS for SMS.

Configured by:

- `NOTIFICATIONS_BACKEND=aws`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `AWS_SES_FROM_EMAIL`
- `AWS_SNS_SENDER_ID`

Current limitation:

- AWS SES/SNS behavior is not covered by integration tests against real AWS services.

## Reminder Worker

The backend starts an in-process reminder loop when reminders are enabled.

Behavior:

- Looks for confirmed bookings roughly 24 hours before start time.
- Uses a configurable tolerance window.
- Claims due bookings with `FOR UPDATE SKIP LOCKED`.
- Tracks attempted reminders separately from successful reminders.
- Stores reminder failure details in `reminder_error`.

Implemented in:

- `backend/app/workers/reminders.py`
- `backend/app/main.py`

Configured by:

- `REMINDERS_ENABLED`
- `REMINDER_LEAD_HOURS`
- `REMINDER_TOLERANCE_MINUTES`
- `REMINDER_INTERVAL_SECONDS`

Current limitation:

- The worker runs inside the FastAPI process. It is protected against duplicate row claims, but operationally a dedicated worker process is cleaner for production.

## Backend Architecture

### Stack

- FastAPI
- SQLAlchemy async ORM
- Alembic migrations
- PostgreSQL
- Redis
- Pydantic schemas
- SlowAPI rate limiting
- Structlog logging
- Boto3 for AWS SES/SNS

### Backend Layout

- `backend/app/main.py`: FastAPI app creation, middleware, lifespan startup/shutdown, health/readiness routes.
- `backend/app/api/v1/router.py`: API router composition.
- `backend/app/api/v1/endpoints`: route handlers.
- `backend/app/services`: business logic.
- `backend/app/db/models`: SQLAlchemy models.
- `backend/app/db/repositories`: query and persistence helpers.
- `backend/app/schemas`: request/response schemas.
- `backend/app/core`: config, security, auth dependencies, rate limiter, websocket manager.
- `backend/app/notifications`: notification abstraction and providers.
- `backend/app/workers`: background reminder worker.
- `backend/alembic/versions`: database migrations.
- `backend/tests`: backend unit and integration tests.

### Main API Areas

Public:

- `GET /api/v1/business-info`
- `GET /api/v1/services`
- `GET /api/v1/staff`
- `GET /api/v1/staff/by-service/{service_id}`
- `GET /api/v1/availability`
- `WS /api/v1/ws/slots/{date}`

Auth:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `PATCH /api/v1/auth/me`
- `POST /api/v1/auth/change-password`
- `POST /api/v1/auth/resend-verification`
- `POST /api/v1/auth/verify-email`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`

Customer booking:

- `GET /api/v1/bookings/my`
- `POST /api/v1/bookings`
- `GET /api/v1/bookings/{booking_id}`
- `POST /api/v1/bookings/{booking_id}/cancel`
- `POST /api/v1/bookings/{booking_id}/reschedule`
- `POST /api/v1/availability/hold`
- `DELETE /api/v1/availability/hold`

Admin:

- `GET /api/v1/admin/dashboard`
- `GET /api/v1/admin/services`
- `POST /api/v1/admin/services`
- `PUT /api/v1/admin/services/{service_id}`
- `DELETE /api/v1/admin/services/{service_id}`
- `GET /api/v1/admin/business-hours`
- `PUT /api/v1/admin/business-hours/{day_of_week}`
- `GET /api/v1/admin/blocked-dates`
- `POST /api/v1/admin/blocked-dates`
- `DELETE /api/v1/admin/blocked-dates/{blocked_date_id}`
- `GET /api/v1/admin/staff`
- `POST /api/v1/admin/staff`
- `PATCH /api/v1/admin/staff/{staff_id}`
- `PUT /api/v1/admin/staff/{staff_id}/services`
- `DELETE /api/v1/admin/staff/{staff_id}`
- `GET /api/v1/admin/staff/{staff_id}/working-hours`
- `PUT /api/v1/admin/staff/{staff_id}/working-hours/{day_of_week}`
- `GET /api/v1/admin/staff/{staff_id}/blocked-times`
- `POST /api/v1/admin/staff/{staff_id}/blocked-times`
- `DELETE /api/v1/admin/staff/{staff_id}/blocked-times/{blocked_time_id}`
- `GET /api/v1/admin/bookings`
- `POST /api/v1/admin/bookings`
- `POST /api/v1/admin/bookings/{booking_id}/cancel`
- `POST /api/v1/admin/bookings/{booking_id}/reschedule`
- `POST /api/v1/admin/bookings/{booking_id}/complete`
- `POST /api/v1/admin/bookings/{booking_id}/no-show`
- `GET /api/v1/admin/bookings/{booking_id}/audit-events`
- `GET /api/v1/admin/waitlist`
- `POST /api/v1/admin/waitlist`
- `PATCH /api/v1/admin/waitlist/{entry_id}`
- `POST /api/v1/admin/waitlist/{entry_id}/book`

Health:

- `GET /health`
- `GET /ready`

### Authentication and Authorization

The backend uses JWT access tokens and refresh tokens.

Implemented details:

- Access tokens have type `access`.
- Refresh tokens have type `refresh`.
- Tokens include a JWT ID (`jti`).
- Refresh token rotation blacklists the consumed refresh token in Redis.
- Logout can blacklist access and refresh tokens.
- Admin routes require `UserRole.ADMIN`.
- Customer booking routes reject admin users.
- Access to a single booking masks non-owned bookings as 404 for customers.

Current limitations:

- Frontend logout only clears local tokens. It does not call backend logout.
- Tokens are stored in localStorage.
- Password reset/change does not revoke all previous sessions.

### Rate Limiting

SlowAPI rate limits are applied to auth-sensitive endpoints. The limiter uses Redis storage.

Implemented in:

- `backend/app/core/limiter.py`
- `backend/app/api/v1/endpoints/auth.py`
- `backend/app/main.py`

## Database Model Summary

### Users

Table:

- `users`

Purpose:

- Customer/admin accounts.
- Email verification state.
- Profile data.
- Password hash.

### Account Tokens

Table:

- `account_tokens`

Purpose:

- Email verification tokens.
- Password reset tokens.
- Stored as SHA-256 token hashes.

### Services

Table:

- `services`

Purpose:

- Salon services with duration, price, description, and active flag.

### Staff

Tables:

- `staff`
- `service_staff`
- `staff_working_hours`
- `staff_blocked_times`

Purpose:

- Staff profiles.
- Service assignment.
- Staff-specific schedules.
- Staff-specific blocked times.

### Business Settings

Tables:

- `business_hours`
- `blocked_dates`

Purpose:

- Global fallback weekly hours.
- Full-day closures.

### Bookings

Table:

- `bookings`

Purpose:

- Customer bookings.
- Admin bookings.
- Walk-ins.
- Booking status.
- Guest customer snapshots.
- Reminder tracking.

Important constraint:

- PostgreSQL exclusion constraint prevents overlapping confirmed bookings for the same staff member.

### Waitlist

Table:

- `waitlist_entries`

Purpose:

- Admin-managed waitlist entries with service/staff/date preference and conversion to booking.

### Booking Audit Events

Table:

- `booking_audit_events`

Purpose:

- Booking lifecycle history with actor and before/after values.

## Frontend Architecture

### Stack

- React 18
- Vite
- TypeScript
- Tailwind CSS
- TanStack Query
- React Router
- Axios
- Lucide icons
- Framer Motion

### Frontend Layout

- `frontend/src/App.tsx`: route definitions and route-level lazy loading.
- `frontend/src/lib/api.ts`: Axios client and token refresh interceptor.
- `frontend/src/context/AuthContext.tsx`: auth state and login/register/logout helpers.
- `frontend/src/pages`: customer/public pages.
- `frontend/src/pages/admin`: admin pages.
- `frontend/src/components`: shared components.
- `frontend/src/components/admin/AdminLayout.tsx`: admin shell.
- `frontend/src/hooks`: business info, toast, and websocket hooks.
- `frontend/src/types/index.ts`: frontend API data types.

### Frontend Routes

Public/customer:

- `/`
- `/book`
- `/bookings/:id/confirmation`
- `/my-bookings`
- `/profile`
- `/login`
- `/register`
- `/forgot-password`
- `/reset-password`
- `/verify-email`

Admin:

- `/admin`
- `/admin/dashboard`
- `/admin/bookings`
- `/admin/waitlist`
- `/admin/services`
- `/admin/staff`
- `/admin/hours`
- `/admin/blocked-dates`

### Bundle Splitting

The frontend uses route-level lazy loading and Vite manual chunks to keep the initial bundle small.

Implemented in:

- `frontend/src/App.tsx`
- `frontend/vite.config.ts`

Validation result:

- Frontend build passes.
- Main JS bundle is split into page chunks and vendor chunks.
- The previous Vite chunk-size warning is gone.

## Deployment Architecture

### Local Development

Local development uses `docker-compose.yml`.

Services:

- PostgreSQL
- Redis
- Backend with Uvicorn reload
- Frontend with Vite dev server

Ports:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- PostgreSQL: `5432`
- Redis: `6379`

### Production Shape

Production uses `docker-compose.prod.yml`.

Services:

- Caddy edge proxy.
- Backend.
- Frontend served by nginx.
- PostgreSQL.
- Redis.
- One-shot migration service.
- One-shot seed service.

Production edge routing:

- `/api/*` goes to backend.
- `/health` goes to backend.
- `/ready` goes to backend.
- Everything else goes to frontend.

Implemented in:

- `docker-compose.prod.yml`
- `deploy/Caddyfile`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `docs/deployment.md`

Current deployment state:

- Production can use `VITE_API_URL=/api` safely. The frontend normalizes the API
  base so calls like `/api/v1/services` do not become `/api/api/v1/services`.
- Development and production compose builds use distinct image tags so building
  one shape does not overwrite the other local image.

## CI and Validation

### GitHub Actions

CI currently runs:

- Backend tests.
- Alembic migrations.
- Alembic migration drift detection.
- Frontend lint.
- Frontend build.
- Frontend Playwright smoke tests.
- Development compose config validation.
- Production compose config validation.

Implemented in:

- `.github/workflows/ci.yml`

Current limitation:

- Branch protection must be configured in GitHub settings for CI to actually block merges.

### Current Local Validation Results

Last local validation with Docker running, 2026-05-15:

- `docker compose ps`: backend, frontend, db, redis running.
- `docker compose exec backend alembic current`: `0009 (head)`.
- `docker compose exec backend alembic check`: no new upgrade operations.
- `/ready`: database OK, Redis OK.
- `docker compose exec backend python -m pytest`: 75 passed.
- `npm.cmd run lint`: passed.
- `npm.cmd run build`: passed.
- `npm.cmd run test:e2e`: 2 passed.
- `npm.cmd run test:api-url`: passed.
- `npm.cmd run test:datetime`: passed.
- `npm.cmd audit --omit=dev`: 0 vulnerabilities.
- `npm.cmd audit`: 0 vulnerabilities after Vite/tooling upgrade.
- `docker compose config --quiet`: passed.
- `docker compose -f docker-compose.prod.yml config --quiet`: passed, with local Docker config permission warning only.
- `docker compose build`: passed.
- `docker compose -f docker-compose.prod.yml build`: passed.
- `curl http://localhost:8000/api/v1/services`: 200.
- `curl http://localhost:8000/api/api/v1/services`: 404.

### Backend Test Coverage

Existing backend tests cover:

- Booking service rules.
- Availability service rules.
- Reminder worker accounting.
- Account token service.
- Admin dashboard aggregate behavior.
- FastAPI route behavior for auth, booking, admin booking, waitlist conversion,
  audit history, and verified booking dependencies.
- Database-level same-staff overlap constraint.
- Different-staff overlapping bookings allowed.

Current limitation:

- Browser smoke coverage currently focuses on customer booking and logout. A
  broader admin e2e suite would still be useful before a larger admin release.

## Configuration

Important environment variables:

- `SECRET_KEY`: required, at least 32 characters.
- `DATABASE_URL`: backend database URL.
- `REDIS_URL`: backend Redis URL.
- `ALLOWED_ORIGINS`: comma-separated browser origins allowed by CORS.
- `FRONTEND_URL`: public frontend URL used in account action links.
- `SALON_TIMEZONE`: IANA timezone for salon-local dates and business hours.
- `FIRST_ADMIN_EMAIL`: optional first admin seed email.
- `FIRST_ADMIN_PASSWORD`: optional first admin seed password.
- `NOTIFICATIONS_BACKEND`: `console` or `aws`.
- `AWS_ACCESS_KEY_ID`: AWS credential for SES/SNS.
- `AWS_SECRET_ACCESS_KEY`: AWS credential for SES/SNS.
- `AWS_REGION`: AWS region.
- `AWS_SES_FROM_EMAIL`: sender email for SES.
- `AWS_SNS_SENDER_ID`: sender ID for SNS where supported.
- `SLOT_HOLD_TTL_SECONDS`: slot hold TTL.
- `CANCELLATION_WINDOW_HOURS`: customer cancellation/reschedule window.
- `CANCELLATION_LIMIT_PER_DAY`: daily cancellation limit.
- `SLOT_COOLDOWN_SECONDS`: post-cancellation rebooking cooldown.
- `MIN_LEAD_MINUTES`: minimum advance booking window.
- `REMINDERS_ENABLED`: enables/disables reminder loop.
- `REMINDER_LEAD_HOURS`: reminder lead time.
- `REMINDER_TOLERANCE_MINUTES`: reminder matching tolerance.
- `REMINDER_INTERVAL_SECONDS`: reminder loop interval.

Production-only:

- `DOMAIN`: public deployment domain.
- `TLS_EMAIL`: email used by Caddy/ACME.
- `VITE_API_URL`: frontend build-time API base.

## Known Gaps and Risks

### Critical

No critical code issues are currently open from the senior-engineer remediation
plan.

### Launch Operations

1. Branch protection still needs to be configured in GitHub settings so CI
   failures block merges to `main`.

2. Production secrets, DNS, host provisioning, and backup automation are still
   operator tasks.

3. After first production seed, remove `FIRST_ADMIN_EMAIL` and
   `FIRST_ADMIN_PASSWORD` from the production environment.

4. Keep the launch deployment to one backend container/process. Horizontal
   scaling needs Redis pub/sub for slot broadcasts and a dedicated reminder
   worker process.

### Product Decisions

1. Customer-facing waitlist remains deferred. Backend/admin waitlist support
   exists, but customers cannot join a waitlist from the booking UI unless the
   client asks for it.

### Medium Priority

1. Browser smoke coverage exists for booking and logout, but a broader admin
   e2e suite would still be useful before heavy admin feature work.

2. Security hardening can go further after launch: CSP/HSTS headers, refresh
   token rotation policy review, and broader session revocation after password
   reset/change.

## Recommended Next Work

Recommended order:

1. Configure branch protection for `main`.
2. Prepare production secrets, DNS, host, and backup automation.
3. Run a deployed staging/production smoke test with real Caddy routing.
4. Remove first-admin seed credentials from production after initial setup.
5. Decide whether the client wants customer-facing waitlist.
6. Add broader admin e2e coverage if admin workflows keep expanding.
7. Continue security hardening after launch.

## Future Optional Features

Do not build these until the business need is confirmed.

- Online payments.
- Deposits.
- Refund rules.
- No-show fee policy.
- Customer mobile app.
- Push notifications.
- Course/video selling interface.
- Paid learning content.
- Staff payroll/commission reporting.
- Customer loyalty or membership system.
- Marketing campaigns.
