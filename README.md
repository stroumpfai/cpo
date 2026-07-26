# CPO — Chief Pizza Officer

A lightweight, self-hosted web app for coordinating team pizza orders. A **Chief Pizza Officer** opens a time-bound ordering session; team members visit a shareable link (no login required) to pick their pizzas; the CPO watches a live order summary and exports the consolidated list for the pizzeria.

## Features

- **Role-based access** — Admin manages CPO accounts; CPO manages their team; team members order without an account
- **Time-bound sessions** — Sessions open and close automatically at configured times, with an optional grace period
- **Live order board** — CPO dashboard updates in real time via Server-Sent Events
- **Per-team menu** — CPO curates a pizza list (name + price) that persists across sessions
- **Menu import / export** — Share or back up menus as JSON
- **Single-file database** — All data in one SQLite file on a mounted Docker volume; existing JSON-file installs are imported automatically on first start
- **Single container** — Backend (FastAPI) serves the bundled React SPA; one `docker compose up` is all it takes

## Roles

| Role | Access | Can do |
|---|---|---|
| **Admin** | `/admin` (login required) | Create and manage CPO accounts |
| **CPO** | `/dashboard` (login required) | Manage sessions, menu, live order board |
| **Team member** | `/orders/{link}` (no login) | Submit orders while session is active |

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.14 · FastAPI · uvicorn |
| Frontend | React 18 · React Router 6 · Vite |
| Auth | JWT (HS256, 30-day expiry) |
| Storage | SQLite (SQLAlchemy Core + Alembic migrations) |
| Real-time | Server-Sent Events (SSE) |
| Container | Docker (single image) |

---

## Quick Start (Docker)

### 1. Build the frontend and the image

```bash
cd frontend && npm install && npm run build && cd ..
docker build -t cpo-app .
```

### 2. Create local data directories and configure

```bash
mkdir -p ./config ./data
# The container runs as appuser (UID 1000). Give that UID write access to the bind-mounted dirs.
sudo chown -R 1000:1000 ./config ./data
cp .env.example .env
```

> **Note:** If your host user is already UID 1000 (check with `id -u`) the `chown` is a no-op and can be skipped.

Edit `.env` and set a strong `JWT_SECRET`:

```
JWT_SECRET=change-me-to-a-long-random-secret
```

