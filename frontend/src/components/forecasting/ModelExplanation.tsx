import { Lightbulb, Droplets, Thermometer, BarChart2 } from 'lucide-react';

interface Props {
  bullets: string[];
}

const ICON_PALETTE = [
  { icon: Droplets, color: 'text-sky-500', bg: 'bg-sky-50' },
  { icon: Thermometer, color: 'text-blue-500', bg: 'bg-blue-50' },
  { icon: BarChart2, color: 'text-rose-500', bg: 'bg-rose-50' },
  { icon: Lightbulb, color: 'text-amber-500', bg: 'bg-amber-50' },
];

/** Tách bullet "Tiêu đề — Nội dung" thành 2 phần để render đẹp. */
function splitBullet(text: string): { title: string; body: string } {
  const sep = text.includes('—') ? '—' : ' - ';
  const idx = text.indexOf(sep);
  if (idx === -1) return { title: '', body: text };
  return {
    title: text.slice(0, idx).trim(),
    body: text.slice(idx + sep.length).trim(),
  };
}

export default function ModelExplanation({ bullets }: Props) {
  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-neutral-900 mb-4">
        <Lightbulb className="w-4 h-4 text-amber-500" />
        Giải thích mô hình
      </h3>

      <ul className="space-y-4">
        {bullets.map((b, idx) => {
          const { icon: Icon, color, bg } = ICON_PALETTE[idx % ICON_PALETTE.length];
          const { title, body } = splitBullet(b);
          return (
            <li key={idx} className="flex items-start gap-3">
              <span
                className={`shrink-0 w-7 h-7 rounded-lg flex items-center justify-center ${bg}`}
              >
                <Icon className={`w-4 h-4 ${color}`} />
              </span>
              <div className="min-w-0">
                {title && (
                  <p className="text-sm font-semibold text-neutral-900 leading-snug">
                    {title}
                  </p>
                )}
                <p className="text-xs text-neutral-500 leading-relaxed mt-0.5">
                  {body}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
