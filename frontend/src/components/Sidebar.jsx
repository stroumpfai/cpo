import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { clearAuth } from '../utils/auth.js';

const NAV = [
  { label: 'Dashboard',          to: '/dashboard' },
  { label: 'Open a new session', to: '/dashboard/new-session' },
  { label: 'Menus',              to: '/dashboard/menus' },
  { label: 'Statistics',         to: '/dashboard/stats' },
  { label: 'Settings',           to: '/dashboard/settings' },
];

export function Sidebar() {
  const [teamName, setTeamName] = useState('');
  const [username, setUsername] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/cpo/me').then((me) => {
      setTeamName(me.team_name);
      setUsername(me.username);
    }).catch(() => {});
  }, []);

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
        {NAV.map(({ label, to }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/dashboard'}
            className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
          >
            {label}
          </NavLink>
        ))}
      </div>

      <div className="sidebar-spacer" />

      <div className="sidebar-user">
        <span>{username || '…'}</span>
        <button className="sidebar-logout" onClick={logout}>log out</button>
      </div>
    </nav>
  );
}
