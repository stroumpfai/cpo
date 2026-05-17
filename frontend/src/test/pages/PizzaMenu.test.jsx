import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { PizzaMenu } from '../../pages/PizzaMenu.jsx';
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

const mockPizzas = [
  { id: 'p1', name: 'Margherita', price: 12.5 },
  { id: 'p2', name: 'Pepperoni', price: 14.0 },
];

function renderPizzaMenu() {
  return renderWithRouter(
    <Routes>
      <Route path="/dashboard/pizzas" element={<PizzaMenu />} />
      <Route path="/dashboard" element={<div>Dashboard</div>} />
    </Routes>,
    { initialEntries: ['/dashboard/pizzas'] }
  );
}

describe('PizzaMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock confirm to avoid jsdom issues
    globalThis.confirm = vi.fn(() => true);
  });

  describe('loading state', () => {
    it('shows loading while fetching', () => {
      api.get.mockReturnValue(new Promise(() => {}));
      renderPizzaMenu();
      expect(screen.getByText('Loading…')).toBeInTheDocument();
    });
  });

  describe('listing pizzas', () => {
    it('lists pizzas from api.get', async () => {
      api.get.mockResolvedValue(mockPizzas);
      renderPizzaMenu();
      await waitFor(() => {
        expect(screen.getByText('Margherita')).toBeInTheDocument();
        expect(screen.getByText('Pepperoni')).toBeInTheDocument();
      });
    });

    it('renders prices formatted to 2 decimal places', async () => {
      api.get.mockResolvedValue(mockPizzas);
      renderPizzaMenu();
      await waitFor(() => {
        expect(screen.getByText('12.50')).toBeInTheDocument();
        expect(screen.getByText('14.00')).toBeInTheDocument();
      });
    });

    it('shows empty state when no pizzas', async () => {
      api.get.mockResolvedValue([]);
      renderPizzaMenu();
      await waitFor(() => {
        expect(screen.getByText(/No pizzas yet/)).toBeInTheDocument();
      });
    });
  });

  describe('adding a pizza', () => {
    it('submits correct payload when adding a new pizza', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue([]);
      api.post.mockResolvedValue({ id: 'p-new', name: 'Quattro Stagioni', price: 16.0 });

      renderPizzaMenu();

      await waitFor(() => screen.getByPlaceholderText(/type pizza name/i));

      await user.type(screen.getByPlaceholderText(/type pizza name/i), 'Quattro Stagioni');
      // Find the price input by placeholder
      await user.type(screen.getByPlaceholderText('0.00'), '16.00');

      await user.click(screen.getByRole('button', { name: /^add$/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/cpo/menu', {
          name: 'Quattro Stagioni',
          price: 16.0,
        });
      });
    });

    it('shows validation error when name is empty', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue([]);
      renderPizzaMenu();

      await waitFor(() => screen.getByPlaceholderText('0.00'));

      // Type price but no name
      await user.type(screen.getByPlaceholderText('0.00'), '10.00');
      // add button should be disabled without a name — so we check disabled state
      expect(screen.getByRole('button', { name: /^add$/i })).toBeDisabled();
    });

    it('reloads the menu after adding a pizza', async () => {
      const user = userEvent.setup();
      // First call returns empty, after add it returns one pizza
      api.get
        .mockResolvedValueOnce([])
        .mockResolvedValueOnce([{ id: 'p-new', name: 'Quattro Stagioni', price: 16.0 }]);
      api.post.mockResolvedValue({ id: 'p-new', name: 'Quattro Stagioni', price: 16.0 });

      renderPizzaMenu();

      await waitFor(() => screen.getByPlaceholderText(/type pizza name/i));

      await user.type(screen.getByPlaceholderText(/type pizza name/i), 'Quattro Stagioni');
      await user.type(screen.getByPlaceholderText('0.00'), '16.00');
      await user.click(screen.getByRole('button', { name: /^add$/i }));

      await waitFor(() => {
        expect(screen.getByText('Quattro Stagioni')).toBeInTheDocument();
      });
    });
  });

  describe('deleting a pizza', () => {
    it('calls api.delete when delete button is clicked and confirmed', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(mockPizzas);
      api.delete.mockResolvedValue(null);

      renderPizzaMenu();

      await waitFor(() => screen.getAllByText(/✕ delete/i));

      const deleteButtons = screen.getAllByText(/✕ delete/i);
      await user.click(deleteButtons[0]);

      expect(globalThis.confirm).toHaveBeenCalled();
      await waitFor(() => {
        expect(api.delete).toHaveBeenCalledWith('/cpo/menu/p1');
      });
    });

    it('does not call api.delete when confirm is cancelled', async () => {
      const user = userEvent.setup();
      globalThis.confirm = vi.fn(() => false);
      api.get.mockResolvedValue(mockPizzas);

      renderPizzaMenu();

      await waitFor(() => screen.getAllByText(/✕ delete/i));

      const deleteButtons = screen.getAllByText(/✕ delete/i);
      await user.click(deleteButtons[0]);

      expect(api.delete).not.toHaveBeenCalled();
    });
  });

  describe('page header', () => {
    it('renders page title', async () => {
      api.get.mockResolvedValue([]);
      renderPizzaMenu();
      expect(screen.getByText('List of Pizzas')).toBeInTheDocument();
    });

    it('has a close button that navigates to /dashboard', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue([]);
      renderPizzaMenu();

      await user.click(screen.getByRole('button', { name: /✕ close/i }));

      await waitFor(() => {
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });
    });
  });
});