See [Configuration](#configuration) for all options.

### 3. Run

```bash
docker compose up -d
```

On a fresh install, create the admin account first (writes directly into the database file):

```bash
venv/bin/python scripts/create_admin.py --db ./data/cpo.db
```

Then open `http://localhost:8002/login` and sign in as admin.

**Upgrading from a JSON-file install?** Nothing to do: on first start the app runs its schema migrations, imports `config.json` and all `data/{cpo_id}/*.json` files into `data/cpo.db`, and archives the originals (`data/_migrated_json/`, `config.json.migrated`). Check the logs:

```bash
docker compose logs app | grep -i "import"
```

---

## Development Setup

### Backend (FastAPI)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run with hot-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8002
```

### Frontend (React + Vite)

In a second terminal:

```bash
cd frontend
npm install
npm run dev          # dev server on http://localhost:5173 (proxies /api → :8002)
```

The Vite dev server proxies `/api` requests to `localhost:8002`, so the frontend and backend talk without CORS issues.

### Production build (frontend bundled into backend)

```bash
cd frontend && npm run build    # outputs to backend/dist/
```

FastAPI then serves `backend/dist/` as a static SPA for all non-`/api` paths.

---

## Running Tests

```bash
# Backend
cd backend && pytest tests/ -v

# Frontend (unit)
cd frontend && npm test

# Frontend (E2E — requires running app)
cd frontend && npx playwright test
```

Test coverage includes:
- **Unit**: Pydantic models, storage I/O, session status computation, password hashing
- **Integration**: auth (login, JWT, role guards), admin endpoints, CPO endpoints (sessions, menus, summaries, order deletion), public order endpoints, SSE streaming
- **End-to-end**: full ordering flow, grace-period logic, rate limiting, role separation, multi-pizza submissions

---

## Configuration

### Environment variables

All configuration is via environment variables (`.env` file or passed directly to the container):

| Variable | Required | Default | Description |
|---|---|---|---|
| `JWT_SECRET` | **yes** | `dev-secret-change-in-production` | HS256 signing key — **change this in production** |
| `ALLOWED_ORIGINS` | no | same-origin | Comma-separated CORS origins (e.g. `https://cpo.example.com`) |
| `TRUSTED_PROXY` | behind a proxy: **yes** | — | Comma-separated IPs of reverse proxies (enables `X-Forwarded-For` parsing). Without it, all requests appear to come from the proxy IP: rate limits become global (one user can block everyone) and per-order IP tracking is useless |
| `COOKIE_SECURE` | no | `true` | `Secure` flag on the auth cookie. Leave on in production (TLS at the proxy); set `false` only for plain-HTTP local runs |
| `DATABASE_PATH` | no | `/app/data/cpo.db` | Path to the SQLite database file |
| `CONFIG_PATH` | no | `/app/config/config.json` | Legacy credentials file — only read once, for the JSON→SQLite import |
| `DATA_DIR` | no | `/app/data` | Data directory (holds the database; legacy JSON session files are imported from here) |

Generate a strong secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Data Storage

All data lives in a single SQLite database:

```
/app/data/
├── cpo.db                     # accounts, menus, sessions, orders
├── cpo.db-wal, cpo.db-shm     # SQLite write-ahead-log sidecar files
└── _migrated_json/            # archived legacy JSON files (after first-boot import)
```

Tables: `admins`, `cpos`, `menus`, `pizzas`, `sessions`, `orders`. The schema is
versioned with Alembic (`backend/migrations/`) and upgraded automatically at startup.
CPO accounts are created via the Admin panel — no manual editing required.

**Backups**: while the container is running, use `sqlite3 /app/data/cpo.db ".backup /app/data/backup.db"`;
or stop the container and copy `cpo.db*` (including the `-wal` file).

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Docker container                  │
│                                                     │
│  React SPA (built, served as static files)          │
│         │ /api/*                                    │
│         ▼                                           │
│  FastAPI (uvicorn)                                  │
│    ├── /api/auth      — login, logout               │
│    ├── /api/admin     — CPO account management      │
│    ├── /api/cpo       — sessions, menu, summary     │
│    │     └── /summary/sse  — Server-Sent Events     │
│    └── /api/orders    — public order submission     │
│                                                     │
│  SQLite (mounted volume)                            │
│    /app/data/cpo.db                                 │
└─────────────────────────────────────────────────────┘
```

**Key design decisions:**
- **Single container** — FastAPI serves both the API and the pre-built React bundle
- **SQLite, single file** — no database server; survives restarts via the volume mount; WAL mode keeps the live dashboard reads unblocked during order writes; ready for joins (statistics, multiple menus per team)
- **SSE, not polling** — the CPO dashboard subscribes to `GET /api/cpo/sessions/{id}/summary/sse`; orders from team members push events within ~1 second
- **Rate limiting in-process** — 1 order submission per IP per 5 seconds; resets on container restart (acceptable for MVP)
- **Stateless JWT** — 30-day tokens; logout is client-side (token dropped from `localStorage`)

---

## Session Lifecycle

```
[CPO creates session]
        │
        ▼
  upcoming ──► (start_time reached) ──► active
                                            │
                                  (end_time + grace_period)
                                            │
                                            ▼
                                         closed
```

- **Grace period** (default 2 min): orders submitted within 2 minutes after `end_time` are still accepted server-side. The team order page UI hides the form at `end_time`, but late network submissions are processed.
- **One active session per CPO**: creating a second session while one is active or upcoming returns HTTP 409.

---

## Project Structure

```
cpo/
├── backend/            # FastAPI app
│   ├── main.py         # Entry point, middleware, router wiring
│   ├── routers/        # auth, admin, cpo, orders
│   ├── services/       # Business logic
│   ├── models.py       # Pydantic schemas
│   ├── storage.py      # SQLite persistence (SQLAlchemy Core)
│   ├── schema.py       # Table definitions
│   ├── db.py           # Engine + migration runner
│   ├── migrations/     # Alembic schema migrations
│   ├── json_migration.py # One-time legacy JSON import
│   ├── security.py     # JWT & auth helpers
│   └── tests/
├── frontend/           # React / Vite SPA
│   └── src/
│       ├── pages/      # LoginPage, AdminPanel, CPODashboard, TeamOrderPage, …
│       ├── components/
│       └── api.js      # API client
├── spec/               # Requirements & design reference
├── design/             # Wireframes
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## API Overview

Full spec in [`spec/specification.md`](spec/specification.md).

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/login` | none | Returns JWT + role |
| `GET` | `/api/admin/cpos` | admin | List CPO accounts |
| `POST` | `/api/admin/cpos` | admin | Create CPO account |
| `POST` | `/api/admin/cpos/{id}/reset-password` | admin | Reset CPO password |
| `GET` | `/api/cpo/me` | cpo | Current CPO profile (includes `unique_link`) |
| `POST` | `/api/cpo/sessions` | cpo | Create session |
| `GET` | `/api/cpo/sessions` | cpo | List sessions |
| `GET` | `/api/cpo/sessions/{id}/summary` | cpo | Fetch order summary |
| `GET` | `/api/cpo/sessions/{id}/summary/sse` | cpo\* | Live summary stream (SSE) |
| `GET/POST/PUT/DELETE` | `/api/cpo/menu[/{id}]` | cpo | Pizza menu CRUD |
| `DELETE` | `/api/cpo/orders/{id}` | cpo | Delete an order |
| `GET` | `/api/orders/{link}` | none | Session status + menu |
| `POST` | `/api/orders/{link}/submit` | none | Submit order (rate-limited) |

\* The SSE endpoint also accepts `?token=<jwt>` because browser `EventSource` cannot send custom headers.

---

## Security Notes

- Passwords hashed with bcrypt (12 rounds)
- JWT signed with HS256; set a strong `JWT_SECRET` in production
- Browsers authenticate via an `HttpOnly; Secure; SameSite=strict` cookie (not readable from JS, so XSS cannot exfiltrate the token); `Authorization: Bearer` is still accepted for API clients
- Request bodies are capped at 1 MB (HTTP 413 above that)
- Rate limiting: 1 submission per IP per 5 seconds (in-process, resets on restart)
- Team ordering links are 16+ character random alphanumeric strings — hard to guess
- CORS: restrict `ALLOWED_ORIGINS` to your domain in production

---

## Deployment Checklist

- [ ] Set a strong `JWT_SECRET` environment variable
- [ ] Mount `/app/data` as a persistent volume (keep `/app/config` mounted for the release that imports a legacy JSON install; it can be dropped afterwards)
- [ ] Point a reverse proxy (nginx, Caddy) at port 8002 and terminate TLS there
- [ ] Set `TRUSTED_PROXY` to the reverse proxy IP — **required behind a proxy**, otherwise rate limiting degrades to a single global bucket and recorded client IPs are all the proxy's
- [ ] Set `ALLOWED_ORIGINS` to your domain
- [ ] Set up log rotation for container stdout

---

## Roadmap

Possible improvements beyond the current MVP:

**Menu**
- [ ] Multiple named menu lists (e.g. per-occasion or per-pizzeria)
- [ ] CSV import of pizza list
- [ ] Sorting pizzas in the menu list

**Dashboard**
- [ ] Sorting the order table by column
- [ ] Show/hide columns: timestamp and IP address

**Sessions & Teams**
- [ ] Multiple CPOs sharing one team
- [ ] Magic link / one-time-token for self-service CPO account creation

**Settings (per CPO)**
- [ ] Default session duration and mode (predefined time slots vs. manual)
- [ ] Default grace period

**Admin**
- [ ] Activity stats: flag teams with no sessions in the last N days

**Infrastructure**
- [x] Switch storage from JSON files to SQLite

---

## License

MIT
