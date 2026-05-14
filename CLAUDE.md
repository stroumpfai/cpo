# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CPO (Chief Pizza Officer)** is a team pizza ordering web application. It enables a "Chief Pizza Officer" to open time-bound ordering sessions, team members to submit orders via a unique link (no login), and the CPO to view real-time order summaries and export data.

Three roles:
- **Admin** — manages CPO accounts (login-required)
- **CPO** — manages one team, opens/closes sessions, curates pizza menu, views live order board (login-required)
- **Team Member** — visits a unique team link, selects pizzas, submits order (no login)

## Technology Stack

| Layer | Choice |
|---|---|
| Frontend | React (SPA, bundled and served by FastAPI) |
| Backend | FastAPI (Python 3.14) with uvicorn |
| Auth | JWT (HS256, 1-month expiry) |
| Storage | JSON files in Docker volumes (`/app/config/`, `/app/data/`) |
| Real-time | Server-Sent Events (SSE) for live order updates |
| Containerization | Single Docker container, Python 3.14-slim |

## Architecture

### Backend (FastAPI)
- **Structure**: Modular FastAPI app with routers for auth, admin, CPO, and team endpoints
- **Authentication**: JWT tokens issued on login, required for admin/CPO routes
- **Storage**: 
  - Admin + CPO credentials: `/app/config/config.json` (bcrypt-hashed passwords)
  - Sessions, orders, menus: `/app/data/{cpo_id}/` (JSON files, one per session)
- **Real-time**: SSE endpoint streams summary updates to connected CPO dashboards

### Frontend (React)
- **Layout**: Sidebar nav + main content area (authenticated routes show sidebar)
- **State**: React `useState` + `useEffect` (no global state library)
- **Routing**: Six main routes (see Routes section below)
- **Real-time**: `EventSource` API connected to SSE endpoint during active sessions

### Data Models
See `spec/specification.md` §7 for full schemas. Key entities:
- **Session**: Time-bound ordering window (start, end, optional 2-min grace period)
- **Order**: Single pizza for one member; multiple pizzas = multiple order rows
- **Menu**: Per-CPO pizza list (name, price); persists across sessions
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
- **config.json** format: See `spec/specification.md` §11.3
- **Environment**: No env vars required; all config via JSON files

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
│   ├── config.py              # Config loader, constants
│   └── tests/
├── frontend/                  # React app (optional, if built separately)
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── dist/                  # Built bundle (copied to backend)
├── Dockerfile
├── docker-compose.yml         # Optional: for local dev
└── CLAUDE.md
```

## Routes & Screens

| Path | Component | Auth | Key Behavior |
|---|---|---|---|
| `/login` | Login | none | Shared form; redirects to `/admin` (Admin) or `/dashboard` (CPO) after JWT issued |
| `/admin` | AdminPanel | Admin JWT | CPO account management: list, create, reset password |
| `/dashboard` | CPODashboard | CPO JWT | Order summary with live SSE updates; two tabs (per-person + pizzeria consolidated) |
| `/dashboard/new-session` | NewSession | CPO JWT | Create session: date, start time, end time, grace period (2 min default) |
| `/dashboard/pizzas` | PizzaMenu | CPO JWT | Edit menu: add/edit/delete pizzas (name, price); persists across sessions |
| `/orders/:link` | TeamOrderPage | none | Team member: enter name, pick pizza, add to cart, submit; shows session status |

## Key API Endpoints

See `spec/specification.md` §9 for full spec. Essential endpoints:

**Auth**
- `POST /api/auth/login` — Shared admin/CPO login → JWT token

**CPO endpoints** (authenticated)
- `GET /api/cpo/me` — Current CPO profile
- `POST /api/cpo/sessions` — Create session
- `GET /api/cpo/sessions/{session_id}/summary` — Fetch summary (both views)
- `GET /api/cpo/sessions/{session_id}/summary/sse` — Stream updates via SSE
- `POST /api/cpo/menu`, `PUT /api/cpo/menu/{id}`, `DELETE /api/cpo/menu/{id}` — Menu ops

**Team endpoints** (no auth)
- `GET /api/orders/{unique_link}` — Session status + available pizzas
- `POST /api/orders/{unique_link}/submit` — Submit order (rate-limited 1 per IP per 5s)

## Important Design Decisions

1. **Single container**: All code (backend + frontend bundle) runs in one Docker container; no microservices
2. **JSON files, not DB**: Simpler deployment; mounted volumes persist data across restarts; file I/O can be a bottleneck at scale (200 teams max)
3. **No order modification by users**: CPO has full control; users contact CPO if they change mind
4. **Quantity = 1 per row**: Users add multiple pizzas by submitting multiple times; simplifies model
5. **IP tracking + rate limit**: Combined defense against spam; CPO can manually review/delete suspicious orders
6. **SSE, not polling**: Real-time updates without constant client requests; reduces server load
7. **JWT, 1-month expiry**: Reasonable for internal teams; login required after expiry
8. **No timezone support**: Prototype simplification; all times local to server

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
npm test                                          # Run tests

# Docker
docker build -t cpo-app .
docker run -v /path/to/config:/app/config -v /path/to/data:/app/data -p 8000:8000 cpo-app
```

## Testing Strategy

- **Unit tests**: Router logic, session/order/menu services
- **Integration tests**: End-to-end order submission (session open → submit → summary updates)
- **Rate limiting**: Verify 429 response after 1 submission per IP per 5s
- **Session auto-close**: Verify session closes 2 min after end_time
- **Manual E2E**: Test all wireframe screens in browser (no automated E2E suite required for MVP)

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
/app/
├── config/
│   └── config.json          # Admin + CPO credentials (bcrypt-hashed)
└── data/
    ├── {cpo_id}/
    │   ├── menu.json        # Pizza menu (persists across sessions)
    │   ├── {session_id}.json # Session data + orders
    │   └── ...
    └── ...
```

## Future Enhancements (Out of Scope)

See `spec/specification.md` §12. Examples: database integration, email notifications, payment processing, analytics.

## References

- **Full specification**: `spec/specification.md` (9 sections: roles, sessions, orders, menus, summaries, data models, API, non-functional requirements, deployment)
- **Design reference**: `design/README.md` + `design/wireframes.html` (all 9 screens with interactions, design tokens)
- **Vision**: `spec/vision.md` (high-level overview)
