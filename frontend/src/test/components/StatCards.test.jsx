import { render, screen } from '@testing-library/react';
import { StatCards } from '../../components/StatCards.jsx';

const defaultProps = {
  memberCount: 5,
  pizzaCount: 12,
  totalPrice: 98.5,
  countdown: '14:32',
  countdownPct: 60,
  isClosed: false,
  currency: 'CHF',
};

describe('StatCards', () => {
  it('renders member count', () => {
    render(<StatCards {...defaultProps} />);
    expect(screen.getByText('members')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('renders pizza count', () => {
    render(<StatCards {...defaultProps} />);
    expect(screen.getByText('plates')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
  });

  it('renders CHF total formatted to 2 decimal places', () => {
    render(<StatCards {...defaultProps} />);
    expect(screen.getByText('CHF total')).toBeInTheDocument();
    expect(screen.getByText('98.50')).toBeInTheDocument();
  });

  describe('when session is active (isClosed=false)', () => {
    it('shows "ends in" label', () => {
      render(<StatCards {...defaultProps} isClosed={false} />);
      expect(screen.getByText('ends in')).toBeInTheDocument();
    });

    it('shows the countdown value', () => {
      render(<StatCards {...defaultProps} countdown="14:32" isClosed={false} />);
      expect(screen.getByText('14:32')).toBeInTheDocument();
    });

    it('shows the live chip', () => {
      render(<StatCards {...defaultProps} isClosed={false} />);
      expect(screen.getByText(/live/i)).toBeInTheDocument();
    });
  });

  describe('when session is closed (isClosed=true)', () => {
    it('shows "session closed" label', () => {
      render(<StatCards {...defaultProps} isClosed={true} />);
      expect(screen.getByText('session closed')).toBeInTheDocument();
    });

    it('shows em-dash instead of countdown', () => {
      render(<StatCards {...defaultProps} isClosed={true} />);
      expect(screen.getByText('—')).toBeInTheDocument();
    });

    it('does not show the live chip', () => {
      render(<StatCards {...defaultProps} isClosed={true} />);
      expect(screen.queryByText(/live/i)).not.toBeInTheDocument();
    });

    it('does not show "ends in"', () => {
      render(<StatCards {...defaultProps} isClosed={true} />);
      expect(screen.queryByText('ends in')).not.toBeInTheDocument();
    });
  });
});
