# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CPO (Chief Pizza Officer)** is a team pizza ordering web application. It enables a "Chief Pizza Officer" to open time-bound ordering sessions, team members to submit orders via a unique link (no login), and the CPO to view real-time order summaries and export data.

Three roles:
- **Admin** — manages CPO accounts and other admin accounts (login-required); multiple admins supported, each can change their own password
- **CPO** — manages one team, opens/closes sessions, curates pizza menu, views live order board (login-required); a team can have several CPO accounts (e.g. a deputy covering holidays), all equal peers
- **Team Member** — visits a unique team link, selects pizzas, submits order (no login)

## Technology Stack

| Layer | Choice |
|---|---|
| Frontend | React (SPA, bundled and served by FastAPI) |
| Backend | FastAPI (Python 3.14) with uvicorn |
| Auth | JWT (HS256, 1-month expiry) |
| Storage | SQLite (`/app/data/cpo.db`, SQLAlchemy Core + Alembic migrations) |
| Real-time | Server-Sent Events (SSE) for live order updates |
| i18n | i18next + react-i18next (`en`, `de-CH`, `fr-CH`, `it-CH`, bundled statically) |
| Containerization | Single Docker container, Python 3.14-slim |

## Architecture

### Backend (FastAPI)
- **Structure**: Modular FastAPI app with routers for auth, admin, CPO, and team endpoints
- **Authentication**: JWT tokens issued on login, required for admin/CPO routes
- **Storage**: SQLite at `/app/data/cpo.db` (override with `DATABASE_PATH`).
  - `backend/storage.py` is the only persistence layer (SQLAlchemy Core); it accepts/returns the Pydantic models from `models.py`
  - Tables in `backend/schema.py`: `admins`, `teams`, `cpos`, `team_invites`, `menus`, `pizzas`, `sessions`, `orders`; schema versioned via Alembic (`backend/migrations/`), upgraded at startup
  - **`teams` owns the data, `cpos` is just a login**: `menus.team_id` and `sessions.team_id` reference `teams.id`; each `cpos` row carries a `team_id` FK, so several logins share one team's menus/sessions/orders
  - `cpos.language` and `admins.language` (both nullable text, migration `0007_language`) hold the account's UI language; `NULL` = follow the browser
  - Legacy JSON installs (`config.json` + `/app/data/{cpo_id}/*.json`) are imported once at startup by `backend/json_migration.py`, then archived
- **Real-time**: SSE endpoint streams summary updates to connected CPO dashboards

### Frontend (React)
- **Layout**: Sidebar nav + main content area (authenticated routes show sidebar)
- **State**: React `useState` + `useEffect` (no global state library)
- **Routing**: Six main routes (see Routes section below)
- **Real-time**: `EventSource` API connected to SSE endpoint during active sessions
- **Copy**: no literals in JSX — every string goes through `useTranslation()`'s `t()` (see Internationalization below)

