import { AlertOctagon, AlertTriangle, Info, MinusCircle } from 'lucide-react';
import { cn } from '../../utils/cn';
import type { Insight } from '../../types/dashboardV2';

const TONE: Record<Insight['tone'], { icon: React.ReactNode; cls: string }> = {
  info: { icon: <Info className="w-4 h-4" />, cls: 'text-blue-600' },
  warn: { icon: <AlertTriangle className="w-4 h-4" />, cls: 'text-amber-600' },
  critical: { icon: <AlertOctagon className="w-4 h-4" />, cls: 'text-red-600' },
  muted: { icon: <MinusCircle className="w-4 h-4" />, cls: 'text-neutral-400' },
};

/**
 * Diễn giải do backend sinh theo quy tắc từ chính số liệu trên màn hình —
 * mỗi dòng đều dẫn được về một con số ở thẻ hoặc bảng phía trên.
 */
export default function InsightsCard({ items }: { items: Insight[] }) {
  if (items.length === 0) {
    return <div className="py-6 text-center text-sm text-neutral-400">Không có điểm cần lưu ý.</div>;
  }
  return (
    <ul className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2.5">
      {items.map((it, i) => {
        const t = TONE[it.tone] ?? TONE.info;
        return (
          <li key={i} className="grid grid-cols-[20px_1fr] gap-2 items-start text-[12.5px] text-neutral-700 leading-snug">
            <span className={cn('mt-px', t.cls)}>{t.icon}</span>
            <span>{it.text}</span>
          </li>
        );
      })}
    </ul>
  );
}
