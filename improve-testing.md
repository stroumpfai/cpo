# Testing Improvement Plan

## Current state

| Layer | Tests | Coverage |
|---|---|---|
| Backend unit/integration | 131 tests, all passing | ~96% line coverage (pytest-cov) |
| Backend E2E | 12 HTTP-level scenarios | Full happy-path + edge cases |
| Frontend unit | **0** | None |
| Browser E2E | **0** | None |

Frontend uses Vitest (already in `devDependencies`) but has no test files.
No browser automation tool is installed.

---

## Work packages — designed for parallel sub-agents

Each agent works independently. Agents A and B can start simultaneously.
Agents C, D, E depend on Agent A completing first (shared test infrastructure).

---

### Agent A — Frontend test infrastructure
**Scope**: Install missing dependencies and configure Vitest for React component testing.

**What to install** (add to `frontend/package.json` devDependencies):
```
@testing-library/react          # render(), screen, fireEvent
@testing-library/user-event     # realistic user interactions
@testing-library/jest-dom       # toBeInTheDocument() etc.
jsdom                           # DOM environment for Vitest
```

**Vitest config** — add a `test` block to `frontend/vite.config.js` (or create `frontend/vitest.config.js`):
```js
test: {
  environment: 'jsdom',
  globals: true,
  setupFiles: ['./src/test/setup.js'],
}
```

**Setup file** at `frontend/src/test/setup.js`:
```js
import '@testing-library/jest-dom';
```

**Test utilities** at `frontend/src/test/utils.jsx`:
- `renderWithRouter(ui, { initialEntries })` — wraps render() in MemoryRouter
- `mockApi(overrides)` — vi.mock('../api.js') helper returning controllable resolved/rejected values
- `makeJwt(payload)` — build a fake JWT string for localStorage seeding in auth tests

**Deliverable**: `npm test` runs without errors on an empty test suite; `vitest --coverage` is configured.

---

### Agent B — Playwright setup
**Scope**: Install Playwright and create the project scaffold. No test scenarios yet — that's Agent E.

**Install**:
```bash
cd frontend
npm install --save-dev @playwright/test
npx playwright install chromium   # only chromium needed for CI
```

**Config** — `frontend/playwright.config.js`:
```js
import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://localhost:8002',
    headless: true,
  },
  webServer: {                      // starts the full stack before tests
    command: 'cd ../backend && uvicorn main:app --port 8002',
    url: 'http://localhost:8002',
    reuseExistingServer: !process.env.CI,
  },
});
```

**Shared fixtures** — `frontend/e2e/fixtures.js`:
- `seedAdmin()` — writes a minimal `config/test-config.json` with a known admin password hash
- `seedCpo(adminToken)` — POSTs to `/api/admin/cpos` to create a CPO with known credentials
- `seedMenu(cpoToken, pizzas)` — POSTs pizzas to `/api/cpo/menu`
- `seedSession(cpoToken)` — creates an active session spanning now ± 30 min
- `loginAs(page, username, password)` — navigates to `/login`, fills and submits form, awaits redirect

**Deliverable**: `npx playwright test` runs, finds 0 tests, exits 0.

---

### Agent C — Frontend unit tests: utils and API client
**Depends on**: Agent A complete.

**Files to create**:

#### `frontend/src/test/utils/auth.test.js`
Test every export from `utils/auth.js`. All are pure-ish functions over `localStorage`.

| Test | What to assert |
|---|---|
| `setToken` / `getToken` roundtrip | reads back stored value |
| `removeToken` | returns null after removal |
| `getRole` with valid JWT | returns `"admin"` or `"cpo"` from payload |
| `getRole` with no token | returns null |
| `getRole` with malformed token | returns null (no throw) |
| `getUserId` | extracts `sub` claim |
| `isExpired` with future `exp` | returns false |
| `isExpired` with past `exp` | returns true |
| `isExpired` with no token | returns true |
| `isAuthenticated` — valid token | returns true |
| `isAuthenticated` — expired | returns false |

#### `frontend/src/test/utils/time.test.js`
Pure functions — no mocks needed.

| Test | Input | Expected |
|---|---|---|
| `localHhmmToUtc` on UTC+2 offset | `"2024-06-15"`, `"14:00"` | `"12:00"` |
| `utcHhmmToLocal` round-trip | any date + UTC time | same time after `localHhmmToUtc` |
| `parseUtcDt` returns epoch-ms | `"2024-01-01"`, `"00:00"` | `Date.UTC(2024,0,1,0,0)` |
| midnight rollover in `localHhmmToUtc` | `"2024-06-15"`, `"00:30"` (UTC+2) | `"22:30"` previous day handled |

