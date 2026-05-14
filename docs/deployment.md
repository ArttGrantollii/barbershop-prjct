# Production Deployment

This project targets a simple first production deployment on one AWS EC2 host
running Docker Compose.

## Target Shape

- EC2 instance with Docker Engine and Docker Compose plugin.
- DNS `A` record points the salon domain to the EC2 public IP.
- Caddy terminates TLS on ports 80/443 and routes traffic internally:
  - `/api/*`, `/health`, `/ready` -> backend
  - everything else -> frontend
- PostgreSQL and Redis run as Compose services on the same private Docker
  network for the first launch.

This is intentionally a single-host deployment. Move Postgres to RDS and Redis
to ElastiCache once availability, backups, or traffic justify the extra cost.

For the first launch, run exactly one backend container/process. Slot WebSocket
broadcasts are currently in-memory, and the reminder loop runs in-process. Do
not horizontally scale the backend until slot broadcasts use Redis pub/sub and
reminders run in a dedicated worker process.

## Scaling Boundary

The production compose file is a single-backend deployment. Before running two
or more backend replicas, implement all of the following:

- Redis pub/sub, or equivalent shared fanout, for slot WebSocket broadcasts.
- A dedicated reminder worker process so web replicas do not each own a worker
  loop.
- Monitoring for reminder failures and worker health.

Until then, do not use `docker compose up --scale backend=2` or an equivalent
multi-replica setup.

## Frontend API URL

For the single-domain production deployment, keep:

```env
VITE_API_URL=/api
```

The frontend normalizes this value so browser requests go to `/api/v1/...`
through Caddy. Local development can continue to use a direct backend origin,
such as `http://localhost:8000`.

## Seeding

FastAPI startup does not create users, hours, or services. Initial data is
created by an explicit command:

```bash
python -m app.ops.seed
```

In development, the backend container runs this command after migrations for
convenience. In production, `docker-compose.prod.yml` runs it as a one-shot
`seed` service after `migrate` and before `backend`.

The command is idempotent:

- creates default business hours only when no business hours exist
- creates default services only when no services exist
- creates `FIRST_ADMIN_EMAIL` only when both first-admin env vars are set and
  that email does not already exist

After first production setup, remove `FIRST_ADMIN_EMAIL` and
`FIRST_ADMIN_PASSWORD` from `.env` so future seed runs cannot recreate an admin
account you intentionally removed.

## Required AWS Security Group Rules

- Inbound `80/tcp` from `0.0.0.0/0` and `::/0`
- Inbound `443/tcp` from `0.0.0.0/0` and `::/0`
- Inbound `22/tcp` only from your IP
- Do not expose Postgres, Redis, backend, or frontend container ports publicly.

## First Deploy

1. Install Docker on the EC2 instance.
2. Clone the repository.
3. Copy `.env.prod.example` to `.env`.
4. Fill every required production value:
   - `DOMAIN`
   - `TLS_EMAIL`
   - `POSTGRES_PASSWORD`
   - `SECRET_KEY`
   - `ALLOWED_ORIGINS`
   - `FRONTEND_URL`
   - AWS notification settings if `NOTIFICATIONS_BACKEND=aws`
5. Start production services:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The `migrate` service runs `alembic upgrade head` before the backend starts.
The `seed` service then creates default data if needed.
Caddy will request and renew TLS certificates automatically for `DOMAIN`.

## Health Checks

- `GET /health` is a lightweight process check.
- `GET /ready` checks database and Redis connectivity.

Use `/ready` for container readiness and deployment validation.

## Updating

```bash
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl -fsS https://your-domain.example/ready
```

## Rollback

1. Identify the last known-good commit.
2. Check it out on the server.
3. Rebuild and restart:

```bash
git checkout <known-good-sha>
docker compose -f docker-compose.prod.yml up -d --build
curl -fsS https://your-domain.example/ready
```

Rollback is safest before migrations that remove columns or tables. Treat
destructive migrations as separate release events with a database backup.

## Backups

For the single-host launch, schedule regular Postgres dumps and copy them off
the instance. Before any production migration, take a fresh backup.

When the business depends on this system daily, move the database to RDS with
automated backups.
