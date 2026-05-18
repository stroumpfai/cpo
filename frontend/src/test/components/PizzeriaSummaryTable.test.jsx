import { render, screen } from '@testing-library/react';
import { PizzeriaSummaryTable } from '../../components/PizzeriaSummaryTable.jsx';

const defaultProps = {
  rows: [],
  totalOrders: 0,
  totalPrice: 0,
};

describe('PizzeriaSummaryTable', () => {
  describe('empty state', () => {
    it('shows "No orders yet." when rows is empty', () => {
      render(<PizzeriaSummaryTable {...defaultProps} />);
      expect(screen.getByText('No orders yet.')).toBeInTheDocument();
    });
  });

  describe('with rows', () => {
    const rows = [
      { pizza_name: 'Margherita', count: 3, total_price: 37.5 },
      { pizza_name: 'Pepperoni', count: 2, total_price: 27.0 },
    ];

    it('renders one row per pizza type', () => {
      render(<PizzeriaSummaryTable rows={rows} totalOrders={5} totalPrice={64.5} />);
      expect(screen.getByText('Margherita')).toBeInTheDocument();
      expect(screen.getByText('Pepperoni')).toBeInTheDocument();
    });

    it('renders count for each pizza', () => {
      render(<PizzeriaSummaryTable rows={rows} totalOrders={5} totalPrice={64.5} />);
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('renders subtotal for each pizza formatted to 2 decimal places', () => {
      render(<PizzeriaSummaryTable rows={rows} totalOrders={5} totalPrice={64.5} />);
      expect(screen.getByText('37.50')).toBeInTheDocument();
      expect(screen.getByText('27.00')).toBeInTheDocument();
    });

    it('renders footer with total orders count', () => {
      render(<PizzeriaSummaryTable rows={rows} totalOrders={5} totalPrice={64.5} />);
      // The footer row has "total" label and the count
      expect(screen.getByText('total')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('renders footer with total price formatted to 2 decimal places', () => {
      render(<PizzeriaSummaryTable rows={rows} totalOrders={5} totalPrice={64.5} />);
      expect(screen.getByText('64.50')).toBeInTheDocument();
    });

    it('renders the total row', () => {
      render(<PizzeriaSummaryTable rows={rows} totalOrders={5} totalPrice={64.5} />);
      expect(screen.getByText('total')).toBeInTheDocument();
    });
  });

  describe('notes column', () => {
    it('shows — when a row has no comments', () => {
      const rowsNoComments = [{ pizza_name: 'Margherita', count: 2, total_price: 25, comments: [] }];
      render(<PizzeriaSummaryTable rows={rowsNoComments} totalOrders={2} totalPrice={25} />);
      expect(screen.getByText('—')).toBeInTheDocument();
    });

    it('shows — when comments field is absent', () => {
      const rowsNoField = [{ pizza_name: 'Margherita', count: 1, total_price: 12.5 }];
      render(<PizzeriaSummaryTable rows={rowsNoField} totalOrders={1} totalPrice={12.5} />);
      expect(screen.getByText('—')).toBeInTheDocument();
    });

    it('renders a single comment without count suffix', () => {
      const rowsWithComment = [{
        pizza_name: 'Margherita', count: 1, total_price: 12.5,
        comments: [{ text: 'no olives', count: 1 }],
      }];
      render(<PizzeriaSummaryTable rows={rowsWithComment} totalOrders={1} totalPrice={12.5} />);
      expect(screen.getByText('no olives')).toBeInTheDocument();
    });

    it('renders a comment with ×N suffix when count > 1', () => {
      const rowsWithComment = [{
        pizza_name: 'Margherita', count: 3, total_price: 37.5,
        comments: [{ text: 'no olives', count: 2 }],
      }];
      render(<PizzeriaSummaryTable rows={rowsWithComment} totalOrders={3} totalPrice={37.5} />);
      expect(screen.getByText('no olives (×2)')).toBeInTheDocument();
    });

    it('renders multiple comments joined by comma', () => {
      const rowsWithComments = [{
        pizza_name: 'Margherita', count: 3, total_price: 37.5,
        comments: [{ text: 'extra cheese', count: 1 }, { text: 'no olives', count: 2 }],
      }];
      render(<PizzeriaSummaryTable rows={rowsWithComments} totalOrders={3} totalPrice={37.5} />);
      expect(screen.getByText('extra cheese, no olives (×2)')).toBeInTheDocument();
    });
  });
});
