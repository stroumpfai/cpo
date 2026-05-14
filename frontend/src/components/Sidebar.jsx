import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { removeToken, getUserId } from '../utils/auth.js';

const NAV = [
  { label: 'Dashboard',          to: '/dashboard' },
  { label: 'Open a new session', to: '/dashboard/new-session' },
  { label: 'List of Pizzas',     to: '/dashboard/pizzas' },
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

  function logout() {
    api.post('/auth/logout').catch(() => {});
    removeToken();
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
