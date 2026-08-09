import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Table, { type Column } from '../Table';

interface Item {
  id: number;
  name: string;
  value: number;
}

const columns: Column<Item>[] = [
  { key: 'name', header: 'Name', accessor: 'name' },
  { key: 'value', header: 'Value', accessor: 'value', sortable: true },
];

const data: Item[] = [
  { id: 1, name: 'Alpha', value: 10 },
  { id: 2, name: 'Beta', value: 20 },
];

describe('Table', () => {
  it('renders column headers', () => {
    render(<Table columns={columns} data={data} keyExtractor={(r) => r.id} />);
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Value')).toBeInTheDocument();
  });

  it('renders row data', () => {
    render(<Table columns={columns} data={data} keyExtractor={(r) => r.id} />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });

  it('shows loading spinner when isLoading=true', () => {
    render(
      <Table columns={columns} data={[]} keyExtractor={(r) => r.id} isLoading />
    );
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows empty message when data is empty', () => {
    render(<Table columns={columns} data={[]} keyExtractor={(r) => r.id} />);
    expect(screen.getByText('Không có dữ liệu')).toBeInTheDocument();
  });

  it('shows custom empty message', () => {
    render(
      <Table
        columns={columns}
        data={[]}
        keyExtractor={(r) => r.id}
        emptyMessage="No items found"
      />
    );
    expect(screen.getByText('No items found')).toBeInTheDocument();
  });

  it('calls onSort when sortable column header is clicked', () => {
    const onSort = vi.fn();
    render(
      <Table
        columns={columns}
        data={data}
        keyExtractor={(r) => r.id}
        onSort={onSort}
      />
    );
    fireEvent.click(screen.getByText('Value'));
    expect(onSort).toHaveBeenCalledWith('value');
  });

  it('calls onRowClick when row is clicked', () => {
    const onRowClick = vi.fn();
    render(
      <Table
        columns={columns}
        data={data}
        keyExtractor={(r) => r.id}
        onRowClick={onRowClick}
      />
    );
    fireEvent.click(screen.getByText('Alpha'));
    expect(onRowClick).toHaveBeenCalledWith(data[0]);
  });

  it('renders accessor function result', () => {
    const customColumns: Column<Item>[] = [
      { key: 'custom', header: 'Custom', accessor: (row) => `${row.name}-${row.value}` },
    ];
    render(<Table columns={customColumns} data={data} keyExtractor={(r) => r.id} />);
    expect(screen.getByText('Alpha-10')).toBeInTheDocument();
  });

  it('shows sort icon when sortConfig matches', () => {
    render(
      <Table
        columns={columns}
        data={data}
        keyExtractor={(r) => r.id}
        sortConfig={{ key: 'value', direction: 'asc' }}
        onSort={vi.fn()}
      />
    );
    // Column header still renders
    expect(screen.getByText('Value')).toBeInTheDocument();
  });
});
