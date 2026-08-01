import { useEffect, useState } from 'react';
import { api } from '../api.js';

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

  async function loadMembers() {
    try {
      setMembers(await api.get('/cpo/team-members'));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadInvites() {
    try {
      setInvites(await api.get('/cpo/team-invites'));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { loadMembers(); loadInvites(); }, []);

  async function handleRemove(member) {
    const isLast = members.length <= 1;
    if (isLast) {
      globalThis.alert('You cannot remove the last account on a team.');
      return;
    }
    const message = member.is_self
      ? 'Leave this team? You will be logged out and lose access immediately.'
      : `Remove "${member.username}" from the team?`;
    if (!globalThis.confirm(message)) return;
    try {
      await api.delete(`/cpo/team-members/${member.id}`);
      loadMembers();
    } catch (err) {
      setError(err.message);
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
      setResetError(err.message);
    }
  }

  async function handleCreateInvite() {
    setInviteError('');
    setCreatingInvite(true);
    try {
      await api.post('/cpo/team-invites');
      loadInvites();
    } catch (err) {
      setInviteError(err.message);
    } finally {
      setCreatingInvite(false);
    }
  }

  async function handleRevokeInvite(id) {
    if (!globalThis.confirm('Revoke this invite link? It will no longer work.')) return;
    try {
      await api.delete(`/cpo/team-invites/${id}`);
      loadInvites();
    } catch (err) {
      setError(err.message);
    }
  }

  async function copyInvite(token) {
    const url = inviteUrl(token);
    try {
      await navigator.clipboard.writeText(url);
      setCopiedToken(token);
      setTimeout(() => setCopiedToken(''), 2000);
    } catch {
      globalThis.prompt('Copy this invite link:', url);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Team</h1>
          <p className="page-subtitle">
            Everyone on your team is a peer — any account can manage sessions, menus, and invite
            or remove teammates.
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* ── Members ──────────────────────────────────────────────────────── */}
      <div className="card table-scroll" style={{ marginBottom: 32 }}>
        {loading && <div className="card-pad text-soft text-sm">Loading…</div>}

        {!loading && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Joined</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {members.map(member => {
                const isReseting = resetingId === member.id;
                return (
                  <tr key={member.id}>
                    <td style={{ fontWeight: 500 }}>
                      {member.username}
                      {member.is_self && <span className="text-soft"> (you)</span>}
                    </td>
                    <td className="text-soft">{member.email}</td>
                    <td className="text-soft">{new Date(member.created_at).toLocaleDateString()}</td>
                    <td>
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
                              onClick={() => handleResetPassword(member.id)}
                              disabled={newPassword.length < 8}>Save</button>
                            <button className="btn btn-ghost" style={BTN_SM}
                              onClick={cancelReset}>Cancel</button>
                          </div>
                          {resetError && (
                            <div className="alert alert-error text-xs">{resetError}</div>
                          )}
                        </div>
                      )}

                      {!isReseting && (
                        <div className="row" style={{ gap: 6 }}>
                          <button className="btn btn-ghost" style={BTN_SM}
                            onClick={() => startReset(member.id)}>reset pw</button>
                          {members.length > 1 && (
                            <button
                              className="btn btn-ghost"
                              style={{ ...BTN_SM, color: 'var(--color-accent)' }}
                              onClick={() => handleRemove(member)}>
                              {member.is_self ? '✕ leave' : '✕ remove'}
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
          <h2 className="page-title" style={{ fontSize: 'var(--font-size-lg)' }}>Invite links</h2>
          <p className="page-subtitle">
            Share a link with a teammate so they can create their own account on this team.
            Links expire after 24 hours and work once.
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleCreateInvite} disabled={creatingInvite}>
          {creatingInvite ? 'Creating…' : '+ Generate invite link'}
        </button>
      </div>

      {inviteError && <div className="alert alert-error" style={{ marginBottom: 16 }}>{inviteError}</div>}

      <div className="card table-scroll">
        {invites.length === 0 && (
          <div className="card-pad text-soft text-sm">No pending invite links.</div>
        )}
        {invites.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Link</th>
                <th>Expires</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {invites.map(invite => (
                <tr key={invite.id}>
                  <td className="mono text-sm" style={{ overflowWrap: 'anywhere' }}>
                    {inviteUrl(invite.token)}
                  </td>
                  <td className="text-soft">{new Date(invite.expires_at).toLocaleString()}</td>
                  <td>
                    <div className="row" style={{ gap: 6 }}>
                      <button className="btn btn-ghost" style={BTN_SM}
                        onClick={() => copyInvite(invite.token)}>
                        {copiedToken === invite.token ? 'copied ✓' : 'copy'}
                      </button>
                      <button
                        className="btn btn-ghost"
                        style={{ ...BTN_SM, color: 'var(--color-accent)' }}
                        onClick={() => handleRevokeInvite(invite.id)}>✕ revoke</button>
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
