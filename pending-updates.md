# Pending dependency updates

These updates require code changes and should be done in dedicated sessions.
Safe/patch updates were applied on 2026-05-29 (FastAPI, uvicorn, pydantic, PyJWT, python-multipart, jsdom).

---

## 1. bcrypt 4.2.1 → 5.0.0

**Risk:** Breaking — Python API changed from bytes to str.

**What changed:**
In bcrypt 5.x, `hashpw` and `checkpw` accept and return `str` instead of `bytes`.
Any call that does `.encode()` / `.decode()` will need to be removed.

**Files to touch:**
- `backend/services/admin_service.py` — find all `bcrypt.hashpw` / `bcrypt.checkpw` calls
- `backend/tests/` — any fixtures that construct raw bcrypt hashes

**Steps:**
1. `pip install bcrypt==5.0.0`
2. `grep -rn "bcrypt\." backend/` to locate every call site
3. Remove `.encode('utf-8')` on inputs; remove `.decode()` on hash outputs
4. Run `JWT_SECRET=test pytest backend/tests/ -q` — all tests must pass
5. Pin `bcrypt==5.0.0` in `requirements.txt`

---

## 2. pytest 8.3.4 → 9.0.3  +  pytest-asyncio 0.24.0 → 1.4.0

**Risk:** pytest-asyncio is a major rewrite (0.x → 1.x); pytest 9 is a minor step.

**What changed in pytest-asyncio 1.x:**
- `asyncio_mode = "auto"` is now the default; no longer need `@pytest.mark.asyncio` on every test
- Config key moved: must be declared in `pyproject.toml` or `pytest.ini`
- Fixture scoping rules tightened (async fixtures must match test scope)

**Steps:**
1. Add `asyncio_mode = "auto"` to `backend/pytest.ini` (or create one):
   ```ini
   [pytest]
   asyncio_mode = auto
   ```
2. `pip install pytest==9.0.3 pytest-asyncio==1.4.0`
3. Run tests; fix any scope mismatches in async fixtures (usually `scope="session"` on async fixtures no longer allowed without explicit `loop_scope`)
4. Optionally remove all `@pytest.mark.asyncio` decorators (now redundant in auto mode)
5. Pin new versions in `requirements.txt`

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

## 6. Python 3.12 (local) → 3.13 (Docker alignment)

**Note:** The Dockerfile already uses Python 3.13. Local dev uses 3.12.3, which causes a
runtime mismatch that could hide 3.13-specific behaviour.

**Steps:**
1. Install Python 3.13 locally (pyenv or system package)
2. Recreate the venv: `python3.13 -m venv venv && pip install -r backend/requirements.txt -r backend/requirements-dev.txt`
3. Run full test suite to confirm parity
4. Update `CLAUDE.md` — currently says "Python 3.14" which is incorrect; should say "Python 3.13"
