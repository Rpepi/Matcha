# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Matcha is a dating web app (42 school project). Stack: **FastAPI** (async) + **PostgreSQL** + **Redis** + **React/TypeScript/Vite**, orchestrated with Docker Compose. No ORM, no Pydantic validators — all SQL is hand-written with parameterized queries, all input validation is manual.

## Commands

All services run via Docker Compose:

```bash
# Start everything (backend on :5000, frontend on :5173, mailpit on :8025)
docker compose up --build

# Run migrations (from inside the backend container or with DATABASE_URL set)
docker compose exec backend python -m app.db.migrations.runner

# Seed 500 fake users
docker compose exec backend python -m app.seed

# Backend logs only
docker compose logs -f backend

# Connect to the DB directly
docker compose exec db psql -U matcha -d matcha
```

There are no test commands yet.

## Architecture

### Backend (`backend/`)

Entry point: `app/wsgi.py` → `app/__init__.py::create_app()`.

`create_app()` wires:
- **Lifespan**: opens the psycopg `AsyncConnectionPool` and a Redis connection pool; both are torn down on shutdown.
- **CORS**: allows `http://localhost:5173` with credentials.
- **Routers**: each domain gets its own `APIRouter` registered in `create_app()`. Currently: `health`, `authentification`.

**Dependency injection pattern** (FastAPI `Depends`):
- `app/db/dependencies.py::get_db` — yields an `AsyncConnection` from the pool (one per request, auto-returned).
- `app/cache/dependencies.py::get_redis` — returns `request.app.state.redis` (shared pool).

**Database** (`app/db/`):
- `pool.py` holds a module-level `AsyncConnectionPool` (psycopg v3, `dict_row` factory — rows come back as dicts).
- `migrations/runner.py` is a standalone script: tracks applied files in a `migrations` table, runs `.sql` files in sorted order.

**Security** (`app/security/`):
- `passwords.py` — Argon2id hashing (`argon2-cffi`). `hash_password`/`verify_password` are async (offloaded to thread). `is_password_valid` checks against `10k-most-common.txt` and rejects all-alpha / all-digit passwords.
- `session.py` — cookie-based sessions stored in Redis (`session:<token>` → `user_id`, TTL 7 days). Cookie signed with HMAC-SHA256 (`SESSION_SECRET` env var). `httponly=True`, `samesite="lax"`.

**New routes**: add a file under `app/routes/`, define an `APIRouter`, then import and `app.include_router(...)` it in `create_app()`.

### Database schema

Migrations live in `app/db/migrations/` (numbered `.sql` files). Key tables:

| Table | Purpose |
|---|---|
| `users` | Core user data, geoloc (`latitude`/`longitude`/`city`), `fame_rating`, `is_online`/`last_seen` |
| `photos` | Up to 5 photos per user, one marked `is_profile` |
| `tags` / `user_tags` | Reusable interest tags |
| `likes` | Mutual like → match |
| `visits` | Profile view history |
| `messages` | Chat messages (matched users only) |
| `notifications` | Real-time notification queue |
| `blocked` | Block list (removes from search, disables chat) |

Geography uses `cube` + `earthdistance` extensions (migration `001`).

### Frontend

Frontend (`frontend/`) is React + TypeScript + Vite. **Not yet scaffolded** — the Dockerfile and source files were deleted from the current branch. Will be rebuilt as part of feature work.

Dev proxy: Vite proxies `/api` → `http://localhost:5000` to avoid CORS in dev.

### Infrastructure

`.env` at repo root (never committed) provides:
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `REDIS_PASSWORD`
- `SESSION_SECRET` (needed by session signing — add this)

Mailpit catches all outbound emails in dev; UI at `http://localhost:8025`.

## Key Constraints (42 project rules)

- **No ORM** — write SQL directly with `%s` placeholders (psycopg parameterized).
- **No Pydantic for input validation** — validate request bodies manually in route handlers.
- **No plaintext passwords**, no SQL injection, no XSS, no unauthorized uploads.
- Pydantic is present (FastAPI dependency) but must not be used for user-input validation. Be ready to argue this point: FastAPI uses Pydantic internally for its own machinery, but route handlers receive raw `Request` objects and parse/validate JSON manually.