Note: pin timezone via `process.env.TZ = 'Europe/Zurich'` in the test file.

#### `frontend/src/test/api.test.js`
Mock `fetch` with `vi.fn()`.

| Test | Setup | Assert |
|---|---|---|
| GET sends Authorization header | token in localStorage | header `Bearer <token>` present |
| POST serialises body as JSON | body object | `Content-Type: application/json`, correct body |
| 401 response clears token and redirects | fetch returns 401 | `localStorage` cleared, `location.href` set to `/login` |
| 204 response returns null | fetch returns 204 | resolved value is null |
| Non-OK response with JSON detail throws | fetch returns 400 + `{detail: "bad"}` | throws Error with message `"bad"` |
| Non-OK response with non-JSON body throws | fetch returns 500 text | throws Error with default message |

---

### Agent D — Frontend unit tests: components and pages
**Depends on**: Agent A complete.

**Files to create**:

#### `frontend/src/test/components/StatCards.test.jsx`
- Renders member count, pizza count, CHF total, countdown string
- When `isClosed=true`: shows "session closed", hides progress bar and live chip
- When `isClosed=false`: shows countdown value and live chip

#### `frontend/src/test/components/SessionHeader.test.jsx`
- Renders session date formatted as "Mon 15 Jan"
- Converts UTC start/end times to local for display (pin TZ)
- "Copy link" button writes the correct URL to clipboard (mock `navigator.clipboard`)
- After copy, button text changes to "✓ copied"

#### `frontend/src/test/components/PrivateRoute.test.jsx`
- With a valid non-expired token in localStorage: renders children
- With no token: redirects to `/login`
- With expired token: redirects to `/login`

#### `frontend/src/test/components/OrdersPerPersonTable.test.jsx`
- Renders one row per order with member name, pizza name, price
- Delete button calls `onDelete(orderId)`
- Paid toggle calls `onTogglePaid(orderId)`
- Empty state: renders a "no orders yet" message
- `isClosed=true`: delete button is hidden

#### `frontend/src/test/components/PizzeriaSummaryTable.test.jsx`
- Renders one row per pizza type with count and subtotal
- Footer shows total orders and total price
- Empty state handled

#### `frontend/src/test/pages/LoginPage.test.jsx`
Mock `api.post`. Use `renderWithRouter`.

| Test | Setup | Assert |
|---|---|---|
| Renders username/password fields and submit button | — | elements present |
| Successful admin login | api resolves `{token, role:'admin'}` | navigates to `/admin` |
| Successful CPO login | api resolves `{token, role:'cpo'}` | navigates to `/dashboard` |
| Failed login | api rejects with `{message:'Invalid credentials'}` | error text shown |
| Button disabled while loading | slow promise | button has `disabled` attribute during request |

#### `frontend/src/test/pages/TeamOrderPage.test.jsx`
Mock `api.get` and `api.post`. Most complex page — highest value.

| Test | Setup | Assert |
|---|---|---|
| Loading state | api.get pending | "Loading…" text shown |
| Closed session renders banner | api.get resolves with `status:'closed'` | "Session is closed." shown |
| Active session shows pizza menu | api.get resolves with active session + pizzas | pizza options in select |
| Add to cart without name shows error | click "add to your order" with no name | "Enter your name first." shown |
| Add to cart adds row | fill name, select pizza, click add | cart row appears |
| Remove from cart removes row | add then click ✕ | row gone |
| Submit sends correct payload | cart with 2 items | `api.post` called with `pizza_ids` array |
| Successful submit shows confirmation | api.post resolves | "Order placed!" shown |
| Rate-limit error (429) shows message | api.post rejects with status 429 | "Too many orders" shown |
| Closed session error (403) shows message | api.post rejects with status 403 | "Session is closed" shown |
| "Add another order" resets state | click after submit | back to order form |

#### `frontend/src/test/pages/CPODashboard.test.jsx`
Mock `api.get`, `api.delete`. Mock `EventSource` globally.

