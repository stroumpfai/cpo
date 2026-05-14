import { useNavigate } from 'react-router-dom';
import { removeToken } from '../utils/auth.js';
import { api } from '../api.js';

export function AdminPanel() {
  const navigate = useNavigate();

  function logout() {
    api.post('/auth/logout').catch(() => {});
    removeToken();
    navigate('/login', { replace: true });
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-surface)' }}>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 32px',
        background: 'var(--color-bg)',
        borderBottom: '1px solid var(--color-border)',
      }}>
        <span style={{ fontWeight: 700, fontSize: 'var(--font-size-lg)' }}>
          🍕 CPO · Admin
        </span>
        <button className="btn btn-ghost" onClick={logout}>Log out</button>
      </header>

      <div style={{ padding: 32 }}>
        <div className="page-header">
          <div>
            <h1 className="page-title">Admin Panel</h1>
            <p className="page-subtitle">Manage CPO accounts</p>
          </div>
        </div>
        {/* Implemented in Phase 8 */}
        <div className="card card-pad text-soft text-sm">
          CPO account management — coming in Phase 8.
        </div>
      </div>
    </div>
  );
}
