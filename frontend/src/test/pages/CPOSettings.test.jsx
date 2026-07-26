import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CPOSettings } from '../../pages/CPOSettings.jsx';
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

const mockCpo = {
  id: 'c1',
  username: 'john',
  email: 'john@example.com',
  team_name: 'Engineering',
  unique_link: 'abcdefghij123456',
  created_at: '2026-01-01T00:00:00Z',
  currency: 'CHF',
  member_identifier: 'name',
};

function renderSettings() {
  return renderWithRouter(<CPOSettings />, { initialEntries: ['/dashboard/settings'] });
}

describe('CPOSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.patch.mockResolvedValue(mockCpo);
  });

  describe('loading', () => {
    it('loads team name, currency and member identifier from /cpo/me', async () => {
      api.get.mockResolvedValue({ ...mockCpo, member_identifier: 'email', currency: 'EUR' });
      renderSettings();

      await waitFor(() => {
        expect(screen.getByLabelText('Team name')).toHaveValue('Engineering');
      });
      expect(screen.getByLabelText('Currency unit')).toHaveValue('EUR');
      expect(screen.getByLabelText(/identify themselves by/i)).toHaveValue('email');
    });

    it('defaults the select to name when the server omits the field', async () => {
      const { member_identifier, ...withoutField } = mockCpo;   // eslint-disable-line no-unused-vars
      api.get.mockResolvedValue(withoutField);
      renderSettings();

      await waitFor(() => {
        expect(screen.getByLabelText(/identify themselves by/i)).toHaveValue('name');
      });
    });

    it('renders the "applies to new orders only" hint', async () => {
      api.get.mockResolvedValue(mockCpo);
      renderSettings();

      expect(
        await screen.findByText(/Applies to new orders only/i)
      ).toBeInTheDocument();
    });
  });

  describe('saving', () => {
    it('issues all three PATCHes including member-identifier', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(mockCpo);
      renderSettings();

      await waitFor(() => screen.getByLabelText(/identify themselves by/i));
      await user.selectOptions(screen.getByLabelText(/identify themselves by/i), 'email');
      await user.click(screen.getByRole('button', { name: /^save$/i }));

      await waitFor(() => {
        expect(api.patch).toHaveBeenCalledWith('/cpo/member-identifier', {
          member_identifier: 'email',
        });
      });
      expect(api.patch).toHaveBeenCalledWith('/cpo/team-name', { team_name: 'Engineering' });
      expect(api.patch).toHaveBeenCalledWith('/cpo/currency', { currency: 'CHF' });
    });

    it('shows "Saved." when all three resolve', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(mockCpo);
      renderSettings();

      await waitFor(() => screen.getByLabelText(/identify themselves by/i));
      await user.click(screen.getByRole('button', { name: /^save$/i }));

      expect(await screen.findByText('Saved.')).toBeInTheDocument();
    });

    it('shows a field error and no "Saved." when the identifier PATCH rejects', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(mockCpo);
      api.patch.mockImplementation(path =>
        path === '/cpo/member-identifier'
          ? Promise.reject(new Error('Bad identifier'))
          : Promise.resolve(mockCpo)
      );
      renderSettings();

      await waitFor(() => screen.getByLabelText(/identify themselves by/i));
      await user.click(screen.getByRole('button', { name: /^save$/i }));

      expect(await screen.findByText('Bad identifier')).toBeInTheDocument();
      expect(screen.queryByText('Saved.')).not.toBeInTheDocument();
    });

    it('clears a previous error when the select changes', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(mockCpo);
      api.patch.mockImplementation(path =>
        path === '/cpo/member-identifier'
          ? Promise.reject(new Error('Bad identifier'))
          : Promise.resolve(mockCpo)
      );
      renderSettings();

      await waitFor(() => screen.getByLabelText(/identify themselves by/i));
      await user.click(screen.getByRole('button', { name: /^save$/i }));
      await screen.findByText('Bad identifier');

      await user.selectOptions(screen.getByLabelText(/identify themselves by/i), 'email');

      expect(screen.queryByText('Bad identifier')).not.toBeInTheDocument();
    });
  });
});
