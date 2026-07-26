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

## 3. React 18 → 19  +  @types/react 18 → 19  +  @types/react-dom 18 → 19

**Risk:** Major version — concurrent rendering changes can surface latent `useEffect` bugs.

**What changed:**
- `prop-types` is deprecated; React 19 removes `defaultProps` on function components
  → `PrivateRoute` already logs a warning about this; must migrate to JS default params
- `act()` behaviour tightened in tests; some `@testing-library/react` patterns need `await`
- `use()` hook, `ref` as prop, Actions API all available but opt-in

**Steps:**
1. `npm install react@19 react-dom@19 @types/react@19 @types/react-dom@19`
2. Fix `PrivateRoute.jsx`: replace `Component.defaultProps = {...}` with JS default params
3. Remove `prop-types` dependency if all PropTypes usages are gone
4. Run `npm test` and fix any `act()` warnings promoted to errors
5. Manual smoke-test: login → dashboard → order page → admin panel

---

## 4. react-router-dom 6 → 7

**Risk:** Major version — new loader/action API replaces nested `<Route>` with data patterns.

**What changed:**
- The JSX `<Route>` / `<Routes>` API still works but is the "legacy" path
- Future flags (`v7_startTransition`, `v7_relativeSplatPath`) are now required (no more warnings)
- `useNavigate`, `useParams`, `useLocation` unchanged

**Recommended approach — incremental (no rewrite required):**
1. `npm install react-router-dom@7`
2. Add future flags to the root `<BrowserRouter>`:
   ```jsx
   <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
   ```
3. Run `npm test` and fix any routing-related failures
4. Manual smoke-test all 6 routes (login, admin, dashboard, new-session, pizzas, orders)

---

## 5. Vite 6 → 8  +  vitest 2 → 4  +  @vitejs/plugin-react 4 → 6

**Risk:** Medium — Vite 8 drops CommonJS output; any CJS-only dependency will break the build.

**What changed:**
- Vite 8: ESM-only, faster cold starts, no more `require()` in config files
- vitest 4 requires Vite 8; new browser-mode API (not used here, so low impact)
- `@vitejs/plugin-react` 6 aligns with Vite 8's new plugin API

**Pre-check before upgrading:**
```bash
grep -r "require(" frontend/vite.config.* frontend/src/
```
If anything uses `require()`, convert to `import` first.

**Steps:**
1. `npm install vite@8 vitest@4 @vitejs/plugin-react@6`
2. Convert `vite.config.js` to ESM if not already (`"type": "module"` is set — likely fine)
3. `npm run build` — fix any CJS-related errors
4. `npm test` — fix any vitest API changes
5. `npm run preview` — smoke-test the production bundle

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