### Internationalization
- **Locales**: `en` (default, fallback and source of truth), `de-CH`, `fr-CH`, `it-CH`. Exactly these four tags everywhere — DB column, API literal, JSON filenames, i18next keys, `localStorage`. Swiss conventions: `de-CH` never uses `ß` (always `ss`), dates render `01.08.2026`, prices stay `12.50` in all four
- **Module**: `frontend/src/i18n/` — `locales.js` (the `LOCALES` registry: `{ tag, label, resource }`, plus `DEFAULT_LOCALE`/`SUPPORTED_TAGS`), `index.js` (i18next init + `applyLanguage`/`applyAccountLanguage`), `detect.js`, `storage.js` (the `cpo_lang` mirror), `apiError.js`, `locales/*.json`. Resources are bundled statically — no lazy loading, no Suspense
- **Detection order**, first hit wins: `localStorage['cpo_lang']` → the account's `language` (from `GET /api/cpo/me` or `GET /api/admin/me`; `null` = no opinion) → `navigator.languages` (exact tag, then primary subtag, so `de`/`de-DE`/`de-AT` → `de-CH`) → `en`. The localStorage mirror exists so a reload applies the account language *before* the profile fetch resolves, instead of flashing English
- **Where the preference lives**: CPOs set it in CPOSettings' "Your preferences" card (`PATCH /api/cpo/language`), admins in AdminPanel's "My account" section (`PATCH /api/admin/language`). Both write the login's own row and apply immediately — neither logs the user out. Public pages have no account, so `components/LanguageSwitcher.jsx` (order page, join page, login page) writes the localStorage mirror instead
- **Key namespaces**: one JSON file per language, nested one level — `common`, `nav`, `order`, `auth`, `dashboard`, `session`, `menus`, `stats`, `team`, `settings`, `admin`, `errors`. Plurals use i18next suffixes (`plateCount_one`/`plateCount_other`), interpolation uses `{{name}}`
- **Adding a language** (the `LOCALES` registry is the only extension point): copy `en.json`, translate every value, add one row to `LOCALES`, extend the `Language` literal in `backend/models.py`, run `npm test`. `src/test/i18n/parity.test.js` names every missing/extra key, empty value, mismatched placeholder, and any `ß` in `de-CH`; `backend/tests/test_error_codes.py` checks every error code has an `errors.<code>` message. See README → *Adding a language*
- **Dates**: `frontend/src/utils/format.js` (`formatDate`/`formatIsoDate`/`formatTime`/`formatDateTime`) — always pass `i18n.language`, never `undefined` (that is the browser's locale, not the user's choice). Prices keep `toFixed(2)`

### Data Models
See `spec/specification.md` §7 for full schemas. Key entities:
- **Session**: Time-bound ordering window (start, end, optional 2-min grace period); references the menu it serves (`menu_id`, live — no snapshot)
- **Order**: Single pizza for one member; multiple pizzas = multiple order rows
- **Member identity**: `orders.member_name` holds either a display name or an email address, depending on the owning team's `member_identifier` setting. Values are stripped in both modes; emails are validated (RFC 5322, no DNS lookup) and lower-cased before storage
- **Team**: The unit that owns everything — `team_name`, the public `unique_link`, `currency`, `member_identifier`, `stats_reset_at`, plus all menus/sessions/orders. One or more CPO logins belong to it
- **CPO login**: Credentials only (`username`, `email`, `password_hash`, `token_version`) plus a `team_id` and a personal `language` (`"en" | "de-CH" | "fr-CH" | "it-CH" | null`). All logins on a team are equal peers
- **Admin account**: `username`, `password_hash`, `token_version`, plus the same personal `language` (`null` = follow the browser)
- **Team invite**: Single-use, 24h-expiry token (`config.TEAM_INVITE_EXPIRY_HOURS`) letting a new CPO self-register onto an existing team via the public `/join/{token}` page
- **Menu**: Multiple named menus per team (each: name, website URL, item list); exactly one is the default while any exist; persists across sessions
- **Summary**: Two views — "orders per person" (with IPs/names for CPO oversight) and "consolidated for pizzeria" (anonymized counts)

## Key Requirements & Constraints

### Security
- **Rate limiting**: Max 1 order submission per IP per 5 seconds (HTTP 429 if exceeded)
- **IP tracking**: CPO sees client IP in order summary (identifies coordinated spam)
- **Session link**: Random alphanumeric 16+ chars, unique per team (prevents guessing)
- **Password hashing**: bcrypt, minimum 10 rounds
- **Input validation**: Sanitize all user inputs; validate pizza prices ≥ 0.01, name/pizza name required

### Session Lifecycle
- **Automatic opening**: Session opens at specified start time
- **Automatic closing**: Session closes 2 min after specified end time (grace period)
- **Status**: Active session = orders accepted; closed session = reject all submissions, show "Session is closed"
- **One per team**: Only one active session per CPO/team at any time; multiple teams can run in parallel

### Order Model
- **Add-to-cart**: Team members add multiple pizzas in one submission; creates one order row per pizza
- **No modification post-submit**: End-users cannot edit/cancel after submission; CPO can delete individual orders
- **Quantity fixed**: Always 1 pizza per order row (users add multiple rows for multiple pizzas)

