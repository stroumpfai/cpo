import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { clearAuth } from '../utils/auth.js';

const EMPTY_CREATE = { username: '', email: '', team_name: '', initial_password: '' };
const EMPTY_ADMIN_CREATE = { username: '', initial_password: '' };
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

  // Administrators
  const [admins, setAdmins]                     = useState([]);
  const [showAdminCreate, setShowAdminCreate]   = useState(false);
  const [adminCreateForm, setAdminCreateForm]   = useState(EMPTY_ADMIN_CREATE);
  const [adminCreateError, setAdminCreateError] = useState('');
  const [adminCreating, setAdminCreating]       = useState(false);
  const [adminResetingId, setAdminResetingId]   = useState(null);
  const [adminNewPassword, setAdminNewPassword] = useState('');
  const [adminResetError, setAdminResetError]   = useState('');

  // Change my password
  const [pwCurrent, setPwCurrent]         = useState('');
  const [pwNew, setPwNew]                 = useState('');
  const [pwConfirm, setPwConfirm]         = useState('');
  const [pwClientError, setPwClientError] = useState('');
  const [pwServerError, setPwServerError] = useState('');
  const [pwSubmitting, setPwSubmitting]   = useState(false);

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

  async function loadAdmins() {
    try {
      setAdmins(await api.get('/admin/admins'));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { loadCpos(); loadAdmins(); }, []);

  async function logout() {
    // Await so the Set-Cookie clearing the session is processed before navigating
    await api.post('/auth/logout').catch(() => {});
    clearAuth();
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

  // ── Administrators ────────────────────────────────────────────────────────
  async function handleAdminCreate(e) {
    e.preventDefault();
    setAdminCreateError('');
    setAdminCreating(true);
    try {
      await api.post('/admin/admins', adminCreateForm);
      setAdminCreateForm(EMPTY_ADMIN_CREATE);
      setShowAdminCreate(false);
      loadAdmins();
    } catch (err) {
      setAdminCreateError(err.message);
    } finally {
      setAdminCreating(false);
    }
  }

  function setAdminField(key, val) {
    setAdminCreateForm(f => ({ ...f, [key]: val }));
  }

  async function handleAdminDelete(admin) {
    if (!globalThis.confirm(`Delete admin account "${admin.username}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/admin/admins/${admin.id}`);
      loadAdmins();
    } catch (err) {
      setError(err.message);
    }
  }

  function startAdminReset(id) {
    setAdminResetingId(id);
    setAdminNewPassword('');
    setAdminResetError('');
  }

  function cancelAdminReset() {
    setAdminResetingId(null);
    setAdminNewPassword('');
    setAdminResetError('');
  }

  async function handleAdminResetPassword(adminId) {
    setAdminResetError('');
    try {
      await api.post(`/admin/admins/${adminId}/reset-password`, { new_password: adminNewPassword });
      setAdminResetingId(null);
      setAdminNewPassword('');
    } catch (err) {
      setAdminResetError(err.message);
    }
  }

  // ── Change my password ────────────────────────────────────────────────────
  async function handleChangePassword(e) {
    e.preventDefault();
    setPwClientError('');
    setPwServerError('');

    if (pwNew.length < 8) {
      setPwClientError('New password must be at least 8 characters.');
      return;
    }
    if (pwNew !== pwConfirm) {
      setPwClientError('New password and confirmation do not match.');
      return;
    }

    setPwSubmitting(true);
    try {
      await api.post('/admin/change-password', {
        current_password: pwCurrent,
        new_password: pwNew,
      });
      // Old cookie is revoked server-side (token_version bump); clear it client-side too
      await api.post('/auth/logout').catch(() => {});
      clearAuth();
      navigate('/login', { replace: true });
    } catch (err) {
      setPwServerError(err.message);
    } finally {
      setPwSubmitting(false);
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
                    placeholder="Min 8 chars, not a common password"
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
                                placeholder="Min 8 chars — not common, not username"
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

        {/* ── Administrators ───────────────────────────────────────────────── */}
        <div className="page-header" style={{ marginTop: 40 }}>
          <div>
            <h2 className="page-title" style={{ fontSize: 'var(--font-size-lg)' }}>Administrators</h2>
            <p className="page-subtitle">Manage admin accounts</p>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => { setShowAdminCreate(s => !s); setAdminCreateError(''); }}
          >
            {showAdminCreate ? 'Cancel' : '+ Create admin'}
          </button>
        </div>

        {showAdminCreate && (
          <div className="card card-pad" style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 16 }}>
              New admin account
            </h2>
            {adminCreateError && (
              <div className="alert alert-error" style={{ marginBottom: 12 }}>{adminCreateError}</div>
            )}
            <form onSubmit={handleAdminCreate}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="adm-username">Username</label>
                  <input id="adm-username" className="form-input" required
                    value={adminCreateForm.username}
                    onChange={e => setAdminField('username', e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="adm-pw">Initial password</label>
                  <input id="adm-pw" className="form-input" type="password" required minLength={8}
                    placeholder="Min 8 chars, not a common password"
                    value={adminCreateForm.initial_password}
                    onChange={e => setAdminField('initial_password', e.target.value)} />
                </div>
              </div>
              <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                <button type="button" className="btn"
                  onClick={() => { setShowAdminCreate(false); setAdminCreateError(''); }}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={adminCreating}>
                  {adminCreating ? 'Creating…' : 'Create admin'}
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="card table-scroll">
          {admins.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {admins.map(admin => {
                  const isReseting = adminResetingId === admin.id;

                  return (
                    <tr key={admin.id}>
                      <td style={{ fontWeight: 500 }}>
                        {admin.username}
                        {admin.is_self && <span className="text-soft"> (you)</span>}
                      </td>
                      <td className="text-soft">
                        {new Date(admin.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        {isReseting && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            <div className="row" style={{ gap: 6 }}>
                              <input
                                className="form-input" type="password"
                                placeholder="Min 8 chars — not common, not username"
                                minLength={8} value={adminNewPassword}
                                onChange={e => setAdminNewPassword(e.target.value)}
                                style={{ width: 210 }}
                                autoFocus
                              />
                              <button className="btn btn-primary" style={BTN_SM}
                                onClick={() => handleAdminResetPassword(admin.id)}
                                disabled={adminNewPassword.length < 8}>Save</button>
                              <button className="btn btn-ghost" style={BTN_SM}
                                onClick={cancelAdminReset}>Cancel</button>
                            </div>
                            {adminResetError && (
                              <div className="alert alert-error text-xs">{adminResetError}</div>
                            )}
                          </div>
                        )}

                        {!isReseting && !admin.is_self && (
                          <div className="row" style={{ gap: 6 }}>
                            <button className="btn btn-ghost" style={BTN_SM}
                              onClick={() => startAdminReset(admin.id)}>reset pw</button>
                            {admins.length > 1 && (
                              <button
                                className="btn btn-ghost"
                                style={{ ...BTN_SM, color: 'var(--color-accent)' }}
                                onClick={() => handleAdminDelete(admin)}>✕ delete</button>
                            )}
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

        {/* ── Change my password ───────────────────────────────────────────── */}
        <div className="page-header" style={{ marginTop: 40 }}>
          <div>
            <h2 className="page-title" style={{ fontSize: 'var(--font-size-lg)' }}>Change my password</h2>
            <p className="page-subtitle">
              After saving, you will be logged out and must sign in again.
            </p>
          </div>
        </div>

        {pwClientError && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>{pwClientError}</div>
        )}
        {pwServerError && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>{pwServerError}</div>
        )}

        <form onSubmit={handleChangePassword} style={{ maxWidth: 420 }}>
          <div className="card card-pad" style={{ marginBottom: 16 }}>
            <div className="form-group">
              <label className="form-label" htmlFor="cp-current">Current password</label>
              <input
                id="cp-current"
                className="form-input"
                type="password"
                required
                value={pwCurrent}
                onChange={e => setPwCurrent(e.target.value)}
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
                value={pwNew}
                onChange={e => setPwNew(e.target.value)}
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
                value={pwConfirm}
                onChange={e => setPwConfirm(e.target.value)}
              />
            </div>
          </div>

          <div className="row" style={{ gap: 8, justifyContent: 'flex-end' }}>
            <button type="submit" className="btn btn-primary" disabled={pwSubmitting}>
              {pwSubmitting ? 'Saving…' : 'Change password'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
