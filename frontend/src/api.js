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
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch { /* non-JSON error body */ }
    const err = new Error(detail);
    err.status = res.status;
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
