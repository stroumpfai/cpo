// Mirror of the active language, kept next to the `cpo_auth` marker.
//
// Two jobs:
//   - it *is* the preference for team members on the public order page (no account to store it on)
//   - for a CPO/admin it caches the account preference, so a reload renders in the right language
//     immediately instead of flashing English until GET /cpo/me resolves
import { isSupported } from './locales.js';

const LANG_KEY = 'cpo_lang';

export function getStoredLanguage() {
  try {
    const tag = localStorage.getItem(LANG_KEY);
    return isSupported(tag) ? tag : null;
  } catch {
    return null;
  }
}

/** Store a tag, or clear the mirror with null/an unsupported tag ("follow my browser"). */
export function setStoredLanguage(tag) {
  try {
    if (isSupported(tag)) localStorage.setItem(LANG_KEY, tag);
    else localStorage.removeItem(LANG_KEY);
  } catch {
    // Private mode or quota exceeded — remembering the choice is a convenience,
    // never a reason to break the page.
  }
}
