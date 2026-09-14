import {
  BLOCK_LABELS,
  CARE_BUCKET_LABELS,
  type BlockCode,
  type CareBucket,
  type CareLevelSection,
} from '../../types/dashboardV2';

/** Dải tuần tự một tông xanh (bậc 250 → 700), NT0 là xám vì "chưa phân cấp". */
const BUCKET_COLOR: Record<CareBucket, string> = {
  NGT: '#86b6ef',
  NT1: '#3987e5',
  NT2: '#1c5cab',
  NT3: '#0d366b',
  NT0: '#c3c2b7',
};
const ORDER: CareBucket[] = ['NGT', 'NT1', 'NT2', 'NT3', 'NT0'];

/**
 * Làm tròn "largest remainder": từng đoạn làm tròn độc lập có thể cho tổng
 * 99 hoặc 101; cách này bảo đảm tổng nhãn của một thanh luôn đúng 100.
 */
function roundTo100(values: Partial<Record<CareBucket, number>>): Partial<Record<CareBucket, number>> {
  const keys = ORDER.filter((ro) => (values[ro] ?? 0) > 0);
  const total = keys.reduce((a, ro) => a + (values[ro] ?? 0), 0);
  if (total <= 0) return {};
  const scaled = keys.map((ro) => ((values[ro] ?? 0) * 100) / total);
  const floors = scaled.map((x) => Math.floor(x));
  let rest = 100 - floors.reduce((a, b) => a + b, 0);
  const order = scaled
    .map((x, i) => ({ i, frac: x - floors[i] }))
    .sort((a, b) => b.frac - a.frac);
  for (const { i } of order) {
    if (rest <= 0) break;
    floors[i] += 1;
    rest -= 1;
  }
  const out: Partial<Record<CareBucket, number>> = {};
  keys.forEach((ro, i) => {
    out[ro] = floors[i];
  });
  return out;
}

/**
 * Tỷ trọng phân cấp chăm sóc p̂(g, rổ) — thanh 100 % cho từng khối ICD.
 * Đây là đầu vào của Tầng 2 (định mức thực nghiệm tính theo rổ), nên hiển
 * thị để người xem hiểu vì sao cùng một số ca lại cho nhu cầu khác nhau.
 */
export default function CareLevelChart({
  data,
  block,
}: {
  data: CareLevelSection;
  block: BlockCode | 'all';
}) {
  const blocks = (Object.keys(BLOCK_LABELS) as BlockCode[]).filter((b) => block === 'all' || b === block);
  const byBlock: Record<string, Partial<Record<CareBucket, number>>> = {};
  for (const s of data.shares) {
    (byBlock[s.block_code] ??= {})[s.ro] = s.share_pct;
  }
  const present = ORDER.filter((ro) => data.shares.some((s) => s.ro === ro && s.share_pct > 0));

  if (data.shares.length === 0) {
    return <div className="py-8 text-center text-sm text-neutral-400">Chưa có dữ liệu phân cấp chăm sóc.</div>;
  }

  return (
    <div>
      <div className="space-y-3">
        {blocks.map((b) => {
          const d = byBlock[b] ?? {};
          const rounded = roundTo100(d);
          return (
            <div key={b} className="grid grid-cols-[92px_1fr] gap-3 items-center">
              <div>
                <div className="text-xs font-semibold text-neutral-800">{b}</div>
                <div className="text-[10.5px] text-neutral-500 leading-tight">{BLOCK_LABELS[b]}</div>
              </div>
              <div className="flex h-6 gap-[2px]" role="img" aria-label={`Phân cấp ${b}`}>
                {ORDER.map((ro) => {
                  const v = d[ro] ?? 0;
                  const pct = rounded[ro] ?? 0;
                  if (v <= 0) return null;
                  const dark = ro === 'NGT' || ro === 'NT0';
                  return (
                    <div
                      key={ro}
                      title={`${CARE_BUCKET_LABELS[ro]}: ${v.toFixed(1)} %`}
                      style={{ flex: `${v} 1 0`, minWidth: 18, background: BUCKET_COLOR[ro] }}
                      className="flex items-center justify-center rounded-sm overflow-hidden font-semibold"
                    >
                      <span
                        className="whitespace-nowrap leading-none"
                        style={{ color: dark ? '#0b0b0b' : '#fff', fontSize: pct >= 8 ? 10 : 9 }}
                      >
                        {pct}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-neutral-600">
        {present.map((ro) => (
          <span key={ro} className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: BUCKET_COLOR[ro] }} />
            {ro} · {CARE_BUCKET_LABELS[ro]}
          </span>
        ))}
      </div>
      {data.cua_so?.tu_ky && (
        <p className="mt-2 text-[11px] text-neutral-500">
          Cửa sổ {data.cua_so.so_ky} kỳ ({data.cua_so.tu_ky} → {data.cua_so.den_ky}); rổ mẫu nhỏ đã co ngót về nhóm.
        </p>
      )}
    </div>
  );
}
