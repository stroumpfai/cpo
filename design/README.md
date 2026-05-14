# Handoff: CPO — Chief Pizza Officer

## Overview

CPO is a team pizza ordering web app. A **Chief Pizza Officer (CPO)** opens a session with a time window; team members follow a shared link and pick their pizzas; the CPO watches orders arrive live and exports a summary to the pizzeria.

There are three roles:
- **Admin** — manages CPO accounts
- **CPO** — runs ordering sessions, manages the pizza menu, views the live order board
- **Team member** — visits the team link, picks pizzas, submits (no login)

---

## About the Design Files

`wireframes.html`, `screens.jsx`, and `app.jsx` in this folder are **low-fidelity wireframes created as design references** — not production code. Open `wireframes.html` in a browser to see all screens on a pan/zoom canvas (click ⤢ on any artboard to fullscreen it).

Your task is to **implement these screens from scratch** in the production codebase using the spec and this README as your guide. Apply clean production styling — the wireframe uses a sketchy hand-drawn aesthetic that should not carry over.

---

## Fidelity

**Low-fidelity wireframes.** The screens show layout, content hierarchy, component placement, and interaction flows. Use a clean, minimal design system in production. Suggested defaults if no existing system:

| Token | Value |
|---|---|
| Background | `#ffffff` |
| Surface / card | `#f8f8f8` |
| Border | `#e2e2e2` |
| Text primary | `#111111` |
| Text secondary | `#666666` |
| Accent / primary action | `#d7372b` (tomato red) |
| Accent soft (bg) | `#fff0ef` |
| Font | Geist Sans or Inter, 14px base |
| Mono | Geist Mono or JetBrains Mono |
| Border radius | 8px cards, 6px inputs, 999px pills |
| Shadow | `0 1px 3px rgba(0,0,0,.10)` |

---

## Technology

| Layer | Choice |
|---|---|
| Frontend | React (SPA, served by FastAPI as a single bundle) |
| Backend | FastAPI (Python 3.14) |
| Auth | JWT — HS256, 1-month expiry |
| Storage | JSON files in Docker volumes (`/app/config/`, `/app/data/`) |
| Real-time | Server-Sent Events (SSE) for live order updates |

Full API spec and data models: see `specification.md`.

---

## Screens

### 1 — Login (`/login`)

**Shared for Admin and CPO.** Single form, role-based redirect after JWT is issued.

| Field | Notes |
|---|---|
| Username / email | text input, required |
| Password | password input, required |
| Submit | "Log in", primary button, full width |

- On success: Admin → `/admin`, CPO → `/dashboard`
- On failure: inline error "Invalid credentials"
- JWT stored in `localStorage` (or `httpOnly` cookie); auto-redirect if already authenticated

---

### 2 — Admin panel (`/admin`)

CPO account management only. Header shows "CPO · Admin" + logout link.

**CPO list table**

| Column | Notes |
|---|---|
| Username | |
| Email | |
| Team name | |
| Actions | "reset password" link |

**Create CPO form** (inline below table, or modal):
- Username, email, team name, initial password — all required
- Submit → "Create CPO", primary button
- Validation: duplicate username rejected with inline error

---

### 3 — CPO Dashboard, "Orders per person" tab (`/dashboard`)

Main screen during an active session. Left sidebar + main content.

**Sidebar** (fixed width, ~170px):
- App name / team name
- Nav items: Dashboard · Open a new session · List of Pizzas · Settings
- Active item highlighted; others dashed/muted
- Bottom: username + log out chip

**Header area:**
- `H1`: "Session — {date}"
- Sub-line: time-range input showing ordering window, e.g. `11:30 — 12:02`, with "(ordering window incl. 2' grace)" label
- Top-right buttons (left to right): `↻ refresh` (secondary), `⎙ print` (tertiary/ghost), `🔗 orders.app/{link}` (primary accent — copies link on click)

**Stat cards** (4-column grid):
| Card | Value |
|---|---|
| members | count of distinct member names |
| pizzas | total pizza rows |
| CHF total | sum of all prices |
| ends in | countdown MM:SS, accent colour, pulsing "live" dot, progress bar |

**Tab bar:**
- "Orders per person" (active in this view)
- "List for ordering at Pizzeria"

**Distribution table** (this tab):

