import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { clearAuth } from '../utils/auth.js';

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

  const [teamSettingsSaving, setTeamSettingsSaving] = useState(false);
  const [teamSettingsSuccess, setTeamSettingsSuccess] = useState('');

  const navigate = useNavigate();

  useEffect(() => {
    api.get('/cpo/me').then(cpo => {
      setCurrency(cpo.currency ?? 'CHF');
      setTeamName(cpo.team_name ?? '');
      setMemberIdentifier(cpo.member_identifier ?? 'name');
    }).catch(() => {});
  }, []);

  async function handleSaveTeamSettings() {
    const trimmedName = teamName.trim();
    const trimmedCurrency = currency.trim();
    setTeamNameError('');
    setCurrencyError('');
    setMemberIdentifierError('');
    setTeamSettingsSuccess('');

    if (!trimmedName) { setTeamNameError('Team name cannot be empty.'); return; }
    if (!trimmedCurrency) { setCurrencyError('Currency cannot be empty.'); return; }

    setTeamSettingsSaving(true);
    const [nameResult, currencyResult, identifierResult] = await Promise.allSettled([
      api.patch('/cpo/team-name', { team_name: trimmedName }),
      api.patch('/cpo/currency', { currency: trimmedCurrency }),
      api.patch('/cpo/member-identifier', { member_identifier: memberIdentifier }),
    ]);
    setTeamSettingsSaving(false);

    if (nameResult.status === 'rejected') setTeamNameError(nameResult.reason.message);
    if (currencyResult.status === 'rejected') setCurrencyError(currencyResult.reason.message);
    if (identifierResult.status === 'rejected') setMemberIdentifierError(identifierResult.reason.message);
    if (nameResult.status === 'fulfilled'
        && currencyResult.status === 'fulfilled'
        && identifierResult.status === 'fulfilled') {
      setTeamSettingsSuccess('Saved.');
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setClientError('');
    setServerError('');

    if (newPassword.length < 8) {
      setClientError('New password must be at least 8 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setClientError('New password and confirmation do not match.');
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
      setServerError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">
            Manage your account settings. After saving, you will be logged out and must sign in again.
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
        <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 12 }}>Team settings</h2>
        <div className="card card-pad">
          <div className="form-group">
            <label className="form-label" htmlFor="team-name-input">Team name</label>
            <input
              id="team-name-input"
              className="form-input"
              maxLength={128}
              placeholder="e.g. Engineering"
              value={teamName}
              onChange={e => { setTeamName(e.target.value); setTeamSettingsSuccess(''); setTeamNameError(''); }}
            />
            {teamNameError && (
              <div className="alert alert-error text-xs" style={{ marginTop: 6 }}>{teamNameError}</div>
            )}
          </div>
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label className="form-label" htmlFor="currency-input">Currency unit</label>
            <input
              id="currency-input"
              className="form-input"
              maxLength={10}
              placeholder="CHF"
              value={currency}
              onChange={e => { setCurrency(e.target.value); setTeamSettingsSuccess(''); setCurrencyError(''); }}
              style={{ maxWidth: 120 }}
            />
            {currencyError && (
              <div className="alert alert-error text-xs" style={{ marginTop: 6 }}>{currencyError}</div>
            )}
          </div>
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label className="form-label" htmlFor="member-identifier-input">
              Team members identify themselves by
            </label>
            <select
              id="member-identifier-input"
              className="form-input"
              value={memberIdentifier}
              onChange={e => {
                setMemberIdentifier(e.target.value);
                setTeamSettingsSuccess('');
                setMemberIdentifierError('');
              }}
              style={{ maxWidth: 220 }}
            >
              <option value="name">Name</option>
              <option value="email">Email address</option>
            </select>
            <p className="text-xs text-soft" style={{ marginTop: 6 }}>
              Pick “Email address” if you notify your team by email after delivery.
              Applies to new orders only — orders already submitted keep the value
              they were entered with.
            </p>
            {memberIdentifierError && (
              <div className="alert alert-error text-xs" style={{ marginTop: 6 }}>{memberIdentifierError}</div>
            )}
          </div>
          <div className="row" style={{ justifyContent: 'flex-end', alignItems: 'center', gap: 12 }}>
            {teamSettingsSuccess && (
              <span className="text-sm" style={{ color: 'var(--color-accent)' }}>{teamSettingsSuccess}</span>
            )}
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSaveTeamSettings}
              disabled={teamSettingsSaving || !teamName.trim() || !currency.trim()}
            >
              {teamSettingsSaving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} style={{ maxWidth: 420 }}>
        <div className="card card-pad" style={{ marginBottom: 16 }}>
          <div className="form-group">
            <label className="form-label" htmlFor="cp-current">Current password</label>
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
            <label className="form-label" htmlFor="cp-new">New password</label>
            <input
              id="cp-new"
              className="form-input"
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              placeholder="Min 8 chars, not a common password"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="cp-confirm">Confirm new password</label>
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
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting}
          >
            {submitting ? 'Saving…' : 'Change password'}
          </button>
        </div>
      </form>
    </div>
  );
}
