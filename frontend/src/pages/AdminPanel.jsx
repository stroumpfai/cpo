import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { removeToken } from '../utils/auth.js';

const EMPTY_CREATE = { username: '', email: '', team_name: '', initial_password: '' };

export function AdminPanel() {
  const [cpos, setCpos]           = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_CREATE);
  const [createError, setCreateError] = useState('');
  const [creating, setCreating]   = useState(false);
  const [resetingId, setResetingId] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [resetError, setResetError] = useState('');
  const navigate = useNavigate();

  async function loadCpos() {
    try {
      setCpos(await api.get('/admin/cpos'));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadCpos(); }, []);

  function logout() {
    api.post('/auth/logout').catch(() => {});
    removeToken();
    navigate('/login', { replace: true });
  }

  async function handleCreate(e) {
    e.preventDefault();
    setCreateError('');
    setCreating(true);
    try {
      await api.post('/admin/cpos', createForm);
      setCreateForm(EMPTY_CREATE);
      setShowCreate(false);
      loadCpos();
    } catch (err) {
      setCreateError(err.message);
    } finally {
      setCreating(false);
    }
  }

  async function handleResetPassword(cpoId) {
    setResetError('');
    try {
      await api.post(`/admin/cpos/${cpoId}/reset-password`, { new_password: newPassword });
      setResetingId(null);
      setNewPassword('');
    } catch (err) {
      setResetError(err.message);
    }
  }

  function startReset(id) {
    setResetingId(id);
    setNewPassword('');
    setResetError('');
  }

  function cancelReset() {
    setResetingId(null);
    setNewPassword('');
    setResetError('');
  }

  function setField(key, val) {
    setCreateForm(f => ({ ...f, [key]: val }));
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-surface)' }}>
      {/* Header */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 32px',
        background: 'var(--color-bg)',
        borderBottom: '1px solid var(--color-border)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <span style={{ fontWeight: 700, fontSize: 'var(--font-size-lg)' }}>🍕 CPO · Admin</span>
        <button className="btn btn-ghost" onClick={logout}>Log out</button>
      </header>

      <div style={{ maxWidth: 900, margin: '0 auto', padding: 32 }}>
        <div className="page-header">
          <div>
            <h1 className="page-title">Admin Panel</h1>
            <p className="page-subtitle">Manage CPO accounts</p>
          </div>
          <button className="btn btn-primary" onClick={() => { setShowCreate(s => !s); setCreateError(''); }}>
            {showCreate ? 'Cancel' : '+ Create CPO'}
          </button>
        </div>

        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

        {/* Create form */}
        {showCreate && (
          <div className="card card-pad" style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 16 }}>
              New CPO account
            </h2>
            {createError && <div className="alert alert-error" style={{ marginBottom: 12 }}>{createError}</div>}
            <form onSubmit={handleCreate}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-username">Username</label>
                  <input
                    id="cr-username" className="form-input" required
                    value={createForm.username}
                    onChange={e => setField('username', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-email">Email</label>
                  <input
                    id="cr-email" className="form-input" type="email" required
                    value={createForm.email}
                    onChange={e => setField('email', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-team">Team name</label>
                  <input
                    id="cr-team" className="form-input" required
                    value={createForm.team_name}
                    onChange={e => setField('team_name', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-pw">Initial password</label>
                  <input
                    id="cr-pw" className="form-input" type="password" required minLength={8}
                    value={createForm.initial_password}
                    onChange={e => setField('initial_password', e.target.value)}
                  />
                </div>
              </div>
              <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                <button type="button" className="btn" onClick={() => { setShowCreate(false); setCreateError(''); }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={creating}>
                  {creating ? 'Creating…' : 'Create CPO'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* CPO table */}
        <div className="card">
          {loading && <div className="card-pad text-soft text-sm">Loading…</div>}
          {!loading && cpos.length === 0 && (
            <div className="card-pad text-soft text-sm">No CPO accounts yet. Create one above.</div>
          )}
          {!loading && cpos.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Team</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {cpos.map(cpo => (
                  <tr key={cpo.id}>
                    <td style={{ fontWeight: 500 }}>{cpo.username}</td>
                    <td className="text-soft">{cpo.email}</td>
                    <td>{cpo.team_name}</td>
                    <td>
                      {resetingId === cpo.id ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                          <div className="row" style={{ gap: 6 }}>
                            <input
                              className="form-input"
                              type="password"
                              placeholder="New password (min 8 chars)"
                              minLength={8}
                              value={newPassword}
                              onChange={e => setNewPassword(e.target.value)}
                              style={{ width: 220 }}
                              autoFocus
                            />
                            <button
                              className="btn btn-primary"
                              onClick={() => handleResetPassword(cpo.id)}
                              disabled={newPassword.length < 8}
                            >
                              Save
                            </button>
                            <button className="btn btn-ghost" onClick={cancelReset}>Cancel</button>
                          </div>
                          {resetError && (
                            <div className="alert alert-error text-xs">{resetError}</div>
                          )}
                        </div>
                      ) : (
                        <button
                          className="btn btn-ghost"
                          style={{ fontSize: 'var(--font-size-xs)', padding: '4px 10px' }}
                          onClick={() => startReset(cpo.id)}
                        >
                          reset password
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>  {/* .card */}
      </div>
    </div>
  );
}
