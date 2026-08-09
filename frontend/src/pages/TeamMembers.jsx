import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../api.js';
import { translateApiError } from '../i18n/apiError.js';
import { formatDateTime, formatIsoDate } from '../utils/format.js';

const BTN_SM = { fontSize: 'var(--font-size-xs)', padding: '3px 10px' };

function inviteUrl(token) {
  return `${globalThis.location.origin}/join/${token}`;
}

export function TeamMembers() {
  const [members, setMembers]   = useState([]);
  const [invites, setInvites]   = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');

  const [resetingId, setResetingId]   = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [resetError, setResetError]   = useState('');

  const [creatingInvite, setCreatingInvite] = useState(false);
  const [inviteError, setInviteError]       = useState('');
  const [copiedToken, setCopiedToken]       = useState('');

  const { t, i18n } = useTranslation();

  async function loadMembers() {
    try {
      setMembers(await api.get('/cpo/team-members'));
    } catch (err) {
      setError(translateApiError(err, t));
    } finally {
      setLoading(false);
    }
  }

  async function loadInvites() {
    try {
      setInvites(await api.get('/cpo/team-invites'));
    } catch (err) {
      setError(translateApiError(err, t));
    }
  }

  useEffect(() => { loadMembers(); loadInvites(); }, []);

  async function handleRemove(member) {
    const isLast = members.length <= 1;
    if (isLast) {
      globalThis.alert(t('errors.lastTeamMember'));
      return;
    }
    const message = member.is_self
      ? t('team.leaveConfirm')
      : t('team.removeConfirm', { username: member.username });
    if (!globalThis.confirm(message)) return;
    try {
      await api.delete(`/cpo/team-members/${member.id}`);
      loadMembers();
    } catch (err) {
      setError(translateApiError(err, t));
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

  async function handleResetPassword(memberId) {
    setResetError('');
    try {
      await api.post(`/cpo/team-members/${memberId}/reset-password`, { new_password: newPassword });
      setResetingId(null);
      setNewPassword('');
    } catch (err) {
      setResetError(translateApiError(err, t));
    }
  }

  async function handleCreateInvite() {
    setInviteError('');
    setCreatingInvite(true);
    try {
      await api.post('/cpo/team-invites');
      loadInvites();
    } catch (err) {
      setInviteError(translateApiError(err, t));
    } finally {
      setCreatingInvite(false);
    }
  }

  async function handleRevokeInvite(id) {
    if (!globalThis.confirm(t('team.revokeConfirm'))) return;
    try {
      await api.delete(`/cpo/team-invites/${id}`);
      loadInvites();
    } catch (err) {
      setError(translateApiError(err, t));
    }
  }

  async function copyInvite(token) {
    const url = inviteUrl(token);
    try {
      await navigator.clipboard.writeText(url);
      setCopiedToken(token);
      setTimeout(() => setCopiedToken(''), 2000);
    } catch {
      globalThis.prompt(t('team.copyPrompt'), url);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('team.title')}</h1>
          <p className="page-subtitle">
            {t('team.subtitle')}
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* ── Members ──────────────────────────────────────────────────────── */}
      <div className="card table-scroll" style={{ marginBottom: 32 }}>
        {loading && <div className="card-pad text-soft text-sm">{t('common.loading')}</div>}

        {!loading && (
          <table className="data-table">
            <thead>
              <tr>
                <th>{t('team.colUsername')}</th>
                <th>{t('team.colEmail')}</th>
                <th>{t('team.colJoined')}</th>
                <th>{t('team.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {members.map(member => {
                const isReseting = resetingId === member.id;
                return (
                  <tr key={member.id}>
                    <td style={{ fontWeight: 500 }}>
                      {member.username}
                      {member.is_self && <span className="text-soft"> {t('team.you')}</span>}
                    </td>
                    <td className="text-soft">{member.email}</td>
                    <td className="text-soft">{formatIsoDate(member.created_at, i18n.language)}</td>
                    <td>
                      {isReseting && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                          <div className="row" style={{ gap: 6 }}>
                            <input
                              className="form-input" type="password"
                              placeholder={t('team.passwordPlaceholder')}
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

                      {!isReseting && (
                        <div className="row" style={{ gap: 6 }}>
                          <button className="btn btn-ghost" style={BTN_SM}
                            onClick={() => startReset(member.id)}>{t('team.resetPw')}</button>
                          {members.length > 1 && (
                            <button
                              className="btn btn-ghost"
                              style={{ ...BTN_SM, color: 'var(--color-accent)' }}
                              onClick={() => handleRemove(member)}>
                              {member.is_self ? t('team.leave') : t('team.remove')}
                            </button>
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

      {/* ── Invites ──────────────────────────────────────────────────────── */}
      <div className="page-header" style={{ marginTop: 8 }}>
        <div>
          <h2 className="page-title" style={{ fontSize: 'var(--font-size-lg)' }}>{t('team.inviteTitle')}</h2>
          <p className="page-subtitle">
            {t('team.inviteSubtitle')}
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleCreateInvite} disabled={creatingInvite}>
          {creatingInvite ? t('team.creating') : t('team.generateInvite')}
        </button>
      </div>

      {inviteError && <div className="alert alert-error" style={{ marginBottom: 16 }}>{inviteError}</div>}

      <div className="card table-scroll">
        {invites.length === 0 && (
          <div className="card-pad text-soft text-sm">{t('team.noInvites')}</div>
        )}
        {invites.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>{t('team.colLink')}</th>
                <th>{t('team.colExpires')}</th>
                <th>{t('team.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {invites.map(invite => (
                <tr key={invite.id}>
                  <td className="mono text-sm" style={{ overflowWrap: 'anywhere' }}>
                    {inviteUrl(invite.token)}
                  </td>
                  <td className="text-soft">{formatDateTime(invite.expires_at, i18n.language)}</td>
                  <td>
                    <div className="row" style={{ gap: 6 }}>
                      <button className="btn btn-ghost" style={BTN_SM}
                        onClick={() => copyInvite(invite.token)}>
                        {copiedToken === invite.token ? t('team.copied') : t('team.copy')}
                      </button>
                      <button
                        className="btn btn-ghost"
                        style={{ ...BTN_SM, color: 'var(--color-accent)' }}
                        onClick={() => handleRevokeInvite(invite.id)}>{t('team.revoke')}</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
