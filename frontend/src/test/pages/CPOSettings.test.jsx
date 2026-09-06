import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CPOSettings } from '../../pages/CPOSettings.jsx';
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

const mockCpo = {
  id: 'c1',
  username: 'john',
  email: 'john@example.com',
  team_name: 'Engineering',
  unique_link: 'abcdefghij123456',
  created_at: '2026-01-01T00:00:00Z',
  currency: 'CHF',
  member_identifier: 'name',
  default_grace_period_minutes: 2,
};

function renderSettings() {
  return renderWithRouter(<CPOSettings />, { initialEntries: ['/dashboard/settings'] });
}

describe('CPOSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    api.patch.mockResolvedValue(mockCpo);
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('loading', () => {
    it('does not overwrite what the user edited while /cpo/me was in flight', async () => {
      const user = userEvent.setup();
      let resolveProfile;
      api.get.mockReturnValue(new Promise(resolve => { resolveProfile = resolve; }));
      renderSettings();

      // The form is interactive before the profile lands — a fast user gets there first.
      await user.selectOptions(screen.getByLabelText(/identify themselves by/i), 'email');
      await user.clear(screen.getByLabelText('Currency unit'));
      await user.type(screen.getByLabelText('Currency unit'), 'EUR');

      resolveProfile({ ...mockCpo, member_identifier: 'name', currency: 'CHF', team_name: 'Engineering' });

      // The untouched field hydrates; the edited ones keep the user's input.
      await waitFor(() => expect(screen.getByLabelText('Team name')).toHaveValue('Engineering'));
      expect(screen.getByLabelText(/identify themselves by/i)).toHaveValue('email');
      expect(screen.getByLabelText('Currency unit')).toHaveValue('EUR');
    });

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

    it('loads the account language from /cpo/me', async () => {
      api.get.mockResolvedValue({ ...mockCpo, language: 'de-CH' });
      renderSettings();

      await waitFor(() => {
        expect(screen.getByLabelText('Language')).toHaveValue('de-CH');
      });
    });

    it('shows "Follow my browser" when the account has no language', async () => {
      api.get.mockResolvedValue({ ...mockCpo, language: null });
      renderSettings();

      await waitFor(() => {
        expect(screen.getByLabelText('Language')).toHaveValue('');
      });
    });

    it('loads the default grace period from /cpo/me', async () => {
      api.get.mockResolvedValue({ ...mockCpo, default_grace_period_minutes: 5 });
      renderSettings();

      expect(await screen.findByText('5')).toBeInTheDocument();
    });

    it('renders the "applies to new orders only" hint', async () => {
      api.get.mockResolvedValue(mockCpo);
      renderSettings();

      expect(
        await screen.findByText(/Applies to new orders only/i)
      ).toBeInTheDocument();
    });
  });

  describe('translated', () => {
    it('renders the preferences card in German', async () => {
      api.get.mockResolvedValue({ ...mockCpo, language: 'de-CH' });
      renderWithLanguage(<CPOSettings />, { lng: 'de-CH', initialEntries: ['/dashboard/settings'] });

      expect(await screen.findByText('Deine Einstellungen')).toBeInTheDocument();
      expect(screen.getByLabelText('Sprache')).toHaveValue('de-CH');
      expect(screen.getByRole('option', { name: 'Meinem Browser folgen' })).toBeInTheDocument();
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

    it('issues a PATCH for the default grace period', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(mockCpo);
      renderSettings();

      await waitFor(() => screen.getByLabelText(/identify themselves by/i));
      await user.click(screen.getByRole('button', { name: '+' }));
      await user.click(screen.getByRole('button', { name: /^save$/i }));

      await waitFor(() => {
        expect(api.patch).toHaveBeenCalledWith('/cpo/default-grace-period', {
          default_grace_period_minutes: 3,
        });
      });
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

    it('issues the language PATCH alongside the team settings', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(mockCpo);
      renderSettings();

      await waitFor(() => screen.getByLabelText('Language'));
      await user.selectOptions(screen.getByLabelText('Language'), 'de-CH');
      await user.click(screen.getByRole('button', { name: /^save$/i }));

      await waitFor(() => {
        expect(api.patch).toHaveBeenCalledWith('/cpo/language', { language: 'de-CH' });
      });
    });

    it('applies the new language immediately without logging out', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue(mockCpo);
      renderSettings();

      await waitFor(() => screen.getByLabelText('Language'));
      await user.selectOptions(screen.getByLabelText('Language'), 'de-CH');
      await user.click(screen.getByRole('button', { name: /^save$/i }));

      // The page itself flips — unlike the password form, nothing signs out
      expect(await screen.findByText('Einstellungen')).toBeInTheDocument();
      expect(api.post).not.toHaveBeenCalled();
    });

    it('sends null when "Follow my browser" is picked', async () => {
      const user = userEvent.setup();
      api.get.mockResolvedValue({ ...mockCpo, language: 'fr-CH' });
      renderSettings();

      await waitFor(() => expect(screen.getByLabelText('Language')).toHaveValue('fr-CH'));
      await user.selectOptions(screen.getByLabelText('Language'), '');
      await user.click(screen.getByRole('button', { name: /^save$/i }));

      await waitFor(() => {
        expect(api.patch).toHaveBeenCalledWith('/cpo/language', { language: null });
      });
      expect(localStorage.getItem('cpo_lang')).toBeNull();
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
