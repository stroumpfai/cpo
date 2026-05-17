import { screen } from '@testing-library/react';
import { Routes, Route } from 'react-router-dom';
import { PrivateRoute } from '../../components/PrivateRoute.jsx';
import { renderWithRouter, makeJwt } from '../utils.jsx';

// Clear localStorage between tests
beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

function renderRoutes(token) {
  if (token) {
    localStorage.setItem('cpo_token', token);
  }

  return renderWithRouter(
    <Routes>
      <Route
        path="/"
        element={
          <PrivateRoute>
            <div>Protected Content</div>
          </PrivateRoute>
        }
      />
      <Route path="/login" element={<div>Login Page</div>} />
    </Routes>,
    { initialEntries: ['/'] }
  );
}

function renderRoutesWithRole(token, requiredRole) {
  if (token) {
    localStorage.setItem('cpo_token', token);
  }

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
  describe('with a valid non-expired token', () => {
    it('renders children', () => {
      // exp far in the future (year 2099)
      const token = makeJwt({ sub: 'user1', role: 'cpo', exp: Math.floor(Date.UTC(2099, 0, 1) / 1000) });
      renderRoutes(token);
      expect(screen.getByText('Protected Content')).toBeInTheDocument();
    });
  });

  describe('with no token', () => {
    it('redirects to /login', () => {
      renderRoutes(null);
      expect(screen.getByText('Login Page')).toBeInTheDocument();
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('with an expired token', () => {
    it('redirects to /login', () => {
      // exp in the past
      const token = makeJwt({ sub: 'user1', role: 'cpo', exp: Math.floor(Date.UTC(2000, 0, 1) / 1000) });
      renderRoutes(token);
      expect(screen.getByText('Login Page')).toBeInTheDocument();
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('with role mismatch', () => {
    it('redirects to /login when user role does not match required role', () => {
      const token = makeJwt({ sub: 'user1', role: 'cpo', exp: Math.floor(Date.UTC(2099, 0, 1) / 1000) });
      renderRoutesWithRole(token, 'admin');
      expect(screen.getByText('Login Page')).toBeInTheDocument();
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });

    it('renders children when role matches', () => {
      const token = makeJwt({ sub: 'user1', role: 'admin', exp: Math.floor(Date.UTC(2099, 0, 1) / 1000) });
      renderRoutesWithRole(token, 'admin');
      expect(screen.getByText('Protected Content')).toBeInTheDocument();
    });
  });
});
