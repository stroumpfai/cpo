# CPO Web Application - Implementation Plan

## Context

The CPO (Chief Pizza Officer) project is a team pizza ordering web application requiring a complete implementation from scratch. The specification is detailed and well-documented with wireframes. The project involves three interconnected layers: FastAPI backend, React frontend, and JSON file storage. This plan breaks implementation into logical phases, prioritized to deliver core functionality first.

## High-Level Approach

**Architecture**: Single-container application (FastAPI + React bundle) with three distinct layers:
1. **Backend** (FastAPI): Authentication, session management, order processing, real-time streaming
2. **Frontend** (React): Multi-screen SPA with sidebar navigation and form handling
3. **Storage** (JSON files): Config, sessions, orders, and menus persisted across restarts

**Sequencing**: Implement bottom-up to minimize integration risk:
- Backend infrastructure and models first
- Authentication and core business logic
- Frontend screens (scaffolding, then integration)
- Real-time features (SSE, live updates)
- Polish, testing, and deployment

**Note on Sidebar Nav**: The design mentions a "Settings" nav item, but no Settings screen is specified. This is treated as out of scope for MVP unless clarified. The implemented nav items are: Dashboard, Open a new session, List of Pizzas.

**Key Decisions**:
- No database complexity; JSON files acceptable for 200-team limit
- Frontend uses React `useState` + `useEffect` (no Redux/Context needed at this scale)
- SSE for real-time updates (simpler than WebSocket)
- Rate limiting applied at request handler level (not middleware)
- Session auto-close via lazy evaluation on each request

---

## Implementation Phases

### Phase 0: Project Setup & Infrastructure (Day 1)

**Objective**: Establish project structure, dependencies, and local dev environment.

**Deliverables**:
- Directory structure created (backend/, frontend/, config/, data/)
- `requirements.txt` with FastAPI, uvicorn, pydantic, bcrypt, pyjwt, python-multipart
- `package.json` with React, react-router-dom, axios (or fetch), and dev dependencies
- Docker and docker-compose files (development + production)
- `.gitignore`, initial configs

**Files to create**:
- `backend/requirements.txt`
- `backend/main.py` (empty FastAPI app entry point)
- `frontend/package.json`
- `Dockerfile` (Python 3.14-slim base)
- `docker-compose.yml` (optional, for local dev)
- `.gitignore`, `.env.example`

**Verification**:
```bash
# Backend: start dev server
cd backend && pip install -r requirements.txt && uvicorn main:app --reload

# Frontend: start dev server (if separate)
cd frontend && npm install && npm run dev
```

---

### Phase 1: Backend Foundation (Days 2–3)

**Objective**: Implement core data models, storage layer, and configuration management.

**Key Features**:
- Pydantic models for all entities (Admin, CPO, Session, Order, Menu)
- JSON file storage module (read/write sessions, orders, menus, config)
- Config loader to read `/app/config/config.json` (admin + CPO accounts)
- Password hashing utilities (bcrypt)
- UUID generation for sessions, orders, menus

**Files to create**:
- `backend/models.py` — Pydantic schemas (AdminAccount, CPOAccount, Session, Order, Menu, etc.)
- `backend/storage.py` — File I/O layer (read/write sessions, orders, menus; atomic writes)
- `backend/config.py` — Config loader, constants (JWT secret, port, etc.)
- `backend/utils.py` — UUID generation, password hashing, token generation
- `backend/routers/` — Directory for route modules (created empty for now)

**Key Implementation Notes**:
- Sessions stored as `{cpo_id}/{session_id}.json` with nested orders array
- Menus stored as `{cpo_id}/menu.json` (persists across sessions)
- Use atomic file writes (write to temp file, then rename) to prevent corruption
- Session status computed lazily: check current time against session.start_time and end_time + grace_period

**Verification**:
```bash
# Unit tests: models, storage, utils
pytest backend/tests/test_models.py
pytest backend/tests/test_storage.py
```

