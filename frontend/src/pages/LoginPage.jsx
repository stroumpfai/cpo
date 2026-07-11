import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { setAuth } from '../utils/auth.js';

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await api.post('/auth/login', { username, password });
      setAuth(data.role, data.expires_in);
      navigate(data.role === 'admin' ? '/admin' : '/dashboard', { replace: true });
    } catch (err) {
      setError(err.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-logo">🍕 CPO</div>
        <div className="login-tagline">Chief Pizza Officer · sign in</div>

        {error && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="col" style={{ gap: 14 }}>
          <div className="form-group">
            <label className="form-label" htmlFor="username">Username</label>
            <input
              id="username"
              className="form-input"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <input
              id="password"
              className="form-input"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-full"
            style={{ marginTop: 4 }}
            disabled={loading}
          >
            {loading ? 'Signing in…' : 'Log in'}
          </button>
        </form>
      </div>
    </div>
  );
}
