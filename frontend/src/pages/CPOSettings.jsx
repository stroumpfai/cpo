import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '../api.js';
import { applyAccountLanguage } from '../i18n/index.js';
import { translateApiError } from '../i18n/apiError.js';
import { LOCALES } from '../i18n/locales.js';
import { clearAuth } from '../utils/auth.js';

// The select's "follow my browser" entry. '' rather than null because that is
// what a <select> hands back; it becomes `null` on the wire.
const BROWSER_LANGUAGE = '';

export function CPOSettings() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [clientError, setClientError] = useState('');
  const [serverError, setServerError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [currency, setCurrency]                     = useState('CHF');
  const [currencyError, setCurrencyError]           = useState('');

  const [teamName, setTeamName]                     = useState('');
  const [teamNameError, setTeamNameError]           = useState('');

  const [memberIdentifier, setMemberIdentifier]           = useState('name');
  const [memberIdentifierError, setMemberIdentifierError] = useState('');

  const [defaultGracePeriod, setDefaultGracePeriod]           = useState(2);
  const [defaultGracePeriodError, setDefaultGracePeriodError] = useState('');

  const [language, setLanguage]           = useState(BROWSER_LANGUAGE);
  const [languageError, setLanguageError] = useState('');

  const [teamSettingsSaving, setTeamSettingsSaving] = useState(false);
  const [teamSettingsSuccess, setTeamSettingsSuccess] = useState('');

  const navigate = useNavigate();
  const { t, i18n } = useTranslation();

  // Fields the user has already edited. The profile fetch resolves after the
  // form is interactive, so hydrating it blindly would discard anything typed
  // or picked in the meantime.
  const edited = useRef(new Set());
  const markEdited = field => edited.current.add(field);

  useEffect(() => {
    api.get('/cpo/me').then(cpo => {
      if (!edited.current.has('currency'))         setCurrency(cpo.currency ?? 'CHF');
      if (!edited.current.has('teamName'))         setTeamName(cpo.team_name ?? '');
      if (!edited.current.has('memberIdentifier')) setMemberIdentifier(cpo.member_identifier ?? 'name');
      if (!edited.current.has('defaultGracePeriod')) setDefaultGracePeriod(cpo.default_grace_period_minutes ?? 2);
      // null on the account means "follow my browser"
      if (!edited.current.has('language'))         setLanguage(cpo.language ?? BROWSER_LANGUAGE);
    }).catch(() => {});
  }, []);

  async function handleSaveTeamSettings() {
    const trimmedName = teamName.trim();
    const trimmedCurrency = currency.trim();
    setTeamNameError('');
    setCurrencyError('');
    setMemberIdentifierError('');
    setDefaultGracePeriodError('');
    setLanguageError('');
    setTeamSettingsSuccess('');

    if (!trimmedName) { setTeamNameError(t('errors.teamNameEmpty')); return; }
    if (!trimmedCurrency) { setCurrencyError(t('errors.currencyEmpty')); return; }

    setTeamSettingsSaving(true);
    // The language is a personal setting, not a team one, but it shares the
    // single Save button — one batch, one round of field errors.
    const [nameResult, currencyResult, identifierResult, gracePeriodResult, languageResult] = await Promise.allSettled([
      api.patch('/cpo/team-name', { team_name: trimmedName }),
      api.patch('/cpo/currency', { currency: trimmedCurrency }),
      api.patch('/cpo/member-identifier', { member_identifier: memberIdentifier }),
      api.patch('/cpo/default-grace-period', { default_grace_period_minutes: defaultGracePeriod }),
      api.patch('/cpo/language', { language: language || null }),
    ]);
    setTeamSettingsSaving(false);

    if (nameResult.status === 'rejected') setTeamNameError(translateApiError(nameResult.reason, t));
    if (currencyResult.status === 'rejected') setCurrencyError(translateApiError(currencyResult.reason, t));
    if (identifierResult.status === 'rejected') setMemberIdentifierError(translateApiError(identifierResult.reason, t));
    if (gracePeriodResult.status === 'rejected') setDefaultGracePeriodError(translateApiError(gracePeriodResult.reason, t));
    if (languageResult.status === 'rejected') {
      setLanguageError(translateApiError(languageResult.reason, t));
    } else {
      // Flip the UI straight away — unlike the password form below, changing
      // the language does not sign anybody out.
      i18n.changeLanguage(applyAccountLanguage(language || null));
    }
    if (nameResult.status === 'fulfilled'
        && currencyResult.status === 'fulfilled'
        && identifierResult.status === 'fulfilled'
        && gracePeriodResult.status === 'fulfilled'
        && languageResult.status === 'fulfilled') {
      setTeamSettingsSuccess(t('settings.saved'));
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setClientError('');
    setServerError('');

    if (newPassword.length < 8) {
      setClientError(t('errors.newPasswordTooShort'));
      return;
    }
    if (newPassword !== confirmPassword) {
      setClientError(t('errors.newPasswordMismatch'));
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/cpo/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      // Old cookie is revoked server-side (token_version bump); clear it client-side too
      await api.post('/auth/logout').catch(() => {});
      clearAuth();
      navigate('/login', { replace: true });
    } catch (err) {
      setServerError(translateApiError(err, t));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('settings.title')}</h1>
          <p className="page-subtitle">
            {t('settings.subtitle')}
          </p>
        </div>
      </div>

      {clientError && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>{clientError}</div>
      )}
      {serverError && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>{serverError}</div>
      )}

      {/* Team settings */}
      <div style={{ maxWidth: 420, marginBottom: 24 }}>
        <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 12 }}>{t('settings.teamSettings')}</h2>
        <div className="card card-pad">
          <div className="form-group">
            <label className="form-label" htmlFor="team-name-input">{t('settings.teamName')}</label>
            <input
              id="team-name-input"
              className="form-input"
              maxLength={128}
              placeholder={t('settings.teamNamePlaceholder')}
              value={teamName}
              onChange={e => { markEdited('teamName'); setTeamName(e.target.value); setTeamSettingsSuccess(''); setTeamNameError(''); }}
            />
            {teamNameError && (
              <div className="alert alert-error text-xs" style={{ marginTop: 6 }}>{teamNameError}</div>
            )}
          </div>
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label className="form-label" htmlFor="currency-input">{t('settings.currency')}</label>
            <input
              id="currency-input"
              className="form-input"
              maxLength={10}
              placeholder="CHF"
              value={currency}
              onChange={e => { markEdited('currency'); setCurrency(e.target.value); setTeamSettingsSuccess(''); setCurrencyError(''); }}
              style={{ maxWidth: 120 }}
            />
            {currencyError && (
              <div className="alert alert-error text-xs" style={{ marginTop: 6 }}>{currencyError}</div>
            )}
          </div>
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label className="form-label" htmlFor="member-identifier-input">
              {t('settings.identifierLabel')}
            </label>
            <select
              id="member-identifier-input"
              className="form-input"
              value={memberIdentifier}
              onChange={e => {
                markEdited('memberIdentifier');
                setMemberIdentifier(e.target.value);
                setTeamSettingsSuccess('');
                setMemberIdentifierError('');
              }}
              style={{ maxWidth: 220 }}
            >
              <option value="name">{t('settings.identifierName')}</option>
              <option value="email">{t('settings.identifierEmail')}</option>
            </select>
            <p className="text-xs text-soft" style={{ marginTop: 6 }}>
              {t('settings.identifierHint')}
            </p>
            {memberIdentifierError && (
              <div className="alert alert-error text-xs" style={{ marginTop: 6 }}>{memberIdentifierError}</div>
            )}
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <span className="form-label" style={{ display: 'block', marginBottom: 5 }}>
              {t('settings.defaultGracePeriod')}
            </span>
            <div className="row" style={{ gap: 6 }}>
              <button
                type="button" className="btn"
                style={{ padding: '6px 12px' }}
                onClick={() => {
                  markEdited('defaultGracePeriod');
                  setDefaultGracePeriod(g => Math.max(0, g - 1));
                  setTeamSettingsSuccess('');
                  setDefaultGracePeriodError('');
                }}
              >−</button>
              <span className="mono" style={{ minWidth: 28, textAlign: 'center', fontWeight: 600, fontSize: 16 }}>
                {defaultGracePeriod}
              </span>
              <button
                type="button" className="btn"
                style={{ padding: '6px 12px' }}
                onClick={() => {
                  markEdited('defaultGracePeriod');
                  setDefaultGracePeriod(g => g + 1);
                  setTeamSettingsSuccess('');
                  setDefaultGracePeriodError('');
                }}
              >+</button>
              <span className="text-soft text-sm">{t('session.minutesShort')}</span>
            </div>
            <p className="text-xs text-soft" style={{ marginTop: 6 }}>
              {t('settings.defaultGracePeriodHint')}
            </p>
            {defaultGracePeriodError && (
              <div className="alert alert-error text-xs" style={{ marginTop: 6 }}>{defaultGracePeriodError}</div>
            )}
          </div>
        </div>

        {/* Personal preferences — stored on this login, not on the team */}
        <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, margin: '20px 0 12px' }}>
          {t('settings.preferences')}
        </h2>
        <div className="card card-pad">
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" htmlFor="language-input">{t('common.language')}</label>
            <select
              id="language-input"
              className="form-input"
              value={language}
              onChange={e => {
                markEdited('language');
                setLanguage(e.target.value);
                setTeamSettingsSuccess('');
                setLanguageError('');
              }}
              style={{ maxWidth: 220 }}
            >
              <option value={BROWSER_LANGUAGE}>{t('settings.followBrowser')}</option>
              {LOCALES.map(({ tag, label }) => (
                <option key={tag} value={tag}>{label}</option>
              ))}
            </select>
            <p className="text-xs text-soft" style={{ marginTop: 6 }}>
              {t('settings.languageHint')}
            </p>
            {languageError && (
              <div className="alert alert-error text-xs" style={{ marginTop: 6 }}>{languageError}</div>
            )}
          </div>
        </div>

        <div className="row" style={{ justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginTop: 12 }}>
          {teamSettingsSuccess && (
            <span className="text-sm" style={{ color: 'var(--color-accent)' }}>{teamSettingsSuccess}</span>
          )}
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSaveTeamSettings}
            disabled={teamSettingsSaving || !teamName.trim() || !currency.trim()}
          >
            {teamSettingsSaving ? t('common.saving') : t('common.save')}
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} style={{ maxWidth: 420 }}>
        <div className="card card-pad" style={{ marginBottom: 16 }}>
          <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 4 }}>
            {t('settings.changePassword')}
          </h2>
          {/* The logout warning belongs here, not in the page subtitle: saving the
              cards above (team settings, language) keeps you signed in. */}
          <p className="text-xs text-soft" style={{ marginBottom: 12 }}>
            {t('settings.passwordNote')}
          </p>
          <div className="form-group">
            <label className="form-label" htmlFor="cp-current">{t('settings.currentPassword')}</label>
            <input
              id="cp-current"
              className="form-input"
              type="password"
              required
              value={currentPassword}
              onChange={e => setCurrentPassword(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="cp-new">{t('settings.newPassword')}</label>
            <input
              id="cp-new"
              className="form-input"
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              placeholder={t('settings.passwordHint')}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="cp-confirm">{t('settings.confirmPassword')}</label>
            <input
              id="cp-confirm"
              className="form-input"
              type="password"
              required
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
            />
          </div>
        </div>

        <div className="row" style={{ gap: 8, justifyContent: 'flex-end' }}>
          <button
            type="button"
            className="btn"
            onClick={() => navigate('/dashboard')}
          >
            {t('common.cancel')}
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting}
          >
            {submitting ? t('common.saving') : t('settings.changePassword')}
          </button>
        </div>
      </form>
    </div>
  );
}
