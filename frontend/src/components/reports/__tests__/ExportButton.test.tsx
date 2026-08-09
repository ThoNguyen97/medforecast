import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ExportButton from '../ExportButton';
import { reportsService } from '../../../services/reportsService';

vi.mock('../../../services/reportsService');

describe('ExportButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock URL methods
    global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    global.URL.revokeObjectURL = vi.fn();
  });

  it('renders export button with default label', () => {
    render(<ExportButton reportType="consumption" />);
    expect(screen.getByRole('button')).toBeInTheDocument();
    expect(screen.getByText('Xuất PDF')).toBeInTheDocument();
  });

  it('renders export button with custom label', () => {
    render(<ExportButton reportType="consumption" label="Download Report" />);
    expect(screen.getByText('Download Report')).toBeInTheDocument();
  });

  it('calls exportReport when clicked', async () => {
    const mockBlob = new Blob(['pdf data'], { type: 'application/pdf' });
    vi.mocked(reportsService.exportReport).mockResolvedValueOnce(mockBlob);

    render(<ExportButton reportType="consumption" />);
    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(reportsService.exportReport).toHaveBeenCalledWith(
        expect.objectContaining({ report_type: 'consumption' })
      );
    });
  });

  it('shows error message when export fails', async () => {
    vi.mocked(reportsService.exportReport).mockRejectedValueOnce(new Error('Server error'));
    render(<ExportButton reportType="consumption" />);
    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByText('Server error')).toBeInTheDocument();
    });
  });
});
