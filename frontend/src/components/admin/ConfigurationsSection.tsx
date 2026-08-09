import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  MapPin,
  Loader2,
  Plus,
  Pencil,
  Trash2,
  Save,
  Percent,
  X,
} from 'lucide-react';
import {
  useAdminDiseases,
  useAdminRegions,
  useCreateDisease,
  useCreateRegion,
  useDeleteDisease,
  useDeleteRegion,
  useSafetyRate,
  useUpdateDisease,
  useUpdateSafetyRate,
} from '../../hooks/useAdminCatalog';
import type {
  DiseaseItem,
  RegionItem,
} from '../../services/adminCatalogService';

export default function ConfigurationsSection() {
  return (
    <div className="space-y-5">
      <SafetyRateCard />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <DiseaseConfigCard />
        <RegionConfigCard />
      </div>
    </div>
  );
}

// ── Safety rate ─────────────────────────────────────────────────────────────

function SafetyRateCard() {
  const { data: rate, isLoading } = useSafetyRate();
  const updateMut = useUpdateSafetyRate();
  const [value, setValue] = useState<number>(0);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (rate !== undefined) setValue(Math.round(rate * 100));
  }, [rate]);

  const onSave = async () => {
    await updateMut.mutateAsync(Math.max(0, Math.min(100, value)) / 100);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5 flex flex-wrap items-center gap-5 justify-between">
      <div className="flex items-center gap-3">
        <span className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center shrink-0">
          <Percent className="w-5 h-5 text-amber-600" />
        </span>
        <div>
          <h3 className="text-sm font-semibold text-neutral-900">
            Hệ số dự phòng (Safety Stock)
          </h3>
          <p className="text-xs text-neutral-500 mt-0.5 max-w-md">
            Tỷ lệ dự phòng cộng thêm vào nhu cầu khi tính số lượng đề xuất nhập kho.
            Mặc định 15%.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin text-neutral-400" />
        ) : (
          <div className="relative">
            <input
              type="number"
              min={0}
              max={100}
              step={1}
              value={value}
              onChange={(e) => setValue(Number(e.target.value))}
              className="w-24 h-10 pl-3 pr-9 rounded-lg border border-neutral-200 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-neutral-500 pointer-events-none">
              %
            </span>
          </div>
        )}
        <button
          type="button"
          onClick={onSave}
          disabled={updateMut.isPending}
          className="inline-flex items-center gap-2 px-4 h-10 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-60"
        >
          {updateMut.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Lưu
        </button>
        {saved && (
          <span className="text-xs text-emerald-700 bg-emerald-50 px-2 py-1 rounded-full">
            ✓ Đã lưu
          </span>
        )}
      </div>
    </div>
  );
}

// ── Disease catalog ─────────────────────────────────────────────────────────

