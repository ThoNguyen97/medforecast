import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Search } from 'lucide-react';

import { dssService } from '../../services/dssService';
import { BLOCK_LABELS, type BlockCode, type CareBucket } from '../../types/dashboardV2';
import { cn } from '../../utils/cn';

const PAGE_SIZE = 25;
const fmt = (v: number | null | undefined, d = 0) =>
  v == null ? '—' : v.toLocaleString('vi-VN', { maximumFractionDigits: d });

/**
 * Định mức thực nghiệm — CHỈ ĐỌC.
 *
 * Bảng này hiện đúng con số Tầng 2 nhân với Ŷ_g × p̂(g,ro): tử số (tiêu hao),
 * mẫu số (ca) và Norm theo từng rổ chăm sóc, trên cùng cửa sổ với tỷ trọng
 * rổ. Định mức tự cập nhật mỗi lần đồng bộ HIS; muốn đổi cách tính thì đổi
 * tham số ở tab "Tham số DSS", không có ô nhập tay.
 *
 * Thay cho tab "Định mức thuốc" (Nhẹ/TB/Nặng, nhập tay) trước 12/09/2026.
 */
export default function EmpiricalNormsSection() {
  const [block, setBlock] = useState<BlockCode>('J00-J06');
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);
  useEffect(() => setPage(1), [block, q]);

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ['dss', 'norms', block, q, page],
    queryFn: () => dssService.getNorms(block, q || undefined, PAGE_SIZE, (page - 1) * PAGE_SIZE),
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));
  const roList = data?.ro ?? [];

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-neutral-200 px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-bold text-neutral-900">Định mức thực nghiệm</h3>
            <p className="text-sm text-neutral-500 mt-0.5">
              Norm(i, g, rổ) = Σ tiêu hao ÷ Σ ca, đo trên dữ liệu HIS. Chỉ đọc — tự cập nhật sau mỗi lần đồng bộ.
            </p>
          </div>
          <div className="flex items-center gap-1">
            {(Object.keys(BLOCK_LABELS) as BlockCode[]).map((b) => (
              <button
                key={b}
                type="button"
                onClick={() => setBlock(b)}
                className={cn(
                  'px-3 h-9 rounded-lg text-sm font-medium border transition',
                  block === b ? 'bg-neutral-900 text-white border-neutral-900' : 'bg-white text-neutral-600 border-neutral-200 hover:bg-neutral-50',
                )}
              >
                {b} · {BLOCK_LABELS[b]}
              </button>
            ))}
          </div>
        </div>
        {data && (
          <>
            <div className="mt-3 grid sm:grid-cols-2 lg:grid-cols-4 gap-2">
              {roList.map((r) => (
                <div key={r.ro} className="rounded-xl border border-neutral-200 px-3 py-2">
                  <div className="text-[11px] uppercase tracking-wide text-neutral-500 font-semibold">
                    {r.ro} · {r.ten}
                  </div>
                  <div className="text-lg font-extrabold tabular-nums text-neutral-900 leading-tight">
                    {fmt(r.ca)} <span className="text-xs font-medium text-neutral-400">ca</span>
                  </div>
                  <div className="text-[11px] text-neutral-500">
                    p̂ = {fmt(r.p_hat * 100, 1)}%
                    {r.mau_nho && <span className="ml-1 px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-100">mẫu nhỏ → gộp</span>}
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[12px] text-neutral-600 leading-snug">
              {data.periods.length > 0
                ? `Cửa sổ ${data.periods[0]} → ${data.periods[data.periods.length - 1]} (${data.periods.length} kỳ)`
                : 'Chưa có kỳ nào trong cửa sổ (chưa đồng bộ HIS)'} ·
              ngưỡng mẫu nhỏ {data.cfg.min_cases_per_bucket} ca · {fmt(data.total)} mã có tiêu hao trong nhóm.
            </p>
            <p className="mt-1 text-[11px] text-neutral-400 leading-snug">{data.cong_thuc}</p>
          </>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-neutral-200">
        <div className="px-5 py-3.5 border-b border-neutral-100 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[220px] max-w-md">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
            <input
              id="norms-search"
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo mã, tên hoạt chất…"
              className="w-full h-9 pl-9 pr-3 rounded-lg border border-neutral-200 bg-neutral-50 text-sm placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
            />
          </div>
          {isFetching && <Loader2 className="w-4 h-4 animate-spin text-neutral-400" />}
        </div>

        {error ? (
          <div className="p-5 text-sm text-red-700">Không tải được định mức: {(error as Error).message}</div>
        ) : isLoading || !data ? (
          <div className="px-5 py-5 space-y-2">
            {[...Array(6)].map((_, i) => <div key={i} className="h-9 rounded bg-neutral-100 animate-pulse" />)}
          </div>
        ) : data.rows.length === 0 ? (
          <div className="py-12 text-center text-sm text-neutral-400">
            {data.periods.length === 0 ? 'Chưa có dữ liệu fact_usage/cases_by_care_level — đồng bộ HIS trước.' : 'Không có mã nào khớp.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-neutral-500 text-[11px] uppercase tracking-wide">
                  <th className="text-left px-5 py-2.5 font-semibold">Thuốc</th>
                  <th className="text-right px-3 py-2.5 font-semibold" title="Σ tiêu hao trong cửa sổ, mọi rổ">Tiêu hao</th>
                  {roList.map((r) => (
                    <th key={r.ro} className="text-right px-3 py-2.5 font-semibold" title={`${r.ten}: tiêu hao ÷ ${fmt(r.ca)} ca`}>
                      Norm {r.ro}
                    </th>
                  ))}
                  <th className="text-right px-5 py-2.5 font-semibold" title="Σ_ro p̂ · Norm — lượng cho MỘT ca dự báo của nhóm">
                    Hiệu dụng / ca
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.supply_code} className="border-t border-neutral-100 hover:bg-neutral-50">
                    <td className="px-5 py-2.5">
                      <div className="font-medium text-neutral-900 leading-tight">{r.ten}</div>
                      <div className="text-[11px] text-neutral-500 font-mono">
                        {r.supply_code}{r.don_vi ? ` · ${r.don_vi}` : ''}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-neutral-600">{fmt(r.tieu_hao_tong)}</td>
                    {roList.map((ro) => {
                      const c = r.theo_ro[ro.ro as CareBucket];
                      return (
                        <td key={ro.ro} className="px-3 py-2.5 text-right tabular-nums">
                          <span className={cn(c?.gop && 'text-amber-800')} title={c ? `${fmt(c.tieu_hao)} ÷ ${fmt(c.ca)}${c.gop ? ' — mẫu nhỏ, dùng định mức gộp nhóm' : ''}` : ''}>
                            {c ? fmt(c.norm, 3) : '—'}
                          </span>
                          {c && !c.gop && (
                            <span className="block text-[10px] text-neutral-400">{fmt(c.tieu_hao)} ÷ {fmt(c.ca)}</span>
                          )}
                        </td>
                      );
                    })}
                    <td className="px-5 py-2.5 text-right tabular-nums font-semibold">{fmt(r.norm_hieu_dung, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="px-5 py-3 border-t border-neutral-100 flex flex-wrap items-center justify-between gap-2 text-xs text-neutral-500">
          <span>{data ? `${fmt(data.total)} mã · sắp theo tiêu hao giảm dần` : '…'}</span>
          <div className="flex items-center gap-2">
            <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="h-8 px-3 rounded-lg border border-neutral-200 bg-white disabled:opacity-40">Trước</button>
            <span className="tabular-nums">{page} / {totalPages}</span>
            <button type="button" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="h-8 px-3 rounded-lg border border-neutral-200 bg-white disabled:opacity-40">Sau</button>
          </div>
        </div>
      </div>
    </div>
  );
}
