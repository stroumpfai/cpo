import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SessionHeader } from '../../components/SessionHeader.jsx';
// The header is fully translated, so every render needs an i18n provider.
import { renderWithRouter as render } from '../utils.jsx';

const mockSession = {
  session_date: '2026-05-17',
  start_time: '10:00',
  end_time: '12:00',
  grace_period_minutes: 2,
};

const defaultProps = {
  session: mockSession,
  uniqueLink: 'abc123xyz',
  onRefresh: vi.fn(),
  onPrint: vi.fn(),
};

describe('SessionHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Dashboard title', () => {
    render(<SessionHeader {...defaultProps} />);
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('renders session date in the subtitle', () => {
    render(<SessionHeader {...defaultProps} />);
    // The subtitle contains "Session —" followed by a formatted date
    expect(screen.getByText(/Session —/)).toBeInTheDocument();
  });

  it('renders the copy link button with the unique link', () => {
    render(<SessionHeader {...defaultProps} />);
    // Button shows the unique link path
    expect(screen.getByTitle('Copy team ordering link')).toBeInTheDocument();
    expect(screen.getByText(/\/orders\/abc123xyz/)).toBeInTheDocument();
  });

  it('calls navigator.clipboard.writeText when copy link button is clicked', async () => {
    // userEvent.setup() installs its own clipboard stub on navigator.clipboard.
    // Spy on writeText after setup() so we intercept the stub's method.
    const user = userEvent.setup();
    const writeTextSpy = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined);
    render(<SessionHeader {...defaultProps} />);
    const copyBtn = screen.getByTitle('Copy team ordering link');
    await user.click(copyBtn);
    expect(writeTextSpy).toHaveBeenCalledWith(
      expect.stringContaining('/orders/abc123xyz')
    );
    writeTextSpy.mockRestore();
  });

  it('changes button text to "✓ copied" after clicking', async () => {
    const user = userEvent.setup();
    render(<SessionHeader {...defaultProps} />);
    const copyBtn = screen.getByTitle('Copy team ordering link');
    await user.click(copyBtn);
    expect(screen.getByText(/✓ copied/)).toBeInTheDocument();
  });

  it('calls onRefresh when refresh button is clicked', async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    render(<SessionHeader {...defaultProps} onRefresh={onRefresh} />);
    await user.click(screen.getByTitle('Refresh'));
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it('calls onPrint when print button is clicked', async () => {
    const user = userEvent.setup();
    const onPrint = vi.fn();
    render(<SessionHeader {...defaultProps} onPrint={onPrint} />);
    await user.click(screen.getByTitle('Print'));
    expect(onPrint).toHaveBeenCalledOnce();
  });

  it('renders grace period info in subtitle', () => {
    render(<SessionHeader {...defaultProps} />);
    expect(screen.getByText(/2′ grace/)).toBeInTheDocument();
  });
});
