/**
 * Turn an error thrown by api.js into a sentence in the user's language.
 *
 * The backend sends {detail, code, params}: `detail` is English prose, `code` is
 * stable and translatable. We translate by code and fall back to `detail`, so an
 * error nobody has translated yet still says something useful instead of nothing.
 */
export function translateApiError(err, t) {
  if (!err) return '';

  if (err.code) {
    const translated = t(`errors.${err.code}`, { ...(err.params ?? {}), defaultValue: '' });
    if (translated) return translated;
  }

  return err.message || t('errors.generic');
}
