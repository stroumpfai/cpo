import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { LoginPage } from '../../pages/LoginPage.jsx';
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

function renderLoginPage() {
  return renderWithRouter(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/admin" element={<div>Admin Page</div>} />
      <Route path="/dashboard" element={<div>Dashboard Page</div>} />
    </Routes>,
    { initialEntries: ['/login'] }
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders username and password fields', () => {
    renderLoginPage();
    expect(screen.getByLabelText('Username')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  it('renders the login button', () => {
    renderLoginPage();
    expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument();
  });

  it('navigates to /admin on successful admin login', async () => {
    const user = userEvent.setup();
    api.post.mockResolvedValue({ token: 'fake-token', role: 'admin' });

    renderLoginPage();

    await user.type(screen.getByLabelText('Username'), 'admin');
    await user.type(screen.getByLabelText('Password'), 'password123');
    await user.click(screen.getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(screen.getByText('Admin Page')).toBeInTheDocument();
    });
  });

  it('navigates to /dashboard on successful CPO login', async () => {
    const user = userEvent.setup();
    api.post.mockResolvedValue({ token: 'fake-token', role: 'cpo' });

    renderLoginPage();

    await user.type(screen.getByLabelText('Username'), 'mycpo');
    await user.type(screen.getByLabelText('Password'), 'password123');
    await user.click(screen.getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(screen.getByText('Dashboard Page')).toBeInTheDocument();
    });
  });

  it('shows error message on failed login', async () => {
    const user = userEvent.setup();
    api.post.mockRejectedValue(new Error('Invalid credentials'));

    renderLoginPage();

    await user.type(screen.getByLabelText('Username'), 'wrong');
    await user.type(screen.getByLabelText('Password'), 'wrong');
    await user.click(screen.getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });
  });

  it('disables the submit button while loading', async () => {
    const user = userEvent.setup();
    // Never-resolving promise to keep loading state
    api.post.mockReturnValue(new Promise(() => {}));

    renderLoginPage();

    await user.type(screen.getByLabelText('Username'), 'user');
    await user.type(screen.getByLabelText('Password'), 'pass');

    const submitBtn = screen.getByRole('button', { name: /log in/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled();
    });
  });

  it('calls api.post with correct payload', async () => {
    const user = userEvent.setup();
    api.post.mockResolvedValue({ token: 'tok', role: 'cpo' });

    renderLoginPage();

    await user.type(screen.getByLabelText('Username'), 'myuser');
    await user.type(screen.getByLabelText('Password'), 'mypassword');
    await user.click(screen.getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/login', {
        username: 'myuser',
        password: 'mypassword',
      });
    });
  });
});
