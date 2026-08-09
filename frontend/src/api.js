import { getRole, clearAuth } from './utils/auth.js';

const BASE = '/api';

// Auth rides on the httpOnly session cookie, sent automatically by fetch
async function request(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 401) {
    const hadAuth = Boolean(getRole());
    clearAuth();
    if (hadAuth) {
      globalThis.location.href = '/login';
      return;
    }
  }

  if (res.status === 204) return null;

  if (!res.ok) {
    let detail = 'Request failed';
    let code;
    let params;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
      // Stable, translatable error identity (see backend/error_codes.py).
      // Absent on FastAPI's own 422s and on anything not yet converted —
      // callers fall back to the English `detail`.
      code   = data.code;
      params = data.params;
    } catch { /* non-JSON error body */ }
    const err = new Error(detail);
    err.status = res.status;
    err.code   = code;
    err.params = params;
    throw err;
  }

  return res.json();
}

export const api = {
  get:    (path)        => request('GET',    path),
  post:   (path, body)  => request('POST',   path, body),
  put:    (path, body)  => request('PUT',    path, body),
  patch:  (path, body)  => request('PATCH',  path, body),
  delete: (path)        => request('DELETE', path),
};
