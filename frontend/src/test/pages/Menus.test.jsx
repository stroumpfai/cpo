import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { Menus } from '../../pages/Menus.jsx';
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

const mockMenus = [
  { id: 'm1', name: 'Pizzas', is_default: true, pizzeria_url: null, pizza_count: 2 },
  { id: 'm2', name: 'Thai', is_default: false, pizzeria_url: 'https://thai.example.com', pizza_count: 1 },
];

const mockPizzas = {
  m1: [
    { id: 'p1', name: 'Margherita', price: 12.5 },
    { id: 'p2', name: 'Pepperoni', price: 14.0 },
  ],
  m2: [{ id: 'p3', name: 'Pad Thai', price: 16.0 }],
};

// The page loads /cpo/menus + /cpo/me; the editor loads /cpo/menus/{id}/pizzas.
function mockGet(menus = mockMenus, pizzas = mockPizzas) {
  api.get.mockImplementation(url => {
    if (url === '/cpo/me') return Promise.resolve({ currency: 'CHF' });
    if (url === '/cpo/menus') return Promise.resolve(menus);
    const match = url.match(/^\/cpo\/menus\/([^/]+)\/pizzas$/);
    if (match) return Promise.resolve(pizzas[match[1]] ?? []);
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

function renderMenus() {
  return renderWithRouter(
    <Routes>
      <Route path="/dashboard/menus" element={<Menus />} />
      <Route path="/dashboard" element={<div>Dashboard</div>} />
    </Routes>,
    { initialEntries: ['/dashboard/menus'] }
  );
}

describe('Menus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.confirm = vi.fn(() => true);
  });

  describe('page header', () => {
    it('renders the Menus title', async () => {
      mockGet([]);
      renderMenus();
      expect(screen.getByText('Menus')).toBeInTheDocument();
    });
  });

  describe('menu list', () => {
    it('lists menus with default star and item counts', async () => {
      mockGet();
      renderMenus();
      await waitFor(() => {
        // "Pizzas" appears in the list row and the "Editing:" heading
        expect(screen.getAllByText('Pizzas').length).toBeGreaterThan(0);
        expect(screen.getByText('Thai')).toBeInTheDocument();
      });
      expect(screen.getByLabelText('Default menu')).toBeInTheDocument();
    });

    it('shows empty state when no menus exist', async () => {
      mockGet([]);
      renderMenus();
      await waitFor(() => {
        expect(screen.getByText(/No menus yet/)).toBeInTheDocument();
      });
    });

    it('selects the default menu and shows its items', async () => {
      mockGet();
      renderMenus();
      await waitFor(() => {
        expect(screen.getByText('Margherita')).toBeInTheDocument();
        expect(screen.getByText('Pepperoni')).toBeInTheDocument();
      });
    });

    it('clicking another menu loads its items', async () => {
      const user = userEvent.setup();
      mockGet();
      renderMenus();
      await waitFor(() => screen.getByText('Thai'));

      await user.click(screen.getByText('Thai'));

      await waitFor(() => {
        expect(screen.getByText('Pad Thai')).toBeInTheDocument();
      });
      expect(api.get).toHaveBeenCalledWith('/cpo/menus/m2/pizzas');
    });
  });

  describe('creating a menu', () => {
    it('posts the new menu name and selects it', async () => {
      const user = userEvent.setup();
      mockGet([]);
      api.post.mockResolvedValue({ id: 'm-new', name: 'Burgers', is_default: true, pizzeria_url: null, pizza_count: 0 });

      renderMenus();
      await waitFor(() => screen.getByPlaceholderText(/new menu name/i));

      await user.type(screen.getByPlaceholderText(/new menu name/i), 'Burgers');
      await user.click(screen.getByRole('button', { name: /\+ new menu/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/cpo/menus', { name: 'Burgers' });
      });
    });

    it('disables the create button without a name', async () => {
      mockGet([]);
      renderMenus();
      await waitFor(() => screen.getByPlaceholderText(/new menu name/i));
      expect(screen.getByRole('button', { name: /\+ new menu/i })).toBeDisabled();
    });
  });

  describe('renaming a menu', () => {
    it('patches the new name', async () => {
      const user = userEvent.setup();
      mockGet();
      api.patch.mockResolvedValue({ ...mockMenus[1], name: 'Thai Corner' });

      renderMenus();
      await waitFor(() => screen.getAllByText(/✎ rename/i));

      await user.click(screen.getAllByText(/✎ rename/i)[1]);
      const input = screen.getByDisplayValue('Thai');
      await user.clear(input);
      await user.type(input, 'Thai Corner');
      // The editor's URL card also has a "save" button; the rename save comes first
      await user.click(screen.getAllByRole('button', { name: /^save$/i })[0]);

      await waitFor(() => {
        expect(api.patch).toHaveBeenCalledWith('/cpo/menus/m2', { name: 'Thai Corner' });
      });
    });
  });

  describe('default menu', () => {
    it('posts to /default when the empty star is clicked', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockResolvedValue(null);

      renderMenus();
      await waitFor(() => screen.getByRole('button', { name: /make default/i }));

      await user.click(screen.getByRole('button', { name: /make default/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/cpo/menus/m2/default');
      });
    });

    it('marks the default menu with an inert star and the rest with a clickable one', async () => {
      mockGet();
      renderMenus();
      await waitFor(() => screen.getByLabelText('Default menu'));
      // m1 carries the filled star, m2 the empty (clickable) one — one each
      expect(screen.getAllByLabelText('Default menu')).toHaveLength(1);
      expect(screen.getAllByRole('button', { name: /make default/i })).toHaveLength(1);
    });
  });

  describe('deleting a menu', () => {
    it('calls api.delete when confirmed', async () => {
      const user = userEvent.setup();
      mockGet();
      api.delete.mockResolvedValue(null);

      renderMenus();
      await waitFor(() => screen.getAllByText(/✕ delete/i));

      // First row's delete button (the editor's item rows also have delete buttons,
      // so scope to the first ones which belong to the menu list)
      await user.click(screen.getAllByText(/✕ delete/i)[0]);

      expect(globalThis.confirm).toHaveBeenCalled();
      await waitFor(() => {
        expect(api.delete).toHaveBeenCalledWith('/cpo/menus/m1');
      });
    });

    it('surfaces the server error when deletion is rejected (menu in use)', async () => {
      const user = userEvent.setup();
      mockGet();
      api.delete.mockRejectedValue(new Error('Menu is used by an active or upcoming session'));

      renderMenus();
      await waitFor(() => screen.getAllByText(/✕ delete/i));

      await user.click(screen.getAllByText(/✕ delete/i)[0]);

      await waitFor(() => {
        expect(screen.getByText(/used by an active or upcoming session/i)).toBeInTheDocument();
      });
    });
  });

  describe('menu editor integration', () => {
    it('adds an item to the selected menu', async () => {
      const user = userEvent.setup();
      mockGet();
      api.post.mockResolvedValue({ id: 'p-new', name: 'Quattro Stagioni', price: 16.0 });

      renderMenus();
      await waitFor(() => screen.getByPlaceholderText(/type item name/i));

      await user.type(screen.getByPlaceholderText(/type item name/i), 'Quattro Stagioni');
      await user.type(screen.getByPlaceholderText('0.00'), '16.00');
      await user.click(screen.getByRole('button', { name: /^add$/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/cpo/menus/m1/pizzas', {
          name: 'Quattro Stagioni',
          price: 16.0,
        });
      });
    });

    it('deletes an item from the selected menu', async () => {
      const user = userEvent.setup();
      mockGet();
      api.delete.mockResolvedValue(null);

      renderMenus();
      await waitFor(() => screen.getByText('Margherita'));

      // Menu-list rows have 2 delete buttons; item rows follow (Margherita, Pepperoni)
      const deleteButtons = screen.getAllByText(/✕ delete/i);
      await user.click(deleteButtons[2]);

      await waitFor(() => {
        expect(api.delete).toHaveBeenCalledWith('/cpo/menus/m1/pizzas/p1');
      });
    });

    it('shows the restaurant website field with the menu url', async () => {
      const user = userEvent.setup();
      mockGet();
      renderMenus();
      await waitFor(() => screen.getByText('Thai'));

      await user.click(screen.getByText('Thai'));

      await waitFor(() => {
        expect(screen.getByLabelText(/Restaurant website/i)).toHaveValue('https://thai.example.com');
      });
    });

    it('shows the item empty state for an empty menu', async () => {
      mockGet(
        [{ id: 'm1', name: 'Pizzas', is_default: true, pizzeria_url: null, pizza_count: 0 }],
        { m1: [] }
      );
      renderMenus();
      await waitFor(() => {
        expect(screen.getByText(/No items yet/)).toBeInTheDocument();
      });
    });
  });
});
