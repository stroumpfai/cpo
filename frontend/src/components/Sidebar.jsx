import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '../api.js';
import { applyAccountLanguage } from '../i18n/index.js';
import { clearAuth } from '../utils/auth.js';
import { VersionLabel } from './VersionLabel.jsx';

// Labels are resolved at render time so a language switch relabels the nav
// without remounting it.
const NAV = [
  { key: 'dashboard',  to: '/dashboard' },
  { key: 'newSession', to: '/dashboard/new-session' },
  { key: 'menus',      to: '/dashboard/menus' },
  { key: 'stats',      to: '/dashboard/stats' },
  { key: 'team',       to: '/dashboard/team' },
  { key: 'settings',   to: '/dashboard/settings' },
];

export function Sidebar() {
  const [teamName, setTeamName] = useState('');
  const [username, setUsername] = useState('');
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();

  useEffect(() => {
    api.get('/cpo/me').then((me) => {
      setTeamName(me.team_name);
      setUsername(me.username);
      // The sidebar is on every authenticated screen, so this doubles as the
      // place where the account's language preference reaches the UI.
      // Only an explicit tag is applied: `null` means "no opinion, follow the
      // browser", which must not wipe a language the user just picked in the
      // switcher. Choosing "Follow my browser" in settings clears it directly.
      if (me.language) i18n.changeLanguage(applyAccountLanguage(me.language));
    }).catch(() => {});
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function logout() {
    // Await so the Set-Cookie clearing the session is processed before navigating
    await api.post('/auth/logout').catch(() => {});
    clearAuth();
    navigate('/login', { replace: true });
  }

  return (
    <nav className="sidebar">
      <div className="sidebar-brand">🍕 CPO</div>
      {teamName && (
        <div className="sidebar-team">{teamName}</div>
      )}

      <div className="sidebar-nav">
        {NAV.map(({ key, to }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/dashboard'}
            className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
          >
            {t(`nav.${key}`)}
          </NavLink>
        ))}
      </div>

      <div className="sidebar-spacer" />

      <div className="sidebar-version"><VersionLabel /></div>

      <div className="sidebar-user">
        <span>{username || '…'}</span>
        <button className="sidebar-logout" onClick={logout}>{t('nav.logOut')}</button>
      </div>
    </nav>
  );
}
