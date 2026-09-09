import { Calculator } from 'lucide-react';

interface Props {
  safetyRate?: number; // 0..1, default 0.15
}

export default function CalculationSidebar({ safetyRate = 0.15 }: Props) {
  return (
    <div className="space-y-4">
      <CalculationBasis safetyRate={safetyRate} />
      <ColorLegend />
    </div>
  );
}

function CalculationBasis({ safetyRate }: { safetyRate: number }) {
  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-neutral-900 mb-3">
        <Calculator className="w-4 h-4 text-blue-600" />
        Cơ sở tính toán
      </h3>

      <p className="text-xs font-medium text-neutral-500 mb-1.5">
        Công thức đề xuất nhập:
      </p>
      <code className="block w-full px-3 py-2 rounded-lg bg-blue-50 text-blue-700 text-[12px] font-mono leading-snug overflow-x-auto whitespace-nowrap">
        SL Đề Xuất = (Nhu cầu dự báo + Ngưỡng AT) − Tồn kho
      </code>

      <ul className="mt-4 space-y-2.5 text-xs text-neutral-600 leading-relaxed">
        <li className="flex gap-2">
          <span className="text-neutral-400 mt-0.5">•</span>
          <span>
            <strong className="text-neutral-700">Nhu cầu dự báo:</strong> Tính
            toán dựa trên mô hình AI (Lịch sử 12 tháng + Yếu tố mùa dịch).
          </span>
        </li>
        <li className="flex gap-2">
          <span className="text-neutral-400 mt-0.5">•</span>
          <span>
            <strong className="text-neutral-700">Dự phòng (Safety Stock):</strong>{' '}
            Mặc định {Math.round(safetyRate * 100)}% — cấu hình ở Module Quản trị.
          </span>
        </li>
      </ul>
    </div>
  );
}

function ColorLegend() {
  const items = [
    { color: 'bg-red-500', label: '< 10% nhu cầu (Nguy hiểm)' },
    { color: 'bg-amber-500', label: '10% – 25% nhu cầu (Cảnh báo)' },
    { color: 'bg-emerald-500', label: '25% – 150% nhu cầu (An toàn)' },
    { color: 'bg-neutral-500', label: '> 150% nhu cầu (Dư tồn)' },
  ];
  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <p className="text-xs font-medium text-neutral-500 mb-3">
        Quy tắc màu sắc (Mức tồn):
      </p>
      <ul className="space-y-2 text-xs text-neutral-700">
        {items.map((it) => (
          <li key={it.label} className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${it.color} shrink-0`} />
            {it.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

function RunForecastCard(_: {
  onRunForecast?: () => void;
  isRunning?: boolean;
}) {
  // Card đã được loại bỏ theo yêu cầu — giữ stub để các import legacy không vỡ
  return null;
}

