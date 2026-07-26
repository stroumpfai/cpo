# Pending dependency updates

These updates require code changes and should be done in dedicated sessions.
Safe/patch updates were applied on 2026-05-29 (FastAPI, uvicorn, pydantic, PyJWT, python-multipart, jsdom).

---

## 1. bcrypt 4.2.1 → 5.0.0 — DONE (2026-07-26)

**Correction:** the "bytes → str" API-change claim previously here was wrong — verified
by installing bcrypt 5.0.0 in an isolated venv; `hashpw`/`checkpw` still take/return
`bytes`. The actual breaking change: passwords over 72 bytes now raise `ValueError`
instead of being silently truncated. The bcrypt calls also weren't in
`backend/services/admin_service.py` — they're in `backend/utils.py` and
`scripts/create_admin.py`.

**Fix applied:** `hash_password`/`verify_password` in `backend/utils.py` and
`hash_password` in `scripts/create_admin.py` now clamp to `plain.encode()[:72]` before
calling bcrypt, preserving the old truncation behavior instead of trading it for a 500.
Regression tests added in `backend/tests/test_admin.py`
(`test_create_cpo_password_over_72_bytes`) and `backend/tests/test_cpo.py`
(`test_change_password_over_72_bytes`) covering a >72-byte password through creation,
change, and subsequent login.

---

## 2. pytest 8.3.4 → 9.1.1  +  pytest-asyncio 0.24.0 → 1.4.0 — DONE (2026-07-26)

**Correction:** `backend/pytest.ini` already had `asyncio_mode = auto` before this bump
(not something newly required), and the suite has no `event_loop` fixture or explicit
`scope=` on async fixtures, so the fixture-scoping tightening in pytest-asyncio 1.x
didn't require any test changes.

**Change applied:** bumped both packages; added
`asyncio_default_fixture_loop_scope = function` to `backend/pytest.ini` to silence
pytest-asyncio 1.4.0's forward-looking deprecation warning about that setting being
unset. Full suite passes unchanged (365 → 367 after the bcrypt regression tests above).

---

## 3. React 18 → 19  +  @types/react 18 → 19  +  @types/react-dom 18 → 19 — DONE (2026-07-26)

**Correction:** this section only named `PrivateRoute.jsx` for the `defaultProps` fix —
`StatCards.jsx` (`StatCard.defaultProps = { mono: false }`) had the identical issue and
was missing from this list. Both were falsy-guarded (`role: null` vs `undefined`,
`mono: false` vs `undefined` — behaviorally identical), so the React 19 silent-ignore of
`defaultProps` was inert either way, just noisy under React 18.3's existing deprecation
warning. `frontend/src/main.jsx` already used `ReactDOM.createRoot`, so the
`ReactDOM.render` removal in 19 didn't apply.

**Fix applied:** converted both `PrivateRoute.jsx` and `StatCards.jsx` from
`Component.defaultProps = {...}` to ES6 default params. Left the 9 files' `prop-types`
usage as-is — React no longer invokes those checks under 19, but the library still works
standalone; removing it is unrelated cleanup, not required for the upgrade. The single
`act()` + `vi.advanceTimersByTimeAsync` test (`TeamOrderPage.test.jsx:363`, the riskiest
spot per the fake-timers/act() combination) passed cleanly, both in isolation and in the
full suite (218/218).

---

## 4. react-router-dom 6 → 7 — DONE (2026-07-26)

**Correction:** the "smoke-test all 6 routes" list here was stale — `App.jsx` actually
defines 10 route entries (including `/dashboard/settings` and `/dashboard/stats`, added
after this doc was written), and `/dashboard/pizzas` is a redirect, not a page.

**Fix applied:** added `future={{ v7_startTransition: true, v7_relativeSplatPath: true }}`
to `<BrowserRouter>` (`App.jsx`) then bumped the package. Full suite green (218/218), dev
server and the Playwright E2E suite both confirmed routing works end-to-end.

