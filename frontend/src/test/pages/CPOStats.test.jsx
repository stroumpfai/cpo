import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CPOStats } from '../../pages/CPOStats.jsx';
import { renderWithRouter } from '../utils.jsx';

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

const emptyStats = {
  recent_sessions: [],
  menus: [],
  total_sessions: 0,
  distinct_members: 0,
  distinct_plates: 0,
  stats_reset_at: null,
};

const populatedStats = {
  recent_sessions: [
    {
      session_id: 's1',
      session_date: '2026-07-20',
      start_time: '11:00',
      end_time: '12:00',
      status: 'closed',
      item_count: 5,
    },
  ],
  menus: [
    {
      menu_id: 'm1',
      menu_name: 'Default',
      use_count: 3,
      top_plates: [
        { pizza_name: 'Margherita', count: 4 },
        { pizza_name: 'Pepperoni', count: 2 },
      ],
      top_people: [
        { member_name: 'Alice', count: 3 },
      ],
    },
  ],
  total_sessions: 3,
  distinct_members: 4,
  distinct_plates: 2,
  stats_reset_at: null,
};

function renderStats() {
  return renderWithRouter(<CPOStats />, { initialEntries: ['/dashboard/stats'] });
}

describe('CPOStats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows a loading indicator before data arrives', () => {
    api.get.mockReturnValue(new Promise(() => {}));
    renderStats();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('shows an error message when the fetch fails', async () => {
    api.get.mockRejectedValue(new Error('Boom'));
    renderStats();
    expect(await screen.findByText('Boom')).toBeInTheDocument();
  });

  describe('empty state', () => {
    it('renders zeroed totals and empty-state cards', async () => {
      api.get.mockResolvedValue(emptyStats);
      renderStats();

      await waitFor(() => expect(screen.getByText('Statistics')).toBeInTheDocument());
      expect(screen.getByText("Counting your team's full history.")).toBeInTheDocument();
      expect(screen.getByText('No sessions yet.')).toBeInTheDocument();
      expect(screen.getByText('No menus yet.')).toBeInTheDocument();
    });
  });

  describe('populated state', () => {
    it('renders recent sessions, menu stats and general totals', async () => {
      api.get.mockResolvedValue(populatedStats);
      renderStats();

      await waitFor(() => expect(screen.getByText('Default')).toBeInTheDocument());
      expect(screen.getByText('Margherita')).toBeInTheDocument();
      expect(screen.getByText('Pepperoni')).toBeInTheDocument();
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();   // total_sessions stat card
      expect(screen.getByText('4')).toBeInTheDocument();   // distinct_members stat card
    });

    it('shows the reset cutoff caption when stats_reset_at is set', async () => {
      api.get.mockResolvedValue({ ...populatedStats, stats_reset_at: '2026-07-25T10:00:00Z' });
      renderStats();

      expect(await screen.findByText(/Counting since/)).toBeInTheDocument();
    });
  });

  describe('reset counters', () => {
    it('does nothing if the confirm dialog is dismissed', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(populatedStats);
      vi.spyOn(globalThis, 'confirm').mockReturnValue(false);
      renderStats();

      await waitFor(() => screen.getByRole('button', { name: /reset counters/i }));
      await user.click(screen.getByRole('button', { name: /reset counters/i }));

      expect(api.post).not.toHaveBeenCalled();
    });

    it('calls the reset endpoint and re-renders with the response when confirmed', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(populatedStats);
      api.post.mockResolvedValue({ ...emptyStats, stats_reset_at: '2026-07-26T12:00:00Z' });
      vi.spyOn(globalThis, 'confirm').mockReturnValue(true);
      renderStats();

      await waitFor(() => screen.getByRole('button', { name: /reset counters/i }));
      await user.click(screen.getByRole('button', { name: /reset counters/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/cpo/stats/reset', {});
      });
      expect(await screen.findByText('No sessions yet.')).toBeInTheDocument();
      expect(await screen.findByText(/Counting since/)).toBeInTheDocument();
    });
  });
});