### UI/UX
- **Responsive**: Mobile-first, works on 320px+ widths
- **Design tokens**: See `design/README.md` for colors, typography, spacing (tomato red accent `#d7372b`, clean minimal aesthetic)
- **Wireframes**: `design/wireframes.html` shows all screens (low-fidelity reference only; implement with clean production styling)

## Development Setup

### Prerequisites
- Python 3.14+
- Node.js 18+ (if building frontend separately)
- Docker (for containerization)

### Backend Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests (if added)
pytest
```

### Frontend Setup
If building frontend separately (before bundling into FastAPI):
```bash
cd frontend
npm install
npm run dev      # Dev server
npm run build    # Production bundle
```

### Configuration
- **config.json** format: See `spec/specification.md` §11.3 (legacy bootstrap; storage is SQLite now)
- **Environment**: `JWT_SECRET` is required — the app refuses to start without it. Optional: `CONFIG_PATH`, `DATA_DIR`, `DATABASE_PATH`, `COOKIE_SECURE`, `ALLOWED_ORIGINS`, `TRUSTED_PROXY`, `LOGIN_MAX_ATTEMPTS` (default 5), `CPO_VERSION`/`CPO_COMMIT` (see README → *Environment variables*)

## Directory Structure (Expected)

```
cpo/
├── spec/                      # Specification & design (read-only reference)
│   ├── specification.md       # Full API, data models, requirements
│   └── vision.md
├── design/                    # Wireframes & design reference (read-only)
│   ├── wireframes.html
│   ├── screens.jsx
│   └── README.md
├── backend/                   # FastAPI app
│   ├── main.py                # App entry point
│   ├── requirements.txt        # Python dependencies
│   ├── routers/               # API route modules (auth, admin, cpo, orders)
│   ├── services/              # Business logic (session, order, menu mgmt)
│   ├── models.py              # Pydantic schemas
│   ├── error_codes.py         # AppError + the CODES frozenset
│   ├── config.py              # Config loader, constants
│   └── tests/
├── frontend/                  # React app (optional, if built separately)
│   ├── src/
│   │   ├── i18n/              # i18next setup + locales/{en,de-CH,fr-CH,it-CH}.json
│   │   └── test/              # Vitest suites
│   ├── e2e/                   # Playwright specs + fixtures
│   ├── public/
│   └── package.json           # `npm run build` outputs straight to backend/dist/
├── Dockerfile
├── docker-compose.yml         # Optional: for local dev
└── CLAUDE.md
```

## Routes & Screens

| Path | Component | Auth | Key Behavior |
|---|---|---|---|
| `/login` | Login | none | Shared form; redirects to `/admin` (Admin) or `/dashboard` (CPO) after JWT issued |
| `/admin` | AdminPanel | Admin JWT | Team management, grouped by team with its member logins nested: create a team (+ its first login), rename a team, edit a login's email, reset a login's password, delete a login (deleting a team's last login deletes the team and its data). An "Administrators" section manages admin accounts, and a "My account" card holds own password change + UI language |
| `/dashboard` | CPODashboard | CPO JWT | Order summary with live SSE updates; two tabs (per-person + pizzeria consolidated). Every column header sorts (per-person defaults to newest first, pizzeria to plate A→Z); each tab keeps its own sort and print reproduces both |
| `/dashboard/new-session` | NewSession | CPO JWT | Create session: date, start time, end time, grace period (2 min default), menu dropdown (default menu preselected; blocked with no menus) |
| `/dashboard/menus` | Menus | CPO JWT | Manage menus: create/rename/delete/set-default; per-menu item editor (add/edit/delete items, website URL, export/import). `/dashboard/pizzas` redirects here |
| `/dashboard/stats` | CPOStats | CPO JWT | Team statistics: last 5 sessions (any status) with item counts, per-menu top 3 plates/people, general totals (sessions, distinct members/plates, per-menu use count), "Reset counters" action |
| `/dashboard/team` | TeamMembers | CPO JWT | Self-service peer management: list teammates (own row marked "you"), reset a teammate's password, remove a teammate or leave (blocked when only one remains), generate/copy/revoke invite links |
| `/dashboard/settings` | CPOSettings | CPO JWT | Team settings (name, currency, member identifier) and a personal "Your preferences" card holding the UI language; separate "Change password" form (that one signs you out, the settings above do not) |
| `/orders/:link` | TeamOrderPage | none | Team member: enter name **or email** (per the team's `member_identifier`), pick pizza, add to cart, submit; the value is remembered in localStorage per team link, with a "not you? clear" link; shows session status; language switcher in the header |
| `/join/:token` | JoinPage | none | Invite redemption: shows the inviting team's name, then username/email/password signup; on success the new CPO is auto-logged-in and lands on `/dashboard`. 404 view for an unknown, expired or already-used token |

## Key API Endpoints

See `spec/specification.md` §9 for full spec. Essential endpoints:

**Auth**
- `POST /api/auth/login` — Shared admin/CPO login → JWT token

**Admin endpoints** (authenticated)
- `GET /api/admin/cpos` — teams, each with its member logins nested; `POST /api/admin/cpos` — create a team plus its first login
- `PUT /api/admin/cpos/{id}` — update one login's email; `PUT /api/admin/teams/{team_id}` — rename a team
- `DELETE /api/admin/cpos/{id}` — delete a login; deleting a team's last login deletes the team (menus/sessions/orders cascade)
- `POST /api/admin/cpos/{id}/reset-password` — reset one login's password
- `GET/POST /api/admin/admins`, `DELETE /api/admin/admins/{id}` — admin account management (cannot delete self or the last admin)
- `POST /api/admin/admins/{id}/reset-password` — peer reset (forbidden on own account; use change-password)
- `POST /api/admin/change-password` — change own password (requires current password; revokes existing tokens)
- `GET /api/admin/me` — own profile (`id`, `username`, `language`)
- `PATCH /api/admin/language` — set own UI language (`"en" | "de-CH" | "fr-CH" | "it-CH" | null`; `null` clears it back to browser detection, 422 on any other value); returns the refreshed profile

**CPO endpoints** (authenticated)
- `GET /api/cpo/me` — Current CPO login joined with its team (`team_id`, `team_name`, `unique_link`, `currency`, `member_identifier`, `language`)
- `GET /api/cpo/team-members` — teammates (own row flagged `is_self`); `DELETE /api/cpo/team-members/{id}` — remove one (409 on the team's last member); `POST /api/cpo/team-members/{id}/reset-password` — peer reset
- `GET/POST /api/cpo/team-invites`, `DELETE /api/cpo/team-invites/{id}` — create/list/revoke invite links (list shows pending only: unused and unexpired)
- `PATCH /api/cpo/team-name`, `PATCH /api/cpo/currency` — team settings
- `PATCH /api/cpo/member-identifier` — what the public form asks members for (`"name" | "email"`; 422 on any other value)
- `PATCH /api/cpo/language` — this login's own UI language (`"en" | "de-CH" | "fr-CH" | "it-CH" | null`; `null` = follow the browser, 422 on any other value); updates by `user_id`, not `team_id`, and returns the refreshed `CPOResponse`
- `POST /api/cpo/change-password` — change own password
- `POST /api/cpo/sessions` — Create session (optional `menu_id`; omitted → default menu; 422 when no menus exist)
- `GET /api/cpo/sessions/{session_id}/summary` — Fetch summary (both views)
- `GET /api/cpo/sessions/{session_id}/summary/sse` — Stream updates via SSE
- `GET/POST /api/cpo/menus`, `PATCH/DELETE /api/cpo/menus/{id}` — menu CRUD (DELETE → 409 if an active/upcoming session uses it; deleting the default promotes the oldest remaining)
- `POST /api/cpo/menus/{id}/default` — set default menu
- `GET/POST /api/cpo/menus/{id}/pizzas`, `PUT/DELETE /api/cpo/menus/{id}/pizzas/{pizza_id}` — item ops
- `GET /api/cpo/menus/{id}/export`, `POST /api/cpo/menus/{id}/import` — portable menu JSON
- `GET /api/cpo/stats` — recent sessions (up to 5), per-menu top-3 plates/people + use count, general totals; all figures respect `stats_reset_at`
- `POST /api/cpo/stats/reset` — sets `stats_reset_at` to now (returns the refreshed stats); deletes no session/order data, only shifts the counting cutoff

**Team endpoints** (no auth)
- `GET /api/orders/{unique_link}` — Session status + available pizzas + `member_identifier`
- `POST /api/orders/{unique_link}/submit` — Submit order (rate-limited 1 per IP per 5s). 400 when the identity is empty after stripping, over its per-mode length cap (100 names / 254 emails), or — in email mode — not a valid address

**Join endpoints** (no auth)
- `GET /api/join/{token}` — the inviting team's name; 404 if the token is unknown, expired or used
- `POST /api/join/{token}` — redeem: creates a CPO login on that team and returns a `LoginResponse` (+ auth cookie) for auto-login. 409 on duplicate username/email, 422 on a weak password, 404 on an invalid token

## Important Design Decisions

1. **Single container**: All code (backend + frontend bundle) runs in one Docker container; no microservices
2. **SQLite, not a DB server**: Single-file database in the existing data volume; WAL mode + busy_timeout handle the app's thread concurrency; schema is multi-menu-ready (menus table separate from pizzas) for future features
3. **No order modification by users**: CPO has full control; users contact CPO if they change mind
4. **Quantity = 1 per row**: Users add multiple pizzas by submitting multiple times; simplifies model
5. **IP tracking + rate limit**: Combined defense against spam; CPO can manually review/delete suspicious orders
6. **SSE, not polling**: Real-time updates without constant client requests; reduces server load
7. **JWT, 1-month expiry**: Reasonable for internal teams; login required after expiry
8. **No timezone support**: Prototype simplification; all times local to server
9. **Member identity is one column, read live**: `orders.member_name` stores a name or an email; there is no per-order mode column, and the team's setting is read per request rather than snapshotted onto the session. Flipping it mid-session therefore leaves a mix of names and emails in that session — accepted, because there is no name→email mapping to convert existing rows with, and the CPO can delete and re-add affected orders
10. **Team identity is separate from login identity**: the JWT's `sub` is still the login's own id, but `require_cpo` resolves it to a `team_id` that every menu/session/order/stats query scopes on (`CurrentUser.team_id`). Password and self/peer checks use `user_id`; everything else uses `team_id`. Migration 0006 reuses each pre-existing CPO's id as its new team's id, so no `menus`/`sessions` FK value had to be rewritten
11. **All CPO logins on a team are equal peers**: no owner/deputy hierarchy — any member can run sessions, edit menus, invite teammates, remove a teammate, and reset a peer's password. The only asymmetry is that a team must keep at least one login (mirrors the "cannot delete the last admin" guard). Nothing records *which* login performed an action; per-action attribution was deliberately left out
12. **Invite links, not emailed invitations**: the app sends no email, so joining is a shareable single-use link (24h expiry) redeemed on a public page. `mark_invite_used` only updates rows whose `used_at` is still NULL, making redemption race-safe
13. **Error responses carry a code, and `detail` stays English**: failures return `{detail, code, params}` — `code` is a stable snake_case string from `backend/error_codes.py`'s `CODES` frozenset, `params` holds the interpolated values (`{"max": 100}`, `{"seconds": 5}`). The client translates `errors.<code>` with `params` and falls back to `detail`. `detail` is deliberately left as an English string rather than becoming a structured object: existing pytest assertions read `r.json()["detail"]`, API clients depend on it, and it is the only sensible fallback for a code the frontend does not know yet. `code`/`params` are purely additive; a plain `HTTPException` still produces FastAPI's default shape
14. **Language is a per-login preference, not a team setting**: it lives on `cpos.language`/`admins.language` and is updated by `user_id` — contrast `member_identifier` and `currency`, which live on `teams` and are updated by `team_id`. Two CPOs on the same team can read the app in different languages; what the *team* asks members for is shared. On the public order page there is no account at all, so the choice lives only in the `cpo_lang` localStorage mirror

## Common Development Commands

```bash
# Backend
python -m uvicorn main:app --reload              # Dev server with auto-reload
python -m pytest tests/ -v                        # Run all tests
python -m pytest tests/test_orders.py::test_name # Run single test
python -m black backend/                          # Format code
python -m flake8 backend/                         # Lint code

