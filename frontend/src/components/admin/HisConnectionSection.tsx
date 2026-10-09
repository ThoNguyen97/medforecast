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
  type HisConnectionInput,
} from '../../services/syncService';
import { cn } from '../../utils/cn';

/** Cấu hình kết nối CSDL DW, lưu ở system_config.
 *  Mật khẩu chỉ đi một chiều: server không trả lại, form chỉ biết has_password. */

const RONG: HisConnectionInput = {
  source: 'sqlserver',
  host: 'localhost',
  port: 1433,
  instance: '',
  database: 'MEDFORECAST_DW',
  auth: 'windows',
  username: 'medforecast_app',
  password: '',
  driver: 'ODBC Driver 18 for SQL Server',
  trust_cert: true,
  sql_profile: 'dw',
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
    setTestResult(null); // cấu hình đổi thì kết quả thử cũ vô hiệu
  };

  const laSqlServer = form.source === 'sqlserver';
  const laWindowsAuth = form.auth === 'windows';

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
          <h3 className="font-semibold text-neutral-800">Nguồn dữ liệu: CSDL trung gian MEDFORECAST_DW</h3>
          {cfg?.da_luu_trong_db ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              đang dùng cấu hình lưu trong hệ thống
            </span>
          ) : (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
              chưa lưu: đang chạy theo file .env của backend
            </span>
          )}
        </div>

        <div className="border rounded-xl p-3 border-primary-500 bg-primary-50/50 ring-1 ring-primary-500 max-w-xl">
          <div className="font-medium text-sm text-neutral-800">SQL Server: CSDL trung gian MEDFORECAST_DW</div>
          <div className="text-xs text-neutral-500 mt-0.5">
            Cơ sở dữ liệu trung gian của bệnh viện (12 bảng MF_*, đã khử định danh, được đồng bộ tự động
            hằng đêm bằng các thủ tục usp_MedForecast_*). Ứng dụng chỉ đọc 7 view vw_MedForecast_*
            tại đây, không kết nối trực tiếp tới HIS.
          </div>
        </div>
      </div>

      {/* Thông số kết nối */}
      {laSqlServer && (
        <div className="bg-white rounded-2xl border border-neutral-200 p-5 space-y-4">
          <h3 className="font-semibold text-neutral-800">Thông số kết nối</h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Truong label="Máy chủ SQL Server" required ghiChu="Tên máy hoặc địa chỉ IP máy chủ MEDFORECAST_DW">
              <input className={o} value={form.host} placeholder="localhost"
                     onChange={(e) => doi('host', e.target.value)} />
            </Truong>
            <Truong label="Instance (nếu có)" ghiChu="Đặt instance thì port bị bỏ qua">
              <input className={o} value={form.instance} placeholder="vd: SQLEXPRESS"
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
            <Truong label="Xác thực" ghiChu="SQL auth với tài khoản chỉ đọc medforecast_app, hoặc Windows Authentication">
              <select className={o} value={form.auth}
                      onChange={(e) => doi('auth', e.target.value as 'windows' | 'sql')}>
                <option value="windows">Windows Authentication</option>
                <option value="sql">SQL Server Authentication (tài khoản/mật khẩu)</option>
              </select>
            </Truong>
            <Truong label="Tài khoản" required={!laWindowsAuth}>
              <input className={o} value={form.username} autoComplete="off" disabled={laWindowsAuth}
                     onChange={(e) => doi('username', e.target.value)} />
            </Truong>
            <Truong
              label="Mật khẩu"
              required={!laWindowsAuth && !cfg?.has_password}
              ghiChu={laWindowsAuth ? 'Không dùng với Windows Authentication'
                      : cfg?.has_password ? 'Để trống = giữ mật khẩu đã lưu' : undefined}
            >
              <input className={o} type="password" value={form.password ?? ''}
                     placeholder={cfg?.has_password ? '••••••••' : ''} disabled={laWindowsAuth}
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
            <Truong label="Số kỳ nạp lại (tháng)"
                    ghiChu="Số kỳ gần nhất được xoá-nạp lại mỗi lần đồng bộ">
              <input className={o} type="number" min={0} max={24} value={form.lookback_months}
                     onChange={(e) => doi('lookback_months', Number(e.target.value) || 0)} />
            </Truong>
            <Truong label="Chứng chỉ máy chủ">
              <label className="flex items-center gap-2 h-10 text-sm text-neutral-700">
                <input type="checkbox" className="rounded border-neutral-300"
                       checked={form.trust_cert}
                       onChange={(e) => doi('trust_cert', e.target.checked)} />
                Tin chứng chỉ tự ký của máy chủ SQL Server
              </label>
            </Truong>
          </div>
        </div>
      )}

      {/* Hành động */}
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
              <CheckCircle2 className="w-4 h-4" /> Đã lưu: lần đồng bộ sau sẽ dùng cấu hình này
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
                ? 'Kết nối tốt: đọc được đủ 7 view vw_MedForecast_*'
                : 'Chưa kết nối được: xem từng bước bên dưới'}
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
          một chiều lên máy chủ và được mã hoá trước khi lưu, hệ thống không bao giờ
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
