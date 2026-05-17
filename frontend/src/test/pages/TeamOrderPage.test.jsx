import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { TeamOrderPage } from '../../pages/TeamOrderPage.jsx';
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

function renderTeamOrderPage(link = 'testlink123') {
  return renderWithRouter(
    <Routes>
      <Route path="/orders/:link" element={<TeamOrderPage />} />
    </Routes>,
    { initialEntries: [`/orders/${link}`] }
  );
}

const activeSession = {
  status: 'active',
  team_name: 'Dev Team',
  session_date: '2026-05-17',
  start_time: '10:00',
  end_time: '23:59',  // far-future end keeps countdown active for the full test run
  pizzas: [
    { id: 'p1', name: 'Margherita', price: 12.5 },
    { id: 'p2', name: 'Pepperoni', price: 14 },
  ],
};

const closedSession = {
  status: 'closed',
  team_name: 'Dev Team',
  session_date: '2026-05-17',
  start_time: '10:00',
  end_time: '12:00',
  pizzas: [],
};

describe('TeamOrderPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('loading state', () => {
    it('shows loading indicator initially', () => {
      // api.get never resolves during this test
      api.get.mockReturnValue(new Promise(() => {}));
      renderTeamOrderPage();
      expect(screen.getByText('Loading…')).toBeInTheDocument();
    });
  });

  describe('closed session', () => {
    it('shows "Session is closed." when session status is not active', async () => {
      api.get.mockResolvedValue(closedSession);
      renderTeamOrderPage();
      await waitFor(() => {
        expect(screen.getByText('Session is closed.')).toBeInTheDocument();
      });
    });

    it('shows "No more orders for today."', async () => {
      api.get.mockResolvedValue(closedSession);
      renderTeamOrderPage();
      await waitFor(() => {
        expect(screen.getByText('No more orders for today.')).toBeInTheDocument();
      });
    });
  });

  describe('active session', () => {
    it('shows pizza options in the select', async () => {
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();
      await waitFor(() => {
        expect(screen.getByText(/Margherita/)).toBeInTheDocument();
        expect(screen.getByText(/Pepperoni/)).toBeInTheDocument();
      });
    });

    it('shows team name in the header', async () => {
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();
      await waitFor(() => {
        expect(screen.getByText(/Dev Team/)).toBeInTheDocument();
      });
    });

    it('shows name input field', async () => {
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();
      await waitFor(() => {
        expect(screen.getByLabelText('Your name')).toBeInTheDocument();
      });
    });
  });

  describe('cart behavior', () => {
    it('shows error when adding to cart without a name', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByText(/Margherita/));

      // Do not enter a name, just click add
      await user.click(screen.getByRole('button', { name: /add to your order/i }));

      expect(screen.getByText('Enter a name first.')).toBeInTheDocument();
    });

    it('adds a row to the cart when name and pizza are provided', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));

      await user.type(screen.getByLabelText('Your name'), 'Alice');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));

      // Cart should show the pizza and the name baked into the row
      await waitFor(() => {
        expect(screen.getByTitle('Remove')).toBeInTheDocument();
        expect(screen.getByText('Alice')).toBeInTheDocument();
      });
    });

    it('removes a row from cart when remove button is clicked', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));

      await user.type(screen.getByLabelText('Your name'), 'Bob');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));

      // Now click the remove button (✕) in the cart
      await waitFor(() => screen.getAllByTitle('Remove'));
      const removeButtons = screen.getAllByTitle('Remove');
      await user.click(removeButtons[0]);

      // Cart should be empty again
      expect(screen.getByText('Nothing added yet.')).toBeInTheDocument();
    });
  });

  describe('order submission', () => {
    it('sends correct payload on submit', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      api.post.mockResolvedValue({});
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));

      await user.type(screen.getByLabelText('Your name'), 'Charlie');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));

      await waitFor(() => screen.getByRole('button', { name: /submit order/i }));
      await user.click(screen.getByRole('button', { name: /submit order/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith(
          '/orders/testlink123/submit',
          expect.objectContaining({
            items: expect.arrayContaining([
              expect.objectContaining({ member_name: 'Charlie', pizza_id: 'p1' }),
            ]),
          })
        );
      });
    });

    it('shows order placed confirmation after successful submit', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      api.post.mockResolvedValue({});
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));

      await user.type(screen.getByLabelText('Your name'), 'Dave');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));

      await waitFor(() => screen.getByRole('button', { name: /submit order/i }));
      await user.click(screen.getByRole('button', { name: /submit order/i }));

      await waitFor(() => {
        expect(screen.getByText('Order placed!')).toBeInTheDocument();
      });
    });

    it('shows rate-limit error on 429 response', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      const rateLimitErr = Object.assign(new Error('Too many requests'), { status: 429 });
      api.post.mockRejectedValue(rateLimitErr);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));

      await user.type(screen.getByLabelText('Your name'), 'Eve');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));
      await waitFor(() => screen.getByRole('button', { name: /submit order/i }));
      await user.click(screen.getByRole('button', { name: /submit order/i }));

      await waitFor(() => {
        expect(screen.getByText(/Too many orders/i)).toBeInTheDocument();
      });
    });

    it('shows session closed error on 403 response', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      const closedErr = Object.assign(new Error('Session closed'), { status: 403 });
      api.post.mockRejectedValue(closedErr);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));

      await user.type(screen.getByLabelText('Your name'), 'Frank');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));
      await waitFor(() => screen.getByRole('button', { name: /submit order/i }));
      await user.click(screen.getByRole('button', { name: /submit order/i }));

      await waitFor(() => {
        expect(screen.getByText(/Session is closed — no more orders accepted/i)).toBeInTheDocument();
      });
    });
  });
});
