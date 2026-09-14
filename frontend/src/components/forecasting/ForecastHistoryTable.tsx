import { Fragment, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Filter,
  Loader2,
  Trash2,
} from 'lucide-react';
import {
  forecastAnalysisService,
  type ForecastHistoryItem,
} from '../../services/forecastAnalysisService';
import { useAuthStore } from '../../store/authStore';
import { formatThoiGianMayChu } from '../../utils/formatters';

interface Props {
  rows: ForecastHistoryItem[];
  isLoading?: boolean;
  /** Gọi sau khi xoá để nạp lại danh sách. */
  onChanged?: () => void;
}

type YeuCauXoa =
  | { kieu: 'mot'; row: ForecastHistoryItem }
  | { kieu: 'tatca' };

/** Số liệu cộng dồn dùng chung cho mọi cấp của cây.
 *  Số ca thực tế và độ lệch không hiện ở đây — chúng nằm ở màn hình Báo cáo. */
interface TongHop {
  duBao: number;
  /** Thời điểm ghi nhận gần nhất trong nhánh. */
  ghiNhanLuc: string | null;
  /** Tài khoản của bản ghi nhận gần nhất trong nhánh. */
  nguoiGhiNhan: string | null;
}

function cong(ds: ForecastHistoryItem[]): TongHop {
  let duBao = 0;
  let ghiNhanLuc: string | null = null;
  let nguoiGhiNhan: string | null = null;
  for (const r of ds) {
    duBao += r.predicted_cases ?? 0;
    if (r.created_at && (!ghiNhanLuc || r.created_at > ghiNhanLuc)) {
      ghiNhanLuc = r.created_at;
      nguoiGhiNhan = r.created_by ?? null;
    }
  }
  return { duBao, ghiNhanLuc, nguoiGhiNhan };
}

/** Bản ghi nhận mới nhất trong danh sách (so theo created_at); null nếu rỗng. */
function moiNhat(ds: ForecastHistoryItem[]): ForecastHistoryItem | null {
  if (ds.length === 0) return null;
  return ds.reduce((a, b) => ((b.created_at ?? '') > (a.created_at ?? '') ? b : a));
}

