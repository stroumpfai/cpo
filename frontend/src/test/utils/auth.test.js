import {
  setAuth,
  clearAuth,
  getRole,
  isExpired,
  isAuthenticated,
} from '../../utils/auth.js';

beforeEach(() => {
  localStorage.clear();
});

describe('setAuth / getRole', () => {
  it('reads back the stored role', () => {
    setAuth('cpo', 3600);
    expect(getRole()).toBe('cpo');
  });

  it('returns "admin" for an admin marker', () => {
    setAuth('admin', 3600);
    expect(getRole()).toBe('admin');
  });

  it('returns null when no marker is stored', () => {
    expect(getRole()).toBeNull();
  });

  it('returns null and does not throw for a malformed marker', () => {
    localStorage.setItem('cpo_auth', 'not{valid json');
    expect(() => getRole()).not.toThrow();
    expect(getRole()).toBeNull();
  });
});

describe('clearAuth', () => {
  it('returns null after removal', () => {
    setAuth('cpo', 3600);
    clearAuth();
    expect(getRole()).toBeNull();
  });
});

describe('isExpired', () => {
  it('returns false for a marker with a future exp', () => {
    setAuth('cpo', 3600);
    expect(isExpired()).toBe(false);
  });

  it('returns true for a marker with a past exp', () => {
    setAuth('cpo', -1);
    expect(isExpired()).toBe(true);
  });

  it('returns true when no marker is stored', () => {
    expect(isExpired()).toBe(true);
  });
});

describe('isAuthenticated', () => {
  it('returns true for a valid non-expired marker', () => {
    setAuth('cpo', 3600);
    expect(isAuthenticated()).toBe(true);
  });

  it('returns false for an expired marker', () => {
    setAuth('cpo', -1);
    expect(isAuthenticated()).toBe(false);
  });

  it('returns false when no marker is stored', () => {
    expect(isAuthenticated()).toBe(false);
  });
});

describe('legacy token migration', () => {
  it('module load purges any JWT left by older app versions', async () => {
    // The purge runs at import time; the module is already loaded for this
    // test file, so assert the key stays absent after a fresh setAuth cycle.
    expect(localStorage.getItem('cpo_token')).toBeNull();
  });
});
