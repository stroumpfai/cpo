import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { NewSession } from '../../pages/NewSession.jsx';
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

const mockCpo = {
  username: 'john',
  team_name: 'Engineering',
  unique_link: 'abcdef1234567890',
  currency: 'CHF',
};

const mockMenus = [
  { id: 'm1', name: 'Pizzas', is_default: false, pizzeria_url: null, pizza_count: 2 },
  { id: 'm2', name: 'Thai', is_default: true, pizzeria_url: null, pizza_count: 1 },
];

function mockGet({ menus = mockMenus, sessions = [] } = {}) {
  api.get.mockImplementation(url => {
    if (url === '/cpo/me') return Promise.resolve(mockCpo);
    if (url === '/cpo/menus') return Promise.resolve(menus);
    if (url === '/cpo/sessions') return Promise.resolve(sessions);
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

function renderNewSession() {
  return renderWithRouter(
    <Routes>
      <Route path="/dashboard/new-session" element={<NewSession />} />
      <Route path="/dashboard" element={<div>Dashboard</div>} />
      <Route path="/dashboard/menus" element={<div>Menus page</div>} />
    </Routes>,
    { initialEntries: ['/dashboard/new-session'] }
  );
}

describe('NewSession', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // The form pre-fills "now" and "an hour from now" and refuses a window that
    // has passed or spans midnight, so a real clock made these tests fail when
    // the suite happened to run within an hour of midnight. Fake Date only —
    // userEvent needs the real setTimeout.
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 0, 15, 12, 0, 0));   // local noon
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('menu dropdown', () => {
    it('lists all menus as options', async () => {
      mockGet();
      renderNewSession();
      await waitFor(() => {
        expect(screen.getByRole('option', { name: 'Pizzas' })).toBeInTheDocument();
        expect(screen.getByRole('option', { name: 'Thai' })).toBeInTheDocument();
      });
    });

    it('preselects the default menu', async () => {
      mockGet();
      renderNewSession();
      await waitFor(() => {
        expect(screen.getByLabelText('Menu')).toHaveValue('m2');
      });
    });

    it('includes the selected menu_id in the session payload', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockResolvedValue({ id: 's1' });

      renderNewSession();
      await waitFor(() => screen.getByLabelText('Menu'));

      await user.selectOptions(screen.getByLabelText('Menu'), 'm1');
      await user.click(screen.getByRole('button', { name: /Open session/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith(
          '/cpo/sessions',
          expect.objectContaining({ menu_id: 'm1' })
        );
      });
    });
  });

  describe('default times', () => {
    it('pre-fills an hour ahead during the day', async () => {
      mockGet();
      renderNewSession();
      await waitFor(() => screen.getByLabelText('Menu'));

      expect(screen.getByLabelText('Start time')).toHaveValue('12:00');
      expect(screen.getByLabelText('End time')).toHaveValue('13:00');
    });

    it('clamps the pre-filled end time to 23:59 late at night', async () => {
      // An hour past 23:30 is 00:30 tomorrow, which the form rejects as
      // midnight-spanning — so the default must clamp instead of wrapping.
      vi.setSystemTime(new Date(2026, 0, 15, 23, 30, 0));
      mockGet();
      renderNewSession();
      await waitFor(() => screen.getByLabelText('Menu'));

      expect(screen.getByLabelText('Start time')).toHaveValue('23:30');
      expect(screen.getByLabelText('End time')).toHaveValue('23:59');
    });

    it('submits the late-night defaults without a midnight-spanning error', async () => {
      const user = userEvent.setup();
      vi.setSystemTime(new Date(2026, 0, 15, 23, 30, 0));
      mockGet();
      api.post.mockResolvedValue({ id: 's1' });

      renderNewSession();
      await waitFor(() => screen.getByLabelText('Menu'));
      await user.click(screen.getByRole('button', { name: /Open session/i }));

      await waitFor(() => expect(api.post).toHaveBeenCalled());
      expect(
        screen.queryByText(/Sessions spanning midnight are not supported/i)
      ).not.toBeInTheDocument();
    });
  });

  describe('default grace period', () => {
    it('submits the team default grace period when the CPO does not touch the stepper', async () => {
      api.get.mockImplementation(url => {
        if (url === '/cpo/me') return Promise.resolve({ ...mockCpo, default_grace_period_minutes: 10 });
        if (url === '/cpo/menus') return Promise.resolve(mockMenus);
        if (url === '/cpo/sessions') return Promise.resolve([]);
        return Promise.reject(new Error(`unexpected GET ${url}`));
      });
      api.post.mockResolvedValue({ id: 's1' });
      const user = userEvent.setup();

      renderNewSession();
      await waitFor(() => screen.getByLabelText('Menu'));
      await user.click(screen.getByRole('button', { name: /Open session/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith(
          '/cpo/sessions',
          expect.objectContaining({ grace_period_minutes: 10 })
        );
      });
    });

    it('keeps a manually adjusted grace period even after /cpo/me resolves', async () => {
      const user = userEvent.setup();
      let resolveProfile;
      api.get.mockImplementation(url => {
        if (url === '/cpo/me') return new Promise(resolve => { resolveProfile = resolve; });
        if (url === '/cpo/menus') return Promise.resolve(mockMenus);
        if (url === '/cpo/sessions') return Promise.resolve([]);
        return Promise.reject(new Error(`unexpected GET ${url}`));
      });
      api.post.mockResolvedValue({ id: 's1' });

      renderNewSession();
      await waitFor(() => screen.getByLabelText('Menu'));
      await user.click(screen.getByRole('button', { name: '+' }));   // grace now 3, before /cpo/me lands

      resolveProfile({ ...mockCpo, default_grace_period_minutes: 10 });

      await user.click(screen.getByRole('button', { name: /Open session/i }));
      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith(
          '/cpo/sessions',
          expect.objectContaining({ grace_period_minutes: 3 })
        );
      });
    });
  });

  describe('midnight-spanning sessions', () => {
    it('rejects end time <= start time without calling the API', async () => {
      const user = userEvent.setup();
      mockGet();
      renderNewSession();
      await waitFor(() => screen.getByLabelText('Menu'));

      const startInput = screen.getByLabelText('Start time');
      const endInput = screen.getByLabelText('End time');
      await user.clear(startInput);
      await user.type(startInput, '23:00');
      await user.clear(endInput);
      await user.type(endInput, '01:00');

      await user.click(screen.getByRole('button', { name: /Open session/i }));

      await waitFor(() => {
        expect(screen.getByText(/Sessions spanning midnight are not supported/i)).toBeInTheDocument();
      });
      expect(api.post).not.toHaveBeenCalled();
    });
  });

  describe('without menus', () => {
    it('shows a hint linking to the Menus page and disables submit', async () => {
      mockGet({ menus: [] });
      renderNewSession();

      await waitFor(() => {
        expect(screen.getByText(/You need a menu before opening a session/i)).toBeInTheDocument();
      });
      expect(screen.getByRole('link', { name: 'Menus' })).toHaveAttribute('href', '/dashboard/menus');
      expect(screen.getByRole('button', { name: /Open session/i })).toBeDisabled();
    });
  });
});
