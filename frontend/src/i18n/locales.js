// The registry of shipped languages — the single place to touch when adding one.
//
// Adding a language:
//   1. copy locales/en.json, translate every value (keys must match exactly)
//   2. import it below and add one row to LOCALES
//   3. extend the `Language` literal in backend/models.py with the same tag
//   4. npm test — the parity test names any key you missed
import en from './locales/en.json';
import deCH from './locales/de-CH.json';
import frCH from './locales/fr-CH.json';
import itCH from './locales/it-CH.json';

// `label` is deliberately written in its own language — a French speaker looking
// for their language scans for "Français", not "French".
export const LOCALES = [
  { tag: 'en',    label: 'English',  resource: en },
  { tag: 'de-CH', label: 'Deutsch',  resource: deCH },
  { tag: 'fr-CH', label: 'Français', resource: frCH },
  { tag: 'it-CH', label: 'Italiano', resource: itCH },
];

export const DEFAULT_LOCALE = 'en';

export const SUPPORTED_TAGS = LOCALES.map(l => l.tag);

export function isSupported(tag) {
  return SUPPORTED_TAGS.includes(tag);
}
