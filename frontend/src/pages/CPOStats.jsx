import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { RecentSessionsTable } from '../components/RecentSessionsTable.jsx';
import { MenuStatsCard } from '../components/MenuStatsCard.jsx';

const RESET_CONFIRM_MSG =
  "Reset statistics counters? Historical sessions and orders are kept — " +
  "the numbers below will just start counting from now.";

export function CPOStats() {
  const [stats, setStats]         = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    api.get('/cpo/stats')
      .then(setStats)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleReset() {
    if (!globalThis.confirm(RESET_CONFIRM_MSG)) return;
    setResetting(true);
    setError('');
    try {
      setStats(await api.post('/cpo/stats/reset', {}));
    } catch (err) {
      setError(err.message);
    } finally {
      setResetting(false);
    }
  }

  if (loading) return <div className="text-soft text-sm">Loading…</div>;
  if (error)   return <div className="alert alert-error">{error}</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Statistics</h1>
          <p className="page-subtitle">
            {stats.stats_reset_at
              ? `Counting since ${new Date(stats.stats_reset_at).toLocaleString()}`
              : "Counting your team's full history."}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={handleReset}
          disabled={resetting}
        >
          {resetting ? 'Resetting…' : 'Reset counters'}
        </button>
      </div>

      <div className="stat-cards" style={{ marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-label">total sessions</div>
          <div className="stat-value">{stats.total_sessions}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">distinct members</div>
          <div className="stat-value">{stats.distinct_members}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">distinct plates</div>
          <div className="stat-value">{stats.distinct_plates}</div>
        </div>
      </div>

      <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 12 }}>
        Recent sessions
      </h2>
      <RecentSessionsTable rows={stats.recent_sessions} />

      <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, margin: '24px 0 12px' }}>
        By menu
      </h2>
      {stats.menus.length === 0 ? (
        <div className="card card-pad text-soft text-sm">No menus yet.</div>
      ) : (
        <div className="row" style={{ flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' }}>
          {stats.menus.map(menu => (
            <MenuStatsCard key={menu.menu_id} menu={menu} />
          ))}
        </div>
      )}
    </div>
  );
}
