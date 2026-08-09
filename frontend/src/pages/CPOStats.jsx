import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../api.js';
import { translateApiError } from '../i18n/apiError.js';
import { formatDateTime } from '../utils/format.js';
import { RecentSessionsTable } from '../components/RecentSessionsTable.jsx';
import { MenuStatsCard } from '../components/MenuStatsCard.jsx';

export function CPOStats() {
  const [stats, setStats]         = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [resetting, setResetting] = useState(false);

  const { t, i18n } = useTranslation();

  useEffect(() => {
    api.get('/cpo/stats')
      .then(setStats)
      .catch(err => setError(translateApiError(err, t)))
      .finally(() => setLoading(false));
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function handleReset() {
    if (!globalThis.confirm(t('stats.resetConfirm'))) return;
    setResetting(true);
    setError('');
    try {
      setStats(await api.post('/cpo/stats/reset', {}));
    } catch (err) {
      setError(translateApiError(err, t));
    } finally {
      setResetting(false);
    }
  }

  if (loading) return <div className="text-soft text-sm">{t('common.loading')}</div>;
  if (error)   return <div className="alert alert-error">{error}</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('stats.title')}</h1>
          <p className="page-subtitle">
            {stats.stats_reset_at
              ? t('stats.countingSince', { date: formatDateTime(stats.stats_reset_at, i18n.language) })
              : t('stats.countingAll')}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={handleReset}
          disabled={resetting}
        >
          {resetting ? t('stats.resetting') : t('stats.reset')}
        </button>
      </div>

      <div className="stat-cards" style={{ marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-label">{t('stats.totalSessions')}</div>
          <div className="stat-value">{stats.total_sessions}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{t('stats.distinctMembers')}</div>
          <div className="stat-value">{stats.distinct_members}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{t('stats.distinctPlates')}</div>
          <div className="stat-value">{stats.distinct_plates}</div>
        </div>
      </div>

      <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 12 }}>
        {t('stats.recentSessions')}
      </h2>
      <RecentSessionsTable rows={stats.recent_sessions} />

      <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, margin: '24px 0 12px' }}>
        {t('stats.byMenu')}
      </h2>
      {stats.menus.length === 0 ? (
        <div className="card card-pad text-soft text-sm">{t('stats.noMenus')}</div>
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
