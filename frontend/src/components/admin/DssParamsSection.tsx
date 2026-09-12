import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, RotateCcw, Save } from 'lucide-react';

import { dssService } from '../../services/dssService';
import type { CareLevelParams, DssParams, ParamMeta, ThresholdParams } from '../../types/dss';
import { cn } from '../../utils/cn';

type Draft = { thresholds: ThresholdParams; care_level: CareLevelParams };

/**
 * Tham số DSS — toàn bộ núm vặn của Tầng 2 và Tầng 3, nối thẳng vào hai bản
 * ghi `system_config` mà DSS thật sự đọc (`dss.thresholds`, `dss.care_level`).
 * Sửa ở đây → Tổng quan và Cảnh báo thiếu hụt đổi ngay ở lần tải kế tiếp.
 *
 * Thay cho tab "Ngưỡng cảnh báo" (3/7/14 ngày) trước 12/09/2026 — tab đó ghi
 * vào ba key mà không service nào đọc.
 */
export default function DssParamsSection() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ['dss', 'params'],
    queryFn: () => dssService.getParams(),
    staleTime: 30_000,
  });

  const [draft, setDraft] = useState<Draft | null>(null);
  const [msg, setMsg] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null);
  useEffect(() => {
    if (data) setDraft({ thresholds: { ...data.thresholds.gia_tri }, care_level: { ...data.care_level.gia_tri } });
  }, [data]);

  const changed = useMemo(() => {
    if (!data || !draft) return { thresholds: {}, care_level: {} } as Required<NonNullable<DssParams['da_doi']>>;
    const diff = <T extends Record<string, number | string>>(a: T, b: T) =>
      Object.fromEntries(Object.keys(a).filter((k) => String(a[k]) !== String(b[k])).map((k) => [k, b[k]])) as Partial<T>;
    return {
      thresholds: diff(data.thresholds.gia_tri, draft.thresholds),
      care_level: diff(data.care_level.gia_tri, draft.care_level),
    };
  }, [data, draft]);
  const soDoi = Object.keys(changed.thresholds).length + Object.keys(changed.care_level).length;

  const save = useMutation({
    mutationFn: () =>
      dssService.updateParams({
        ...(Object.keys(changed.thresholds).length ? { thresholds: changed.thresholds } : {}),
        ...(Object.keys(changed.care_level).length ? { care_level: changed.care_level } : {}),
      }),
    onSuccess: (res) => {
      setMsg({ tone: 'ok', text: `Đã lưu ${soDoi} tham số. Tổng quan và Cảnh báo sẽ tính lại ở lần tải kế tiếp.` });
      qc.setQueryData(['dss', 'params'], res);
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      qc.invalidateQueries({ queryKey: ['dss'] });
      qc.invalidateQueries({ queryKey: ['audit-logs'] });
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setMsg({ tone: 'err', text: detail ?? (e as Error).message });
    },
  });

  const clientErr = useMemo(() => {
    if (!draft) return null;
    if (Number(draft.thresholds.doi_red_days) >= Number(draft.thresholds.doi_amber_days))
      return 'Ngưỡng Đỏ phải nhỏ hơn ngưỡng Vàng.';
    return null;
  }, [draft]);

  if (isLoading || !draft || !data) {
    return (
      <div className="bg-white rounded-2xl border border-neutral-200 p-8 text-sm text-neutral-500 flex items-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin" /> Đang tải tham số…
      </div>
    );
  }
  if (error) {
    return <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">Không tải được tham số: {(error as Error).message}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-neutral-200 px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-bold text-neutral-900">Tham số DSS</h3>
            <p className="text-sm text-neutral-500 mt-0.5">
              Đây là toàn bộ những gì hệ thống đọc khi tính nhu cầu và xếp mức cảnh báo. Không có bảng nào khác.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => { setDraft({ thresholds: { ...data.thresholds.gia_tri }, care_level: { ...data.care_level.gia_tri } }); setMsg(null); }}
              disabled={soDoi === 0}
              className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg border border-neutral-200 bg-white text-sm text-neutral-700 disabled:opacity-40"
            >
              <RotateCcw className="w-4 h-4" /> Hoàn tác
            </button>
            <button
              type="button"
              onClick={() => { setMsg(null); save.mutate(); }}
              disabled={soDoi === 0 || !!clientErr || save.isPending}
              className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-blue-600 text-white text-sm font-medium disabled:opacity-40"
            >
              {save.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Lưu {soDoi > 0 ? `(${soDoi})` : ''}
            </button>
          </div>
        </div>
        <pre className="mt-3 text-[12px] leading-5 text-neutral-700 bg-neutral-50 border border-neutral-100 rounded-lg px-3 py-2 overflow-x-auto whitespace-pre">
{data.cong_thuc.join('\n')}
        </pre>
        {(clientErr || msg) && (
          <p className={cn('mt-3 text-sm rounded-lg px-3 py-2 border',
            clientErr || msg?.tone === 'err' ? 'bg-red-50 border-red-200 text-red-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800')}>
            {clientErr ?? msg?.text}
          </p>
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <ParamCard
          title="Tầng 3 — Ngưỡng cảnh báo"
          subtitle={`system_config → ${data.thresholds.config_key}`}
          nguon={data.thresholds.nguon}
          keys={Object.keys(data.thresholds.mo_ta)}
          moTa={data.thresholds.mo_ta}
          values={draft.thresholds}
          defaults={data.thresholds.mac_dinh}
          onChange={(k, v) => setDraft({ ...draft, thresholds: { ...draft.thresholds, [k]: v } })}
        />
        <ParamCard
          title="Tầng 2 — Định mức & tỷ trọng rổ"
          subtitle={`system_config → ${data.care_level.config_key}`}
          nguon={data.care_level.nguon}
          keys={Object.keys(data.care_level.mo_ta)}
          moTa={data.care_level.mo_ta}
          values={draft.care_level}
          defaults={data.care_level.mac_dinh}
          onChange={(k, v) => setDraft({ ...draft, care_level: { ...draft.care_level, [k]: v } })}
        />
      </div>
    </div>
  );
}

function ParamCard<T extends Record<string, number | string>>({
  title, subtitle, nguon, keys, moTa, values, defaults, onChange,
}: {
  title: string;
  subtitle: string;
  nguon: string | null;
  keys: string[];
  moTa: Record<string, ParamMeta>;
  values: T;
  defaults: T;
  onChange: (k: string, v: number | string) => void;
}) {
  return (
    <div className="bg-white rounded-2xl border border-neutral-200">
      <div className="px-5 py-3.5 border-b border-neutral-100">
        <h4 className="font-semibold text-neutral-900">{title}</h4>
        <p className="text-[11px] text-neutral-500 font-mono">{subtitle}</p>
      </div>
      <div className="divide-y divide-neutral-100">
        {keys.map((k) => {
          const m = moTa[k];
          const v = values[k];
          const isKy = m.kieu === 'ky';
          const daDoi = String(v) !== String(defaults[k]);
          return (
            <div key={k} className="px-5 py-3 grid grid-cols-[1fr_140px] gap-3 items-start">
              <div>
                <label htmlFor={`dss-${k}`} className="text-sm font-medium text-neutral-800">
                  {m.ten}
                </label>
                <p className="text-xs text-neutral-500 mt-0.5 leading-snug">{m.y_nghia}</p>
                <p className="text-[11px] text-neutral-400 mt-0.5 font-mono">
                  {k} · mặc định {String(defaults[k])}
                  {!isKy && m.min != null ? ` · [${m.min}, ${m.max}]` : ''}
                </p>
              </div>
              <input
                id={`dss-${k}`}
                type={isKy ? 'text' : 'number'}
                inputMode={isKy ? 'text' : 'decimal'}
                value={v}
                min={m.min}
                max={m.max}
                step={k === 'overstock_factor' ? 0.1 : 1}
                pattern={isKy ? '\\d{4}-\\d{2}' : undefined}
                placeholder={isKy ? 'YYYY-MM' : undefined}
                onChange={(e) => onChange(k, isKy ? e.target.value : e.target.value === '' ? '' : Number(e.target.value))}
                className={cn(
                  'h-9 w-full px-3 rounded-lg border text-sm text-right tabular-nums focus:outline-none focus:ring-2 focus:ring-blue-500/30',
                  daDoi ? 'border-blue-300 bg-blue-50/40' : 'border-neutral-200 bg-white',
                )}
              />
            </div>
          );
        })}
      </div>
      {nguon && (
        <div className="px-5 py-2.5 border-t border-neutral-100 text-[11px] text-neutral-500 leading-snug">
          Nguồn giá trị hiện tại: {nguon}
        </div>
      )}
    </div>
  );
}
