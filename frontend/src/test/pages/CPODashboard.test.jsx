import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { CPODashboard } from '../../pages/CPODashboard.jsx';
import { renderWithRouter, makeJwt } from '../utils.jsx';

// Mock the api module
vi.mock('../../api.js', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import { api } from '../../api.js';

const mockCpo = {
  id: 'cpo-1',
  username: 'testcpo',
  team_name: 'Dev Team',
  unique_link: 'devteam123',
};

const mockSession = {
  id: 'session-1',
  status: 'active',
  session_date: '2026-05-17',
  start_time: '10:00',
  end_time: '23:59',
  grace_period_minutes: 2,
};

const mockSummary = {
  status: 'active',
  distribution: [
    {
      order_id: 'o1',
      member_name: 'Alice',
      client_ip: '127.0.0.1',
      pizza_name: 'Margherita',
      price: 12.5,
      created_at: '2026-05-17T10:00:00Z',
      received: false,
    },
  ],
  pizzeria: [
    { pizza_name: 'Margherita', count: 1, total_price: 12.5 },
  ],
  total_orders: 1,
  total_price: 12.5,
};

function renderDashboard() {
  // Set a valid token so auth works if needed
  const token = makeJwt({ sub: 'cpo-1', role: 'cpo', exp: Math.floor(Date.UTC(2099, 0, 1) / 1000) });
  localStorage.setItem('cpo_token', token);

  return renderWithRouter(
    <Routes>
      <Route path="/dashboard" element={<CPODashboard />} />
      <Route path="/dashboard/new-session" element={<div>New Session Page</div>} />
    </Routes>,
    { initialEntries: ['/dashboard'] }
  );
}

describe('CPODashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    // Mock EventSource globally
    globalThis.EventSource = vi.fn(() => ({
      addEventListener: vi.fn(),
      close: vi.fn(),
    }));
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('loading state', () => {
    it('shows loading indicator initially', () => {
      api.get.mockReturnValue(new Promise(() => {}));
      renderDashboard();
      expect(screen.getByText('Loading…')).toBeInTheDocument();
    });
  });

  describe('no sessions', () => {
    it('shows "No sessions yet." when sessions array is empty', async () => {
      api.get.mockImplementation((path) => {
        if (path === '/cpo/me') return Promise.resolve(mockCpo);
        if (path === '/cpo/sessions') return Promise.resolve([]);
        return Promise.resolve(null);
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText('No sessions yet.')).toBeInTheDocument();
      });
    });

    it('shows a link to create a new session', async () => {
      api.get.mockImplementation((path) => {
        if (path === '/cpo/me') return Promise.resolve(mockCpo);
        if (path === '/cpo/sessions') return Promise.resolve([]);
        return Promise.resolve(null);
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByRole('link', { name: /Open a new session/i })).toBeInTheDocument();
      });
    });
  });

  describe('with active session', () => {
    beforeEach(() => {
      api.get.mockImplementation((path) => {
        if (path === '/cpo/me') return Promise.resolve(mockCpo);
        if (path === '/cpo/sessions') return Promise.resolve([mockSession]);
        if (path.includes('/summary')) return Promise.resolve(mockSummary);
        return Promise.resolve(null);
      });
    });

    it('renders Dashboard title', async () => {
      renderDashboard();
      await waitFor(() => {
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });
    });

    it('shows order data in distribution tab', async () => {
      renderDashboard();
      await waitFor(() => {
        expect(screen.getAllByText('Alice').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Margherita').length).toBeGreaterThan(0);
      });
    });

    it('shows tab buttons', async () => {
      renderDashboard();
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Orders per person/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /List for ordering at Pizzeria/i })).toBeInTheDocument();
      });
    });

    it('switches to pizzeria tab when clicked', async () => {
      const user = userEvent.setup();
      renderDashboard();

      await waitFor(() => screen.getByRole('button', { name: /List for ordering at Pizzeria/i }));

      await user.click(screen.getByRole('button', { name: /List for ordering at Pizzeria/i }));

      await waitFor(() => {
        expect(screen.getAllByText('Margherita').length).toBeGreaterThan(0);
      });
    });

    it('shows stat cards with member count', async () => {
      renderDashboard();
      await waitFor(() => {
        expect(screen.getByText('members')).toBeInTheDocument();
        expect(screen.getByText('pizzas')).toBeInTheDocument();
        expect(screen.getByText('CHF total')).toBeInTheDocument();
      });
    });
  });

  describe('with closed session', () => {
    it('shows "This session is closed." alert', async () => {
      const closedSession = { ...mockSession, status: 'closed' };
      const closedSummary = { ...mockSummary, status: 'closed' };

      api.get.mockImplementation((path) => {
        if (path === '/cpo/me') return Promise.resolve(mockCpo);
        if (path === '/cpo/sessions') return Promise.resolve([closedSession]);
        if (path.includes('/summary')) return Promise.resolve(closedSummary);
        return Promise.resolve(null);
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText(/This session is closed/i)).toBeInTheDocument();
      });
    });
  });

  describe('error state', () => {
    it('shows error message when API fails', async () => {
      api.get.mockRejectedValue(new Error('Network error'));
      renderDashboard();
      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });
  });
});