---

### Phase 2: Authentication & JWT (Days 4–5)

**Objective**: Implement login endpoint, JWT token generation, and authentication middleware.

**Key Features**:
- `POST /api/auth/login` — Accept username + password, validate against config, return JWT
- JWT creation (HS256, 1-month expiry)
- Auth dependency for protected routes (FastAPI dependency injection)
- Role extraction from JWT (admin vs. cpo)
- Logout endpoint (no-op, client deletes token)

**Files to modify/create**:
- `backend/routers/auth.py` — Login, logout, token validation
- `backend/security.py` — JWT creation/validation, password verification

**Key Implementation Notes**:
- JWT payload includes `role` (admin|cpo) and `user_id`
- For admin, `user_id` = "admin"; for CPO, `user_id` = cpo.id (UUID)
- Token stored client-side in localStorage (or httpOnly cookie if stricter)
- Protected routes use `Depends(get_current_user)` to validate JWT

**Verification**:
```bash
# Test login with valid/invalid credentials
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'

# Test protected route with JWT
curl -H "Authorization: Bearer {token}" http://localhost:8000/api/cpo/me
```

---

### Phase 3: Admin Endpoints (Days 5–6)

**Objective**: Implement admin panel functionality (CPO account management).

**Endpoints**:
- `GET /api/admin/cpos` — List all CPO accounts
- `POST /api/admin/cpos` — Create new CPO account
- `POST /api/admin/cpos/{cpo_id}/reset-password` — Reset CPO password (optional, or inline in listing)

**Files to create/modify**:
- `backend/routers/admin.py` — Admin endpoints
- `backend/services/admin_service.py` — Business logic (create CPO, reset password)

**Key Implementation Notes**:
- Only accessible with admin JWT
- CPO creation: generate UUID, hash password with bcrypt, store in config.json
- Password reset: generate temporary password or allow admin to set new one
- Validate unique username (case-insensitive) and email

**Verification**:
- Create CPO via API
- Verify config.json updated with new account
- List CPOs, confirm new account appears

---

### Phase 4: CPO Core Endpoints (Days 7–9)

**Objective**: Implement CPO session and menu management.

**Endpoints**:
- `GET /api/cpo/me` — Current CPO's profile
- `POST /api/cpo/sessions` — Create session
- `GET /api/cpo/sessions` — List sessions
- `GET /api/cpo/sessions/{session_id}/summary` — Fetch order summary (both views)
- `POST /api/cpo/menu` — Add pizza to menu
- `GET /api/cpo/menu` — List menu
- `PUT /api/cpo/menu/{pizza_id}` — Edit pizza
- `DELETE /api/cpo/menu/{pizza_id}` — Delete pizza
- `DELETE /api/cpo/orders/{order_id}` — CPO deletes an order (from summary)

**Files to create/modify**:
- `backend/routers/cpo.py` — CPO endpoints
- `backend/services/cpo_service.py` — Session, menu, order logic
- `backend/services/summary_service.py` — Generate distribution + pizzeria summaries

**Key Implementation Notes**:
- Session creation: generate unique link (16+ char alphanumeric), store with date/start/end times
- Menu operations: enforce unique pizza names per CPO, min price 0.01
- Summary: two views — per-member (with IPs) and per-pizza (anonymized)
- Session status: compute from current time vs. session times + grace period
- Only one active session per CPO at a time (validate on creation)

**Verification**:
- Create session, verify unique link generated
- Add/edit/delete pizzas, verify menu persists
- Query summary, verify both views return correct data
- Verify only one active session allowed per CPO

---

### Phase 5: Team Order Endpoints (Days 10–11)

**Objective**: Implement order submission and session status for team members (no auth required).

**Endpoints**:
- `GET /api/orders/{unique_link}` — Session status + available pizzas (no auth)
- `POST /api/orders/{unique_link}/submit` — Submit order batch (no auth, rate-limited)

