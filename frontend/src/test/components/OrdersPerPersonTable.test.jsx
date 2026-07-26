import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OrdersPerPersonTable } from '../../components/OrdersPerPersonTable.jsx';

function makeRow(overrides = {}) {
  return {
    order_id: 'order-1',
    member_name: 'Alice',
    client_ip: '192.168.1.1',
    pizza_name: 'Margherita',
    price: 12.5,
    created_at: '2026-05-17T10:00:00Z',
    ...overrides,
  };
}

const defaultProps = {
  rows: [],
  paidSet: new Set(),
  onTogglePaid: vi.fn(),
  onDelete: vi.fn(),
  isClosed: false,
};

describe('OrdersPerPersonTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('empty state', () => {
    it('shows empty state message when rows is empty', () => {
      render(<OrdersPerPersonTable {...defaultProps} />);
      expect(screen.getByText(/No orders yet/)).toBeInTheDocument();
    });
  });

  describe('with rows', () => {
    it('renders member name', () => {
      const row = makeRow({ member_name: 'Alice' });
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} />);
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });

    it('renders pizza name', () => {
      const row = makeRow({ pizza_name: 'Margherita' });
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} />);
      expect(screen.getByText('Margherita')).toBeInTheDocument();
    });

    it('renders price formatted to 2 decimal places', () => {
      const row = makeRow({ price: 12.5 });
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} />);
      expect(screen.getByText('12.50')).toBeInTheDocument();
    });

    it('renders client IP', () => {
      const row = makeRow({ client_ip: '10.0.0.1' });
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} />);
      expect(screen.getByText('10.0.0.1')).toBeInTheDocument();
    });

    it('renders one row per order', () => {
      const rows = [
        makeRow({ order_id: 'o1', member_name: 'Alice', pizza_name: 'Margherita' }),
        makeRow({ order_id: 'o2', member_name: 'Bob', pizza_name: 'Pepperoni' }),
      ];
      render(<OrdersPerPersonTable {...defaultProps} rows={rows} />);
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
      expect(screen.getByText('Margherita')).toBeInTheDocument();
      expect(screen.getByText('Pepperoni')).toBeInTheDocument();
    });
  });

  describe('actions when session is open (isClosed=false)', () => {
    it('shows delete button', () => {
      const row = makeRow();
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} />);
      expect(screen.getByText(/✕ delete/)).toBeInTheDocument();
    });

    it('calls onDelete with order_id when delete is clicked', async () => {
      const user = userEvent.setup();
      const onDelete = vi.fn();
      const row = makeRow({ order_id: 'order-abc' });
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} onDelete={onDelete} />);
      await user.click(screen.getByTitle('Delete order'));
      expect(onDelete).toHaveBeenCalledWith('order-abc');
    });

    it('shows paid toggle button', () => {
      const row = makeRow();
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} />);
      // 💰 received or ✓ received
      expect(screen.getByTitle(/Mark/)).toBeInTheDocument();
    });

    it('calls onTogglePaid with order_id when paid button is clicked', async () => {
      const user = userEvent.setup();
      const onTogglePaid = vi.fn();
      const row = makeRow({ order_id: 'order-xyz' });
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} onTogglePaid={onTogglePaid} />);
      await user.click(screen.getByTitle('Mark paid'));
      expect(onTogglePaid).toHaveBeenCalledWith('order-xyz');
    });

    it('shows "✓ received" when order is in paidSet', () => {
      const row = makeRow({ order_id: 'order-1' });
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} paidSet={new Set(['order-1'])} />);
      expect(screen.getByTitle('Mark unpaid')).toBeInTheDocument();
    });
  });

  describe('comment field', () => {
    it('renders comment below pizza name when present', () => {
      const row = makeRow({ pizza_name: 'Margherita', comment: 'no olives' });
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} />);
      expect(screen.getByText('no olives')).toBeInTheDocument();
    });

    it('does not render a comment span when comment is absent', () => {
      const row = makeRow({ pizza_name: 'Margherita' });
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} />);
      expect(screen.queryByText('no olives')).not.toBeInTheDocument();
    });

    it('renders comment in printMode', () => {
      const row = makeRow({ pizza_name: 'Margherita', comment: 'extra cheese' });
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} printMode />);
      expect(screen.getByText('extra cheese')).toBeInTheDocument();
    });
  });

  describe('sorting', () => {
    // Deliberately out of order on every column so each sort has to do work.
    const rows = [
      makeRow({ order_id: 'o1', member_name: 'carol', client_ip: '10.0.0.10', pizza_name: 'Quattro', price: 9.0,  created_at: '2026-05-17T10:02:00Z' }),
      makeRow({ order_id: 'o2', member_name: 'Alice', client_ip: '10.0.0.2',  pizza_name: 'Tonno',   price: 21.0, created_at: '2026-05-17T10:00:00Z' }),
      makeRow({ order_id: 'o3', member_name: 'Bob',   client_ip: '10.0.0.9',  pizza_name: 'Funghi',  price: 15.0, created_at: '2026-05-17T10:01:00Z' }),
    ];

    // Column index into the screen table: time, member, client ip, plate, price, action
    function columnOrder(index) {
      const [, ...body] = screen.getAllByRole('row');
      return body.map(row => row.cells[index].textContent);
    }

    it('defaults to newest first', () => {
      render(<OrdersPerPersonTable {...defaultProps} rows={rows} />);
      expect(columnOrder(1)).toEqual(['carol', 'Bob', 'Alice']);
    });

    it('calls onSort with the column key when a header is clicked', async () => {
      const user = userEvent.setup();
      const onSort = vi.fn();
      render(<OrdersPerPersonTable {...defaultProps} rows={rows} onSort={onSort} />);
      await user.click(screen.getByRole('button', { name: /member/i }));
      expect(onSort).toHaveBeenCalledWith('member_name');
    });

    it('sorts by member name case-insensitively', () => {
      render(<OrdersPerPersonTable {...defaultProps} rows={rows} sortKey="member_name" sortDir="asc" />);
      expect(columnOrder(1)).toEqual(['Alice', 'Bob', 'carol']);
    });

    it('reverses the order when sortDir is desc', () => {
      render(<OrdersPerPersonTable {...defaultProps} rows={rows} sortKey="member_name" sortDir="desc" />);
      expect(columnOrder(1)).toEqual(['carol', 'Bob', 'Alice']);
    });

    it('sorts price numerically, not as text', () => {
      render(<OrdersPerPersonTable {...defaultProps} rows={rows} sortKey="price" sortDir="asc" />);
      expect(columnOrder(4)).toEqual(['9.00', '15.00', '21.00']);
    });

    it('sorts IPs numerically per octet', () => {
      render(<OrdersPerPersonTable {...defaultProps} rows={rows} sortKey="client_ip" sortDir="asc" />);
      expect(columnOrder(2)).toEqual(['10.0.0.2', '10.0.0.9', '10.0.0.10']);
    });

    it('sorts by received state using paidSet', () => {
      render(
        <OrdersPerPersonTable {...defaultProps} rows={rows} paidSet={new Set(['o2'])}
          sortKey="received" sortDir="desc" />
      );
      expect(columnOrder(1)).toEqual(['Alice', 'carol', 'Bob']);
    });

    it('marks only the active column with aria-sort', () => {
      render(<OrdersPerPersonTable {...defaultProps} rows={rows} sortKey="price" sortDir="asc" onSort={vi.fn()} />);
      const headers = screen.getAllByRole('columnheader');
      const sorted  = headers.filter(h => h.hasAttribute('aria-sort'));
      expect(sorted).toHaveLength(1);
      expect(sorted[0]).toHaveTextContent(/price/i);
      expect(sorted[0]).toHaveAttribute('aria-sort', 'ascending');
    });

    it('applies the same sort in printMode', () => {
      render(<OrdersPerPersonTable {...defaultProps} rows={rows} sortKey="member_name" sortDir="asc" printMode />);
      // print columns: time, member, plate, price, received
      expect(columnOrder(1)).toEqual(['Alice', 'Bob', 'carol']);
    });

    it('renders plain headers when no onSort is given', () => {
      render(<OrdersPerPersonTable {...defaultProps} rows={rows} />);
      const clickable = screen.getAllByRole('columnheader').filter(h => h.querySelector('button'));
      expect(clickable).toHaveLength(0);
    });
  });

  describe('when session is closed (isClosed=true)', () => {
    it('hides delete button', () => {
      const row = makeRow();
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} isClosed={true} />);
      expect(screen.queryByText(/✕ delete/)).not.toBeInTheDocument();
    });

    it('still shows received toggle button so CPO can mark payment', () => {
      const row = makeRow();
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} isClosed={true} />);
      expect(screen.getByTitle(/Mark/)).toBeInTheDocument();
    });

    it('hides the action column header', () => {
      const row = makeRow();
      render(<OrdersPerPersonTable {...defaultProps} rows={[row]} isClosed={true} />);
      expect(screen.queryByText('action')).not.toBeInTheDocument();
    });
  });
});
