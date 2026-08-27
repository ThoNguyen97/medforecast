import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  Layers,
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
  useAdminDiseaseGroups,
  useCreateDisease,
  useCreateDiseaseGroup,
  useDeleteDisease,
  useDeleteDiseaseGroup,
  useSafetyRate,
  useUpdateDisease,
  useUpdateDiseaseGroup,
  useUpdateSafetyRate,
} from '../../hooks/useAdminCatalog';
import type {
  DiseaseGroupItem,
  DiseaseItem,
} from '../../services/adminCatalogService';

export default function ConfigurationsSection() {
  return (
    <div className="space-y-5">
      <SafetyRateCard />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <DiseaseConfigCard />
        <DiseaseGroupConfigCard />
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

// ── Disease group catalog ────────────────────────────────────────────────────

function DiseaseGroupConfigCard() {
  const { data: groups = [], isLoading } = useAdminDiseaseGroups();
  const { data: diseases = [] } = useAdminDiseases();
  const createMut = useCreateDiseaseGroup();
  const updateMut = useUpdateDiseaseGroup();
  const deleteMut = useDeleteDiseaseGroup();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<DiseaseGroupItem | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<DiseaseGroupItem | null>(null);

  const diseaseLabel = (code: string) =>
    diseases.find((d) => d.key === code)?.label ?? code;

  const onSave = async (vals: DiseaseGroupItem) => {
    if (editing) {
      await updateMut.mutateAsync({ key: editing.key, payload: vals });
    } else {
      await createMut.mutateAsync(vals);
    }
  };

  const sortedList = useMemo(
    () => [...groups].sort((a, b) => a.name.localeCompare(b.name, 'vi')),
    [groups],
  );

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center">
            <Layers className="w-4 h-4 text-emerald-600" />
          </span>
          <div>
            <h3 className="text-sm font-semibold text-neutral-900">Danh mục nhóm bệnh</h3>
            <p className="text-xs text-neutral-500">
              Gộp các bệnh liên quan thành nhóm — dùng để hiển thị & lọc
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
          Thêm nhóm bệnh
        </button>
      </div>

      <ul className="divide-y divide-neutral-100 max-h-[460px] overflow-y-auto">
        {isLoading ? (
          <li className="px-5 py-6 flex items-center gap-2 text-sm text-neutral-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Đang tải...
          </li>
        ) : sortedList.length === 0 ? (
          <li className="px-5 py-6 text-sm text-neutral-400 text-center">
            Chưa có nhóm bệnh nào
          </li>
        ) : (
          sortedList.map((g) => (
            <li
              key={g.key}
              className="px-5 py-3 flex items-center justify-between gap-3 hover:bg-neutral-50/60"
            >
              <div className="min-w-0">
                <p className="text-sm font-semibold text-neutral-900">{g.name}</p>
                <p className="text-xs text-neutral-400 mt-0.5">{g.key}</p>
                <p className="text-xs text-neutral-500 mt-0.5 truncate max-w-sm">
                  {g.icd_codes.length === 0
                    ? 'Chưa gán bệnh nào'
                    : `${g.icd_codes.length} bệnh: ${g.icd_codes
                        .map((c) => diseaseLabel(c))
                        .join(', ')}`}
                </p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <IconButton
                  title="Sửa"
                  onClick={() => {
                    setEditing(g);
                    setDialogOpen(true);
                  }}
                >
                  <Pencil className="w-3.5 h-3.5 text-blue-600" />
                </IconButton>
                <IconButton
                  title="Xoá"
                  onClick={() => setConfirmDelete(g)}
                >
                  <Trash2 className="w-3.5 h-3.5 text-red-600" />
                </IconButton>
              </div>
            </li>
          ))
        )}
      </ul>

      {dialogOpen && (
        <DiseaseGroupFormDialog
          initial={editing}
          diseases={diseases}
          onClose={() => setDialogOpen(false)}
          onSubmit={onSave}
        />
      )}

      {confirmDelete && (
        <ConfirmDialog
          title="Xoá nhóm bệnh"
          message={`Xoá nhóm bệnh "${confirmDelete.name}"? Các bệnh trong nhóm vẫn còn ở Danh mục bệnh, chỉ nhóm bị xoá.`}
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

function DiseaseGroupFormDialog({
  initial,
  diseases,
  onClose,
  onSubmit,
}: {
  initial: DiseaseGroupItem | null;
  diseases: DiseaseItem[];
  onClose: () => void;
  onSubmit: (vals: DiseaseGroupItem) => Promise<void>;
}) {
  const [vals, setVals] = useState<DiseaseGroupItem>(
    initial ?? { key: '', name: '', icd_codes: [] },
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isEdit = !!initial;

  const toggleCode = (code: string) => {
    setVals((v) => ({
      ...v,
      icd_codes: v.icd_codes.includes(code)
        ? v.icd_codes.filter((c) => c !== code)
        : [...v.icd_codes, code],
    }));
  };

  return (
    <DialogShell title={isEdit ? 'Sửa nhóm bệnh' : 'Thêm nhóm bệnh mới'} onClose={onClose}>
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
        <Field label="Mã nhóm (key)" required>
          <input
            type="text"
            required
            disabled={isEdit}
            value={vals.key}
            onChange={(e) => setVals({ ...vals, key: e.target.value })}
            className={inputClass + (isEdit ? ' bg-neutral-50 text-neutral-500' : '')}
            placeholder="J00-J06"
          />
        </Field>
        <Field label="Tên nhóm" required>
          <input
            type="text"
            required
            value={vals.name}
            onChange={(e) => setVals({ ...vals, name: e.target.value })}
            className={inputClass}
            placeholder="Nhiễm khuẩn cấp đường hô hấp trên"
          />
        </Field>
        <Field label={`Bệnh thuộc nhóm (${vals.icd_codes.length} đã chọn)`}>
          <div className="max-h-48 overflow-y-auto border border-neutral-200 rounded-lg divide-y divide-neutral-100">
            {diseases.length === 0 ? (
              <p className="px-3 py-3 text-xs text-neutral-400">
                Chưa có bệnh nào trong Danh mục bệnh — thêm bệnh trước.
              </p>
            ) : (
              diseases.map((d) => (
                <label
                  key={d.key}
                  className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-neutral-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={vals.icd_codes.includes(d.key)}
                    onChange={() => toggleCode(d.key)}
                    className="rounded border-neutral-300"
                  />
                  <span className="text-neutral-700">{d.label}</span>
                  <span className="text-neutral-400 text-xs ml-auto shrink-0">{d.key}</span>
                </label>
              ))
            )}
          </div>
        </Field>
        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error}
          </div>
        )}
        <DialogFooter
          submitting={submitting}
          submitLabel={isEdit ? 'Lưu thay đổi' : 'Thêm nhóm bệnh'}
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
