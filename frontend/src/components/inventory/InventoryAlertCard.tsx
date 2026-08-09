import { AlertTriangle } from 'lucide-react';

interface Props {
  count: number;
}

export default function InventoryAlertCard({ count }: Props) {
  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5 max-w-md">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center shrink-0">
          <AlertTriangle className="w-5 h-5 text-red-600" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-red-50 text-red-700 border border-red-100 text-[11px] font-semibold">
            CẦN CHÚ Ý
          </span>
          <p className="text-[11px] uppercase tracking-wider text-neutral-500 font-semibold mt-3">
            Vật tư sắp hết / hết
          </p>
          <p className="text-3xl font-extrabold text-red-600 mt-1 tabular-nums">
            {count.toLocaleString('vi-VN')}{' '}
            <span className="text-base font-medium text-neutral-500">mục</span>
          </p>
        </div>
      </div>
    </div>
  );
}