# Frontend (if separate build)
npm run dev                                       # Dev server
npm run build                                     # Production bundle
npm test                                          # Vitest unit tests (incl. locale parity)
E2E_PORT=8123 npx playwright test                 # E2E — must be a FREE port, see below

# Docker — APP_VERSION/GIT_COMMIT stamp the version shown in the UI.
# APP_VERSION is used verbatim; omitted they default to "dev"/"unknown".
# CPO_VERSION set at runtime (e.g. in .env) overrides the baked-in value.
docker build --build-arg APP_VERSION=1.5.0 \
             --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) -t cpo-app .
docker run -v /path/to/config:/app/config -v /path/to/data:/app/data -p 8000:8000 cpo-app
APP_VERSION=1.5.0 GIT_COMMIT=$(git rev-parse --short HEAD) docker compose build
```

## Testing Strategy

- **Unit tests**: Router logic, session/order/menu services
- **Integration tests**: End-to-end order submission (session open → submit → summary updates)
- **Rate limiting**: Verify 429 response after 1 submission per IP per 5s
- **Session auto-close**: Verify session closes 2 min after end_time
- **Translation parity**: `frontend/src/test/i18n/parity.test.js` (key/placeholder/empty-value checks, no `ß` in `de-CH`) and `backend/tests/test_error_codes.py` (every code has an `errors.<code>` message in `en.json`)
- **Playwright E2E** (`frontend/e2e/`): `ordering.spec.js` covers login routing, the ordering flow, closed sessions, rate limiting, admin/menu/session management and email mode; `i18n.spec.js` walks the order page in German and proves the account language survives a login from a clean browser context. Fixtures in `e2e/fixtures.js` seed through the API and reset the SQLite rows between tests
  - The suite starts its own backend on `E2E_PORT` against a temp `DATA_DIR`, but `reuseExistingServer` is on outside CI: **run it on a free port** or it will silently drive — and wipe — whatever is already listening (a dev container on 8002, for example). It also needs the gitignored `config/test-config.json` (admin credentials the fixtures seed)
- **Manual E2E**: Walk the wireframe screens in a browser for anything the suites do not cover

## Security Checklist

- [ ] Bcrypt password hashing (min 10 rounds)
- [ ] JWT validation on protected routes
- [ ] Rate limiting on `/api/orders/{link}/submit` (1 per IP per 5s)
- [ ] Client IP captured with each order
- [ ] Input validation: member name/pizza name required, price ≥ 0.01, duplicate pizza names rejected
- [ ] Session link: random alphanumeric 16+ chars, unique per team
- [ ] CORS: restrict to same-origin (or configured domains)
- [ ] No sensitive data in URLs (e.g., session ID not in query string)

## File Storage Layout

```
/app/data/
├── cpo.db                   # SQLite database: admins, teams, cpos, team_invites, menus, pizzas, sessions, orders
├── cpo.db-wal, cpo.db-shm   # WAL sidecar files
└── _migrated_json/          # archived legacy JSON tree (after one-time import)
```

Legacy layout (pre-SQLite, imported on first boot then archived): `/app/config/config.json`
for credentials, `/app/data/{cpo_id}/menu.json` + `{session_id}.json` for data.

## Future Enhancements (Out of Scope)

See `spec/specification.md` §12. Examples: database integration, email notifications, payment processing, analytics.

## References

- **Full specification**: `spec/specification.md` (9 sections: roles, sessions, orders, menus, summaries, data models, API, non-functional requirements, deployment)
- **Design reference**: `design/README.md` + `design/wireframes.html` (all 9 screens with interactions, design tokens)
- **Vision**: `spec/vision.md` (high-level overview)
