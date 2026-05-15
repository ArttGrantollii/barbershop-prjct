# Vendos Salon

Full-stack salon/barbershop booking app with a FastAPI backend, React/Vite frontend, PostgreSQL, Redis-backed slot holds, Alembic migrations, and Docker Compose for local development.

## Stack

- Backend: FastAPI, SQLAlchemy async, Alembic, PostgreSQL, Redis
- Frontend: React, Vite, TypeScript, Tailwind CSS, TanStack Query
- Background work: in-process booking reminder loop
- Local orchestration: Docker Compose

## Environment

Copy the example env file and fill the required secret:

```powershell
Copy-Item .env.example .env
```

`SECRET_KEY` must be at least 32 characters. Generate one with any secure random generator. If Python is available:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Important local values:

- `SALON_TIMEZONE`: IANA timezone for business hours and customer-facing dates.
- `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD`: optional first admin created by the explicit seed command.
- `ALLOWED_ORIGINS`: comma-separated browser origins allowed by CORS.
- `NOTIFICATIONS_BACKEND`: `console` for local development, `aws` for SES/SNS notification sending.

## Run Locally With Docker

```powershell
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Health check: `http://localhost:8000/health`
- Readiness check: `http://localhost:8000/ready`
- API schema: `http://localhost:8000/api/v1/openapi.json`

The backend dev container runs Alembic migrations and `python -m app.ops.seed`
before starting Uvicorn. The seed command creates default hours/services and an
optional first admin only when those records do not already exist.

The default `docker-compose.yml` is for development. It uses bind mounts,
Vite dev server, and backend autoreload.

## Production Compose

Production has a separate compose file and Dockerfile behavior:

```powershell
Copy-Item .env.prod.example .env
docker compose -f docker-compose.prod.yml up --build
```

Production differences:

- Caddy edge proxy terminates TLS on ports 80/443 and routes `/api`,
  `/health`, and `/ready` to the backend.
- backend runs Uvicorn without `--reload`
- migrations run in a one-shot `migrate` service before the backend starts
- default data and optional first admin are created by a one-shot `seed` service
  before the backend starts
- frontend is built with `npm ci` and served by nginx
- no source-code bind mounts
- Postgres credentials are required by environment expansion

See [docs/deployment.md](docs/deployment.md) for the AWS EC2 single-host
deployment shape, security group rules, update process, and rollback notes.

## Validation

Backend tests are currently easiest to run inside the backend container:

```powershell
docker compose exec backend python -m pytest
docker compose exec backend alembic check
```

The backend suite includes integration tests that create and drop a separate
`vendos_salon_integration_test` PostgreSQL database, run Alembic migrations
against it, and verify database-level booking constraints. Run them against the
Docker Compose database or another Postgres user with database creation rights.

Frontend dependencies should be installed from the lockfile:

```powershell
cd frontend
npm.cmd ci
npm.cmd run lint
npm.cmd run build
npm.cmd audit
```

On Windows PowerShell, prefer `npm.cmd` over `npm` if the `npm.ps1` shim hits permission issues.

Frontend smoke checks:

```powershell
cd frontend
npm.cmd run test:api-url
npm.cmd run test:datetime
npm.cmd run test:e2e
```

The e2e smoke test uses Playwright. On a fresh machine, install the browser once:

```powershell
cd frontend
npx playwright install chromium
```

## Known Local Tooling Notes

- Local Python may not be installed on every development machine; Docker is the reliable backend test path.
- Docker Desktop may require elevated access on Windows for commands that connect to the daemon.
- If npm cannot write under the default user cache, set a writable cache location:

```powershell
$env:NPM_CONFIG_CACHE='C:\tmp\npm-cache'
npm.cmd ci
```

## Development Priorities

Current near-term engineering plan lives in
[docs/open-issues.md](docs/open-issues.md). Work it phase by phase and run each
phase's verification gate before starting the next one.

Current launch checklist:

1. Configure GitHub branch protection so CI is required before merge.
2. Prepare production secrets, DNS, host, and database backups.
3. Run a deployed production smoke test with real Caddy routing.
4. Remove first-admin seed credentials from production after initial setup.
5. Decide whether customer-facing waitlist belongs in the first client release.
