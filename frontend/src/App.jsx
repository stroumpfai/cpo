import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { PrivateRoute } from './components/PrivateRoute.jsx';
import { Layout } from './components/Layout.jsx';
import { LoginPage } from './pages/LoginPage.jsx';
import { AdminPanel } from './pages/AdminPanel.jsx';
import { CPODashboard } from './pages/CPODashboard.jsx';
import { NewSession } from './pages/NewSession.jsx';
import { Menus } from './pages/Menus.jsx';
import { CPOSettings } from './pages/CPOSettings.jsx';
import { TeamOrderPage } from './pages/TeamOrderPage.jsx';
import { isAuthenticated, getRole } from './utils/auth.js';

function LoginOrRedirect() {
  if (isAuthenticated()) {
    return <Navigate to={getRole() === 'admin' ? '/admin' : '/dashboard'} replace />;
  }
  return <LoginPage />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginOrRedirect />} />
        <Route path="/orders/:link" element={<TeamOrderPage />} />

        {/* Admin */}
        <Route
          path="/admin"
          element={
            <PrivateRoute role="admin">
              <AdminPanel />
            </PrivateRoute>
          }
        />

        {/* CPO — all wrapped in Layout (sidebar) */}
        <Route
          path="/dashboard"
          element={
            <PrivateRoute role="cpo">
              <Layout><CPODashboard /></Layout>
            </PrivateRoute>
          }
        />
        <Route
          path="/dashboard/new-session"
          element={
            <PrivateRoute role="cpo">
              <Layout><NewSession /></Layout>
            </PrivateRoute>
          }
        />
        <Route
          path="/dashboard/menus"
          element={
            <PrivateRoute role="cpo">
              <Layout><Menus /></Layout>
            </PrivateRoute>
          }
        />
        {/* Old bookmark: the pizza list became Menus */}
        <Route path="/dashboard/pizzas" element={<Navigate to="/dashboard/menus" replace />} />
        <Route
          path="/dashboard/settings"
          element={
            <PrivateRoute role="cpo">
              <Layout><CPOSettings /></Layout>
            </PrivateRoute>
          }
        />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