export default function ForecastHistoryTable({
  rows,
  isLoading,
  onChanged,
}: Props) {
  const { user } = useAuthStore();
  const laQuanTri = user?.role === 'Administrator';

  /** Xoá được khi là người đã ghi nhận bản đó, hoặc là Quản trị viên.
   *  (Backend kiểm tra lại y hệt — đây chỉ là phần hiển thị.) */
  const duocXoa = (r: ForecastHistoryItem) =>
    laQuanTri || (!!r.created_by && r.created_by === user?.username);

  const [xacNhanXoa, setXacNhanXoa] = useState<YeuCauXoa | null>(null);
  const [loiXoa, setLoiXoa] = useState<string | null>(null);
  const [showFilter, setShowFilter] = useState(false);
  const [filterMonth, setFilterMonth] = useState<string>('all');
  const [filterDisease, setFilterDisease] = useState<string>('all');
  /** Nút đang mở, khoá dạng "10/2026" (cấp tháng) và "10/2026|Cúm..." (cấp nhóm). */
  const [dangMo, setDangMo] = useState<Record<string, boolean>>({});

  const xoaMot = useMutation({
    mutationFn: (id: number) => forecastAnalysisService.deleteForecast(id),
    onSuccess: () => {
      setXacNhanXoa(null);
      onChanged?.();
    },
    onError: (err: any) => setLoiXoa(err?.message || 'Không xoá được.'),
  });

  const xoaTatCa = useMutation({
    mutationFn: () => forecastAnalysisService.deleteAllForecasts(),
    onSuccess: () => {
      setXacNhanXoa(null);
      onChanged?.();
    },
    onError: (err: any) => setLoiXoa(err?.message || 'Không xoá được.'),
  });

  const dangXoa = xoaMot.isPending || xoaTatCa.isPending;

  // Toàn bộ bản ghi (kể cả Toàn quốc) dùng để liệt kê tháng/nhóm bệnh cho bộ lọc.
  const uniqueMonths = useMemo(
    () => Array.from(new Set(rows.map((r) => r.month))).sort(),
    [rows],
  );
  const uniqueDiseases = useMemo(
    () => Array.from(new Set(rows.map((r) => r.disease_label))).sort(),
    [rows],
  );

  const filteredRows = useMemo(
    () =>
      rows.filter((r) => {
        if (filterMonth !== 'all' && r.month !== filterMonth) return false;
        if (filterDisease !== 'all' && r.disease_label !== filterDisease)
          return false;
        return true;
      }),
    [rows, filterMonth, filterDisease],
  );

  /** Cây 3 cấp: tháng → nhóm bệnh → (Toàn quốc chính thức + chi tiết theo tỉnh).
   *
   *  Từ 12/09/2026 bản Toàn quốc (location=NULL) dùng công thức top-down
   *  riêng (Tầng 1) — KHÔNG còn là tổng của các tỉnh. Vì vậy số "chính thức"
   *  của tháng/nhóm bệnh LUÔN lấy từ bản Toàn quốc mới nhất (đúng số nuôi
   *  Tổng quan/Cảnh báo), không phải cộng các tỉnh — cộng các tỉnh sẽ ra một
   *  tổng khác, lặp lại đúng kiểu lệch 392/424 cũ ở một màn hình khác. Các
   *  bản theo tỉnh vẫn hiện đầy đủ (kể cả xoá được) nhưng chỉ để tham khảo
   *  dịch tễ, tách hẳn khỏi con số chính thức.
   */
  const cay = useMemo(() => {
    type Xo = { toanQuoc: ForecastHistoryItem[]; tinh: ForecastHistoryItem[] };
    const theoThang = new Map<string, Map<string, Xo>>();
    for (const r of filteredRows) {
      if (!theoThang.has(r.month)) theoThang.set(r.month, new Map());
      const nhom = theoThang.get(r.month)!;
      if (!nhom.has(r.disease_label)) nhom.set(r.disease_label, { toanQuoc: [], tinh: [] });
      const xo = nhom.get(r.disease_label)!;
      (r.is_nationwide ? xo.toanQuoc : xo.tinh).push(r);
    }
    return Array.from(theoThang.entries())
      .sort((a, b) => b[0].localeCompare(a[0])) // tháng mới nhất lên đầu
      .map(([thang, nhomMap]) => {
        const nhoms = Array.from(nhomMap.entries())
          .sort((a, b) => a[0].localeCompare(b[0], 'vi'))
          .map(([tenNhom, { toanQuoc, tinh }]) => {
            const chinhThuc = moiNhat(toanQuoc);
            // Ghi nhận lại Toàn quốc tạo bản mới chứ không sửa bản cũ — các
            // bản cũ hơn vẫn hiện (và xoá được) cùng khu vực "theo tỉnh".
            const toanQuocCu = toanQuoc.filter((r) => r !== chinhThuc);
            return {
              tenNhom,
              chinhThuc,
              toanQuocCu,
              tinh: [...tinh].sort(
                (a, b) => (b.predicted_cases ?? 0) - (a.predicted_cases ?? 0),
              ),
              tongTinh: cong(tinh),
            };
          });
        const banChinhThuc = nhoms
          .map((n) => n.chinhThuc)
          .filter((x): x is ForecastHistoryItem => !!x);
        return {
          thang,
          nhoms,
          tong: cong(banChinhThuc),
          soNhomThieuToanQuoc: nhoms.filter((n) => !n.chinhThuc).length,
        };
      });
  }, [filteredRows]);

  const bat = (khoa: string) =>
    setDangMo((m) => ({ ...m, [khoa]: !(m[khoa] ?? false) }));
  // Mặc định mở hết cả ba cấp — thấy ngay chi tiết từng tỉnh; ai muốn gọn thì
  // tự thu lại.
  const moThang = (k: string) => dangMo[k] ?? true;
  const moNhom = (k: string) => dangMo[k] ?? true;

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4">
        <h3 className="text-sm font-semibold text-neutral-900">
          Lịch sử dự báo gần đây
        </h3>
        <div className="flex items-center gap-1">
          {laQuanTri && rows.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setLoiXoa(null);
                setXacNhanXoa({ kieu: 'tatca' });
              }}
              disabled={dangXoa}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-red-700 bg-red-50 border border-red-200 hover:bg-red-100 disabled:opacity-50"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Xoá toàn bộ
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowFilter(!showFilter)}
            className={`w-9 h-9 inline-flex items-center justify-center rounded-lg text-neutral-500 hover:text-neutral-700 hover:bg-neutral-50 ${
              showFilter ? 'bg-blue-50 text-blue-600' : ''
            }`}
            aria-label="Lọc lịch sử"
          >
            <Filter className="w-4 h-4" />
          </button>
        </div>
      </div>

      {showFilter && (
        <div className="px-5 py-3 bg-neutral-50 border-y border-neutral-100 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs font-medium text-neutral-600 mb-1.5 block">
                Tháng
              </span>
              <select
                value={filterMonth}
                onChange={(e) => setFilterMonth(e.target.value)}
                className="w-full h-9 px-3 rounded-lg border border-neutral-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
              >
                <option value="all">Tất cả các tháng</option>
                {uniqueMonths.map((m) => (
                  <option key={m} value={m}>
                    Tháng {m}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-xs font-medium text-neutral-600 mb-1.5 block">
                Nhóm bệnh
              </span>
              <select
                value={filterDisease}
                onChange={(e) => setFilterDisease(e.target.value)}
                className="w-full h-9 px-3 rounded-lg border border-neutral-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
              >
                <option value="all">Tất cả nhóm bệnh</option>
                {uniqueDiseases.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {(filterMonth !== 'all' || filterDisease !== 'all') && (
            <button
              type="button"
              onClick={() => {
                setFilterMonth('all');
                setFilterDisease('all');
              }}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              Xóa bộ lọc
            </button>
          )}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-neutral-500 text-xs border-y border-neutral-100">
              <th className="text-left px-5 py-3 font-medium">
                Tháng / Nhóm bệnh / Tỉnh, thành phố
              </th>
              <th className="text-right px-5 py-3 font-medium whitespace-nowrap">Số ca dự báo</th>
              <th className="text-left px-5 py-3 font-medium whitespace-nowrap">Ghi nhận lúc</th>
              <th className="text-left px-5 py-3 font-medium whitespace-nowrap">Người ghi nhận</th>
              <th className="text-right px-5 py-3 font-medium w-20">Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="py-8">
                  <div className="flex items-center justify-center gap-2 text-neutral-500 text-sm">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Đang tải lịch sử...
                  </div>
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-10 text-center text-sm text-neutral-400">
                  Chưa có lịch sử dự báo
                </td>
              </tr>
            ) : cay.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-10 text-center text-sm text-neutral-400">
                  Không tìm thấy kết quả phù hợp với bộ lọc
                </td>
              </tr>
            ) : (
              cay.map((thangNode) => {
                const khoaThang = thangNode.thang;
                const mo = moThang(khoaThang);
                return (
                  <Fragment key={khoaThang}>
                    {/* CẤP 1 — tháng: số CHÍNH THỨC = tổng các bản Toàn quốc (nuôi
                        Tổng quan/Cảnh báo), không phải cộng các tỉnh. */}
                    <tr
                      onClick={() => bat(khoaThang)}
                      className="border-t border-neutral-100 bg-neutral-50/70 cursor-pointer hover:bg-neutral-100/70"
                    >
                      <td className="px-5 py-3 font-semibold text-neutral-900">
                        <span className="inline-flex items-center gap-1.5">
                          {mo ? (
                            <ChevronDown className="w-4 h-4 text-neutral-500" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-neutral-500" />
                          )}
                          Tháng {thangNode.thang}
                          {thangNode.soNhomThieuToanQuoc > 0 && (
                            <span
                              className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-50 text-amber-700"
                              title="Số nhóm bệnh chưa có bản Toàn quốc — thiếu trong tổng bên cạnh"
                            >
                              thiếu {thangNode.soNhomThieuToanQuoc} nhóm Toàn quốc
                            </span>
                          )}
                        </span>
                      </td>
                      <OTong tong={thangNode.tong} dam />
                      <td className="px-5 py-3 text-xs text-neutral-500 whitespace-nowrap">
                        {formatThoiGianMayChu(thangNode.tong.ghiNhanLuc)}
                      </td>
                      <td className="px-5 py-3 text-xs text-neutral-600 whitespace-nowrap">
                        {thangNode.tong.nguoiGhiNhan || '—'}
                      </td>
                      <td />
                    </tr>

                    {mo &&
                      thangNode.nhoms.map((nhomNode) => {
                        const khoaNhom = `${khoaThang}|${nhomNode.tenNhom}`;
                        const moN = moNhom(khoaNhom);
                        return (
                          <Fragment key={khoaNhom}>
                            {/* CẤP 2 — nhóm bệnh: hiện đúng bản Toàn quốc, không
                                cộng các tỉnh vào đây. */}
                            <tr
                              onClick={() => bat(khoaNhom)}
                              className="border-t border-neutral-100 cursor-pointer hover:bg-neutral-50"
                            >
                              <td className="px-5 py-2.5 pl-10 font-medium text-neutral-800">
                                <span className="inline-flex items-center gap-1.5">
                                  {moN ? (
                                    <ChevronDown className="w-3.5 h-3.5 text-neutral-400" />
                                  ) : (
                                    <ChevronRight className="w-3.5 h-3.5 text-neutral-400" />
                                  )}
                                  {nhomNode.tenNhom}
                                </span>
                              </td>
                              {nhomNode.chinhThuc ? (
                                <>
                                  <td className="px-5 py-2.5 text-right tabular-nums font-medium text-neutral-800">
                                    {nhomNode.chinhThuc.predicted_cases.toLocaleString('vi-VN')}
                                  </td>
                                  <td className="px-5 py-2.5 text-xs text-neutral-500 whitespace-nowrap">
                                    {formatThoiGianMayChu(nhomNode.chinhThuc.created_at)}
                                  </td>
                                  <td className="px-5 py-2.5 text-xs text-neutral-600 whitespace-nowrap">
                                    {nhomNode.chinhThuc.created_by || '—'}
                                  </td>
                                </>
                              ) : (
                                <>
                                  <td
                                    className="px-5 py-2.5 text-right text-xs font-medium text-amber-700"
                                    title="Chưa bấm Ghi nhận dự báo ở mục Toàn quốc cho nhóm bệnh này — số này KHÔNG có trong Tổng quan/Cảnh báo."
                                  >
                                    Chưa ghi nhận Toàn quốc
                                  </td>
                                  <td />
                                  <td />
                                </>
                              )}
                              <td />
                            </tr>

                            {/* Bản Toàn quốc cũ hơn (ghi nhận lại, chưa xoá bản trước) */}
                            {moN &&
                              nhomNode.toanQuocCu.map((r) => (
                                <DongChiTiet
                                  key={r.id}
                                  r={r}
                                  nhan="Toàn quốc (bản ghi trước)"
                                  duocXoa={duocXoa(r)}
                                  dangXoa={dangXoa}
                                  onXoa={() => {
                                    setLoiXoa(null);
                                    setXacNhanXoa({ kieu: 'mot', row: r });
                                  }}
                                />
                              ))}

                            {/* CẤP 3 — theo tỉnh: CHỈ tham khảo dịch tễ, không
                                cộng vào số chính thức ở trên. */}
                            {moN && nhomNode.tinh.length > 0 && (
                              <tr className="border-t border-neutral-100">
                                <td
                                  colSpan={5}
                                  className="px-5 py-1.5 pl-[4.5rem] text-[11px] text-neutral-400 italic"
                                >
                                  Theo tỉnh — tham khảo dịch tễ, không cộng vào Toàn quốc
                                  (tổng các tỉnh: {nhomNode.tongTinh.duBao.toLocaleString('vi-VN')})
                                </td>
                              </tr>
                            )}
                            {moN &&
                              nhomNode.tinh.map((r) => (
                                <DongChiTiet
                                  key={r.id}
                                  r={r}
                                  duocXoa={duocXoa(r)}
                                  dangXoa={dangXoa}
                                  onXoa={() => {
                                    setLoiXoa(null);
                                    setXacNhanXoa({ kieu: 'mot', row: r });
                                  }}
                                />
                              ))}
                          </Fragment>
                        );
                      })}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Xác nhận xoá */}
      {xacNhanXoa && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex items-start gap-3 px-5 py-4 border-b border-neutral-100">
              <div className="w-10 h-10 rounded-xl bg-red-50 text-red-600 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h3 className="text-base font-semibold text-neutral-900 mt-1.5">
                {xacNhanXoa.kieu === 'tatca'
                  ? 'Xoá toàn bộ lịch sử dự báo?'
                  : 'Xoá lần dự báo này?'}
              </h3>
            </div>

            <div className="px-5 py-4 space-y-2 text-sm text-neutral-700">
              {xacNhanXoa.kieu === 'tatca' ? (
                <>
                  <p>
                    Sẽ xoá toàn bộ dự báo đã ghi nhận của mọi nhóm bệnh, tỉnh/thành
                    và tháng.
                  </p>
                  <p className="text-neutral-500">
                    Tổng quan và Cảnh báo sẽ báo "chưa ghi nhận dự báo" cho tới khi
                    ghi nhận lại. Thao tác không hoàn tác được.
                  </p>
                </>
              ) : (
                <>
                  <p>
                    {xacNhanXoa.row.disease_label} · {xacNhanXoa.row.region} · tháng{' '}
                    {xacNhanXoa.row.month} —{' '}
                    <span className="font-semibold">
                      {xacNhanXoa.row.predicted_cases.toLocaleString('vi-VN')}
                    </span>{' '}
                    ca dự báo.
                  </p>
                  <p className="text-neutral-500">Thao tác không hoàn tác được.</p>
                </>
              )}

              {loiXoa && (
                <p className="text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  {loiXoa}
                </p>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-neutral-100">
              <button
                type="button"
                onClick={() => {
                  setXacNhanXoa(null);
                  setLoiXoa(null);
                }}
                disabled={dangXoa}
                className="px-4 py-2 text-sm font-medium text-neutral-700 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50 disabled:opacity-60"
              >
                Huỷ
              </button>
              <button
                type="button"
                disabled={dangXoa}
                onClick={() => {
                  setLoiXoa(null);
                  if (xacNhanXoa.kieu === 'tatca') xoaTatCa.mutate();
                  else xoaMot.mutate(xacNhanXoa.row.id);
                }}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-60"
              >
                {dangXoa ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                {xacNhanXoa.kieu === 'tatca' ? 'Xoá toàn bộ' : 'Xoá'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** Một dòng chi tiết có thể xoá — dùng cho cả "theo tỉnh" lẫn bản Toàn quốc cũ. */
function DongChiTiet({
  r,
  nhan,
  duocXoa,
  dangXoa,
  onXoa,
}: {
  r: ForecastHistoryItem;
  /** Nhãn thay cho r.region — dùng khi dòng này là bản Toàn quốc cũ. */
  nhan?: string;
  duocXoa: boolean;
  dangXoa: boolean;
  onXoa: () => void;
}) {
  return (
    <tr className="border-t border-neutral-100">
      <td className="px-5 py-2.5 pl-[4.5rem] text-neutral-600">
        {nhan ?? r.region}
      </td>
      <td className="px-5 py-2.5 text-right tabular-nums text-neutral-700">
        {r.predicted_cases.toLocaleString('vi-VN')}
      </td>
      <td className="px-5 py-2.5 text-xs text-neutral-500 whitespace-nowrap">
        {formatThoiGianMayChu(r.created_at)}
      </td>
      <td className="px-5 py-2.5 text-neutral-600 whitespace-nowrap">
        {r.created_by || '—'}
      </td>
      <td className="px-5 py-2.5 text-right">
        <button
          type="button"
          disabled={!duocXoa || dangXoa}
          onClick={onXoa}
          title={
            duocXoa
              ? 'Xoá lần dự báo này'
              : 'Chỉ người đã ghi nhận hoặc Quản trị viên mới xoá được'
          }
          className="inline-flex items-center justify-center w-8 h-8 rounded-lg text-red-600 hover:bg-red-50 disabled:text-neutral-300 disabled:hover:bg-transparent disabled:cursor-not-allowed"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </td>
    </tr>
  );
}

/** Ô số ca dự báo cộng dồn của một cấp gộp. */
function OTong({ tong, dam = false }: { tong: TongHop; dam?: boolean }) {
  const co = dam ? 'font-semibold text-neutral-900' : 'font-medium text-neutral-800';
  return (
    <td className={`px-5 py-3 text-right tabular-nums ${co}`}>
      {tong.duBao.toLocaleString('vi-VN')}
    </td>
  );
}
