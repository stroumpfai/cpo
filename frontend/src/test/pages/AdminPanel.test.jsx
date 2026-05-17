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
    delete: vi.fn(),
  },
}));

import { api } from '../../api.js';

const mockCpos = [
  { id: 'c1', username: 'alice_cpo', email: 'alice@example.com', team_name: 'Team Alpha' },
  { id: 'c2', username: 'bob_cpo', email: 'bob@example.com', team_name: 'Team Beta' },
];

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

  describe('listing CPOs', () => {
    it('lists CPOs from api.get', async () => {
      api.get.mockResolvedValue(mockCpos);
      renderAdminPanel();
      await waitFor(() => {
        expect(screen.getByText('alice_cpo')).toBeInTheDocument();
        expect(screen.getByText('bob_cpo')).toBeInTheDocument();
      });
    });

    it('shows email and team name for each CPO', async () => {
      api.get.mockResolvedValue(mockCpos);
      renderAdminPanel();
      await waitFor(() => {
        expect(screen.getByText('alice@example.com')).toBeInTheDocument();
        expect(screen.getByText('Team Alpha')).toBeInTheDocument();
        expect(screen.getByText('bob@example.com')).toBeInTheDocument();
        expect(screen.getByText('Team Beta')).toBeInTheDocument();
      });
    });

    it('shows empty state when no CPOs', async () => {
      api.get.mockResolvedValue([]);
      renderAdminPanel();
      await waitFor(() => {
        expect(screen.getByText(/No CPO accounts yet/i)).toBeInTheDocument();
      });
    });
  });

  describe('creating a CPO', () => {
    it('shows create form when "+ Create CPO" button is clicked', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue([]);
      renderAdminPanel();

      await waitFor(() => screen.getByRole('button', { name: /\+ Create CPO/i }));
      await user.click(screen.getByRole('button', { name: /\+ Create CPO/i }));

      expect(screen.getByLabelText('Username')).toBeInTheDocument();
      expect(screen.getByLabelText('Email')).toBeInTheDocument();
      expect(screen.getByLabelText('Team name')).toBeInTheDocument();
      expect(screen.getByLabelText('Initial password')).toBeInTheDocument();
    });

    it('submits correct payload on create', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue([]);
      api.post.mockResolvedValue({ id: 'c-new', username: 'newcpo' });

      renderAdminPanel();

      await waitFor(() => screen.getByRole('button', { name: /\+ Create CPO/i }));
      await user.click(screen.getByRole('button', { name: /\+ Create CPO/i }));

      await user.type(screen.getByLabelText('Username'), 'newcpo');
      await user.type(screen.getByLabelText('Email'), 'newcpo@example.com');
      await user.type(screen.getByLabelText('Team name'), 'New Team');
      await user.type(screen.getByLabelText('Initial password'), 'secret123');

      await user.click(screen.getByRole('button', { name: /Create CPO/i }));

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
      api.get.mockResolvedValue([]);
      api.post.mockResolvedValue({ id: 'c-new', username: 'newcpo' });

      renderAdminPanel();

      await waitFor(() => screen.getByRole('button', { name: /\+ Create CPO/i }));
      await user.click(screen.getByRole('button', { name: /\+ Create CPO/i }));

      await user.type(screen.getByLabelText('Username'), 'newcpo');
      await user.type(screen.getByLabelText('Email'), 'newcpo@example.com');
      await user.type(screen.getByLabelText('Team name'), 'New Team');
      await user.type(screen.getByLabelText('Initial password'), 'secret123');

      await user.click(screen.getByRole('button', { name: /Create CPO/i }));

      await waitFor(() => {
        // After successful creation, form should be hidden (button text back to "+ Create CPO")
        expect(screen.getByRole('button', { name: /\+ Create CPO/i })).toBeInTheDocument();
      });
    });
  });

  describe('page header', () => {
    it('renders Admin Panel title', async () => {
      api.get.mockResolvedValue([]);
      renderAdminPanel();
      expect(screen.getByText('Admin Panel')).toBeInTheDocument();
    });

    it('renders a logout button', async () => {
      api.get.mockResolvedValue([]);
      renderAdminPanel();
      expect(screen.getByRole('button', { name: /Log out/i })).toBeInTheDocument();
    });
  });

  describe('deleting a CPO', () => {
    it('calls api.delete when delete is clicked and confirmed', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(mockCpos);
      api.delete.mockResolvedValue(null);

      renderAdminPanel();

      await waitFor(() => screen.getAllByText(/✕ delete/i));

      const deleteButtons = screen.getAllByText(/✕ delete/i);
      await user.click(deleteButtons[0]);

      expect(globalThis.confirm).toHaveBeenCalled();
      await waitFor(() => {
        expect(api.delete).toHaveBeenCalledWith('/admin/cpos/c1');
      });
    });
  });
});
