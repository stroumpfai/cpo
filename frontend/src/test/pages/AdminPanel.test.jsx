import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { AdminPanel } from '../../pages/AdminPanel.jsx';
import { renderWithRouter } from '../utils.jsx';

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

const mockTeams = [
  {
    team_id: 'c1', team_name: 'Team Alpha', unique_link: 'link1',
    currency: 'CHF', member_identifier: 'name', created_at: '2026-01-01T00:00:00Z',
    members: [{ id: 'm1', username: 'alice_cpo', email: 'alice@example.com', created_at: '2026-01-01T00:00:00Z' }],
  },
  {
    team_id: 'c2', team_name: 'Team Beta', unique_link: 'link2',
    currency: 'CHF', member_identifier: 'name', created_at: '2026-01-02T00:00:00Z',
    members: [{ id: 'm2', username: 'bob_cpo', email: 'bob@example.com', created_at: '2026-01-02T00:00:00Z' }],
  },
];

const mockAdmins = [
  { id: 1, username: 'admin', created_at: '2026-01-01T00:00:00Z', is_self: true },
  { id: 2, username: 'root2', created_at: '2026-02-01T00:00:00Z', is_self: false },
];

const mockStats = [
  {
    team_id: 'c1',
    team_name: 'Team Alpha',
    past_session_count: 5,
    total_orders: 23,
    latest_sessions: [
      { session_id: 's3', session_date: '2026-07-10', start_time: '11:00', end_time: '12:00', order_count: 9 },
      { session_id: 's2', session_date: '2026-07-03', start_time: '11:00', end_time: '12:00', order_count: 7 },
      { session_id: 's1', session_date: '2026-06-26', start_time: '11:00', end_time: '12:00', order_count: 7 },
    ],
  },
  {
    team_id: 'c2',
    team_name: 'Team Beta',
    past_session_count: 0,
    total_orders: 0,
    latest_sessions: [],
  },
];

// The panel fetches /admin/cpos, /admin/admins and /admin/stats — route the mock by path.
function mockGet({ teams = [], admins = mockAdmins, stats = [] } = {}) {
  api.get.mockImplementation(path => {
    if (path === '/admin/admins') return Promise.resolve(admins);
    if (path === '/admin/stats') return Promise.resolve(stats);
    return Promise.resolve(teams);
  });
}

function renderAdminPanel() {
  return renderWithRouter(
    <Routes>
      <Route path="/admin" element={<AdminPanel />} />
      <Route path="/login" element={<div>Login Page</div>} />
    </Routes>,
    { initialEntries: ['/admin'] }
  );
}

