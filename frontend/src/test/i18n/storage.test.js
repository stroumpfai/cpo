import { getStoredLanguage, setStoredLanguage } from '../../i18n/storage.js';

beforeEach(() => {
  localStorage.clear();
});

describe('language mirror', () => {
  it('round-trips a supported tag', () => {
    setStoredLanguage('de-CH');
    expect(getStoredLanguage()).toBe('de-CH');
  });

  it('clears the mirror on null — "follow my browser"', () => {
    setStoredLanguage('it-CH');
    setStoredLanguage(null);
    expect(getStoredLanguage()).toBeNull();
    expect(localStorage.getItem('cpo_lang')).toBeNull();
  });

  it('refuses to store a language we do not ship', () => {
    setStoredLanguage('de-DE');
    expect(getStoredLanguage()).toBeNull();
  });

  it('ignores a stale value left by an older version', () => {
    localStorage.setItem('cpo_lang', 'klingon');
    expect(getStoredLanguage()).toBeNull();
  });

  it('returns null when localStorage is unavailable', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('private mode');
    });

    expect(getStoredLanguage()).toBeNull();
    spy.mockRestore();
  });

  it('never throws when localStorage rejects a write', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota exceeded');
    });

    expect(() => setStoredLanguage('fr-CH')).not.toThrow();
    spy.mockRestore();
  });
});
