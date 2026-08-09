import { browserLanguages, detectLanguage } from '../../i18n/detect.js';

describe('detectLanguage', () => {
  it('matches an exact tag', () => {
    expect(detectLanguage(['fr-CH'])).toBe('fr-CH');
    expect(detectLanguage(['it-CH'])).toBe('it-CH');
  });

  it('matches on the primary subtag, so every German browser lands on Swiss German', () => {
    expect(detectLanguage(['de'])).toBe('de-CH');
    expect(detectLanguage(['de-DE'])).toBe('de-CH');
    expect(detectLanguage(['de-AT'])).toBe('de-CH');
  });

  it('is case-insensitive', () => {
    expect(detectLanguage(['FR-ch'])).toBe('fr-CH');
  });

  it('honours preference order and skips languages we do not ship', () => {
    expect(detectLanguage(['es-ES', 'it-IT', 'en'])).toBe('it-CH');
  });

  it('falls back to English for an unsupported language', () => {
    expect(detectLanguage(['es-ES'])).toBe('en');
    expect(detectLanguage(['ja'])).toBe('en');
  });

  it('falls back to English for empty, missing or malformed input', () => {
    expect(detectLanguage([])).toBe('en');
    expect(detectLanguage(undefined)).toBe('en');
    expect(detectLanguage(null)).toBe('en');
    expect(detectLanguage(['', '   '])).toBe('en');
    expect(detectLanguage([42, {}, 'de'])).toBe('de-CH');
  });

  it('keeps English English', () => {
    expect(detectLanguage(['en-US'])).toBe('en');
  });
});

describe('browserLanguages', () => {
  const original = Object.getOwnPropertyDescriptor(globalThis.navigator, 'languages');

  afterEach(() => {
    if (original) Object.defineProperty(globalThis.navigator, 'languages', original);
  });

  it('reads navigator.languages', () => {
    Object.defineProperty(globalThis.navigator, 'languages', {
      value: ['fr-CH', 'de-CH'],
      configurable: true,
    });

    expect(browserLanguages()).toEqual(['fr-CH', 'de-CH']);
    expect(detectLanguage()).toBe('fr-CH');
  });

  it('falls back to navigator.language when the list is empty', () => {
    Object.defineProperty(globalThis.navigator, 'languages', { value: [], configurable: true });

    expect(browserLanguages()).toEqual([globalThis.navigator.language]);
  });
});