**Files to create/modify**:
- `backend/routers/orders.py` — Public order endpoints
- `backend/services/order_service.py` — Order submission, validation, rate limiting

**Key Implementation Notes**:
- Rate limiting: track IP + timestamp, allow 1 submission per IP per 5 seconds
- Return HTTP 429 if rate limit exceeded
- Validate session is active (within start/end + grace period)
- Create one Order record per pizza_id in submission
- Capture client IP in each order (use `request.client.host`)
- Return error if session closed (even if within grace period, show "Session is closed")
- **Grace period logic**: Accept submissions up to 2 min after `end_time`; reject if beyond

**Verification**:
```bash
# Submit order while session active
curl -X POST http://localhost:8000/api/orders/{link}/submit \
  -H "Content-Type: application/json" \
  -d '{"member_name": "Alice", "pizza_ids": ["uuid1", "uuid2"]}'

# Test rate limit: submit twice within 5 seconds, second should return 429
# Test grace period: submit within 2 min after end_time (accepted), beyond 2 min (rejected)
```

---

### Phase 6: Real-time Updates via SSE (Days 12–13)

**Objective**: Implement Server-Sent Events for live order summary updates on CPO dashboard.

**Endpoints**:
- `GET /api/cpo/sessions/{session_id}/summary/sse` — Stream summary updates (text/event-stream)

**Files to modify**:
- `backend/routers/cpo.py` — Add SSE endpoint
- `backend/services/cpo_service.py` — Trigger SSE events on order changes

**Key Implementation Notes**:
- Use FastAPI `StreamingResponse` to send SSE
- Emit summary JSON on each order submission, update, or deletion
- Include event type (order_added, order_deleted, session_closed)
- Client connects with `EventSource()`, listens for events
- Cleanup: close connection when session closes or after 5+ minutes idle

**Verification**:
- Connect to SSE endpoint with curl or browser DevTools
- Submit order via team page
- Verify SSE event fires with updated summary

---

### Phase 7: Frontend — Project Setup & Core Layout (Days 14–16)

**Objective**: Bootstrap React app with routing, sidebar, and layout components.

**Components**:
- `App.jsx` — Routes and layout shell
- `Sidebar.jsx` — Navigation, active state, logout
- `Layout.jsx` — Header + sidebar wrapper
- Router configuration (react-router-dom v6)

**Pages** (scaffolded, not yet integrated):
- `LoginPage.jsx` — Login form
- `AdminPanel.jsx` — CPO list + create form
- `CPODashboard.jsx` — Order summary (placeholder)
- `NewSession.jsx` — Session creation form (placeholder)
- `PizzaMenu.jsx` — Pizza list editor (placeholder)
- `TeamOrderPage.jsx` — Team order form (placeholder)

**Files to create**:
- `frontend/src/App.jsx` — Routes, layout
- `frontend/src/components/Sidebar.jsx`
- `frontend/src/components/Layout.jsx`
- `frontend/src/pages/` — All page components (scaffolded)
- `frontend/src/api.js` — Axios instance with JWT token injection
- `frontend/src/utils/auth.js` — JWT storage, token validation
- `frontend/src/styles/` — Global CSS, design tokens

**Key Implementation Notes**:
- Use `localStorage` for JWT token (set after login, clear on logout)
- `PrivateRoute` component: check JWT, redirect to /login if missing
- `/login` accessible without auth; auto-redirect to dashboard if already logged in
- Admin routes require `role === 'admin'`; CPO routes require `role === 'cpo'`

**Verification**:
- Run dev server, navigate between routes
- Verify sidebar shows active item
- Verify redirect to /login when accessing protected routes without token

---

### Phase 8: Frontend — Login & Admin Panel (Days 17–18)

**Objective**: Implement authentication UI and admin account management.

**Screens**:
- **Login**: Username, password inputs; submit button; error display
- **Admin Panel**: CPO table (list), create form

