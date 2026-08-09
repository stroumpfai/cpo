import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TeamMembers } from '../../pages/TeamMembers.jsx';
import { renderWithRouter, renderWithLanguage } from '../utils.jsx';

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

const mockMembers = [
  { id: 'm1', username: 'alice', email: 'alice@example.com', created_at: '2026-01-01T00:00:00Z', is_self: true },
  { id: 'm2', username: 'bob', email: 'bob@example.com', created_at: '2026-01-02T00:00:00Z', is_self: false },
];

const mockInvites = [
  { id: 'i1', token: 'invite-token-123', created_at: '2026-01-01T00:00:00Z', expires_at: '2026-01-02T00:00:00Z' },
];

function mockGet({ members = mockMembers, invites = [] } = {}) {
  api.get.mockImplementation(path => {
    if (path === '/cpo/team-invites') return Promise.resolve(invites);
    return Promise.resolve(members);
  });
}

function renderTeamMembers() {
  return renderWithRouter(<TeamMembers />, { initialEntries: ['/dashboard/team'] });
}

describe('TeamMembers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.confirm = vi.fn(() => true);
  });

  describe('listing members', () => {
    it('lists members and marks the caller with "(you)"', async () => {
      mockGet();
      renderTeamMembers();

      await waitFor(() => {
        expect(screen.getByText('alice')).toBeInTheDocument();
        expect(screen.getByText('bob')).toBeInTheDocument();
      });
      expect(screen.getByText('(you)')).toBeInTheDocument();
    });

    it('hides remove/leave actions when only one member remains', async () => {
      mockGet({ members: [mockMembers[0]] });
      renderTeamMembers();

      await waitFor(() => screen.getByText('alice'));
      expect(screen.queryByText(/✕ leave/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/✕ remove/i)).not.toBeInTheDocument();
    });
  });

  describe('translated', () => {
    // Midday UTC so the local date is the same on either side of Zurich.
    const joined = { ...mockMembers[0], created_at: '2026-08-01T12:00:00Z' };

    it('renders German copy and a German join date', async () => {
      mockGet({ members: [joined] });
      renderWithLanguage(<TeamMembers />, { lng: 'de-CH', initialEntries: ['/dashboard/team'] });

      expect(await screen.findByText('Beigetreten')).toBeInTheDocument();
      expect(screen.getByText('1.8.2026')).toBeInTheDocument();   // en renders 8/1/2026
      expect(screen.getByText('(du)')).toBeInTheDocument();
    });

    it('renders the English join date by default', async () => {
      mockGet({ members: [joined] });
      renderTeamMembers();

      expect(await screen.findByText('8/1/2026')).toBeInTheDocument();
    });
  });

  describe('removing a member', () => {
    it('confirms and calls api.delete for another member', async () => {
      const user = userEvent.setup();
      mockGet();
      api.delete.mockResolvedValue(null);
      renderTeamMembers();

      await waitFor(() => screen.getByText(/✕ remove/i));
      await user.click(screen.getByText(/✕ remove/i));

      expect(globalThis.confirm).toHaveBeenCalled();
      await waitFor(() => {
        expect(api.delete).toHaveBeenCalledWith('/cpo/team-members/m2');
      });
    });

    it('offers "leave" wording on the caller\'s own row', async () => {
      mockGet();
      renderTeamMembers();
      await waitFor(() => screen.getByText(/✕ leave/i));
    });
  });

  describe('resetting a teammate password', () => {
    it('disables Save until 8 characters are entered, then posts', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockResolvedValue(mockMembers[1]);
      renderTeamMembers();

      await waitFor(() => screen.getAllByText(/reset pw/i));
      await user.click(screen.getAllByText(/reset pw/i)[1]);

      const input = screen.getByPlaceholderText(/Min 8 chars — not common/i);
      const saveButton = screen.getByRole('button', { name: /^Save$/i });

      await user.type(input, 'short');
      expect(saveButton).toBeDisabled();

      await user.type(input, 'enough1');
      expect(saveButton).toBeEnabled();

      await user.click(saveButton);
      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/cpo/team-members/m2/reset-password', {
          new_password: 'shortenough1',
        });
      });
    });
  });

  describe('invite links', () => {
    it('lists pending invites with a copyable link', async () => {
      mockGet({ invites: mockInvites });
      renderTeamMembers();

      await waitFor(() => {
        expect(screen.getByText(/invite-token-123/)).toBeInTheDocument();
      });
    });

    it('shows empty state with no pending invites', async () => {
      mockGet({ invites: [] });
      renderTeamMembers();

      await waitFor(() => {
        expect(screen.getByText(/No pending invite links/i)).toBeInTheDocument();
      });
    });

    it('creates an invite and reloads the list', async () => {
      const user = userEvent.setup();
      mockGet({ invites: [] });
      api.post.mockResolvedValue({ id: 'i2', token: 'new-token', created_at: '2026-01-01T00:00:00Z', expires_at: '2026-01-02T00:00:00Z' });
      renderTeamMembers();

      await waitFor(() => screen.getByRole('button', { name: /generate invite link/i }));
      await user.click(screen.getByRole('button', { name: /generate invite link/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/cpo/team-invites');
        expect(api.get).toHaveBeenCalledWith('/cpo/team-invites');
      });
    });

    it('revokes an invite after confirmation', async () => {
      const user = userEvent.setup();
      mockGet({ invites: mockInvites });
      api.delete.mockResolvedValue(null);
      renderTeamMembers();

      await waitFor(() => screen.getByText(/✕ revoke/i));
      await user.click(screen.getByText(/✕ revoke/i));

      expect(globalThis.confirm).toHaveBeenCalled();
      await waitFor(() => {
        expect(api.delete).toHaveBeenCalledWith('/cpo/team-invites/i1');
      });
    });
  });
});