function DiseaseConfigCard() {
  const { data: diseases = [], isLoading } = useAdminDiseases();
  const createMut = useCreateDisease();
  const updateMut = useUpdateDisease();
  const deleteMut = useDeleteDisease();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<DiseaseItem | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<DiseaseItem | null>(null);

  const onSave = async (vals: DiseaseItem) => {
    if (editing) {
      await updateMut.mutateAsync({ key: editing.key, payload: vals });
    } else {
      await createMut.mutateAsync(vals);
    }
  };

  const sortedList = useMemo(
    () => [...diseases].sort((a, b) => a.label.localeCompare(b.label, 'vi')),
    [diseases],
  );

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-9 h-9 rounded-xl bg-rose-50 flex items-center justify-center">
            <Activity className="w-4 h-4 text-rose-600" />
          </span>
          <div>
            <h3 className="text-sm font-semibold text-neutral-900">Danh mục bệnh</h3>
            <p className="text-xs text-neutral-500">
              Bệnh đang được hệ thống dự báo & nhập dữ liệu
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
          className="inline-flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700"
        >
          <Plus className="w-3.5 h-3.5" />
          Thêm bệnh
        </button>
      </div>

      <ul className="divide-y divide-neutral-100 max-h-[460px] overflow-y-auto">
        {isLoading ? (
          <li className="px-5 py-6 flex items-center gap-2 text-sm text-neutral-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Đang tải...
          </li>
        ) : sortedList.length === 0 ? (
          <li className="px-5 py-6 text-sm text-neutral-400 text-center">
            Chưa có bệnh nào
          </li>
        ) : (
          sortedList.map((d) => (
            <li
              key={d.key}
              className="px-5 py-3 flex items-center justify-between hover:bg-neutral-50/60"
            >
              <div className="min-w-0">
                <p className="text-sm font-semibold text-neutral-900">{d.label}</p>
                <p className="text-xs text-neutral-400 mt-0.5">{d.key}</p>
                {d.description && (
                  <p className="text-xs text-neutral-500 mt-0.5 truncate max-w-xs">
                    {d.description}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-1">
                <IconButton
                  title="Sửa"
                  onClick={() => {
                    setEditing(d);
                    setDialogOpen(true);
                  }}
                >
                  <Pencil className="w-3.5 h-3.5 text-blue-600" />
                </IconButton>
                <IconButton
                  title="Xoá"
                  onClick={() => setConfirmDelete(d)}
                >
                  <Trash2 className="w-3.5 h-3.5 text-red-600" />
                </IconButton>
              </div>
            </li>
          ))
        )}
      </ul>

      {dialogOpen && (
        <DiseaseFormDialog
          initial={editing}
          onClose={() => setDialogOpen(false)}
          onSubmit={onSave}
        />
      )}

      {confirmDelete && (
        <ConfirmDialog
          title="Xoá bệnh"
          message={`Xoá bệnh "${confirmDelete.label}" khỏi hệ thống?`}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={async () => {
            await deleteMut.mutateAsync(confirmDelete.key);
            setConfirmDelete(null);
          }}
          loading={deleteMut.isPending}
        />
      )}
    </div>
  );
}

// ── Region catalog ──────────────────────────────────────────────────────────

function RegionConfigCard() {
  const { data: regions = [], isLoading } = useAdminRegions();
  const createMut = useCreateRegion();
  const deleteMut = useDeleteRegion();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<RegionItem | null>(null);

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center">
            <MapPin className="w-4 h-4 text-emerald-600" />
          </span>
          <div>
            <h3 className="text-sm font-semibold text-neutral-900">Khu vực địa lý</h3>
            <p className="text-xs text-neutral-500">
              Tỉnh/TP, quận/huyện được dùng cho dữ liệu bệnh & thời tiết
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700"
        >
          <Plus className="w-3.5 h-3.5" />
          Thêm khu vực
        </button>
      </div>

      <ul className="divide-y divide-neutral-100 max-h-[460px] overflow-y-auto">
        {isLoading ? (
          <li className="px-5 py-6 flex items-center gap-2 text-sm text-neutral-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Đang tải...
          </li>
        ) : regions.length === 0 ? (
          <li className="px-5 py-6 text-sm text-neutral-400 text-center">
            Chưa có khu vực nào
          </li>
        ) : (
          regions.map((r) => (
            <li
              key={r.name}
              className="px-5 py-3 flex items-center justify-between hover:bg-neutral-50/60"
            >
              <div className="min-w-0">
                <p className="text-sm font-semibold text-neutral-900">{r.name}</p>
                {r.province && (
                  <p className="text-xs text-neutral-400 mt-0.5">{r.province}</p>
                )}
              </div>
              <IconButton
                title="Xoá"
                onClick={() => setConfirmDelete(r)}
              >
                <Trash2 className="w-3.5 h-3.5 text-red-600" />
              </IconButton>
            </li>
          ))
        )}
      </ul>

      {dialogOpen && (
        <RegionFormDialog
          onClose={() => setDialogOpen(false)}
          onSubmit={async (vals) => {
            await createMut.mutateAsync(vals);
          }}
        />
      )}

      {confirmDelete && (
        <ConfirmDialog
          title="Xoá khu vực"
          message={`Xoá khu vực "${confirmDelete.name}"?`}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={async () => {
            await deleteMut.mutateAsync(confirmDelete.name);
            setConfirmDelete(null);
          }}
          loading={deleteMut.isPending}
        />
      )}
    </div>
  );
}

// ── Reusable dialogs ────────────────────────────────────────────────────────

