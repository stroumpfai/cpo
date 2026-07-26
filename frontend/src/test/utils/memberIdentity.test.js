import {
  getMemberIdentity,
  setMemberIdentity,
  clearMemberIdentity,
} from '../../utils/memberIdentity.js';

const KEY = 'cpo_member_identity';

beforeEach(() => {
  localStorage.clear();
});

describe('getMemberIdentity', () => {
  it('returns empty strings for an unknown link', () => {
    expect(getMemberIdentity('nolink')).toEqual({ name: '', email: '' });
  });

  it('returns empty strings when no link is given', () => {
    expect(getMemberIdentity(undefined)).toEqual({ name: '', email: '' });
  });

  it('falls back to defaults for malformed JSON', () => {
    localStorage.setItem(KEY, 'not{valid json');
    expect(() => getMemberIdentity('a')).not.toThrow();
    expect(getMemberIdentity('a')).toEqual({ name: '', email: '' });
  });

  it('falls back to defaults when the stored value is not an object', () => {
    localStorage.setItem(KEY, '[]');
    expect(getMemberIdentity('a')).toEqual({ name: '', email: '' });
    localStorage.setItem(KEY, 'null');
    expect(getMemberIdentity('a')).toEqual({ name: '', email: '' });
  });

  it('ignores non-string stored values', () => {
    localStorage.setItem(KEY, JSON.stringify({ a: { name: 42, email: null } }));
    expect(getMemberIdentity('a')).toEqual({ name: '', email: '' });
  });

  it('does not read through to Object.prototype for a __proto__ link', () => {
    expect(getMemberIdentity('__proto__')).toEqual({ name: '', email: '' });
  });
});

describe('setMemberIdentity', () => {
  it('round-trips a name for a link', () => {
    setMemberIdentity('link1', 'name', 'Alice');
    expect(getMemberIdentity('link1').name).toBe('Alice');
  });

  it('keeps name and email independent for the same link', () => {
    setMemberIdentity('link1', 'name', 'Alice');
    setMemberIdentity('link1', 'email', 'alice@example.com');
    expect(getMemberIdentity('link1')).toEqual({
      name: 'Alice',
      email: 'alice@example.com',
    });
  });

  it('isolates two different links', () => {
    setMemberIdentity('link1', 'name', 'Alice');
    setMemberIdentity('link2', 'name', 'Bob');
    expect(getMemberIdentity('link1').name).toBe('Alice');
    expect(getMemberIdentity('link2').name).toBe('Bob');
  });

  it('ignores an unknown field name', () => {
    setMemberIdentity('link1', 'phone', '12345');
    expect(getMemberIdentity('link1')).toEqual({ name: '', email: '' });
  });

  it('ignores a missing link', () => {
    expect(() => setMemberIdentity('', 'name', 'Alice')).not.toThrow();
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it('survives a throwing localStorage (private mode / quota)', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    expect(() => setMemberIdentity('link1', 'name', 'Alice')).not.toThrow();
    spy.mockRestore();
  });
});

describe('clearMemberIdentity', () => {
  it('removes only the given link', () => {
    setMemberIdentity('link1', 'name', 'Alice');
    setMemberIdentity('link2', 'name', 'Bob');

    clearMemberIdentity('link1');

    expect(getMemberIdentity('link1')).toEqual({ name: '', email: '' });
    expect(getMemberIdentity('link2').name).toBe('Bob');
  });

  it('clears both name and email for that link', () => {
    setMemberIdentity('link1', 'name', 'Alice');
    setMemberIdentity('link1', 'email', 'alice@example.com');

    clearMemberIdentity('link1');

    expect(getMemberIdentity('link1')).toEqual({ name: '', email: '' });
  });

  it('does not throw for an unknown link', () => {
    expect(() => clearMemberIdentity('nope')).not.toThrow();
  });
});