| Column | Notes |
|---|---|
| time ↓ | timestamp, monospace, muted; sorted newest first |
| member | name string |
| client ip | monospace, muted |
| pizza | pizza name |
| price (CHF) | monospace |
| action | two inline links: `💰 received · ✕ delete` OR `✓ received · ✕ delete` (✓ when CPO has marked payment received) |

- One row per pizza ordered (quantity is always 1 per row)
- Multiple rows from same member at the same timestamp = one multi-pizza submission
- "✕ delete" fires `DELETE /api/admin/orders/{order_id}` with CPO JWT
- "💰 received" / "✓ received" = client-side toggle for CPO to track payment collection (not persisted to backend unless you want to add a field)

**SSE connection:** open `GET /api/cpo/sessions/{session_id}/summary/sse` while the dashboard is mounted; on each event, re-render the table and stat cards without a full page reload.

---

### 4 — CPO Dashboard, "List for ordering at Pizzeria" tab

Same chrome as screen 3. Tab switches table:

| Column | Notes |
|---|---|
| pizza | pizza name |
| count | integer; show a horizontal bar scaled proportionally to the max count |
| total (CHF) | monospace |

- Last row: bold totals row — "total · {sum count} · {sum CHF}"
- No member names or IPs in this view (as per spec: anonymised for pizzeria)
- Annotation note: "names & IPs hidden in this view"

---

### 5 — Open a new session (`/dashboard/new-session`)

Opened via "Open a new session" sidebar nav item.

**Header:** "Open a new session" + subtitle + ✕ close button (returns to /dashboard)

**Form (inside a card):**

| Field | Input type | Notes |
|---|---|---|
| Date | date picker (with 📅 icon) | required |
| Start time | time input | required |
| End time | time input | required |
| Grace period | stepper (– N +) + "min" label | default 2; helper text shows computed cutoff, e.g. "orders submitted up to 12:02 still accepted" |

**Team ordering link section** (below a divider):
- Label: "team ordering link · stays the same for every session"
- Shows the team's persistent link as a read-only input + "⧉ copy" button
- This link does NOT change between sessions — it belongs to the CPO/team, not the session

**Footer buttons** (right-aligned): `cancel` (secondary) · `open session` (primary accent)

- POST `/api/cpo/sessions` with `{session_date, start_time, end_time, grace_period_minutes}`
- On success: redirect to `/dashboard` with new session active

---

### 6 — List of Pizzas (`/dashboard/pizzas`)

Opened via "List of Pizzas" sidebar nav.

**Header:** "List of Pizzas" + subtitle "Your menu persists across sessions." + ✕ close button

**Table:**

| Column | Notes |
|---|---|
| pizza name | editable inline on edit action |
| price (CHF) | monospace; editable inline on edit action |
| actions | `✎ edit · ✕ delete` |

**Last row (add new):**
- Pizza name: text input with placeholder "type pizza name…"
- Price: number input with placeholder "0.00"
- Actions: "add" button (primary)

- Duplicate names rejected with inline error
- Minimum price: 0.01

---

### 7 — Team order page (`/orders/{unique_link}`)

No authentication. Shown when session is active.

**Header bar:**
- Team name + "pizza day"
- Right: `● live · closes {HH:MM} (in {MM:SS})` chip (accent colour)

**Two-column grid:**

**Left card — "Add a pizza for a person":**
- Field: "your name" (text input)
- Field: "pick a pizza" (dropdown, shows `Pizza name — CHF price`)
- Button: `add to your order` (primary accent, full width)

**Right card — "Your order":**
- Column headers: NAME · PIZZA · PRICE (CHF)
- Rows: one per added pizza. Each row has: name | pizza | price | ✕ remove
- Separator line
- Total: CHF {sum}

**Bottom buttons** (right-aligned): `cancel` (secondary) · `submit order ✓` (primary accent)

**Disclaimer text** (above buttons, centered, muted):
> "Heads up: orders can't be edited after submission — contact your CPO if you change your mind."

**Flow:**
1. Enter name → select pizza → click "add to your order" → pizza appears in right card
2. Repeat for each pizza (same or different name, same or different pizza)
3. Click "submit order ✓" → POST `/api/orders/{unique_link}/submit` with `{member_name, pizza_ids: [...]}`
4. On success → screen 8

**Rate limiting:** if HTTP 429 → show banner: "Too many orders. Please wait 5 seconds before trying again."

