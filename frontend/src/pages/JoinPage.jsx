import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '../api.js';
import { LanguageSwitcher } from '../components/LanguageSwitcher.jsx';
import { translateApiError } from '../i18n/apiError.js';
import { setAuth } from '../utils/auth.js';

export function JoinPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [teamName, setTeamName] = useState('');
  const [loading, setLoading]   = useState(true);
  const [loadError, setLoadError] = useState('');

  const [username, setUsername] = useState('');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm]   = useState('');
  const [error, setError]       = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get(`/join/${token}`)
      .then(data => setTeamName(data.team_name))
      .catch(err => setLoadError(err.status === 404
        ? t('order.join.invalidInvite')
        : translateApiError(err, t)))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError(t('errors.passwordTooShort'));
      return;
    }
    if (password !== confirm) {
      setError(t('errors.passwordMismatch'));
      return;
    }

    setSubmitting(true);
    try {
      const data = await api.post(`/join/${token}`, { username, email, password });
      setAuth(data.role, data.expires_in);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      // translateApiError already ends at errors.generic when the body carries
      // neither a code nor a message, so there is nothing left to fall back to.
      setError(translateApiError(err, t));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="login-shell">
        <div className="login-card"><span className="text-soft">{t('common.loading')}</span></div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="login-shell">
        <div className="login-card">
          <div className="login-logo">🍕 CPO</div>
          <div className="alert alert-error">{loadError}</div>
          <div className="row" style={{ justifyContent: 'center', marginTop: 16 }}>
            <LanguageSwitcher />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-logo">🍕 CPO</div>
        <div className="login-tagline">{t('order.join.title', { team: teamName })}</div>

        {error && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="col" style={{ gap: 14 }}>
          <div className="form-group">
            <label className="form-label" htmlFor="join-username">{t('order.join.username')}</label>
            <input
              id="join-username"
              className="form-input"
              type="text"
              autoComplete="username"
              required
              maxLength={64}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="join-email">{t('order.join.email')}</label>
            <input
              id="join-email"
              className="form-input"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="join-password">{t('order.join.password')}</label>
            <input
              id="join-password"
              className="form-input"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              placeholder={t('order.join.passwordHint')}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="join-confirm">{t('order.join.confirmPassword')}</label>
            <input
              id="join-confirm"
              className="form-input"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-full"
            style={{ marginTop: 4 }}
            disabled={submitting}
          >
            {t(submitting ? 'order.join.submitting' : 'order.join.submit')}
          </button>
        </form>

        <div className="row" style={{ justifyContent: 'center', marginTop: 16 }}>
          <LanguageSwitcher />
        </div>
      </div>
    </div>
  );
}
