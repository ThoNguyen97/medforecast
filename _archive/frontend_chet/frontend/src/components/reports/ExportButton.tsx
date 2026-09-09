import { useState } from 'react';
import { Download } from 'lucide-react';
import Button from '../common/Button';
import { reportsService } from '../../services/reportsService';
import type { ExportReportRequest, ReportType } from '../../types/reports';

interface ExportButtonProps {
  reportType: ReportType;
  filters?: Omit<ExportReportRequest, 'report_type'>;
  label?: string;
}

/**
 * Button that triggers a PDF export download for the given report type.
 * Handles the blob download without any extra dependencies.
 */
export default function ExportButton({
  reportType,
  filters,
  label = 'Xuất PDF',
}: ExportButtonProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);

    try {
      const blob = await reportsService.exportReport({
        report_type: reportType,
        ...filters,
      });

      // Create a temporary URL and trigger the download
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      const reportLabels: Record<ReportType, string> = {
        consumption: 'bao_cao_tieu_thu',
        'forecast-accuracy': 'bao_cao_do_chinh_xac',
        'inventory-turnover': 'bao_cao_vong_quay',
      };
      const timestamp = new Date().toISOString().slice(0, 10);
      anchor.href = url;
      anchor.download = `${reportLabels[reportType]}_${timestamp}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Không thể xuất báo cáo';
      setError(msg);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="inline-flex flex-col items-end gap-1">
      <Button
        variant="secondary"
        size="sm"
        onClick={handleExport}
        isLoading={isExporting}
        leftIcon={<Download size={14} />}
        disabled={isExporting}
      >
        {label}
      </Button>
      {error && (
        <p className="text-xs text-danger-600">{error}</p>
      )}
    </div>
  );
}
