import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { removeToken } from '../utils/auth.js';

const EMPTY_CREATE = { username: '', email: '', team_name: '', initial_password: '' };
const BTN_SM = { fontSize: 'var(--font-size-xs)', padding: '3px 10px' };

export function AdminPanel() {
  const [cpos, setCpos]             = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_CREATE);
  const [createError, setCreateError] = useState('');
  const [creating, setCreating]     = useState(false);

  // Inline edit (email + team_name)
  const [editingId, setEditingId]   = useState(null);
  const [editEmail, setEditEmail]   = useState('');
  const [editTeam, setEditTeam]     = useState('');
  const [editError, setEditError]   = useState('');

  // Password reset
  const [resetingId, setResetingId] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [resetError, setResetError] = useState('');

  const navigate = useNavigate();

  // ── Data loading ─────────────────────────────────────────────────────────
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

  // ── Create ────────────────────────────────────────────────────────────────
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

  function setField(key, val) {
    setCreateForm(f => ({ ...f, [key]: val }));
  }

  // ── Edit (email + team_name) ──────────────────────────────────────────────
  function startEdit(cpo) {
    setEditingId(cpo.id);
    setEditEmail(cpo.email);
    setEditTeam(cpo.team_name);
    setEditError('');
    cancelReset();
  }

  function cancelEdit() {
    setEditingId(null);
    setEditError('');
  }

  async function handleEdit(cpoId) {
    setEditError('');
    try {
      await api.put(`/admin/cpos/${cpoId}`, { email: editEmail, team_name: editTeam });
      setEditingId(null);
      loadCpos();
    } catch (err) {
      setEditError(err.message);
    }
  }

  // ── Delete ────────────────────────────────────────────────────────────────
  async function handleDelete(cpo) {
    if (!globalThis.confirm(`Delete CPO account "${cpo.username}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/admin/cpos/${cpo.id}`);
      loadCpos();
    } catch (err) {
      setError(err.message);
    }
  }

  // ── Password reset ────────────────────────────────────────────────────────
  function startReset(id) {
    setResetingId(id);
    setNewPassword('');
    setResetError('');
    cancelEdit();
  }

  function cancelReset() {
    setResetingId(null);
    setNewPassword('');
    setResetError('');
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

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-surface)' }}>
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

      <div style={{ maxWidth: 960, margin: '0 auto', padding: 32 }}>
        <div className="page-header">
          <div>
            <h1 className="page-title">Admin Panel</h1>
            <p className="page-subtitle">Manage CPO accounts</p>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => { setShowCreate(s => !s); setCreateError(''); }}
          >
            {showCreate ? 'Cancel' : '+ Create CPO'}
          </button>
        </div>

        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

        {/* ── Create form ─────────────────────────────────────────────────── */}
        {showCreate && (
          <div className="card card-pad" style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 16 }}>
              New CPO account
            </h2>
            {createError && (
              <div className="alert alert-error" style={{ marginBottom: 12 }}>{createError}</div>
            )}
            <form onSubmit={handleCreate}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-username">Username</label>
                  <input id="cr-username" className="form-input" required
                    value={createForm.username} onChange={e => setField('username', e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-email">Email</label>
                  <input id="cr-email" className="form-input" type="email" required
                    value={createForm.email} onChange={e => setField('email', e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-team">Team name</label>
                  <input id="cr-team" className="form-input" required
                    value={createForm.team_name} onChange={e => setField('team_name', e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-pw">Initial password</label>
                  <input id="cr-pw" className="form-input" type="password" required minLength={8}
                    value={createForm.initial_password}
                    onChange={e => setField('initial_password', e.target.value)} />
                </div>
              </div>
              <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                <button type="button" className="btn"
                  onClick={() => { setShowCreate(false); setCreateError(''); }}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={creating}>
                  {creating ? 'Creating…' : 'Create CPO'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ── CPO table ────────────────────────────────────────────────────── */}
        <div className="card table-scroll">
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
                {cpos.map(cpo => {
                  const isEditing  = editingId  === cpo.id;
                  const isReseting = resetingId === cpo.id;

                  return (
                    <tr key={cpo.id}>
                      <td style={{ fontWeight: 500 }}>{cpo.username}</td>

                      {/* Email cell */}
                      <td>
                        {isEditing ? (
                          <input
                            className="form-input" type="email" required
                            value={editEmail}
                            onChange={e => setEditEmail(e.target.value)}
                            autoFocus
                            style={{ width: 200 }}
                          />
                        ) : (
                          <span className="text-soft">{cpo.email}</span>
                        )}
                      </td>

                      {/* Team cell */}
                      <td>
                        {isEditing ? (
                          <input
                            className="form-input" required
                            value={editTeam}
                            onChange={e => setEditTeam(e.target.value)}
                            style={{ width: 160 }}
                          />
                        ) : (
                          cpo.team_name
                        )}
                      </td>

                      {/* Actions cell */}
                      <td>
                        {isEditing && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            <div className="row" style={{ gap: 6 }}>
                              <button className="btn btn-primary" style={BTN_SM}
                                onClick={() => handleEdit(cpo.id)}
                                disabled={!editEmail.trim() || !editTeam.trim()}>
                                Save
                              </button>
                              <button className="btn btn-ghost" style={BTN_SM}
                                onClick={cancelEdit}>Cancel</button>
                            </div>
                            {editError && (
                              <div className="alert alert-error text-xs">{editError}</div>
                            )}
                          </div>
                        )}

                        {isReseting && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            <div className="row" style={{ gap: 6 }}>
                              <input
                                className="form-input" type="password"
                                placeholder="New password (min 8 chars)"
                                minLength={8} value={newPassword}
                                onChange={e => setNewPassword(e.target.value)}
                                style={{ width: 210 }}
                                autoFocus
                              />
                              <button className="btn btn-primary" style={BTN_SM}
                                onClick={() => handleResetPassword(cpo.id)}
                                disabled={newPassword.length < 8}>Save</button>
                              <button className="btn btn-ghost" style={BTN_SM}
                                onClick={cancelReset}>Cancel</button>
                            </div>
                            {resetError && (
                              <div className="alert alert-error text-xs">{resetError}</div>
                            )}
                          </div>
                        )}

                        {!isEditing && !isReseting && (
                          <div className="row" style={{ gap: 6 }}>
                            <button className="btn btn-ghost" style={BTN_SM}
                              onClick={() => startEdit(cpo)}>✎ edit</button>
                            <button className="btn btn-ghost" style={BTN_SM}
                              onClick={() => startReset(cpo.id)}>reset pw</button>
                            <button
                              className="btn btn-ghost"
                              style={{ ...BTN_SM, color: 'var(--color-accent)' }}
                              onClick={() => handleDelete(cpo)}>✕ delete</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
