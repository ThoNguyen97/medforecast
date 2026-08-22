import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  Database,
  Loader2,
  Plug,
  Save,
  XCircle,
} from 'lucide-react';
import {
  syncService,
  type ConnectionTestResult,
  type HisConnectionConfig,
  type HisConnectionInput,
} from '../../services/syncService';
import { cn } from '../../utils/cn';

/**
 * Quản trị → Kết nối HIS.
 *
 * Cấu hình lưu trong DB (bảng system_config) thay vì file .env: admin đổi
 * host/mật khẩu ngay trên giao diện, có nút thử kết nối trước khi lưu, và lần
 * đồng bộ sau tự dùng cấu hình mới — không cần khởi động lại backend.
 *
 * Mật khẩu chỉ đi MỘT CHIỀU (client → server). Server không bao giờ trả lại,
 * form chỉ biết "đã đặt hay chưa" qua has_password.
 */

const RONG: HisConnectionInput = {
  source: 'sqlserver',
  host: '',
  port: 1433,
  instance: '',
  database: 'MEDFORECAST_DW',
  username: 'medforecast_app',
  password: '',
  driver: 'ODBC Driver 18 for SQL Server',
  trust_cert: true,
  sql_profile: 'sta',
  lookback_months: 3,
};

export default function HisConnectionSection() {
  const queryClient = useQueryClient();
  const { data: cfg, isLoading } = useQuery({
    queryKey: ['sync', 'config'],
    queryFn: () => syncService.getConfig(),
  });

  const [form, setForm] = useState<HisConnectionInput>(RONG);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (cfg) {
      const { has_password: _hp, da_luu_trong_db: _db, ...rest } = cfg;
      setForm({ ...rest, password: '' });
    }
  }, [cfg]);

  const testMut = useMutation({
    mutationFn: () => syncService.testConfig(form),
    onSuccess: setTestResult,
    onError: (e: unknown) =>
      setTestResult({
        ok: false,
        steps: [{ name: 'Gọi API', ok: false, detail: String((e as Error)?.message ?? e) }],
      }),
  });

  const saveMut = useMutation({
    mutationFn: () => syncService.saveConfig(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sync', 'config'] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  const doi = <K extends keyof HisConnectionInput>(k: K, v: HisConnectionInput[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    setTestResult(null); // cấu hình đã đổi → kết quả thử cũ không còn giá trị
  };

  const laSqlServer = form.source === 'sqlserver';

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-neutral-500 p-6">
        <Loader2 className="w-4 h-4 animate-spin" /> Đang tải cấu hình…
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Nguồn dữ liệu */}
      <div className="bg-white rounded-2xl border border-neutral-200 p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Database className="w-5 h-5 text-primary-600" />
          <h3 className="font-semibold text-neutral-800">Nguồn dữ liệu đồng bộ</h3>
          {cfg?.da_luu_trong_db ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              đang dùng cấu hình lưu trong hệ thống
            </span>
          ) : (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
              chưa lưu — đang chạy theo file .env trên máy chủ
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-4">
          {(
            [
              ['sqlserver', 'SQL Server (DB trung chuyển STA)', 'Đọc dữ liệu HIS đã tổng hợp — dùng khi triển khai'],
              ['file', 'File CSV nội bộ', 'Dữ liệu mẫu đóng gói sẵn — dùng khi demo/dev'],
            ] as const
          ).map(([val, label, mota]) => (
            <label
              key={val}
              className={cn(
                'flex-1 min-w-[260px] border rounded-xl p-3 cursor-pointer transition',
                form.source === val
                  ? 'border-primary-500 bg-primary-50/50 ring-1 ring-primary-500'
                  : 'border-neutral-200 hover:border-neutral-300',
              )}
            >
              <input
                type="radio"
                className="sr-only"
                checked={form.source === val}
                onChange={() => doi('source', val)}
              />
              <div className="font-medium text-sm text-neutral-800">{label}</div>
              <div className="text-xs text-neutral-500 mt-0.5">{mota}</div>
            </label>
          ))}
        </div>
      </div>

      {/* Thông số kết nối */}
      {laSqlServer && (
        <div className="bg-white rounded-2xl border border-neutral-200 p-5 space-y-4">
          <h3 className="font-semibold text-neutral-800">Thông số kết nối</h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Truong label="Máy chủ (host/IP)" required>
              <input className={o} value={form.host} placeholder="vd: 10.0.0.20"
                     onChange={(e) => doi('host', e.target.value)} />
            </Truong>
            <Truong label="Instance (nếu có)" ghiChu="Đặt instance thì port bị bỏ qua">
              <input className={o} value={form.instance} placeholder="vd: STA"
                     onChange={(e) => doi('instance', e.target.value)} />
            </Truong>
            <Truong label="Port">
              <input className={o} type="number" value={form.port} disabled={!!form.instance}
                     onChange={(e) => doi('port', Number(e.target.value) || 1433)} />
            </Truong>

            <Truong label="Database" required>
              <input className={o} value={form.database}
                     onChange={(e) => doi('database', e.target.value)} />
            </Truong>
            <Truong label="Tài khoản" required>
              <input className={o} value={form.username} autoComplete="off"
                     onChange={(e) => doi('username', e.target.value)} />
            </Truong>
            <Truong
              label="Mật khẩu"
              required={!cfg?.has_password}
              ghiChu={cfg?.has_password ? 'Để trống = giữ mật khẩu đã lưu' : undefined}
            >
              <input className={o} type="password" value={form.password ?? ''}
                     placeholder={cfg?.has_password ? '••••••••' : ''}
                     autoComplete="new-password"
                     onChange={(e) => doi('password', e.target.value)} />
            </Truong>

            <Truong label="Driver ODBC">
              <select className={o} value={form.driver}
                      onChange={(e) => doi('driver', e.target.value)}>
                <option>ODBC Driver 18 for SQL Server</option>
                <option>ODBC Driver 17 for SQL Server</option>
              </select>
            </Truong>
            <Truong label="Cửa sổ nạp lại (tháng)"
                    ghiChu="Phải khớp @SoThangLuiLai của job bên HIS">
              <input className={o} type="number" min={0} max={24} value={form.lookback_months}
                     onChange={(e) => doi('lookback_months', Number(e.target.value) || 0)} />
            </Truong>
            <Truong label="Chứng chỉ máy chủ">
              <label className="flex items-center gap-2 h-10 text-sm text-neutral-700">
                <input type="checkbox" className="rounded border-neutral-300"
                       checked={form.trust_cert}
                       onChange={(e) => doi('trust_cert', e.target.checked)} />
                Tin chứng chỉ tự ký (mạng nội bộ)
              </label>
            </Truong>
          </div>
        </div>
      )}

      {/* Hành động + kết quả thử */}
      <div className="bg-white rounded-2xl border border-neutral-200 p-5 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => testMut.mutate()}
            disabled={testMut.isPending || (laSqlServer && !form.host)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-neutral-300 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            {testMut.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Plug className="w-4 h-4" />}
            Kiểm tra kết nối
          </button>

          <button
            onClick={() => saveMut.mutate()}
            disabled={saveMut.isPending || (laSqlServer && !form.host)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50"
          >
            {saveMut.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Save className="w-4 h-4" />}
            Lưu cấu hình
          </button>

          {saved && (
            <span className="inline-flex items-center gap-1 text-sm text-emerald-600">
              <CheckCircle2 className="w-4 h-4" /> Đã lưu — lần đồng bộ sau sẽ dùng cấu hình này
            </span>
          )}
          {saveMut.isError && (
            <span className="inline-flex items-center gap-1 text-sm text-red-600">
              <XCircle className="w-4 h-4" />
              {String((saveMut.error as Error)?.message ?? 'Lưu thất bại')}
            </span>
          )}
        </div>

        {testResult && (
          <div
            className={cn(
              'rounded-xl border p-4 space-y-2',
              testResult.ok
                ? 'border-emerald-200 bg-emerald-50/50'
                : 'border-red-200 bg-red-50/50',
            )}
          >
            <div className="font-medium text-sm">
              {testResult.ok
                ? 'Kết nối tốt — đọc được dữ liệu từ cả ba nguồn'
                : 'Chưa kết nối được — xem từng bước bên dưới'}
            </div>
            <ul className="space-y-1.5">
              {testResult.steps.map((s, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  {s.ok
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                    : <XCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />}
                  <span>
                    <span className="font-medium">{s.name}:</span>{' '}
                    <span className="text-neutral-600 break-all">{s.detail}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="text-xs text-neutral-500">
          Kiểm tra chạy với cấu hình đang nhập trên form (chưa lưu). Mật khẩu chỉ gửi
          một chiều lên máy chủ và được mã hoá trước khi lưu — hệ thống không bao giờ
          hiển thị lại mật khẩu đã đặt.
        </p>
      </div>
    </div>
  );
}

const o =
  'w-full h-10 px-3 rounded-xl border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-neutral-100 disabled:text-neutral-400';

function Truong({
  label, required, ghiChu, children,
}: {
  label: string; required?: boolean; ghiChu?: string; children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-neutral-700 mb-1">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {ghiChu && <p className="text-xs text-neutral-400 mt-1">{ghiChu}</p>}
    </div>
  );
}
