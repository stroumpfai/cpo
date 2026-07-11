// The JWT itself lives in an httpOnly cookie set by the server (never readable
// from JS). localStorage only holds a non-sensitive {role, exp} marker used
// for client-side routing; the server enforces real authentication.
const AUTH_KEY = 'cpo_auth';

// Purge JWTs stored by older versions of the app
localStorage.removeItem('cpo_token');

export function setAuth(role, expiresInSeconds) {
  const exp = Math.floor(Date.now() / 1000) + expiresInSeconds;
  localStorage.setItem(AUTH_KEY, JSON.stringify({ role, exp }));
}

export function clearAuth() {
  localStorage.removeItem(AUTH_KEY);
}

function readAuth() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_KEY));
  } catch {
    return null;
  }
}

export function getRole() {
  return readAuth()?.role ?? null;
}

export function isExpired() {
  const auth = readAuth();
  if (!auth?.exp) return true;
  return Date.now() / 1000 > auth.exp;
}

export function isAuthenticated() {
  return Boolean(readAuth()) && !isExpired();
}
