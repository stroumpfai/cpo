# CPO — Technical Design

## Technology Stack

| Concern | Choice | Version |
|---|---|---|
| Backend framework | FastAPI | 0.115 |
| ASGI server | Uvicorn (with standard extras) | 0.32 |
| Data validation | Pydantic v2 | 2.10 |
| Authentication | PyJWT (HS256) | 2.10 |
| Password hashing | bcrypt | 4.2 (12 rounds) |
| Frontend framework | React | 18.3 |
| Frontend routing | React Router v6 | 6.28 |
| Frontend bundler | Vite | 6.0 |
| Backend test runner | pytest + pytest-asyncio | 8.3 / 0.24 |
| Frontend test runner | Vitest + Testing Library | 2.1 / 16.1 |
| Runtime | Python 3.13 / Node 18+ | — |
| Container base | python:3.13-slim | — |

---

## High-Level Architecture

```
Browser
  │
  ├─ GET /assets/*        ←  static React bundle (served by FastAPI)
  ├─ GET /api/*           ←  REST + SSE API
  └─ GET /orders/:link    ←  SPA catch-all (index.html)

FastAPI (single process, uvicorn)
  ├─ routers/auth.py      POST /api/auth/login
  ├─ routers/admin.py     /api/admin/**         (Admin JWT required)
  ├─ routers/cpo.py       /api/cpo/**           (CPO JWT required)
  └─ routers/orders.py    /api/orders/**        (no auth)

Storage (JSON files on mounted volumes)
  /app/config/config.json          ← admin + CPO credentials
  /app/data/{cpo_id}/menu.json     ← pizza menu + pizzeria URL
  /app/data/{cpo_id}/{session}.json← session metadata + all orders
```

The frontend bundle is compiled with `npm run build` and copied into `backend/dist/`. FastAPI serves `dist/assets/` as static files and returns `dist/index.html` for every other non-API path (SPA catch-all).

---

## Backend Design

### Layer Model

```
routers/      HTTP boundary — request parsing, response serialisation, auth deps
services/     Business logic — validation, orchestration, SSE streaming
storage.py    I/O layer — atomic JSON reads and writes, no business logic
models.py     Pydantic schemas — storage models and API wire types (separate)
security.py   JWT creation / validation, FastAPI dependency factories
config.py     Constants from environment variables (paths, secrets, limits)
utils.py      Pure helpers — ID generation, password hashing, session status
```

Routers never call `storage` directly; they go through a service. Services are thin modules (one per domain), not classes.

### Data Model

Three kinds of JSON file on disk:

**`config.json`** — single file, holds the `AdminRecord` and the list of `CPORecord`s. Written atomically via a temp-file + `os.replace` rename.

**`{cpo_id}/menu.json`** — per-CPO file, holds the list of `Pizza` objects and an optional `pizzeria_url`. Missing file is treated as an empty menu.

**`{cpo_id}/{session_id}.json`** — one file per session. Contains session metadata (`session_date`, `start_time`, `end_time`, `grace_period_minutes`, optional `closed_at`) and the full list of `Order` objects embedded inline. Each order records: pizza id/name/price, member name, client IP, timestamp, optional comment, and a `received` boolean.

All writes go through `storage._save()` which writes to a `.tmp` sibling file, then renames it atomically — no partial writes visible to concurrent readers.

### Session Lifecycle and Status

Status is computed on every read from three inputs: `session_date`, `end_time + grace_period_minutes`, and an optional `closed_at` override (set by force-close):

- **upcoming** — current UTC time is before `session_date + start_time`
- **active** — between start time and `end_time + grace_period_minutes` (default 2 min)
- **closed** — past grace period, or `closed_at` is set

There is no background scheduler; status is a pure function of the stored times and the wall clock at read time.

### Authentication

