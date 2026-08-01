import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api.js';
import { setAuth } from '../utils/auth.js';

export function JoinPage() {
  const { token } = useParams();
  const navigate = useNavigate();

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
        ? 'This invite link is invalid, expired, or has already been used.'
        : err.message))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Password and confirmation do not match.');
      return;
    }

    setSubmitting(true);
    try {
      const data = await api.post(`/join/${token}`, { username, email, password });
      setAuth(data.role, data.expires_in);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err.message || 'Could not join the team.');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="login-shell">
        <div className="login-card"><span className="text-soft">Loading…</span></div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="login-shell">
        <div className="login-card">
          <div className="login-logo">🍕 CPO</div>
          <div className="alert alert-error">{loadError}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-logo">🍕 CPO</div>
        <div className="login-tagline">Join &quot;{teamName}&quot;</div>

        {error && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="col" style={{ gap: 14 }}>
          <div className="form-group">
            <label className="form-label" htmlFor="join-username">Username</label>
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
            <label className="form-label" htmlFor="join-email">Email</label>
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
            <label className="form-label" htmlFor="join-password">Password</label>
            <input
              id="join-password"
              className="form-input"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              placeholder="Min 8 chars, not a common password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="join-confirm">Confirm password</label>
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
            {submitting ? 'Joining…' : 'Join team'}
          </button>
        </form>
      </div>
    </div>
  );
}