**Components**:
- `LoginPage.jsx` — Form validation, API call, JWT storage, redirect
- `AdminPanel.jsx` — Fetch CPO list, render table, create form
- `CreateCPOForm.jsx` — Form inputs, validation, submit
- `CPOTable.jsx` — Table display, reset password link (optional)

**Files to create/modify**:
- `frontend/src/pages/LoginPage.jsx`
- `frontend/src/pages/AdminPanel.jsx`
- `frontend/src/components/CreateCPOForm.jsx`
- `frontend/src/components/CPOTable.jsx`

**Key Implementation Notes**:
- Login POST to `/api/auth/login`, store token, redirect based on role
- Admin panel loads CPO list on mount (useEffect)
- Form validation: username/email/team name required, password min 8 chars
- Display error if username already exists
- Apply design tokens (colors, spacing, typography) from CLAUDE.md

**Verification**:
- Login with valid admin credentials
- Create new CPO, verify appears in list
- Invalid login shows error

---

### Phase 9: Frontend — CPO Dashboard (Days 19–22)

**Objective**: Implement the main CPO dashboard with live order summary and tabs.

**Screens**:
- **CPODashboard** (main): Session header, stat cards, table (two tabs), action buttons
- **Tab 1**: Orders per person (with member names, IPs, delete action)
- **Tab 2**: Pizzeria summary (consolidated, anonymized)

**Components**:
- `CPODashboard.jsx` — Main container, SSE connection, tab state
- `SessionHeader.jsx` — Session date, time range, buttons (refresh, print, copy link)
- `StatCards.jsx` — Members, pizzas, total, countdown
- `OrdersPerPersonTable.jsx` — Table with member/pizza/IP/price/delete
- `PizzeriaSummaryTable.jsx` — Table with pizza/count/total
- `TabBar.jsx` — Tab switcher

**Files to create/modify**:
- `frontend/src/pages/CPODashboard.jsx`
- `frontend/src/components/SessionHeader.jsx`
- `frontend/src/components/StatCards.jsx`
- `frontend/src/components/OrdersPerPersonTable.jsx`
- `frontend/src/components/PizzeriaSummaryTable.jsx`

**Key Implementation Notes**:
- Connect to SSE endpoint on mount: `EventSource('/api/cpo/sessions/{id}/summary/sse')`
- On SSE event, update `orders` state in-place (no full page reload)
- Countdown timer: update MM:SS every second; pulse when < 1 min
- Copy link button: copies `orders.app/{unique_link}` to clipboard
- Print button: browser print dialog
- Refresh button: manual fetch summary (SSE is automatic, but refresh on demand)
- Delete button: POST to `/api/cpo/orders/{order_id}`, remove from table
- Paid toggle: client-side only (💰 vs ✓ icon)

**Verification**:
- Navigate to dashboard, verify SSE connection opens (DevTools Network)
- Submit order from team page
- Verify order appears in dashboard within 1 second
- Test countdown timer
- Test delete action
- Test paid toggle persistence (in component state)

---

### Phase 10: Frontend — Session & Menu Management (Days 23–24)

**Objective**: Implement new session creation and pizza menu editor.

**Screens**:
- **NewSession**: Date, time inputs, grace period stepper, team link display, buttons
- **PizzaMenu**: Pizza list table, inline edit/delete, add row

**Components**:
- `NewSession.jsx` — Form, computed grace period cutoff, persistent team link
- `PizzaMenu.jsx` — Table, inline editing, add pizza form
- `PizzaEditRow.jsx` — Inline edit row (name, price inputs + save/cancel)
- `PizzaAddRow.jsx` — Add new pizza row

**Files to create/modify**:
- `frontend/src/pages/NewSession.jsx`
- `frontend/src/pages/PizzaMenu.jsx`
- `frontend/src/components/PizzaEditRow.jsx`
- `frontend/src/components/PizzaAddRow.jsx`

