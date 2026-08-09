import { forwardRef, useEffect, useState } from 'react';
import { Loader2, Save } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  useConversionRatios,
  useThresholds,
  useUpdateConversionRatios,
  useUpdateThresholds,
} from '../../hooks/useConfig';
import { DISEASE_TYPE_OPTIONS } from '../../types/config';

const thresholdsSchema = z
  .object({
    critical_days: z.number().min(1).max(30),
    high_days: z.number().min(1).max(60),
    medium_days: z.number().min(1).max(90),
  })
  .refine((v) => v.critical_days < v.high_days, {
    message: 'Nguy hiểm phải nhỏ hơn Cao',
    path: ['critical_days'],
  })
  .refine((v) => v.high_days < v.medium_days, {
    message: 'Cao phải nhỏ hơn Trung bình',
    path: ['high_days'],
  });

const ratiosSchema = z.object({
  ratios: z.array(
    z.object({
      disease_type: z.string(),
      supply_id: z.number(),
      supply_name: z.string().optional(),
      ratio: z.number().min(0.001).max(1000),
      unit: z.string().optional(),
    }),
  ),
});

type ThresholdsForm = z.infer<typeof thresholdsSchema>;
type RatiosForm = z.infer<typeof ratiosSchema>;

export default function ThresholdsAndRatiosSection() {
  return (
    <div className="space-y-5">
      {/* ConversionRatiosCard đã ẩn — định mức dùng cho dự báo nằm ở tab
          "Định mức thuốc/vật tư" (theo Nhẹ/TB/Nặng). */}
      <ThresholdsCard />
    </div>
  );
}

// ── Định mức vật tư cho từng bệnh ──────────────────────────────────────────

