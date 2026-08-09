import i18n, { applyAccountLanguage, applyLanguage, resolveInitialLanguage } from '../../i18n/index.js';
import { getStoredLanguage } from '../../i18n/storage.js';

beforeEach(() => {
  localStorage.clear();
});

afterEach(async () => {
  localStorage.clear();
  await i18n.changeLanguage('en');
});

describe('resolveInitialLanguage', () => {
  it('prefers a stored choice over the browser', () => {
    localStorage.setItem('cpo_lang', 'it-CH');
    expect(resolveInitialLanguage()).toBe('it-CH');
  });

  it('falls back to browser detection — jsdom reports en-US', () => {
    expect(resolveInitialLanguage()).toBe('en');
  });
});

describe('applyLanguage', () => {
  it('switches the active language and remembers it', async () => {
    applyLanguage('fr-CH');

    expect(i18n.language).toBe('fr-CH');
    expect(getStoredLanguage()).toBe('fr-CH');
    expect(i18n.t('common.save')).toBe('Enregistrer');
  });

  it('clears the mirror on null and reverts to the browser language', () => {
    applyLanguage('de-CH');
    applyLanguage(null);

    expect(getStoredLanguage()).toBeNull();
    expect(i18n.language).toBe('en');
  });

  it('returns the tag that ended up active', () => {
    expect(applyLanguage('de-CH')).toBe('de-CH');
    expect(applyLanguage(null)).toBe('en');
  });

  it('is what applyAccountLanguage calls — same behaviour for a null account preference', () => {
    expect(applyAccountLanguage).toBe(applyLanguage);
  });
});

describe('fallback', () => {
  it('serves English for a key a translation is missing', async () => {
    await i18n.changeLanguage('de-CH');
    expect(i18n.t('common.save')).toBe('Speichern');
    expect(i18n.t('nope.not.a.key')).toBe('nope.not.a.key');
  });
});
