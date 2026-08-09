import { screen, waitFor } from '@testing-library/react';
import { Sidebar } from '../../components/Sidebar.jsx';
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
  team_name: 'Engineering',
  language: null,
};

function mockGet(cpo = mockCpo) {
  api.get.mockImplementation(path => {
    if (path === '/cpo/me') return Promise.resolve(cpo);
    return Promise.resolve({});          // /version
  });
}

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders the nav entries and the team name', async () => {
    mockGet();
    renderWithRouter(<Sidebar />);

    expect(await screen.findByText('Engineering')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open a new session' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Menus' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Statistics' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Team' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Settings' })).toBeInTheDocument();
  });

  it('applies the account language from /cpo/me', async () => {
    mockGet({ ...mockCpo, language: 'de-CH' });
    renderWithRouter(<Sidebar />);

    expect(await screen.findByRole('link', { name: 'Menüs' })).toBeInTheDocument();
    // Mirrored so the next page load renders German before the profile arrives
    expect(localStorage.getItem('cpo_lang')).toBe('de-CH');
  });

  it('leaves a language the user picked alone when the account has no preference', async () => {
    // `null` on the account means "no opinion, follow the browser" — it must not
    // undo a choice made in the switcher. Only "Follow my browser" in settings
    // clears the mirror, and it does so directly.
    localStorage.setItem('cpo_lang', 'de-CH');
    mockGet();                                   // language: null
    renderWithRouter(<Sidebar />);

    await screen.findByText('Engineering');
    expect(localStorage.getItem('cpo_lang')).toBe('de-CH');
  });
});
