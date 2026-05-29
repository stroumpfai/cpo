import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { removeToken } from '../utils/auth.js';

export function CPOSettings() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [clientError, setClientError] = useState('');
  const [serverError, setServerError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

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
      removeToken();
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
