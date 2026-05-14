const TOKEN_KEY = 'cpo_token';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function parsePayload(token) {
  if (!token) return null;
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch {
    return null;
  }
}

export function getRole() {
  return parsePayload(getToken())?.role ?? null;
}

export function getUserId() {
  return parsePayload(getToken())?.sub ?? null;
}

export function isExpired() {
  const payload = parsePayload(getToken());
  if (!payload?.exp) return true;
  return Date.now() / 1000 > payload.exp;
}

export function isAuthenticated() {
  return Boolean(getToken()) && !isExpired();
}
