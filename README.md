# Matcha

A dating web app: sign up, build a profile, get suggestions, like, match, chat and get notified in real time. School project (42), built with **FastAPI** (async) + **PostgreSQL 16** + **Redis 7** + **React 19 / TypeScript / Vite**, everything orchestrated by Docker Compose.

No ORM and no validation library: every SQL query is written by hand with parameters (`%s`), and every input is checked by hand (`backend/app/validation.py`).

## Quick start

You only need [Docker](https://docs.docker.com/get-docker/) with Compose.

```bash
# 1. Configuration: copy the template, then replace every "change-me"
#    (generate a secret with: openssl rand -hex 32)
cp .env.example .env

# 2. Build and start everything. The database schema is created automatically
#    (pending migrations run before the API starts).
docker compose up --build

# 3. In a second terminal, fill the database with ~500 fake profiles
docker compose exec backend python -m app.seed
```

Seeding takes a little while: every fake user gets a real Argon2 password hash.

| What | Where |
|---|---|
| The app | http://localhost:5173 |
| The API | http://localhost:5000 |
| Emails sent by the app (verification, password reset) | http://localhost:8025 (Mailpit) |
| PostgreSQL / Redis | `localhost:5432` / `localhost:6379` |

To start again from nothing (this deletes the database and the uploaded photos):

```bash
docker compose down -v
```

### Try it

1. **Register** with an email, a username, your names and a password. Common passwords are refused.
2. Open **Mailpit** (http://localhost:8025) and click the verification link. The account cannot log in before that.
3. **Log in** with your username (or your email), then complete your profile: gender, orientation, bio, interests, birth date, photos (a profile picture is required to like someone) and location.
4. The seeded profiles are spread around a few Thai cities (Bangkok, Chiang Mai, Phuket…). Their passwords are random: to see a match, a chat or notifications, register a second account (use a private window).

### Servers

- **API**: [Uvicorn](https://www.uvicorn.org/) running the FastAPI app, with `--reload` in development. It also serves the chat (WebSocket) and the notifications (Server-Sent Events).
- **Frontend**: the Vite dev server, which forwards `/api/...` to the API.

There is no Apache or Nginx: the subject allows an embedded web server.

## Features

- **Accounts**: registration with email verification, login by username or email, password reset by email, Google sign-in, logout from any page.
- **Profile**: gender, orientation, bio, interests (tags), up to 5 photos, location (GPS or typed city). Everything can be edited at any time.
- **Suggestions and search**: profiles compatible with your orientation, ranked by common interests, fame, age gap and distance. Filter by age, distance, fame and interests; sort by score, age, distance, fame or common interests.
- **Interactions**: like / unlike, matches, block, report as a fake account, visit history, who liked you, online status and last seen.
- **Chat**: real-time messages between matched users.
- **Notifications**: real-time, for likes, visits, messages, matches and unlikes, with an unread badge on every page.

## Development

Everything runs inside the containers (the backend needs the environment variables from `.env`, so run the tests there too):

```bash
docker compose exec backend python -m pytest tests/ -v      # backend tests
docker compose exec frontend npm run lint                   # lint (oxlint)
docker compose exec frontend npm run build                  # type-check + production build
docker compose exec backend python -m app.db.migrations.runner   # apply migrations by hand
docker compose exec db psql -U matcha -d matcha             # open a database shell
docker compose logs -f backend
```

Migrations are numbered `.sql` files in `backend/app/db/migrations/`. Add a new file instead of editing one that was already applied.

```
backend/app/
  routes/        authentification, oauth, profile, users, chat, notifications
  security/      sessions, Argon2 passwords, signed tokens, rate limiting (Redis)
  db/            connection pool and migrations
  presence.py    who is online (notification streams counted in Redis)
  seed.py        fake profiles
backend/tests/   ~1300 tests
frontend/src/    pages, components, hooks, context, api wrappers
```

## Security

- Passwords are hashed with Argon2id; common and weak passwords are refused.
- Every query is parameterized; every value coming from the client is validated before it reaches the database, the password hasher or the file system.
- Sessions live in Redis, in an HttpOnly, `SameSite=Strict` cookie signed with an HMAC.
- Uploads are checked by content (not by the name or the declared type), re-encoded, and served only to logged-in users.
- Requests are rate limited per IP or per account (token bucket in Redis).
- Secrets live in `.env`, which git ignores.

## Troubleshooting

- **The backend exits at start with `RuntimeError ... not set`**: a variable of `.env` is missing; compare it with `.env.example`.
- **A port is already in use** (5000, 5173, 5432, 6379, 8025): stop the other program, or change the mapping in `docker-compose.yml`.
- **"Sign in with Google" fails**: it needs real Google credentials in `.env`. Login with email or username works without them.