**Key Implementation Notes**:
- NewSession: POST to `/api/cpo/sessions`, redirect to `/dashboard` on success
- Grace period stepper: default 2, show computed cutoff time dynamically
- Team link: fetch from CPO profile (GET `/api/cpo/me`), display as read-only + copy button
- PizzaMenu: fetch on mount (GET `/api/cpo/menu`), re-render on edit/delete/add
- Inline edit: click edit → show inputs → save (PUT) or cancel
- Add pizza: text input for name, number input for price → add button (POST)
- Validation: duplicate names rejected, price ≥ 0.01

**Verification**:
- Create new session, verify redirects to dashboard
- Edit pizza name/price, verify updates
- Delete pizza, verify removed from list
- Add pizza, verify appears in list and menu dropdown

---

### Phase 11: Frontend — Team Order Page (Days 25–26)

**Objective**: Implement the public team order submission page.

**Screens**:
- **TeamOrderPage**: Session status header, add-to-cart form, cart preview, submit button
- **Success state**: Order placed confirmation

**Components**:
- `TeamOrderPage.jsx` — Main, session status, form, cart state
- `AddToCartForm.jsx` — Name input, pizza dropdown, add button
- `CartPreview.jsx` — Listed pizzas, remove buttons, total, submit button
- `OrderSuccessModal.jsx` — Confirmation message

**Files to create/modify**:
- `frontend/src/pages/TeamOrderPage.jsx`
- `frontend/src/components/AddToCartForm.jsx`
- `frontend/src/components/CartPreview.jsx`
- `frontend/src/components/OrderSuccessModal.jsx`

**Key Implementation Notes**:
- Fetch session status (GET `/api/orders/{link}`) — shows status (active/closed), pizzas
- If session closed → show "Session is closed" full-screen, no form
- If active: show countdown to end_time (without grace period), form + cart
- Name field persists across "add to cart" clicks
- Pizza dropdown resets after each add
- Rate limit handling: catch 429, show banner message
- Submit: POST to `/api/orders/{link}/submit`, show success state
- Success state has "add another order" button (clears cart, resets name)
- Disclaimer text: "Orders can't be edited after submission"

**Verification**:
- Visit `/orders/{link}` with active session, verify form displays
- Add pizzas, verify appear in cart
- Submit, verify success message
- Submit again within 5 seconds, verify 429 rate limit error
- Visit after session closes, verify "Session is closed" message

---

### Phase 12: Polish, Testing & Deployment (Days 27–30)

**Objective**: Integration testing, end-to-end flows, deployment setup.

**Tasks**:
- **End-to-end tests**: Admin creates CPO → CPO creates session → team submits orders → verify summary updates
- **Edge cases**: Grace period logic, rate limiting, session auto-close, duplicate pizza names
- **Design polish**: Apply design tokens, ensure responsive layout (mobile 320px+)
- **Docker build**: Test containerization, volume mounts for config and data
- **Documentation**: Update README with setup, deployment, configuration instructions

**Files to create/modify**:
- `backend/tests/` — Integration tests (test_auth.py, test_cpo.py, test_orders.py, test_e2e.py)
- `frontend/src/tests/` — Component tests (optional, low priority for MVP)
- `README.md` — Setup, deployment, configuration, development guide
- `docker-compose.yml` — Development environment (FastAPI + React)

**Key Testing Focus**:
- Session auto-close after grace period
- Rate limiting: 1 submission per IP per 5 seconds
- Grace period: orders within 2 min after end_time accepted, beyond rejected
- One active session per CPO
- Unique pizza names per menu
- IP capture in orders
- SSE event streaming
- Admin role restriction
- CPO role restriction
- Team member access via link only

**Verification**:
```bash
# Run all tests
pytest backend/tests/ -v

# Build Docker image
docker build -t cpo-app .

# Run container with volumes
docker run -v /path/to/config:/app/config -v /path/to/data:/app/data -p 8000:8000 cpo-app

# Test from browser
# - Login as admin, create CPO
# - Login as CPO, create session
# - Visit team link, submit orders
# - Verify orders appear in dashboard
# - Verify SSE updates
```

