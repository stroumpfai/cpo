# CPO — Chief Pizza Officer

A lightweight, self-hosted web app for coordinating team pizza orders. A **Chief Pizza Officer** opens a time-bound ordering session; team members visit a shareable link (no login required) to pick their pizzas; the CPO watches a live order summary and exports the consolidated list for the pizzeria.

## Features

- **Role-based access** — Admin manages CPO accounts; CPO manages their team; team members order without an account
- **Time-bound sessions** — Sessions open and close automatically at configured times, with an optional grace period
- **Live order board** — CPO dashboard updates in real time via Server-Sent Events
- **Per-team menu** — CPO curates a pizza list (name + price) that persists across sessions
- **Menu import / export** — Share or back up menus as JSON
- **No database** — All data stored as JSON files in mounted Docker volumes
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
| Backend | Python 3.13 · FastAPI · uvicorn |
| Frontend | React 18 · React Router 6 · Vite |
| Auth | JWT (HS256, 30-day expiry) |
| Storage | JSON files on mounted volumes |
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

Open `http://localhost:8002/login` and sign in as admin.

On first run, a default admin account is created automatically. Check the logs for the generated credentials:

```bash
docker compose logs app | grep -i "admin"
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
| `TRUSTED_PROXY` | no | — | Comma-separated IPs of reverse proxies (enables `X-Forwarded-For` parsing) |
| `CONFIG_PATH` | no | `/app/config/config.json` | Path to the credentials file |
| `DATA_DIR` | no | `/app/data` | Path to the session/order data directory |

Generate a strong secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### config.json format

CPO accounts are created via the Admin panel — no manual editing required. The file structure for reference:

```json
{
  "admin": {
    "username": "admin",
    "password_hash": "<bcrypt hash>",
    "created_at": "2026-05-14T10:00:00+00:00"
  },
  "cpos": [
    {
      "id": "<uuid>",
      "username": "john",
      "email": "john@company.com",
      "password_hash": "<bcrypt hash>",
      "team_name": "Engineering",
      "unique_link": "<16+ alphanumeric chars>",
      "created_at": "2026-05-14T10:00:00+00:00"
    }
  ]
}
```

---

## Data Storage Layout

```
/app/
├── config/
│   └── config.json            # Admin + CPO credentials (bcrypt hashed)
└── data/
    └── {cpo_id}/
        ├── menu.json           # Pizza menu (persists across sessions)
        └── {session_id}.json  # Session + all orders for that session
```

All writes are atomic (write to a `.tmp` file, then `os.replace`), preventing data corruption on crash.

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
│  JSON file storage (mounted volumes)                │
│    /app/config/config.json                          │
│    /app/data/{cpo_id}/...                           │
└─────────────────────────────────────────────────────┘
```

**Key design decisions:**
- **Single container** — FastAPI serves both the API and the pre-built React bundle
- **JSON files, no database** — simple, portable, survives restarts via volume mounts; supports ≤ 200 teams comfortably
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
│   ├── storage.py      # JSON file persistence
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
- Rate limiting: 1 submission per IP per 5 seconds (in-process, resets on restart)
- Team ordering links are 16+ character random alphanumeric strings — hard to guess
- CORS: restrict `ALLOWED_ORIGINS` to your domain in production

---

## Deployment Checklist

- [ ] Set a strong `JWT_SECRET` environment variable
- [ ] Mount `/app/config` and `/app/data` as persistent volumes
- [ ] Point a reverse proxy (nginx, Caddy) at port 8002 and terminate TLS there
- [ ] Set `TRUSTED_PROXY` to the reverse proxy IP so client IPs are recorded correctly
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
- [ ] Switch storage from JSON files to SQLite

---

## License

MIT
