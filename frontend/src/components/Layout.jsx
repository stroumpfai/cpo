import PropTypes from 'prop-types';
import { Sidebar } from './Sidebar.jsx';

export function Layout({ children }) {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">{children}</main>
    </div>
  );
}

Layout.propTypes = {
  children: PropTypes.node.isRequired,
};
