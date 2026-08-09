import { screen, waitFor } from '@testing-library/react';
import { VersionLabel } from '../../components/VersionLabel.jsx';
// The commit tooltip is translated, so every render needs an i18n provider.
import { renderWithRouter as render } from '../utils.jsx';

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

describe('VersionLabel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the version prefixed with v', async () => {
    api.get.mockResolvedValue({ version: '1.4.0', commit: 'a1b2c3d' });
    render(<VersionLabel />);

    expect(await screen.findByText('v1.4.0')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/version');
  });

  it('exposes the commit through the title tooltip', async () => {
    api.get.mockResolvedValue({ version: '1.4.0', commit: 'a1b2c3d' });
    render(<VersionLabel />);

    expect(await screen.findByTitle('commit a1b2c3d')).toBeInTheDocument();
  });

  it('omits the tooltip when the build carries no commit', async () => {
    api.get.mockResolvedValue({ version: '1.0', commit: 'unknown' });
    render(<VersionLabel />);

    const label = await screen.findByText('v1.0');
    expect(label).not.toHaveAttribute('title');
  });

  it('renders nothing when the request fails', async () => {
    api.get.mockRejectedValue(new Error('offline'));
    const { container } = render(<VersionLabel />);

    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing while the request is still in flight', () => {
    api.get.mockReturnValue(new Promise(() => {}));
    const { container } = render(<VersionLabel />);

    expect(container).toBeEmptyDOMElement();
  });
});
