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
