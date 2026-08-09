import { Fragment, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '../api.js';
import { clearAuth } from '../utils/auth.js';
import { utcHhmmToLocal } from '../utils/time.js';
import { formatIsoDate } from '../utils/format.js';
import { applyAccountLanguage } from '../i18n/index.js';
import { LOCALES } from '../i18n/locales.js';
import { translateApiError } from '../i18n/apiError.js';
import { VersionLabel } from '../components/VersionLabel.jsx';

const EMPTY_CREATE = { username: '', email: '', team_name: '', initial_password: '' };
const EMPTY_ADMIN_CREATE = { username: '', initial_password: '' };
const BTN_SM = { fontSize: 'var(--font-size-xs)', padding: '3px 10px' };

// The select needs a string for "no preference"; the API wants null.
const FOLLOW_BROWSER = '';

export function AdminPanel() {
  const [teams, setTeams]           = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');

  // Usage stats (per-team, admin view only)
  const [stats, setStats]           = useState({});
  const [expandedIds, setExpandedIds] = useState(() => new Set());

  // Create form (creates a new team + its first CPO login)
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_CREATE);
  const [createError, setCreateError] = useState('');
  const [creating, setCreating]     = useState(false);

  // Inline edit: team name (team-scoped)
  const [editingTeamId, setEditingTeamId] = useState(null);
  const [editTeamName, setEditTeamName]   = useState('');
  const [editTeamError, setEditTeamError] = useState('');

  // Inline edit: member email (login-scoped)
  const [editingMemberId, setEditingMemberId] = useState(null);
  const [editEmail, setEditEmail]             = useState('');
  const [editError, setEditError]             = useState('');

  // Password reset (login-scoped)
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

  // My account — language preference
  const [language, setLanguage]             = useState(FOLLOW_BROWSER);
  const [languageError, setLanguageError]   = useState('');
  const [languageSaving, setLanguageSaving] = useState(false);

  // My account — change password
  const [pwCurrent, setPwCurrent]         = useState('');
  const [pwNew, setPwNew]                 = useState('');
  const [pwConfirm, setPwConfirm]         = useState('');
  const [pwClientError, setPwClientError] = useState('');
  const [pwServerError, setPwServerError] = useState('');
  const [pwSubmitting, setPwSubmitting]   = useState(false);

  const navigate = useNavigate();
  const { t, i18n } = useTranslation();

  // ── Data loading ─────────────────────────────────────────────────────────
  async function loadTeams() {
    try {
      setTeams(await api.get('/admin/cpos'));
    } catch (err) {
      setError(translateApiError(err, t));
    } finally {
      setLoading(false);
    }
  }

  async function loadAdmins() {
    try {
      setAdmins(await api.get('/admin/admins'));
    } catch (err) {
      setError(translateApiError(err, t));
    }
  }

  async function loadStats() {
    try {
      const list = await api.get('/admin/stats');
      setStats(Object.fromEntries(list.map(s => [s.team_id, s])));
    } catch (err) {
      setError(translateApiError(err, t));
    }
  }

  async function loadProfile() {
    try {
      const me = await api.get('/admin/me');
      setLanguage(me?.language ?? FOLLOW_BROWSER);
      // An explicit account preference applies on whatever browser the admin
      // logged in from — that is the point of storing it server-side. A null
      // preference means "follow my browser", so nothing is forced here.
      if (me?.language) applyAccountLanguage(me.language);
    } catch (err) {
      setError(translateApiError(err, t));
    }
  }

  useEffect(() => { loadTeams(); loadAdmins(); loadStats(); loadProfile(); }, []);

  function toggleExpand(id) {
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function logout() {
    // Await so the Set-Cookie clearing the session is processed before navigating
    await api.post('/auth/logout').catch(() => {});
    clearAuth();
    navigate('/login', { replace: true });
  }

  // ── Create team ──────────────────────────────────────────────────────────
  async function handleCreate(e) {
    e.preventDefault();
    setCreateError('');
    setCreating(true);
    try {
      await api.post('/admin/cpos', createForm);
      setCreateForm(EMPTY_CREATE);
      setShowCreate(false);
      loadTeams();
    } catch (err) {
      setCreateError(translateApiError(err, t));
    } finally {
      setCreating(false);
    }
  }

  function setField(key, val) {
    setCreateForm(f => ({ ...f, [key]: val }));
  }

  // ── Edit team name ───────────────────────────────────────────────────────
  function startEditTeam(team) {
    setEditingTeamId(team.team_id);
    setEditTeamName(team.team_name);
    setEditTeamError('');
    cancelEditMember();
    cancelReset();
  }

  function cancelEditTeam() {
    setEditingTeamId(null);
    setEditTeamError('');
  }

  async function handleEditTeam(teamId) {
    setEditTeamError('');
    try {
      await api.put(`/admin/teams/${teamId}`, { team_name: editTeamName });
      setEditingTeamId(null);
      loadTeams();
    } catch (err) {
      setEditTeamError(translateApiError(err, t));
    }
  }

  // ── Edit member email ────────────────────────────────────────────────────
  function startEditMember(member) {
    setEditingMemberId(member.id);
    setEditEmail(member.email);
    setEditError('');
    cancelEditTeam();
    cancelReset();
  }

  function cancelEditMember() {
    setEditingMemberId(null);
    setEditError('');
  }

  async function handleEditMember(memberId) {
    setEditError('');
    try {
      await api.put(`/admin/cpos/${memberId}`, { email: editEmail });
      setEditingMemberId(null);
      loadTeams();
    } catch (err) {
      setEditError(translateApiError(err, t));
    }
  }

  // ── Delete member (deletes the team too if it's the last one) ──────────────
  async function handleDeleteMember(team, member) {
    const isLast = team.members.length <= 1;
    const message = isLast
      ? t('admin.confirmDeleteLastMember', { username: member.username, team: team.team_name })
      : t('admin.confirmDeleteMember', { username: member.username });
    if (!globalThis.confirm(message)) return;
    try {
      await api.delete(`/admin/cpos/${member.id}`);
      loadTeams();
      loadStats();
    } catch (err) {
      setError(translateApiError(err, t));
    }
  }

  // ── Password reset (login-scoped) ───────────────────────────────────────
  function startReset(id) {
    setResetingId(id);
    setNewPassword('');
    setResetError('');
    cancelEditTeam();
    cancelEditMember();
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
      setResetError(translateApiError(err, t));
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
      setAdminCreateError(translateApiError(err, t));
    } finally {
      setAdminCreating(false);
    }
  }

  function setAdminField(key, val) {
    setAdminCreateForm(f => ({ ...f, [key]: val }));
  }

  async function handleAdminDelete(admin) {
    if (!globalThis.confirm(t('admin.confirmDeleteAdmin', { username: admin.username }))) return;
    try {
      await api.delete(`/admin/admins/${admin.id}`);
      loadAdmins();
    } catch (err) {
      setError(translateApiError(err, t));
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
      setAdminResetError(translateApiError(err, t));
    }
  }

  // ── My account: language ──────────────────────────────────────────────────
  async function handleLanguageChange(e) {
    const picked   = e.target.value;
    const previous = language;
    setLanguage(picked);
    setLanguageError('');
    setLanguageSaving(true);
    try {
      // "" → null: the account follows the browser again.
      await api.patch('/admin/language', { language: picked || null });
      // Writes the localStorage mirror and switches the app-wide instance. That
      // instance is the one behind useTranslation() in the app but not in tests,
      // so the context instance is flipped explicitly too. No logout: unlike a
      // password change, this leaves the session untouched.
      const active = applyAccountLanguage(picked || null);
      if (i18n.language !== active) i18n.changeLanguage(active);
    } catch (err) {
      setLanguage(previous);
      setLanguageError(translateApiError(err, t));
    } finally {
      setLanguageSaving(false);
    }
  }

  // ── My account: change password ───────────────────────────────────────────
  async function handleChangePassword(e) {
    e.preventDefault();
    setPwClientError('');
    setPwServerError('');

    if (pwNew.length < 8) {
      setPwClientError(t('admin.pwTooShort'));
      return;
    }
    if (pwNew !== pwConfirm) {
      setPwClientError(t('admin.pwMismatch'));
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
      setPwServerError(translateApiError(err, t));
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
        {/* Brand and version share a wrapper so the header's space-between
            keeps the logout button pushed right. */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{ fontWeight: 700, fontSize: 'var(--font-size-lg)' }}>{t('admin.brand')}</span>
          <VersionLabel />
        </div>
        <button className="btn btn-ghost" onClick={logout}>{t('admin.logOut')}</button>
      </header>

      <div style={{ maxWidth: 960, margin: '0 auto', padding: 32 }}>
        <div className="page-header">
          <div>
            <h1 className="page-title">{t('admin.title')}</h1>
            <p className="page-subtitle">{t('admin.subtitle')}</p>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => { setShowCreate(s => !s); setCreateError(''); }}
          >
            {showCreate ? t('common.cancel') : t('admin.createTeam')}
          </button>
        </div>

        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

        {/* ── Create form ─────────────────────────────────────────────────── */}
        {showCreate && (
          <div className="card card-pad" style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 16 }}>
              {t('admin.newTeam')}
            </h2>
            {createError && (
              <div className="alert alert-error" style={{ marginBottom: 12 }}>{createError}</div>
            )}
            <form onSubmit={handleCreate}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-username">{t('admin.username')}</label>
                  <input id="cr-username" className="form-input" required
                    value={createForm.username} onChange={e => setField('username', e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-email">{t('admin.email')}</label>
                  <input id="cr-email" className="form-input" type="email" required
                    value={createForm.email} onChange={e => setField('email', e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-team">{t('admin.teamName')}</label>
                  <input id="cr-team" className="form-input" required
                    value={createForm.team_name} onChange={e => setField('team_name', e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="cr-pw">{t('admin.initialPassword')}</label>
                  <input id="cr-pw" className="form-input" type="password" required minLength={8}
                    placeholder={t('admin.passwordHint')}
                    value={createForm.initial_password}
                    onChange={e => setField('initial_password', e.target.value)} />
                </div>
              </div>
              <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                <button type="button" className="btn"
                  onClick={() => { setShowCreate(false); setCreateError(''); }}>{t('common.cancel')}</button>
                <button type="submit" className="btn btn-primary" disabled={creating}>
                  {creating ? t('admin.creating') : t('admin.createTeamSubmit')}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ── Teams table ──────────────────────────────────────────────────── */}
        <div className="card table-scroll">
          {loading && <div className="card-pad text-soft text-sm">{t('common.loading')}</div>}

          {!loading && teams.length === 0 && (
            <div className="card-pad text-soft text-sm">{t('admin.noTeams')}</div>
          )}

          {!loading && teams.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t('admin.colTeamAccount')}</th>
                  <th>{t('admin.email')}</th>
                  <th>{t('admin.colPastSessions')}</th>
                  <th>{t('admin.colActions')}</th>
                </tr>
              </thead>
              <tbody>
                {teams.map(team => {
                  const isEditingTeam = editingTeamId === team.team_id;
                  const stat          = stats[team.team_id];
                  const isExpanded    = expandedIds.has(team.team_id);

                  let pastSessionsCell;
                  if (stat && stat.past_session_count > 0) {
                    pastSessionsCell = (
                      <button
                        className="btn btn-ghost" style={BTN_SM}
                        aria-expanded={isExpanded}
                        onClick={() => toggleExpand(team.team_id)}
                      >
                        {isExpanded ? '▾' : '▸'} {stat.past_session_count}
                      </button>
                    );
                  } else if (stat) {
                    pastSessionsCell = '0';
                  } else {
                    pastSessionsCell = <span className="text-soft">—</span>;
                  }

                  return (
                    <Fragment key={team.team_id}>
                      {/* Team header row */}
                      <tr style={{ background: 'var(--color-surface)' }}>
                        <td colSpan={2}>
                          {isEditingTeam ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                              <div className="row" style={{ gap: 6 }}>
                                <input
                                  className="form-input" required autoFocus
                                  value={editTeamName}
                                  onChange={e => setEditTeamName(e.target.value)}
                                  style={{ width: 200 }}
                                />
                                <button className="btn btn-primary" style={BTN_SM}
                                  onClick={() => handleEditTeam(team.team_id)}
                                  disabled={!editTeamName.trim()}>{t('common.save')}</button>
                                <button className="btn btn-ghost" style={BTN_SM}
                                  onClick={cancelEditTeam}>{t('common.cancel')}</button>
                              </div>
                              {editTeamError && (
                                <div className="alert alert-error text-xs">{editTeamError}</div>
                              )}
                            </div>
                          ) : (
                            <span style={{ fontWeight: 700 }}>
                              {team.team_name}{' '}
                              <span className="text-soft text-xs">
                                · {t('admin.accountCount', { count: team.members.length })}
                              </span>
                            </span>
                          )}
                        </td>
                        <td>{pastSessionsCell}</td>
                        <td>
                          {!isEditingTeam && (
                            <button className="btn btn-ghost" style={BTN_SM}
                              onClick={() => startEditTeam(team)}>{t('admin.rename')}</button>
                          )}
                        </td>
                      </tr>

                      {isExpanded && stat && (
                        <tr>
                          <td colSpan={4} style={{ background: 'var(--color-surface)' }}>
                            <div className="text-sm" style={{ padding: '4px 8px' }}>
                              {stat.latest_sessions.map(s => (
                                <div key={s.session_id} className="row" style={{ gap: 12 }}>
                                  <span>{s.session_date}</span>
                                  <span className="text-soft">
                                    {utcHhmmToLocal(s.session_date, s.start_time)}–{utcHhmmToLocal(s.session_date, s.end_time)}
                                  </span>
                                  <span>{t('admin.orderCount', { count: s.order_count })}</span>
                                </div>
                              ))}
                              <div className="text-soft" style={{ marginTop: 6 }}>
                                {t('admin.totalOrders', {
                                  count: stat.past_session_count,
                                  total: stat.total_orders,
                                })}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}

                      {/* Member rows */}
                      {team.members.map(member => {
                        const isEditingMember = editingMemberId === member.id;
                        const isReseting      = resetingId === member.id;
                        return (
                          <tr key={member.id}>
                            <td style={{ paddingLeft: 24, color: 'var(--color-text-soft)' }}>
                              {member.username}
                            </td>

                            <td>
                              {isEditingMember ? (
                                <input
                                  className="form-input" type="email" required
                                  value={editEmail}
                                  onChange={e => setEditEmail(e.target.value)}
                                  autoFocus
                                  style={{ width: 200 }}
                                />
                              ) : (
                                <span className="text-soft">{member.email}</span>
                              )}
                            </td>

                            <td />

                            <td>
                              {isEditingMember && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                  <div className="row" style={{ gap: 6 }}>
                                    <button className="btn btn-primary" style={BTN_SM}
                                      onClick={() => handleEditMember(member.id)}
                                      disabled={!editEmail.trim()}>{t('common.save')}</button>
                                    <button className="btn btn-ghost" style={BTN_SM}
                                      onClick={cancelEditMember}>{t('common.cancel')}</button>
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
                                      placeholder={t('admin.resetPasswordHint')}
                                      minLength={8} value={newPassword}
                                      onChange={e => setNewPassword(e.target.value)}
                                      style={{ width: 210 }}
                                      autoFocus
                                    />
                                    <button className="btn btn-primary" style={BTN_SM}
                                      onClick={() => handleResetPassword(member.id)}
                                      disabled={newPassword.length < 8}>{t('common.save')}</button>
                                    <button className="btn btn-ghost" style={BTN_SM}
                                      onClick={cancelReset}>{t('common.cancel')}</button>
                                  </div>
                                  {resetError && (
                                    <div className="alert alert-error text-xs">{resetError}</div>
                                  )}
                                </div>
                              )}

                              {!isEditingMember && !isReseting && (
                                <div className="row" style={{ gap: 6 }}>
                                  <button className="btn btn-ghost" style={BTN_SM}
                                    onClick={() => startEditMember(member)}>{t('admin.edit')}</button>
                                  <button className="btn btn-ghost" style={BTN_SM}
                                    onClick={() => startReset(member.id)}>{t('admin.resetPw')}</button>
                                  <button
                                    className="btn btn-ghost"
                                    style={{ ...BTN_SM, color: 'var(--color-accent)' }}
                                    onClick={() => handleDeleteMember(team, member)}>{t('admin.deleteAction')}</button>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* ── Administrators ───────────────────────────────────────────────── */}
        <div className="page-header" style={{ marginTop: 40 }}>
          <div>
            <h2 className="page-title" style={{ fontSize: 'var(--font-size-lg)' }}>{t('admin.administrators')}</h2>
            <p className="page-subtitle">{t('admin.administratorsSubtitle')}</p>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => { setShowAdminCreate(s => !s); setAdminCreateError(''); }}
          >
            {showAdminCreate ? t('common.cancel') : t('admin.createAdmin')}
          </button>
        </div>

        {showAdminCreate && (
          <div className="card card-pad" style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 16 }}>
              {t('admin.newAdmin')}
            </h2>
            {adminCreateError && (
              <div className="alert alert-error" style={{ marginBottom: 12 }}>{adminCreateError}</div>
            )}
            <form onSubmit={handleAdminCreate}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="adm-username">{t('admin.username')}</label>
                  <input id="adm-username" className="form-input" required
                    value={adminCreateForm.username}
                    onChange={e => setAdminField('username', e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="adm-pw">{t('admin.initialPassword')}</label>
                  <input id="adm-pw" className="form-input" type="password" required minLength={8}
                    placeholder={t('admin.passwordHint')}
                    value={adminCreateForm.initial_password}
                    onChange={e => setAdminField('initial_password', e.target.value)} />
                </div>
              </div>
              <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                <button type="button" className="btn"
                  onClick={() => { setShowAdminCreate(false); setAdminCreateError(''); }}>{t('common.cancel')}</button>
                <button type="submit" className="btn btn-primary" disabled={adminCreating}>
                  {adminCreating ? t('admin.creating') : t('admin.createAdminSubmit')}
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
                  <th>{t('admin.username')}</th>
                  <th>{t('admin.colCreated')}</th>
                  <th>{t('admin.colActions')}</th>
                </tr>
              </thead>
              <tbody>
                {admins.map(admin => {
                  const isReseting = adminResetingId === admin.id;

                  return (
                    <tr key={admin.id}>
                      <td style={{ fontWeight: 500 }}>
                        {admin.username}
                        {admin.is_self && <span className="text-soft"> {t('admin.you')}</span>}
                      </td>
                      <td className="text-soft">
                        {formatIsoDate(admin.created_at, i18n.language)}
                      </td>
                      <td>
                        {isReseting && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            <div className="row" style={{ gap: 6 }}>
                              <input
                                className="form-input" type="password"
                                placeholder={t('admin.resetPasswordHint')}
                                minLength={8} value={adminNewPassword}
                                onChange={e => setAdminNewPassword(e.target.value)}
                                style={{ width: 210 }}
                                autoFocus
                              />
                              <button className="btn btn-primary" style={BTN_SM}
                                onClick={() => handleAdminResetPassword(admin.id)}
                                disabled={adminNewPassword.length < 8}>{t('common.save')}</button>
                              <button className="btn btn-ghost" style={BTN_SM}
                                onClick={cancelAdminReset}>{t('common.cancel')}</button>
                            </div>
                            {adminResetError && (
                              <div className="alert alert-error text-xs">{adminResetError}</div>
                            )}
                          </div>
                        )}

                        {!isReseting && !admin.is_self && (
                          <div className="row" style={{ gap: 6 }}>
                            <button className="btn btn-ghost" style={BTN_SM}
                              onClick={() => startAdminReset(admin.id)}>{t('admin.resetPw')}</button>
                            {admins.length > 1 && (
                              <button
                                className="btn btn-ghost"
                                style={{ ...BTN_SM, color: 'var(--color-accent)' }}
                                onClick={() => handleAdminDelete(admin)}>{t('admin.deleteAction')}</button>
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

        {/* ── My account ───────────────────────────────────────────────────── */}
        <div className="page-header" style={{ marginTop: 40 }}>
          <div>
            <h2 className="page-title" style={{ fontSize: 'var(--font-size-lg)' }}>{t('admin.myAccount')}</h2>
            <p className="page-subtitle">{t('admin.myAccountSubtitle')}</p>
          </div>
        </div>

        {/* Language is saved the moment it changes — one field, no Save button,
            and no logout: the session is untouched. */}
        <div className="card card-pad" style={{ maxWidth: 420, marginBottom: 16 }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" htmlFor="acct-language">{t('common.language')}</label>
            <select
              id="acct-language"
              className="form-input"
              value={language}
              disabled={languageSaving}
              onChange={handleLanguageChange}
            >
              <option value={FOLLOW_BROWSER}>{t('admin.followBrowser')}</option>
              {LOCALES.map(({ tag, label }) => (
                <option key={tag} value={tag}>{label}</option>
              ))}
            </select>
            <p className="text-soft text-xs" style={{ marginTop: 6 }}>{t('admin.languageHint')}</p>
          </div>
          {languageError && (
            <div className="alert alert-error text-xs" style={{ marginTop: 8 }}>{languageError}</div>
          )}
        </div>

        {pwClientError && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>{pwClientError}</div>
        )}
        {pwServerError && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>{pwServerError}</div>
        )}

        <form onSubmit={handleChangePassword} style={{ maxWidth: 420 }}>
          <div className="card card-pad" style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 'var(--font-size-md)', fontWeight: 600, marginBottom: 4 }}>
              {t('admin.changePassword')}
            </h3>
            <p className="text-soft text-sm" style={{ marginBottom: 16 }}>
              {t('admin.changePasswordNote')}
            </p>
            <div className="form-group">
              <label className="form-label" htmlFor="cp-current">{t('admin.currentPassword')}</label>
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
              <label className="form-label" htmlFor="cp-new">{t('admin.newPassword')}</label>
              <input
                id="cp-new"
                className="form-input"
                type="password"
                required
                minLength={8}
                value={pwNew}
                onChange={e => setPwNew(e.target.value)}
                placeholder={t('admin.passwordHint')}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="cp-confirm">{t('admin.confirmNewPassword')}</label>
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
              {pwSubmitting ? t('common.saving') : t('admin.changePasswordSubmit')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