function ConversionRatiosCard() {
  const { data: ratios, isLoading } = useConversionRatios();
  const updateMut = useUpdateConversionRatios();
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    formState: { isDirty, errors },
  } = useForm<RatiosForm>({
    resolver: zodResolver(ratiosSchema),
    defaultValues: { ratios: [] },
  });

  useEffect(() => {
    if (ratios) {
      reset({
        ratios: ratios.map((r) => ({
          disease_type: r.disease_type,
          supply_id: r.supply_id,
          supply_name: r.supply_name ?? undefined,
          ratio: r.ratio,
          unit: r.unit ?? undefined,
        })),
      });
    }
  }, [ratios, reset]);

  const onSubmit = async (vals: RatiosForm) => {
    await updateMut.mutateAsync({
      ratios: vals.ratios.map(({ disease_type, supply_id, ratio, unit }) => ({
        disease_type,
        supply_id,
        ratio,
        unit: unit ?? undefined,
      })),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const diseaseLabel = (key: string) =>
    DISEASE_TYPE_OPTIONS.find((d) => d.value === key)?.label ?? key;

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="bg-white rounded-2xl border border-neutral-200 overflow-hidden"
    >
      <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-900">
            Định mức vật tư theo bệnh
          </h3>
          <p className="text-xs text-neutral-500 mt-0.5">
            Số đơn vị vật tư trên mỗi ca bệnh, dùng cho công thức tính nhu cầu.
          </p>
        </div>
        <button
          type="submit"
          disabled={!isDirty || updateMut.isPending}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50"
        >
          {updateMut.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Lưu định mức
        </button>
      </div>

      {isLoading ? (
        <div className="py-10 flex justify-center text-sm text-neutral-500">
          <Loader2 className="w-4 h-4 animate-spin mr-2" />
          Đang tải...
        </div>
      ) : !ratios || ratios.length === 0 ? (
        <div className="py-10 text-center text-sm text-neutral-400">
          Chưa có dữ liệu định mức
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-neutral-500 text-[11px] uppercase tracking-wider border-b border-neutral-100 bg-neutral-50/60">
                <th className="text-left px-5 py-3 font-semibold">Loại bệnh</th>
                <th className="text-left px-5 py-3 font-semibold">Vật tư</th>
                <th className="text-right px-5 py-3 font-semibold">Định mức / ca</th>
                <th className="text-left px-5 py-3 font-semibold">Đơn vị</th>
              </tr>
            </thead>
            <tbody>
              {ratios.map((r, idx) => (
                <tr key={`${r.disease_type}-${r.supply_id}`} className="border-t border-neutral-100">
                  <td className="px-5 py-2.5 text-neutral-700">
                    {diseaseLabel(r.disease_type)}
                    <input type="hidden" {...register(`ratios.${idx}.disease_type`)} />
                    <input type="hidden" {...register(`ratios.${idx}.supply_id`, { valueAsNumber: true })} />
                  </td>
                  <td className="px-5 py-2.5 font-medium text-neutral-900">
                    {r.supply_name ?? `Supply #${r.supply_id}`}
                  </td>
                  <td className="px-5 py-2 text-right">
                    <input
                      type="number"
                      step="0.001"
                      min={0.001}
                      max={1000}
                      {...register(`ratios.${idx}.ratio`, { valueAsNumber: true })}
                      className="w-32 px-2 py-1.5 rounded-lg border border-neutral-200 text-sm text-right focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
                    />
                    {errors.ratios?.[idx]?.ratio && (
                      <p className="text-[11px] text-red-600 mt-0.5">Giá trị không hợp lệ</p>
                    )}
                  </td>
                  <td className="px-5 py-2">
                    <input
                      type="text"
                      {...register(`ratios.${idx}.unit`)}
                      className="w-24 px-2 py-1.5 rounded-lg border border-neutral-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {saved && (
        <div className="px-5 py-2.5 text-sm text-emerald-700 bg-emerald-50 border-t border-emerald-100">
          ✓ Đã lưu định mức vật tư
        </div>
      )}
    </form>
  );
}

// ── Ngưỡng cảnh báo (số ngày tồn kho) — single global threshold ─────────────

function ThresholdsCard() {
  const { data: thresholds, isLoading } = useThresholds();
  const updateMut = useUpdateThresholds();
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    formState: { isDirty, errors },
  } = useForm<ThresholdsForm>({
    resolver: zodResolver(thresholdsSchema),
    defaultValues: { critical_days: 3, high_days: 7, medium_days: 14 },
  });

  useEffect(() => {
    if (thresholds) {
      reset({
        critical_days: thresholds.critical_days,
        high_days: thresholds.high_days,
        medium_days: thresholds.medium_days,
      });
    }
  }, [thresholds, reset]);

  const onSubmit = async (vals: ThresholdsForm) => {
    await updateMut.mutateAsync(vals);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="bg-white rounded-2xl border border-neutral-200 overflow-hidden"
    >
      <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-900">
            Ngưỡng cảnh báo tồn kho
          </h3>
          <p className="text-xs text-neutral-500 mt-0.5">
            Số ngày tồn kho tương ứng từng mức độ cảnh báo (Nguy hiểm &lt; Cao &lt; Trung bình).
          </p>
        </div>
        <button
          type="submit"
          disabled={!isDirty || updateMut.isPending}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50"
        >
          {updateMut.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Lưu ngưỡng
        </button>
      </div>

      {isLoading ? (
        <div className="py-10 flex justify-center text-sm text-neutral-500">
          <Loader2 className="w-4 h-4 animate-spin mr-2" />
          Đang tải...
        </div>
      ) : (
        <div className="px-5 py-5 grid grid-cols-1 sm:grid-cols-3 gap-4">
          <ThresholdField
            label="Nguy hiểm (ngày)"
            color="red"
            min={1}
            max={30}
            error={errors.critical_days?.message}
            {...register('critical_days', { valueAsNumber: true })}
          />
          <ThresholdField
            label="Cao (ngày)"
            color="amber"
            min={1}
            max={60}
            error={errors.high_days?.message}
            {...register('high_days', { valueAsNumber: true })}
          />
          <ThresholdField
            label="Trung bình (ngày)"
            color="yellow"
            min={1}
            max={90}
            {...register('medium_days', { valueAsNumber: true })}
          />
        </div>
      )}

      <div className="px-5 pb-4 text-xs text-neutral-500">
        Ý nghĩa: Khi tồn kho dự kiến sẽ hết trong vòng <strong>X ngày</strong>,
        hệ thống đánh dấu vật tư ở mức cảnh báo tương ứng.
      </div>

      {saved && (
        <div className="px-5 py-2.5 text-sm text-emerald-700 bg-emerald-50 border-t border-emerald-100">
          ✓ Đã lưu ngưỡng cảnh báo
        </div>
      )}
    </form>
  );
}

const COLOR_RING: Record<string, string> = {
  red: 'focus:ring-red-500/30 focus:border-red-500',
  amber: 'focus:ring-amber-500/30 focus:border-amber-500',
  yellow: 'focus:ring-yellow-500/30 focus:border-yellow-500',
};

const COLOR_LABEL: Record<string, string> = {
  red: 'text-red-600',
  amber: 'text-amber-600',
  yellow: 'text-yellow-600',
};

type ThresholdFieldProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  color: 'red' | 'amber' | 'yellow';
  error?: string;
};

const ThresholdField = forwardRef<HTMLInputElement, ThresholdFieldProps>(
  function ThresholdFieldImpl({ label, color, error, ...rest }, ref) {
    return (
      <label className="block">
        <span className={`block text-xs font-semibold uppercase tracking-wide mb-1.5 ${COLOR_LABEL[color]}`}>
          {label}
        </span>
        <input
          ref={ref}
          type="number"
          {...rest}
          className={`w-full h-10 px-3 rounded-lg border border-neutral-300 text-sm text-right tabular-nums focus:outline-none focus:ring-2 ${COLOR_RING[color]}`}
        />
        {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
      </label>
    );
  },
);
