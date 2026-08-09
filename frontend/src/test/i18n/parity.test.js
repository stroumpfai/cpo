import { DEFAULT_LOCALE, LOCALES } from '../../i18n/locales.js';

/** "common.save", "order.plateCount_one", … */
function flatten(obj, prefix = '') {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return value && typeof value === 'object' && !Array.isArray(value)
      ? flatten(value, path)
      : [path];
  });
}

function entries(obj, prefix = '') {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return value && typeof value === 'object' && !Array.isArray(value)
      ? entries(value, path)
      : [[path, value]];
  });
}

const base = LOCALES.find(l => l.tag === DEFAULT_LOCALE);
const translations = LOCALES.filter(l => l.tag !== DEFAULT_LOCALE);
const baseKeys = flatten(base.resource);

describe('locale files', () => {
  it('ships English as the default', () => {
    expect(base).toBeDefined();
    expect(baseKeys.length).toBeGreaterThan(0);
  });

  it.each(translations.map(l => l.tag))('%s has exactly the keys en has', tag => {
    const keys = flatten(LOCALES.find(l => l.tag === tag).resource);

    // Reported as sorted lists so a failure names the offending keys directly.
    const missing = baseKeys.filter(k => !keys.includes(k)).sort();
    const extra   = keys.filter(k => !baseKeys.includes(k)).sort();

    expect({ missing, extra }).toEqual({ missing: [], extra: [] });
  });

  it.each(LOCALES.map(l => l.tag))('%s has no empty or non-string values', tag => {
    const bad = entries(LOCALES.find(l => l.tag === tag).resource)
      .filter(([, value]) => typeof value !== 'string' || value.trim() === '')
      .map(([key]) => key)
      .sort();

    expect(bad).toEqual([]);
  });

  // A translation may legitimately drop a placeholder — German says "Deine
  // Bestellung wurde übermittelt" where English counts the plates. What is never
  // legitimate is a placeholder English does not supply: that renders as an empty
  // string (or literal braces) in front of the user.
  it.each(LOCALES.map(l => l.tag))('%s introduces no placeholder en does not supply', tag => {
    const placeholders = str => (str.match(/\{\{\s*(\w+)\s*\}\}/g) ?? []).map(m => m.replace(/[{}\s]/g, ''));
    const baseByKey = Object.fromEntries(entries(base.resource));

    const unknown = entries(LOCALES.find(l => l.tag === tag).resource)
      .flatMap(([key, value]) => {
        const allowed = placeholders(baseByKey[key] ?? '');
        return placeholders(value)
          .filter(name => !allowed.includes(name))
          .map(name => `${key}: {{${name}}}`);
      })
      .sort();

    expect(unknown).toEqual([]);
  });

  it('never writes ß in Swiss German', () => {
    const deCH = LOCALES.find(l => l.tag === 'de-CH');
    const offenders = entries(deCH.resource)
      .filter(([, value]) => value.includes('ß'))
      .map(([key]) => key);

    expect(offenders).toEqual([]);
  });
});