Login is shared (`POST /api/auth/login`). The response includes a `role` field (`"admin"` or `"cpo"`) so the client knows where to redirect. Tokens are HS256 JWTs with a 30-day expiry, signed with `JWT_SECRET` (env var, defaults to a dev value). The payload contains `sub` (user id) and `role`.

FastAPI dependencies (`require_admin`, `require_cpo`) extract and validate the token from the `Authorization: Bearer …` header. The SSE endpoint also accepts `?token=` in the query string because the browser `EventSource` API cannot set custom headers.

### Real-Time Updates (SSE)

`GET /api/cpo/sessions/{id}/summary/sse` returns a `StreamingResponse` backed by an async generator (`cpo_service.session_sse_events`). The generator polls the session file once per second using `asyncio.to_thread` to avoid blocking the event loop. It computes a hash over the order count, each order's `received` flag, and the session status. A push event is emitted only when the hash changes. The stream terminates and emits a `session_closed` event once the session is past its grace period.

### Rate Limiting

Order submission is rate-limited to one request per client IP per 5 seconds. The limit is enforced in-process via a dict (`{ip: last_monotonic_timestamp}`). The slot is consumed before link or session validation, so even invalid requests count against the limit. The store resets on server restart (acceptable for MVP scale).

---

## Frontend Design

### Routing and Guards

React Router v6 defines six routes:

| Path | Component | Auth |
|---|---|---|
| `/login` | `LoginPage` | none (redirects if already logged in) |
| `/orders/:link` | `TeamOrderPage` | none |
| `/admin` | `AdminPanel` | Admin JWT |
| `/dashboard` | `CPODashboard` | CPO JWT |
| `/dashboard/new-session` | `NewSession` | CPO JWT |
| `/dashboard/pizzas` | `PizzaMenu` | CPO JWT |

`PrivateRoute` wraps protected routes; it reads the JWT from `localStorage`, decodes it without verification (the server validates on each request), and redirects to `/login` if the token is missing or expired.

CPO pages are further wrapped in `Layout`, which renders the sidebar navigation.

### API Client

`src/api.js` exports a single `api` object with `get`, `post`, `put`, `patch`, and `delete` methods. All methods attach `Authorization: Bearer …` from `localStorage`, and redirect to `/login` on a 401 response. A 204 response returns `null`; all other successful responses are parsed as JSON.

### State Management

There is no global state library. Each page component owns its own state with `useState` / `useEffect`. Data flows from API calls into local state; child components receive data and callbacks as props.

The CPO dashboard uses two mechanisms to keep state consistent:

- **SSE** (`EventSource`) for live pushes during an active session — handled by a `useEffect` that opens the stream when a non-closed session is selected and tears it down on cleanup.
- **`reconcilePaidSet`** — syncs the local `paidSet` (which tracks which orders have been marked received) against the authoritative `received` flag in the latest SSE payload, while skipping orders whose PATCH request is still in flight (tracked in `inFlightRef`).

### Component Decomposition

```
CPODashboard
  ├─ SessionHeader       — session info bar, refresh + print buttons
  ├─ StatCards           — member count / pizza count / total / countdown
  ├─ OrdersPerPersonTable— per-person order list with received toggle + delete
  └─ PizzeriaSummaryTable— anonymised pizza counts for the pizzeria
```

Print layout is handled in CSS (`@media print`): tab controls are hidden, both tables are shown stacked with section headings.

---

## Deployment

The app ships as a single Docker image built in two stages:

1. **Builder** (`python:3.13`) — installs Python wheels (including Rust-compiled `pydantic-core`).
2. **Runtime** (`python:3.13-slim`) — copies installed packages and backend source. The React bundle must be built separately (`npm run build`) and placed in `backend/dist/` before the Docker build.

Two volumes are expected at runtime:
- `/app/config` — mounts `config.json` (admin + CPO credentials)
- `/app/data` — mounts the per-CPO session and menu files

The version string (`CPO_VERSION`, `CPO_COMMIT`) is baked in at build time via `ARG`/`ENV` and logged on startup.
