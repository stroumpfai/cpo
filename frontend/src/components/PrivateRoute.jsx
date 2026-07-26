import PropTypes from 'prop-types';
import { Navigate } from 'react-router-dom';
import { isAuthenticated, getRole } from '../utils/auth.js';

export function PrivateRoute({ children, role = null }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />;
  if (role && getRole() !== role) return <Navigate to="/login" replace />;
  return children;
}

PrivateRoute.propTypes = {
  children: PropTypes.node.isRequired,
  role:     PropTypes.string,
};
