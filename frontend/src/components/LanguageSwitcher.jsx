import { useTranslation } from 'react-i18next';
import { LOCALES } from '../i18n/locales.js';
import { setStoredLanguage } from '../i18n/storage.js';

/**
 * Compact language picker for the pages with no account behind them.
 *
 * A team member has nowhere to store a preference server-side, so the choice
 * lives in the localStorage mirror and is picked up again on the next visit.
 *
 * The switch goes through the instance from context rather than the module
 * singleton: in the app they are the same object, and in tests they are not.
 */
export function LanguageSwitcher({ style }) {
  const { t, i18n } = useTranslation();

  function handleChange(e) {
    const tag = e.target.value;
    setStoredLanguage(tag);
    i18n.changeLanguage(tag);
  }

  return (
    <select
      className="form-input"
      aria-label={t('common.language')}
      value={i18n.resolvedLanguage ?? i18n.language}
      onChange={handleChange}
      style={{
        width: 'auto',
        padding: '4px 24px 4px 8px',
        fontSize: 'var(--font-size-sm)',
        color: 'var(--color-text-soft)',
        ...style,
      }}
    >
      {LOCALES.map(({ tag, label }) => (
        <option key={tag} value={tag}>{label}</option>
      ))}
    </select>
  );
}
