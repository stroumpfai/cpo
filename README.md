# CPO — Chief Pizza Officer

A team pizza ordering web app. A **Chief Pizza Officer** opens a time-bound session; team members follow a shared link and pick their pizzas; the CPO watches orders arrive live and exports a summary.

## Roles

| Role | Access | Can do |
|---|---|---|
| **Admin** | `/admin` (login required) | Create and manage CPO accounts |
| **CPO** | `/dashboard` (login required) | Manage sessions, menu, live order board |
| **Team member** | `/orders/{link}` (no login) | Submit orders while session is active |

---

## Quick start (Docker)

```bash
# 1. Build the frontend and the image
cd frontend && npm install && npm run build && cd ..
docker build -t cpo-app .

# 2. Create the config directory and bootstrap the admin account
mkdir -p ./config ./data
python scripts/create_admin.py --config ./config/config.json

# 3. Run
docker run \
  -v "$PWD/config:/app/config" \
  -v "$PWD/data:/app/data" \
  -p 8000:8000 \
  cpo-app
```

Open `http://localhost:8000/login` and sign in as admin.

---

## Development setup

### Backend (FastAPI)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create a dev config (once)
python ../scripts/create_admin.py --config ./dev-config/config.json

# Run with hot-reload
CONFIG_PATH=./dev-config/config.json \
DATA_DIR=./dev-data \
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (React + Vite)

In a second terminal:

```bash
cd frontend
npm install
npm run dev          # dev server on http://localhost:5173 (proxies /api → :8000)
```

The Vite dev server proxies `/api` requests to `localhost:8000`, so the frontend and backend talk without CORS issues.

### Production build (frontend bundled into backend)

```bash
cd frontend && npm run build    # outputs to backend/dist/
```

FastAPI then serves `backend/dist/` as a static SPA for all non-`/api` paths.

---

## Running tests

```bash
cd backend
pytest tests/ -v
```

Test coverage includes:
- **Unit**: Pydantic models, storage I/O, session status computation, password hashing
- **Integration**: auth (login, JWT, role guards), admin endpoints, CPO endpoints (sessions, menus, summaries, order deletion), public order endpoints, SSE streaming
- **End-to-end**: full ordering flow, grace-period logic, rate limiting, role separation, multi-pizza submissions

---

## Configuration

All configuration lives in a single JSON file (`config.json`) mounted at `/app/config/config.json` in the container (overridable via the `CONFIG_PATH` env var).

### config.json format

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

CPO accounts are created via the `/admin` panel — no manual editing required.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `CONFIG_PATH` | `/app/config/config.json` | Path to config file |
| `DATA_DIR` | `/app/data` | Directory for session and order JSON files |
| `JWT_SECRET` | `dev-secret-change-in-production` | **Change this in production** — HS256 signing key |

Set `JWT_SECRET` by passing `-e JWT_SECRET=<secret>` to `docker run`, or use a `.env` file.  Generate a strong secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Data storage layout

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

## Session lifecycle

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

## API overview

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

## Security notes

- Passwords hashed with bcrypt (12 rounds)
- JWT signed with HS256; set a strong `JWT_SECRET` in production
- Rate limiting: 1 submission per IP per 5 seconds (in-process, resets on restart)
- Team ordering links are 16+ character random alphanumeric strings — hard to guess
- CORS: currently `allow_origins=["*"]`; for production deployments behind a reverse proxy, restrict to your domain

---

## Deployment checklist

- [ ] Set a strong `JWT_SECRET` environment variable
- [ ] Mount `/app/config` and `/app/data` as persistent volumes
- [ ] Run `scripts/create_admin.py` once before first boot
- [ ] Point a reverse proxy (nginx, Caddy) at port 8000
- [ ] Restrict CORS origins in `backend/main.py` if needed
- [ ] Set up log rotation for container stdout