---

## Critical File Paths

### Backend
- `backend/main.py` — FastAPI entry point
- `backend/models.py` — Pydantic schemas
- `backend/storage.py` — File I/O layer
- `backend/config.py` — Configuration + constants
- `backend/security.py` — JWT, password hashing
- `backend/routers/auth.py` — Login endpoints
- `backend/routers/admin.py` — Admin endpoints
- `backend/routers/cpo.py` — CPO endpoints
- `backend/routers/orders.py` — Public order endpoints
- `backend/services/` — Business logic modules
- `backend/requirements.txt` — Python dependencies

### Frontend
- `frontend/src/App.jsx` — Routes, layout
- `frontend/src/pages/` — Page components
- `frontend/src/components/` — Reusable components
- `frontend/src/api.js` — HTTP client
- `frontend/src/utils/auth.js` — JWT utilities
- `frontend/src/styles/` — Global CSS
- `frontend/package.json` — Dependencies

### Configuration
- `Dockerfile` — Production image
- `docker-compose.yml` — Development orchestration
- `CLAUDE.md` — Development guidance
- `README.md` — Setup, deployment, configuration

---

## Estimated Timeline

| Phase | Days | Focus |
|---|---|---|
| 0 | 1 | Setup |
| 1 | 2 | Backend models, storage |
| 2 | 2 | JWT, authentication |
| 3 | 1 | Admin endpoints |
| 4 | 3 | CPO sessions, menus, summaries |
| 5 | 2 | Public order endpoints, rate limiting |
| 6 | 2 | SSE real-time updates |
| 7 | 3 | Frontend scaffolding, routing, layout |
| 8 | 2 | Login, admin panel |
| 9 | 4 | CPO dashboard, live orders, tabs |
| 10 | 2 | Session creation, pizza menu editor |
| 11 | 2 | Team order page, success state |
| 12 | 4 | Testing, polish, deployment |
| **Total** | **~30 days** | **Full MVP** |

---

## Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Session auto-close logic (race conditions) | Compute status lazily from current time; use server time consistently; test grace period edge cases |
| Rate limiting correctness | Store IP + timestamp in memory (simple dict); reset on server restart (acceptable for MVP) |
| JSON file I/O corruption | Use atomic writes (write to temp file, rename); lock files during writes if needed |
| SSE connection stability | Auto-reconnect on client close; server detects stale connections after 5 min idle |
| Frontend state sync | SSE is source of truth for orders; refresh endpoint for manual catch-up |
| Large order summaries (performance) | 200 teams × 10 users × 20 pizzas = 40K orders max; JSON should handle, but consider pagination later |

---

## Dependencies & Integration Points

**Backend ↔ Frontend**:
- All endpoints defined in spec; backend must match request/response schemas exactly
- Frontend consumes JWT from login, includes in `Authorization: Bearer {token}` header
- SSE events must match expected format (server sends `data: {...}`)

**Backend ↔ Storage**:
- Sessions and orders stored as JSON files; must handle concurrent reads safely
- Atomic writes prevent partial file corruption

**Frontend ↔ Browser APIs**:
- `localStorage` for JWT token
- `EventSource` for SSE
- `Clipboard API` for copy-to-clipboard
- `Date` object for countdown timer

---

## Success Criteria

- [ ] All 9 wireframe screens implemented and functional
- [ ] Authentication (admin + CPO login) working end-to-end
- [ ] Session creation, ordering, and summary updates working
- [ ] Rate limiting enforced (1 submission per IP per 5 seconds)
- [ ] Grace period logic correct (2 min after end_time)
- [ ] SSE streaming live order updates to dashboard
- [ ] Docker container runs with config + data volumes
- [ ] All tests passing (auth, CPO, orders, e2e)
- [ ] Responsive design (mobile 320px+)
- [ ] README and deployment docs complete
