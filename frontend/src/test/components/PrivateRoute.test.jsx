import { screen } from '@testing-library/react';
import { Routes, Route } from 'react-router-dom';
import { PrivateRoute } from '../../components/PrivateRoute.jsx';
import { renderWithRouter } from '../utils.jsx';
import { setAuth } from '../../utils/auth.js';

// Clear localStorage between tests
beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

function renderRoutes(requiredRole) {
  return renderWithRouter(
    <Routes>
      <Route
        path="/"
        element={
          <PrivateRoute role={requiredRole}>
            <div>Protected Content</div>
          </PrivateRoute>
        }
      />
      <Route path="/login" element={<div>Login Page</div>} />
    </Routes>,
    { initialEntries: ['/'] }
  );
}

describe('PrivateRoute', () => {
  describe('with a valid non-expired auth marker', () => {
    it('renders children', () => {
      setAuth('cpo', 3600);
      renderRoutes();
      expect(screen.getByText('Protected Content')).toBeInTheDocument();
    });
  });

  describe('with no auth marker', () => {
    it('redirects to /login', () => {
      renderRoutes();
      expect(screen.getByText('Login Page')).toBeInTheDocument();
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('with an expired auth marker', () => {
    it('redirects to /login', () => {
      setAuth('cpo', -3600);
      renderRoutes();
      expect(screen.getByText('Login Page')).toBeInTheDocument();
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('with role mismatch', () => {
    it('redirects to /login when user role does not match required role', () => {
      setAuth('cpo', 3600);
      renderRoutes('admin');
      expect(screen.getByText('Login Page')).toBeInTheDocument();
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });

    it('renders children when role matches', () => {
      setAuth('admin', 3600);
      renderRoutes('admin');
      expect(screen.getByText('Protected Content')).toBeInTheDocument();
    });
  });
});
