import { makeJwt } from '../utils.jsx';
import {
  getToken,
  setToken,
  removeToken,
  getRole,
  getUserId,
  isExpired,
  isAuthenticated,
} from '../../utils/auth.js';

beforeEach(() => {
  localStorage.clear();
});

describe('setToken / getToken', () => {
  it('reads back the stored value', () => {
    const token = makeJwt({ role: 'cpo', sub: 'abc', exp: Math.floor(Date.now() / 1000) + 3600 });
    setToken(token);
    expect(getToken()).toBe(token);
  });
});

describe('removeToken', () => {
  it('returns null after removal', () => {
    const token = makeJwt({ role: 'cpo', sub: 'abc', exp: Math.floor(Date.now() / 1000) + 3600 });
    setToken(token);
    removeToken();
    expect(getToken()).toBeNull();
  });
});

describe('getRole', () => {
  it('returns "admin" for a JWT with role:admin', () => {
    setToken(makeJwt({ role: 'admin', sub: 'u1', exp: Math.floor(Date.now() / 1000) + 3600 }));
    expect(getRole()).toBe('admin');
  });

  it('returns "cpo" for a JWT with role:cpo', () => {
    setToken(makeJwt({ role: 'cpo', sub: 'u2', exp: Math.floor(Date.now() / 1000) + 3600 }));
    expect(getRole()).toBe('cpo');
  });

  it('returns null when no token is stored', () => {
    expect(getRole()).toBeNull();
  });

  it('returns null and does not throw for a malformed token', () => {
    setToken('not.validbase64!!!.sig');
    expect(() => getRole()).not.toThrow();
    expect(getRole()).toBeNull();
  });
});

describe('getUserId', () => {
  it('returns the sub claim for a valid JWT', () => {
    setToken(makeJwt({ role: 'cpo', sub: 'user-123', exp: Math.floor(Date.now() / 1000) + 3600 }));
    expect(getUserId()).toBe('user-123');
  });

  it('returns null when no token is stored', () => {
    expect(getUserId()).toBeNull();
  });
});

describe('isExpired', () => {
  it('returns false for a token with a future exp', () => {
    setToken(makeJwt({ role: 'cpo', sub: 'u', exp: Math.floor(Date.now() / 1000) + 3600 }));
    expect(isExpired()).toBe(false);
  });

  it('returns true for a token with a past exp', () => {
    setToken(makeJwt({ role: 'cpo', sub: 'u', exp: Math.floor(Date.now() / 1000) - 1 }));
    expect(isExpired()).toBe(true);
  });

  it('returns true when no token is stored', () => {
    expect(isExpired()).toBe(true);
  });
});

describe('isAuthenticated', () => {
  it('returns true for a valid non-expired token', () => {
    setToken(makeJwt({ role: 'cpo', sub: 'u', exp: Math.floor(Date.now() / 1000) + 3600 }));
    expect(isAuthenticated()).toBe(true);
  });

  it('returns false for an expired token', () => {
    setToken(makeJwt({ role: 'cpo', sub: 'u', exp: Math.floor(Date.now() / 1000) - 1 }));
    expect(isAuthenticated()).toBe(false);
  });

  it('returns false when no token is stored', () => {
    expect(isAuthenticated()).toBe(false);
  });
});