describe('AdminPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    globalThis.confirm = vi.fn(() => true);
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('loading state', () => {
    it('shows loading while fetching CPOs', () => {
      api.get.mockReturnValue(new Promise(() => {}));
      renderAdminPanel();
      expect(screen.getByText('Loading…')).toBeInTheDocument();
    });
  });

  describe('listing teams', () => {
    it('lists team member usernames from api.get', async () => {
      mockGet({ teams: mockTeams });
      renderAdminPanel();
      await waitFor(() => {
        expect(screen.getByText('alice_cpo')).toBeInTheDocument();
        expect(screen.getByText('bob_cpo')).toBeInTheDocument();
      });
    });

    it('shows email and team name for each team', async () => {
      mockGet({ teams: mockTeams });
      renderAdminPanel();
      await waitFor(() => {
        expect(screen.getByText('alice@example.com')).toBeInTheDocument();
        expect(screen.getByText(/Team Alpha/)).toBeInTheDocument();
        expect(screen.getByText('bob@example.com')).toBeInTheDocument();
        expect(screen.getByText(/Team Beta/)).toBeInTheDocument();
      });
    });

    it('shows empty state when no teams', async () => {
      mockGet();
      renderAdminPanel();
      await waitFor(() => {
        expect(screen.getByText(/No teams yet/i)).toBeInTheDocument();
      });
    });
  });

  describe('creating a team', () => {
    it('shows create form when "+ Create team" button is clicked', async () => {
      const user = userEvent.setup();
      mockGet();
      renderAdminPanel();

      await waitFor(() => screen.getByRole('button', { name: /\+ Create team/i }));
      await user.click(screen.getByRole('button', { name: /\+ Create team/i }));

      expect(screen.getByLabelText('Username')).toBeInTheDocument();
      expect(screen.getByLabelText('Email')).toBeInTheDocument();
      expect(screen.getByLabelText('Team name')).toBeInTheDocument();
      expect(screen.getByLabelText('Initial password')).toBeInTheDocument();
    });

    it('submits correct payload on create', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockResolvedValue({ team_id: 'c-new', team_name: 'New Team', members: [] });

      renderAdminPanel();

      await waitFor(() => screen.getByRole('button', { name: /\+ Create team/i }));
      await user.click(screen.getByRole('button', { name: /\+ Create team/i }));

      await user.type(screen.getByLabelText('Username'), 'newcpo');
      await user.type(screen.getByLabelText('Email'), 'newcpo@example.com');
      await user.type(screen.getByLabelText('Team name'), 'New Team');
      await user.type(screen.getByLabelText('Initial password'), 'secret123');

      await user.click(screen.getByRole('button', { name: /Create team/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/admin/cpos', {
          username: 'newcpo',
          email: 'newcpo@example.com',
          team_name: 'New Team',
          initial_password: 'secret123',
        });
      });
    });

    it('hides form after successful create', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockResolvedValue({ team_id: 'c-new', team_name: 'New Team', members: [] });

      renderAdminPanel();

      await waitFor(() => screen.getByRole('button', { name: /\+ Create team/i }));
      await user.click(screen.getByRole('button', { name: /\+ Create team/i }));

      await user.type(screen.getByLabelText('Username'), 'newcpo');
      await user.type(screen.getByLabelText('Email'), 'newcpo@example.com');
      await user.type(screen.getByLabelText('Team name'), 'New Team');
      await user.type(screen.getByLabelText('Initial password'), 'secret123');

      await user.click(screen.getByRole('button', { name: /Create team/i }));

      await waitFor(() => {
        // After successful creation, form should be hidden (button text back to "+ Create team")
        expect(screen.getByRole('button', { name: /\+ Create team/i })).toBeInTheDocument();
      });
    });
  });

  describe('page header', () => {
    it('renders Admin Panel title', async () => {
      mockGet();
      renderAdminPanel();
      expect(screen.getByText('Admin Panel')).toBeInTheDocument();
    });

    it('renders a logout button', async () => {
      mockGet();
      renderAdminPanel();
      expect(screen.getByRole('button', { name: /Log out/i })).toBeInTheDocument();
    });
  });

  describe('deleting a CPO', () => {
    it('calls api.delete when delete is clicked and confirmed', async () => {
      const user = userEvent.setup();
      mockGet({ teams: mockTeams });
      api.delete.mockResolvedValue(null);

      renderAdminPanel();

      await waitFor(() => screen.getAllByText(/✕ delete/i));

      const deleteButtons = screen.getAllByText(/✕ delete/i);
      await user.click(deleteButtons[0]);

      expect(globalThis.confirm).toHaveBeenCalled();
      await waitFor(() => {
        expect(api.delete).toHaveBeenCalledWith('/admin/cpos/m1');
      });
    });
  });

  describe('usage stats', () => {
    it('shows the past-session count for each CPO', async () => {
      mockGet({ teams: mockTeams, stats: mockStats });
      renderAdminPanel();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /5/ })).toBeInTheDocument();
        expect(screen.getByText('0')).toBeInTheDocument();
      });
    });

    it('expands and collapses the latest sessions on click', async () => {
      const user = userEvent.setup();
      mockGet({ teams: mockTeams, stats: mockStats });
      renderAdminPanel();

      const toggle = await screen.findByRole('button', { name: /5/ });
      expect(screen.queryByText('2026-07-10')).not.toBeInTheDocument();

      await user.click(toggle);
      expect(screen.getByText('2026-07-10')).toBeInTheDocument();
      expect(screen.getByText('9 orders')).toBeInTheDocument();
      expect(screen.getByText(/Total orders across 5 past sessions: 23/)).toBeInTheDocument();

      await user.click(toggle);
      expect(screen.queryByText('2026-07-10')).not.toBeInTheDocument();
    });

    it('shows a plain 0 with no expand button for a CPO with no past sessions', async () => {
      mockGet({ teams: mockTeams, stats: mockStats });
      renderAdminPanel();

      await waitFor(() => screen.getByText('bob_cpo'));
      expect(screen.getByText('0')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /0/ })).not.toBeInTheDocument();
    });
  });

  describe('listing admins', () => {
    it('lists admins and marks the caller with "(you)"', async () => {
      mockGet();
      renderAdminPanel();
      await waitFor(() => {
        expect(screen.getByText('admin')).toBeInTheDocument();
        expect(screen.getByText('root2')).toBeInTheDocument();
      });
      expect(screen.getByText('(you)')).toBeInTheDocument();
    });

    it('shows no reset/delete actions on the own row', async () => {
      mockGet();
      renderAdminPanel();
      await waitFor(() => screen.getByText('root2'));
      // Only the other admin gets action buttons
      expect(screen.getAllByText(/reset pw/i)).toHaveLength(1);
      expect(screen.getAllByText(/✕ delete/i)).toHaveLength(1);
    });

    it('hides the delete action when only one admin exists', async () => {
      mockGet({ admins: [{ id: 1, username: 'admin', created_at: '2026-01-01T00:00:00Z', is_self: true }] });
      renderAdminPanel();
      await waitFor(() => screen.getByText('admin'));
      expect(screen.queryByText(/✕ delete/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/reset pw/i)).not.toBeInTheDocument();
    });
  });

  describe('creating an admin', () => {
    it('submits correct payload and reloads the list', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockResolvedValue({ id: 3, username: 'newadmin' });

      renderAdminPanel();

      await waitFor(() => screen.getByRole('button', { name: /\+ Create admin/i }));
      await user.click(screen.getByRole('button', { name: /\+ Create admin/i }));

      await user.type(screen.getByLabelText('Username'), 'newadmin');
      await user.type(screen.getByLabelText('Initial password'), 'secret123');

      await user.click(screen.getByRole('button', { name: /^Create admin$/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/admin/admins', {
          username: 'newadmin',
          initial_password: 'secret123',
        });
      });
      // list reloaded after create
      expect(api.get).toHaveBeenCalledWith('/admin/admins');
    });

    it('shows the server error on failed create', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockRejectedValue(new Error('Username already exists'));

      renderAdminPanel();

      await waitFor(() => screen.getByRole('button', { name: /\+ Create admin/i }));
      await user.click(screen.getByRole('button', { name: /\+ Create admin/i }));

      await user.type(screen.getByLabelText('Username'), 'admin');
      await user.type(screen.getByLabelText('Initial password'), 'secret123');
      await user.click(screen.getByRole('button', { name: /^Create admin$/i }));

      await waitFor(() => {
        expect(screen.getByText('Username already exists')).toBeInTheDocument();
      });
    });
  });

  describe('deleting an admin', () => {
    it('confirms and calls api.delete for the other admin', async () => {
      const user = userEvent.setup();
      mockGet();
      api.delete.mockResolvedValue(null);

      renderAdminPanel();

      await waitFor(() => screen.getAllByText(/✕ delete/i));
      await user.click(screen.getByText(/✕ delete/i));

      expect(globalThis.confirm).toHaveBeenCalled();
      await waitFor(() => {
        expect(api.delete).toHaveBeenCalledWith('/admin/admins/2');
      });
    });
  });

  describe('resetting another admin password', () => {
    it('disables Save until 8 characters are entered, then posts', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockResolvedValue({ id: 2, username: 'root2' });

      renderAdminPanel();

      await waitFor(() => screen.getByText(/reset pw/i));
      await user.click(screen.getByText(/reset pw/i));

      const input = screen.getByPlaceholderText(/Min 8 chars — not common/i);
      const saveButton = screen.getByRole('button', { name: /^Save$/i });

      await user.type(input, 'short');
      expect(saveButton).toBeDisabled();

      await user.type(input, 'enough1');
      expect(saveButton).toBeEnabled();

      await user.click(saveButton);
      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/admin/admins/2/reset-password', {
          new_password: 'shortenough1',
        });
      });
    });

    it('shows the server error on failed reset', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockRejectedValue(new Error('This password is too common'));

      renderAdminPanel();

      await waitFor(() => screen.getByText(/reset pw/i));
      await user.click(screen.getByText(/reset pw/i));

      await user.type(screen.getByPlaceholderText(/Min 8 chars — not common/i), 'password1');
      await user.click(screen.getByRole('button', { name: /^Save$/i }));

      await waitFor(() => {
        expect(screen.getByText('This password is too common')).toBeInTheDocument();
      });
    });
  });

  describe('changing my password', () => {
    async function fillChangePasswordForm(user, { current, next, confirm }) {
      await user.type(screen.getByLabelText('Current password'), current);
      await user.type(screen.getByLabelText('New password'), next);
      await user.type(screen.getByLabelText('Confirm new password'), confirm);
      await user.click(screen.getByRole('button', { name: /^Change password$/i }));
    }

    it('rejects a short new password client-side without calling the API', async () => {
      const user = userEvent.setup();
      mockGet();
      renderAdminPanel();

      await waitFor(() => screen.getByLabelText('Current password'));
      await fillChangePasswordForm(user, { current: 'oldpass99', next: 'short', confirm: 'short' });

      expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
      expect(api.post).not.toHaveBeenCalled();
    });

    it('rejects mismatched confirmation client-side without calling the API', async () => {
      const user = userEvent.setup();
      mockGet();
      renderAdminPanel();

      await waitFor(() => screen.getByLabelText('Current password'));
      await fillChangePasswordForm(user, { current: 'oldpass99', next: 'newsecret1', confirm: 'different1' });

      expect(screen.getByText(/do not match/i)).toBeInTheDocument();
      expect(api.post).not.toHaveBeenCalled();
    });

    it('posts change-password, logs out and navigates to login on success', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockResolvedValue(null);

      renderAdminPanel();

      await waitFor(() => screen.getByLabelText('Current password'));
      await fillChangePasswordForm(user, { current: 'oldpass99', next: 'newsecret1', confirm: 'newsecret1' });

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/admin/change-password', {
          current_password: 'oldpass99',
          new_password: 'newsecret1',
        });
        expect(api.post).toHaveBeenCalledWith('/auth/logout');
        expect(screen.getByText('Login Page')).toBeInTheDocument();
      });
    });

    it('shows the server error when the current password is wrong', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockRejectedValue(new Error('Current password is incorrect.'));

      renderAdminPanel();

      await waitFor(() => screen.getByLabelText('Current password'));
      await fillChangePasswordForm(user, { current: 'wrongpass', next: 'newsecret1', confirm: 'newsecret1' });

      await waitFor(() => {
        expect(screen.getByText('Current password is incorrect.')).toBeInTheDocument();
      });
    });
  });
});
