import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { TeamOrderPage } from '../../pages/TeamOrderPage.jsx';
import { detectLanguage } from '../../i18n/detect.js';
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

function renderTeamOrderPage(link = 'testlink123', lng = undefined) {
  return renderWithRouter(
    <Routes>
      <Route path="/orders/:link" element={<TeamOrderPage />} />
    </Routes>,
    { initialEntries: [`/orders/${link}`], lng }
  );
}

const activeSession = {
  status: 'active',
  team_name: 'Dev Team',
  session_date: '2026-05-17',
  start_time: '10:00',
  end_time: '23:59',  // far-future end keeps countdown active for the full test run
  pizzeria_url: 'https://pizzeria.example.com',
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

const emailSession = { ...activeSession, member_identifier: 'email' };

function getStoredIdentity(link) {
  const all = JSON.parse(localStorage.getItem('cpo_member_identity') ?? '{}');
  return all[link] ?? { name: '', email: '' };
}

describe('TeamOrderPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Every test shares the link 'testlink123' and one jsdom localStorage. Without
    // this, a value persisted by an earlier test prefills the field and
    // userEvent.type appends to it instead of replacing.
    localStorage.clear();
  });

  afterEach(() => {
    // A test that fails mid-way must not leave fake timers installed for the rest.
    vi.useRealTimers();
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

    it('shows pizzeria URL link when pizzeria_url is set', async () => {
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();
      await waitFor(() => {
        const link = screen.getByRole('link', { name: /view online/i });
        expect(link).toBeInTheDocument();
        expect(link).toHaveAttribute('href', 'https://pizzeria.example.com');
      });
    });

    it('shows dash when pizzeria_url is not set', async () => {
      api.get.mockResolvedValue({ ...activeSession, pizzeria_url: null });
      renderTeamOrderPage();
      await waitFor(() => screen.getByText(/Restaurant menu/i));
      expect(screen.queryByRole('link', { name: /view online/i })).not.toBeInTheDocument();
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
      const rateLimitErr = Object.assign(new Error('Too many requests'), {
        status: 429, code: 'rate_limited', params: { seconds: 5 },
      });
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
      const closedErr = Object.assign(new Error('Session closed'), {
        status: 403, code: 'session_closed',
      });
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

  describe('email mode', () => {
    it('asks for an email instead of a name', async () => {
      api.get.mockResolvedValue(emailSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your email'));
      expect(screen.queryByLabelText('Your name')).not.toBeInTheDocument();
    });

    it('renders an email input with the right id', async () => {
      api.get.mockResolvedValue(emailSession);
      renderTeamOrderPage();

      const input = await screen.findByLabelText('Your email');
      expect(input).toHaveAttribute('type', 'email');
      expect(input).toHaveAttribute('id', 'order-email');
    });

    it('shows an error when adding to cart with an empty email', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(emailSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your email'));
      await user.click(screen.getByRole('button', { name: /add to your order/i }));

      expect(await screen.findByText('Enter an email first.')).toBeInTheDocument();
    });

    it('rejects a malformed email', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(emailSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your email'));
      await user.type(screen.getByLabelText('Your email'), 'notanemail');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));

      expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
    });

    it('adds a cart row showing the email', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(emailSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your email'));
      await user.type(screen.getByLabelText('Your email'), 'alice@example.com');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));

      expect(await screen.findByText('alice@example.com')).toBeInTheDocument();
    });

    it('posts the email as member_name', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(emailSession);
      api.post.mockResolvedValue({ status: 'submitted', orders_created: 1, order_ids: ['o1'] });
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your email'));
      await user.type(screen.getByLabelText('Your email'), 'alice@example.com');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));
      await user.click(screen.getByRole('button', { name: /submit order/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/orders/testlink123/submit', {
          items: [{ member_name: 'alice@example.com', pizza_id: 'p1', comment: null }],
        });
      });
    });

    it('blocks submit when the cart holds a name after a mode flip', async () => {
      // shouldAdvanceTime keeps promise/microtask flushing working while still
      // letting us jump the 20 s poll forward.
      vi.useFakeTimers({ shouldAdvanceTime: true });
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      // Session starts in name mode; the 20 s poll flips it to email mid-cart.
      api.get.mockResolvedValueOnce(activeSession).mockResolvedValue(emailSession);
      renderTeamOrderPage();

      await vi.waitFor(() => screen.getByLabelText('Your name'));
      await user.type(screen.getByLabelText('Your name'), 'Alice');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));

      await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
      await vi.waitFor(() => screen.getByLabelText('Your email'));

      await user.click(screen.getByRole('button', { name: /submit order/i }));

      expect(api.post).not.toHaveBeenCalled();
      expect(
        screen.getByText(/no longer valid email addresses/i)
      ).toBeInTheDocument();
      vi.useRealTimers();
    });

    it('still asks for a name when the server omits member_identifier', async () => {
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));
      expect(screen.queryByLabelText('Your email')).not.toBeInTheDocument();
    });
  });

  describe('identity persistence', () => {
    it('prefills the name field from localStorage', async () => {
      localStorage.setItem(
        'cpo_member_identity',
        JSON.stringify({ testlink123: { name: 'Alice', email: '' } })
      );
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();

      await waitFor(() => expect(screen.getByLabelText('Your name')).toHaveValue('Alice'));
    });

    it('keeps the value in the field after adding to the cart', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));
      await user.type(screen.getByLabelText('Your name'), 'Alice');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));

      expect(screen.getByLabelText('Your name')).toHaveValue('Alice');
    });

    it('does not persist before the order is submitted', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));
      await user.type(screen.getByLabelText('Your name'), 'Alice');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));

      expect(localStorage.getItem('cpo_member_identity')).toBeNull();
    });

    it('persists the value after a successful submit', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      api.post.mockResolvedValue({ status: 'submitted', orders_created: 1, order_ids: ['o1'] });
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));
      await user.type(screen.getByLabelText('Your name'), 'Alice');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));
      await user.click(screen.getByRole('button', { name: /submit order/i }));

      await waitFor(() => {
        expect(JSON.parse(localStorage.getItem('cpo_member_identity'))).toEqual({
          testlink123: { name: 'Alice', email: '' },
        });
      });
    });

    it('does not prefill the email field with a stored name', async () => {
      localStorage.setItem(
        'cpo_member_identity',
        JSON.stringify({ testlink123: { name: 'Alice', email: '' } })
      );
      api.get.mockResolvedValue(emailSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your email'));
      expect(screen.getByLabelText('Your email')).toHaveValue('');
    });

    it('does not leak one link\'s value into another', async () => {
      localStorage.setItem(
        'cpo_member_identity',
        JSON.stringify({ otherlink456: { name: 'Bob', email: '' } })
      );
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));
      expect(screen.getByLabelText('Your name')).toHaveValue('');
    });

    it('clears the remembered value via "not you? clear"', async () => {
      const user = userEvent.setup();
      localStorage.setItem(
        'cpo_member_identity',
        JSON.stringify({ testlink123: { name: 'Alice', email: '' } })
      );
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();

      await waitFor(() => expect(screen.getByLabelText('Your name')).toHaveValue('Alice'));
      await user.click(screen.getByRole('button', { name: /not you\? clear/i }));

      expect(screen.getByLabelText('Your name')).toHaveValue('');
      expect(getStoredIdentity('testlink123')).toEqual({ name: '', email: '' });
    });

    it('does not offer the clear link when nothing was remembered', async () => {
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));
      expect(screen.queryByRole('button', { name: /not you\? clear/i })).not.toBeInTheDocument();
    });
  });

  describe('translation', () => {
    const originalLanguages =
      Object.getOwnPropertyDescriptor(globalThis.navigator, 'languages');

    afterEach(() => {
      if (originalLanguages) {
        Object.defineProperty(globalThis.navigator, 'languages', originalLanguages);
      }
    });

    it('renders the order form in Swiss German', async () => {
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage('testlink123', 'de-CH');

      await waitFor(() => screen.getByLabelText('Dein Name'));
      expect(screen.getByText(/Bestelltag/)).toBeInTheDocument();
      expect(screen.getByText('Gericht auswählen')).toBeInTheDocument();
      expect(screen.getByText('Übersicht deiner Bestellung')).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: 'zur Bestellung hinzufügen' })
      ).toBeInTheDocument();
    });

    it('renders the closed-session state in Swiss German', async () => {
      api.get.mockResolvedValue(closedSession);
      renderTeamOrderPage('testlink123', 'de-CH');

      await waitFor(() => {
        expect(screen.getByText('Die Session ist geschlossen.')).toBeInTheDocument();
      });
      expect(screen.getByText('Heute keine Bestellungen mehr.')).toBeInTheDocument();
    });

    it('follows the browser language when it is one we ship', async () => {
      Object.defineProperty(globalThis.navigator, 'languages', {
        value: ['fr-CH', 'en'],
        configurable: true,
      });
      api.get.mockResolvedValue(activeSession);
      renderTeamOrderPage('testlink123', detectLanguage());

      await waitFor(() => screen.getByLabelText('Votre nom'));
      expect(screen.getByText(/jour de commande/)).toBeInTheDocument();
    });

    it('uses the singular plate count for one plate', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      api.post.mockResolvedValue({});
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));
      await user.type(screen.getByLabelText('Your name'), 'Alice');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));
      await user.click(screen.getByRole('button', { name: /submit order/i }));

      expect(await screen.findByText('1 plate heading to the CPO.')).toBeInTheDocument();
    });

    it('uses the plural plate count for two plates', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      api.post.mockResolvedValue({});
      renderTeamOrderPage();

      await waitFor(() => screen.getByLabelText('Your name'));
      await user.type(screen.getByLabelText('Your name'), 'Alice');
      await user.click(screen.getByRole('button', { name: /add to your order/i }));
      await user.click(screen.getByRole('button', { name: /add to your order/i }));
      await user.click(screen.getByRole('button', { name: /submit order/i }));

      expect(await screen.findByText('2 plates heading to the CPO.')).toBeInTheDocument();
    });

    it('translates the rate-limit banner', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      api.post.mockRejectedValue(
        Object.assign(new Error('Too many requests'), {
          status: 429, code: 'rate_limited', params: { seconds: 5 },
        })
      );
      renderTeamOrderPage('testlink123', 'de-CH');

      await waitFor(() => screen.getByLabelText('Dein Name'));
      await user.type(screen.getByLabelText('Dein Name'), 'Anna');
      await user.click(screen.getByRole('button', { name: 'zur Bestellung hinzufügen' }));
      await user.click(screen.getByRole('button', { name: /Bestellung abschicken/ }));

      expect(await screen.findByText(/Zu viele Bestellungen/)).toBeInTheDocument();
    });

    it('translates the closed-session banner and refreshes the status', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      api.post.mockRejectedValue(
        Object.assign(new Error('Session is closed'), {
          status: 403, code: 'session_closed',
        })
      );
      renderTeamOrderPage('testlink123', 'de-CH');

      await waitFor(() => screen.getByLabelText('Dein Name'));
      const callsBefore = api.get.mock.calls.length;
      await user.type(screen.getByLabelText('Dein Name'), 'Anna');
      await user.click(screen.getByRole('button', { name: 'zur Bestellung hinzufügen' }));
      await user.click(screen.getByRole('button', { name: /Bestellung abschicken/ }));

      expect(
        await screen.findByText(/keine Bestellungen mehr angenommen/)
      ).toBeInTheDocument();
      await waitFor(() => {
        expect(api.get.mock.calls.length).toBeGreaterThan(callsBefore);
      });
    });

    it('falls back to the English server message for an untranslated error', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(activeSession);
      api.post.mockRejectedValue(
        Object.assign(new Error('Database on fire'), { status: 500 })
      );
      renderTeamOrderPage('testlink123', 'de-CH');

      await waitFor(() => screen.getByLabelText('Dein Name'));
      await user.type(screen.getByLabelText('Dein Name'), 'Anna');
      await user.click(screen.getByRole('button', { name: 'zur Bestellung hinzufügen' }));
      await user.click(screen.getByRole('button', { name: /Bestellung abschicken/ }));

      expect(await screen.findByText('Database on fire')).toBeInTheDocument();
    });
  });
});