**Note for later:** `react-router-dom` has no v8 release — npm shows it capped at 7.18.1
while the underlying `react-router` package it now just re-exports is already at 8.3.0.
This looks like `react-router-dom` is headed for deprecation as a compat shim; a future
session may need to do a mechanical import rename (`react-router-dom` → `react-router`,
~17 files) if/when a v8 that drops the shim actually matters. Separately: `npm audit`
flags `react-router`/`react-router-dom` "high" for GHSA-qwww-vcr4-c8h2 — verified this
only affects the unstable RSC APIs (React Server Components + data-router actions), which
this app doesn't use anywhere (declarative `<BrowserRouter>`/`<Routes>`/`<Route>` only, no
`createBrowserRouter`, no loaders/actions). Not exploitable here; there's no patched
release in the 7.x line regardless (fix landed in `react-router@8.3.0` only).

---

## 5. Vite 6 → 8  +  vitest 2 → 4  +  @vitejs/plugin-react 4 → 6 — DONE (2026-07-26)

**Correction:** no `require()` calls existed anywhere in `frontend/` before this upgrade
(confirmed) — the pre-check passed cleanly. Also found and fixed in passing: the
`test:coverage` script (`vitest run --coverage`) had never had its provider installed —
added `@vitest/coverage-v8@4.1.10`, pinned to the exact vitest version its peer range
requires.

**Fix applied:** bumped `vitest` → 4.1.10 first (decoupled from Vite, its peer range
covers `^6||^7||^8`), then `vite` → 8.1.5 and `@vitejs/plugin-react` → 6.0.4 together
(plugin-react 6 requires `vite ^8.0.0` and drops Babel entirely for Oxc — no Babel config
existed here, nothing to port). No config changes were needed in `vite.config.js` — none
of the renamed/removed options (`build.rollupOptions`, `coverage.all`, `workspace`, etc.)
were in use. `npm run build` produced the same `../backend/dist` output; the Playwright
E2E suite (16/17, one skipped, one pre-existing time-of-day-dependent flake unrelated to
this upgrade — see below) confirmed the built bundle works end-to-end against a live
backend.

**Also bumped alongside (test tooling batch):** `@testing-library/jest-dom` 6→7 (added
`@testing-library/dom` as an explicit devDependency for its new required peer; switched
`src/test/setup.js` to `import '@testing-library/jest-dom/vitest'`) and `@playwright/test`
1.60→1.62 (no breaking changes in range; required a browser binary re-download via
`npx playwright install chromium`, revision bump 1223→1234).

**Unrelated flaky test found during E2E verification:** `e2e/ordering.spec.js` Scenario 8
("submitting past end_time shows error; valid times redirect to dashboard") computes its
"valid future times" as `start = now`, `end = now + 2h` but reuses today's date string for
both — within ~2 hours of midnight this produces an end time earlier in the day than the
start time (e.g. start 22:02, end 00:02 "today"), which the backend correctly rejects as
invalid, so the test times out waiting for a redirect that legitimately shouldn't happen.
Pre-existing date-math bug in the test, unrelated to any dependency version — not fixed
here (out of scope for a dependency upgrade), but worth a follow-up fix.

---

## 6. Python 3.12 (local) / 3.13 (Docker) → 3.14 everywhere — PARTIALLY DONE (2026-07-26)

**Correction:** the note that CLAUDE.md's "Python 3.14" was a documentation error was
wrong — 3.14 was the intended target all along (confirmed with the user); it was the
Dockerfile and README/spec/design.md that were stale at 3.13.

**Done:** `Dockerfile` (both `FROM` lines and both `python3.13` path segments in the
`COPY --from=builder` lines), `README.md`, and `spec/design.md` now all say 3.14/
`python:3.14-slim`, consistent with CLAUDE.md, spec/specification.md, and
design/README.md. `docker build` succeeds against the 3.14 base images.

**Still open:** the local venv is still 3.12.3. This machine has no Python 3.14 package
(no deadsnakes/equivalent apt source), no pyenv, and no passwordless sudo, so it couldn't
be installed non-interactively. To finish:
1. Install Python 3.14 locally (pyenv, or add a source with a 3.14 package, then
   `sudo apt install python3.14-venv` or equivalent)
2. Recreate the venv: `python3.14 -m venv venv && pip install -r backend/requirements.txt -r backend/requirements-dev.txt`
3. Run the full test suite to confirm parity with the Docker image