function DiseaseFormDialog({
  initial,
  onClose,
  onSubmit,
}: {
  initial: DiseaseItem | null;
  onClose: () => void;
  onSubmit: (vals: DiseaseItem) => Promise<void>;
}) {
  const [vals, setVals] = useState<DiseaseItem>(
    initial ?? { key: '', label: '', description: '' },
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isEdit = !!initial;

  return (
    <DialogShell title={isEdit ? 'Sửa bệnh' : 'Thêm bệnh mới'} onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          try {
            setSubmitting(true);
            await onSubmit(vals);
            onClose();
          } catch (err: any) {
            setError(err?.response?.data?.detail || 'Có lỗi xảy ra');
          } finally {
            setSubmitting(false);
          }
        }}
        className="space-y-3"
      >
        <Field label="Mã bệnh (key)" required>
          <input
            type="text"
            required
            disabled={isEdit}
            value={vals.key}
            onChange={(e) => setVals({ ...vals, key: e.target.value })}
            className={inputClass + (isEdit ? ' bg-neutral-50 text-neutral-500' : '')}
            placeholder="dengue_fever"
          />
        </Field>
        <Field label="Tên hiển thị" required>
          <input
            type="text"
            required
            value={vals.label}
            onChange={(e) => setVals({ ...vals, label: e.target.value })}
            className={inputClass}
            placeholder="Sốt xuất huyết"
          />
        </Field>
        <Field label="Mô tả">
          <textarea
            rows={2}
            value={vals.description ?? ''}
            onChange={(e) => setVals({ ...vals, description: e.target.value })}
            className={inputClass + ' h-auto py-2'}
            placeholder="Mô tả ngắn gọn..."
          />
        </Field>
        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error}
          </div>
        )}
        <DialogFooter
          submitting={submitting}
          submitLabel={isEdit ? 'Lưu thay đổi' : 'Thêm bệnh'}
          onCancel={onClose}
        />
      </form>
    </DialogShell>
  );
}

function RegionFormDialog({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (vals: RegionItem) => Promise<void>;
}) {
  const [vals, setVals] = useState<RegionItem>({ name: '', province: '', description: '' });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <DialogShell title="Thêm khu vực" onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          try {
            setSubmitting(true);
            await onSubmit(vals);
            onClose();
          } catch (err: any) {
            setError(err?.response?.data?.detail || 'Có lỗi xảy ra');
          } finally {
            setSubmitting(false);
          }
        }}
        className="space-y-3"
      >
        <Field label="Tên khu vực" required>
          <input
            type="text"
            required
            value={vals.name}
            onChange={(e) => setVals({ ...vals, name: e.target.value })}
            className={inputClass}
            placeholder="Quận 1"
          />
        </Field>
        <Field label="Tỉnh / Thành phố">
          <input
            type="text"
            value={vals.province ?? ''}
            onChange={(e) => setVals({ ...vals, province: e.target.value })}
            className={inputClass}
            placeholder="TP. Hồ Chí Minh"
          />
        </Field>
        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error}
          </div>
        )}
        <DialogFooter
          submitting={submitting}
          submitLabel="Thêm khu vực"
          onCancel={onClose}
        />
      </form>
    </DialogShell>
  );
}

function ConfirmDialog({
  title,
  message,
  onCancel,
  onConfirm,
  loading,
}: {
  title: string;
  message: string;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
  loading?: boolean;
}) {
  return (
    <DialogShell title={title} onClose={onCancel}>
      <p className="text-sm text-neutral-600">{message}</p>
      <div className="flex items-center justify-end gap-2 mt-5">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm font-medium text-neutral-700 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50"
        >
          Huỷ
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-60"
        >
          {loading && <Loader2 className="w-4 h-4 animate-spin" />}
          Xác nhận xoá
        </button>
      </div>
    </DialogShell>
  );
}

// ── Reusable bits ───────────────────────────────────────────────────────────

const inputClass =
  'w-full h-10 px-3 rounded-lg border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500';

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-neutral-600 mb-1.5">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </span>
      {children}
    </label>
  );
}

function DialogShell({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-neutral-100">
          <h3 className="text-base font-semibold text-neutral-900">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-neutral-100 text-neutral-500"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

function DialogFooter({
  submitting,
  submitLabel,
  onCancel,
}: {
  submitting: boolean;
  submitLabel: string;
  onCancel: () => void;
}) {
  return (
    <div className="flex items-center justify-end gap-2 pt-2">
      <button
        type="button"
        onClick={onCancel}
        className="px-4 py-2 text-sm font-medium text-neutral-700 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50"
      >
        Huỷ
      </button>
      <button
        type="submit"
        disabled={submitting}
        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-60"
      >
        {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
        {submitLabel}
      </button>
    </div>
  );
}

function IconButton({
  title,
  onClick,
  children,
}: {
  title: string;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="p-1.5 rounded-md hover:bg-neutral-100"
    >
      {children}
    </button>
  );
}
