import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { JoinPage } from '../../pages/JoinPage.jsx';
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

function renderJoinPage(token = 'abc123') {
  return renderWithRouter(
    <Routes>
      <Route path="/join/:token" element={<JoinPage />} />
      <Route path="/dashboard" element={<div>Dashboard Page</div>} />
    </Routes>,
    { initialEntries: [`/join/${token}`] }
  );
}

describe('JoinPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('shows the team name once the invite is validated', async () => {
    api.get.mockResolvedValue({ team_name: 'Engineering' });
    renderJoinPage();

    await waitFor(() => {
      expect(screen.getByText(/Join "Engineering"/)).toBeInTheDocument();
    });
    expect(api.get).toHaveBeenCalledWith('/join/abc123');
  });

  it('shows an error and no form for an invalid or expired invite', async () => {
    const err = new Error('Not found');
    err.status = 404;
    api.get.mockRejectedValue(err);
    renderJoinPage();

    await waitFor(() => {
      expect(screen.getByText(/invalid, expired, or has already been used/i)).toBeInTheDocument();
    });
    expect(screen.queryByLabelText('Username')).not.toBeInTheDocument();
  });

  it('rejects a short password client-side without calling the API', async () => {
    const user = userEvent.setup();
    api.get.mockResolvedValue({ team_name: 'Engineering' });
    renderJoinPage();

    await waitFor(() => screen.getByLabelText('Username'));
    await user.type(screen.getByLabelText('Username'), 'newcpo');
    await user.type(screen.getByLabelText('Email'), 'newcpo@example.com');
    await user.type(screen.getByLabelText('Password'), 'short');
    await user.type(screen.getByLabelText('Confirm password'), 'short');
    await user.click(screen.getByRole('button', { name: /join team/i }));

    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('rejects mismatched confirmation client-side without calling the API', async () => {
    const user = userEvent.setup();
    api.get.mockResolvedValue({ team_name: 'Engineering' });
    renderJoinPage();

    await waitFor(() => screen.getByLabelText('Username'));
    await user.type(screen.getByLabelText('Username'), 'newcpo');
    await user.type(screen.getByLabelText('Email'), 'newcpo@example.com');
    await user.type(screen.getByLabelText('Password'), 'password1');
    await user.type(screen.getByLabelText('Confirm password'), 'password2');
    await user.click(screen.getByRole('button', { name: /join team/i }));

    expect(screen.getByText(/do not match/i)).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('submits and navigates to /dashboard on success', async () => {
    const user = userEvent.setup();
    api.get.mockResolvedValue({ team_name: 'Engineering' });
    api.post.mockResolvedValue({ token: 'jwt', role: 'cpo', expires_in: 1209600 });
    renderJoinPage();

    await waitFor(() => screen.getByLabelText('Username'));
    await user.type(screen.getByLabelText('Username'), 'newcpo');
    await user.type(screen.getByLabelText('Email'), 'newcpo@example.com');
    await user.type(screen.getByLabelText('Password'), 'password1');
    await user.type(screen.getByLabelText('Confirm password'), 'password1');
    await user.click(screen.getByRole('button', { name: /join team/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/join/abc123', {
        username: 'newcpo',
        email: 'newcpo@example.com',
        password: 'password1',
      });
      expect(screen.getByText('Dashboard Page')).toBeInTheDocument();
    });
  });

  it('shows the server error on failed join', async () => {
    const user = userEvent.setup();
    api.get.mockResolvedValue({ team_name: 'Engineering' });
    api.post.mockRejectedValue(new Error('Username already exists'));
    renderJoinPage();

    await waitFor(() => screen.getByLabelText('Username'));
    await user.type(screen.getByLabelText('Username'), 'newcpo');
    await user.type(screen.getByLabelText('Email'), 'newcpo@example.com');
    await user.type(screen.getByLabelText('Password'), 'password1');
    await user.type(screen.getByLabelText('Confirm password'), 'password1');
    await user.click(screen.getByRole('button', { name: /join team/i }));

    await waitFor(() => {
      expect(screen.getByText('Username already exists')).toBeInTheDocument();
    });
  });
});