---

### 8 — Order placed — success state

Replaces the order page after a successful submission.

**Header:** Team name + "pizza day" (no live chip)

**Centered card:**
- Big `✓` (accent colour, display font)
- `H1`: "Order placed!"
- Subtext: "{N} pizzas heading to the CPO."
- Small muted note: "Orders can't be edited after submission. Contact your CPO if you change your mind."
- Button: `add another order` (secondary) — reloads the order form

---

### 9 — Session closed (`/orders/{unique_link}` when session inactive)

**Full-screen centered:**
- Top-right: ✕ close button
- Large display text: "Session is closed."
- Muted subtext: "No more orders for today."

---

## Interactions & Behavior

### Real-time countdown
- Dashboard stat card "ends in": count down MM:SS from `session.end_time + grace_period_minutes`
- Team order page chip: count down to `session.end_time` (without grace)
- When countdown hits 0 → session closes automatically server-side; poll or SSE will flip UI to closed state

### SSE updates (dashboard)
- On mount: `EventSource('/api/cpo/sessions/{id}/summary/sse')`
- On each event: update table rows + stat card counts in-place (no flicker)
- On session close event: lock table (remove action links), show "session closed" banner

### Add-to-cart (team order page)
- Name field persists across multiple "add to your order" clicks (user doesn't re-type name)
- Pizza dropdown resets to placeholder after each add
- ✕ remove button removes that row from local cart state (before submission)
- Submitting an empty cart shows validation error: "Add at least one pizza"

### Paid toggle (dashboard, "Orders per person")
- Client-side only toggle per order row
- `💰 received` → click → `✓ received` (and vice versa)
- Visual state: checkmark icon when paid, money bag when unpaid
- Persisted only in component state (or `localStorage` keyed by `session_id + order_id`) — discuss with team if server persistence is needed

---

## State Management

| Screen | Key state |
|---|---|
| Dashboard | `session`, `orders[]`, `countdown`, `activeTab`, `paidSet` (paid order IDs) |
| Team order page | `cart[]` (local pizzas before submit), `name` (persisted across adds) |
| List of Pizzas | `pizzas[]`, `editingId` |
| New session | `form` fields, `computedCutoff` |

Use React `useState` + `useEffect` for local state. No global state library needed at this scale.

---

## Design Tokens (production)

```css
:root {
  --color-bg:          #ffffff;
  --color-surface:     #f8f8f8;
  --color-border:      #e2e2e2;
  --color-text:        #111111;
  --color-text-soft:   #666666;
  --color-text-faint:  #999999;
  --color-accent:      #d7372b;
  --color-accent-soft: #fff0ef;
  --color-accent-dark: #b22a1f;

  --radius-sm:  6px;
  --radius-md:  8px;
  --radius-lg:  12px;
  --radius-pill: 999px;

  --shadow-sm: 0 1px 3px rgba(0,0,0,.10);
  --shadow-md: 0 4px 12px rgba(0,0,0,.12);

  --font-sans: 'Geist', 'Inter', system-ui, sans-serif;
  --font-mono: 'Geist Mono', 'JetBrains Mono', monospace;

  --font-size-xs:  11px;
  --font-size-sm:  13px;
  --font-size-md:  14px;
  --font-size-lg:  16px;
  --font-size-xl:  20px;
  --font-size-2xl: 28px;

  --sidebar-width: 200px;
}
```

---

## Routes

| Path | Component | Auth |
|---|---|---|
| `/login` | Login | none |
| `/admin` | AdminPanel | Admin JWT |
| `/dashboard` | CPODashboard | CPO JWT |
| `/dashboard/new-session` | NewSession | CPO JWT |
| `/dashboard/pizzas` | PizzaMenu | CPO JWT |
| `/orders/:link` | TeamOrderPage | none |

---

## Files

| File | Purpose |
|---|---|
| `wireframes.html` | Browsable wireframe canvas — open in browser |
| `screens.jsx` | JSX source for all wireframe screens |
| `app.jsx` | Canvas layout wiring |
| `design-canvas.jsx` | Pan/zoom canvas component (not for production) |
| `specification.md` | Full product spec incl. API endpoints, data models, security |

---

## Out of Scope (see specification.md §12)

- Database (file-based JSON only)
- Email notifications
- Multi-language
- Payment processing
- Historical analytics