| Test | Assert |
|---|---|
| No sessions → "No sessions yet" + link to new-session | |
| Active session → shows StatCards and both tabs | |
| Tab switch to "List for ordering at Pizzeria" shows PizzeriaSummaryTable | |
| Delete order calls `api.delete` and removes row from distribution | |
| Paid toggle marks row | |

#### `frontend/src/test/pages/PizzaMenu.test.jsx`
| Test | Assert |
|---|---|
| Lists pizzas from `api.get('/cpo/menu')` | |
| Add pizza form submits to `api.post` and adds row | |
| Edit pizza updates name/price inline | |
| Delete pizza calls `api.delete` and removes row | |
| Duplicate name shows inline error (409 from api) | |

#### `frontend/src/test/pages/AdminPanel.test.jsx`
| Test | Assert |
|---|---|
| Lists CPOs from `api.get('/admin/cpos')` | |
| Create CPO form submits correct payload | |
| Password reset sends to correct endpoint | |

---

### Agent E — Playwright browser E2E scenarios
**Depends on**: Agent B complete. **Runs against the real backend** — no mocks.

All tests use the shared fixtures from Agent B. Each test gets a fresh `tmp` data directory via a backend env var (`DATA_DIR`) injected by the fixture.

**File**: `frontend/e2e/ordering.spec.js`

#### Scenario 1 — Login routing
```
CPO logs in → lands on /dashboard
Admin logs in → lands on /admin
Wrong password → error shown on page
```

#### Scenario 2 — Full ordering flow (golden path)
```
Admin creates CPO
CPO adds two pizzas to menu
CPO creates active session
Team member opens /orders/<link>
  → sees both pizzas in dropdown
Team member enters name, adds first pizza, adds second pizza
  → cart shows 2 rows and correct total
Team member clicks "submit order ✓"
  → "Order placed!" confirmation
CPO opens dashboard
  → StatCards shows 1 member, 2 pizzas, correct CHF
  → "Orders per person" tab shows Alice's rows
  → "List for ordering" tab shows consolidated counts
```

#### Scenario 3 — Session closed state
```
CPO creates a session, then time is manipulated (session end backdated via direct storage write)
Team member visits link
  → "Session is closed." banner shown
  → order form not shown
```

#### Scenario 4 — Cart interactions
```
Active session open
Member enters name, adds pizza to cart
Clicks ✕ on cart row → row removed
Adds three pizzas → cart shows 3 rows and summed total
Submits → "Order placed!"
```

#### Scenario 5 — Rate limiting (browser-visible error)
```
Active session open
Member submits an order
Immediately submits again (within 5s)
  → "Too many orders. Please wait 5 seconds" message visible
```

#### Scenario 6 — Admin: create and manage CPO
```
Admin logs in
Clicks "Add CPO" → fills form → submits
  → new CPO appears in list
Edits email inline → saves → updated value shown
Resets password → new password works on login
```

#### Scenario 7 — CPO: pizza menu management
```
CPO logs in
Navigates to /dashboard/pizzas
Adds "Margherita" at 12.50 → appears in list
Adds "margherita" again → inline error "already exists"
Edits price to 13.00 → updated in list
Deletes pizza → removed from list
```

#### Scenario 8 — CPO: new session form validation
```
CPO navigates to /dashboard/new-session
Submits with end_time before start_time → form error
Submits with valid times → redirected to /dashboard
Second session attempt → server 409 → error shown
```

#### Scenario 9 — Live SSE update
```
CPO has dashboard open with active session (SSE connected)
Team member submits order in another tab/context
CPO dashboard updates StatCards without manual refresh
  → total_orders increments
  → member name appears in distribution table
```

#### Scenario 10 — Logout and auth guard
```
CPO logs in
Logs out (sidebar logout button)
  → redirected to /login
Manually navigates to /dashboard
  → redirected to /login (PrivateRoute working)
```

---

## Implementation order for sub-agents

```
Step 1 (parallel): Agent A + Agent B
Step 2 (parallel): Agent C + Agent D + Agent E
```

Agent C and D are independent of each other and can run in parallel once A is done.
Agent E is independent of C and D and can run as soon as B is done.

## Acceptance criteria

- `npm test` in `frontend/` runs all Vitest unit tests, 0 failures
- `npm run test:coverage` shows ≥ 80% line coverage on `src/`
- `npx playwright test` runs all E2E scenarios against a local backend, 0 failures
- No test introduces real network calls or real filesystem writes (Vitest tests mock `fetch`; Playwright tests use a dedicated `DATA_DIR`)
