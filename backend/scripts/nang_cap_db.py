"""NÂNG CẤP LƯỢC ĐỒ DB CHO MÁY ĐÃ CHẠY TRƯỚC ĐÓ (11/09/2026).

Vì sao cần file này: file DB (`data/medforecast.db`) KHÔNG nằm trong git, nên khi
mã nguồn đổi bảng thì mỗi máy phải tự nâng cấp DB của mình. Khi khởi động,
`main.py` gọi `Base.metadata.create_all` — lệnh đó TẠO BẢNG CÒN THIẾU nhưng
KHÔNG BAO GIỜ THÊM CỘT vào bảng đã tồn tại, và cũng không báo lỗi. Hậu quả là
backend chạy được nhưng truy vấn nào chạm cột mới sẽ chết với
"no such column: ..." — dự án đã dính đúng lỗi này một lần (xem ghi chú ở
`app/services/sync_service.py` quanh cột `disease_group`).

Script này so lược đồ khai báo trong code (`Base.metadata` + bảng mart/fact của
data_pipeline) với lược đồ thật trong file SQLite rồi:
  • tạo bảng còn thiếu,
  • sinh `ALTER TABLE ... ADD COLUMN` cho cột còn thiếu,
  • BÁO CÁO (không tự sửa) những khác biệt SQLite không làm an toàn được:
    xoá cột, đổi kiểu, đổi khoá — các việc đó phải chép bảng thủ công.

Mặc định chỉ IN RA KẾ HOẠCH (chạy khô). Thêm `--ap-dung` mới thực thi, và khi
thực thi script tự sao lưu file DB trước.

    cd backend
    python -m scripts.nang_cap_db              # xem sẽ đổi gì
    python -m scripts.nang_cap_db --ap-dung    # thực thi + sao lưu

Nếu máy có thể làm lại từ đầu thì dùng `scripts/khoi_tao_moi.py` đơn giản hơn:
xoá DB rồi dựng lại toàn bộ từ `dataset/v1`. Chỉ dùng script này khi DB đang
chứa dữ liệu đã đồng bộ từ HIS mà không muốn nạp lại.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

# cho phép chạy cả `python scripts/nang_cap_db.py` lẫn `python -m scripts.nang_cap_db`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv          # noqa: E402
load_dotenv()

from sqlalchemy import inspect, text    # noqa: E402

from app.database import Base, engine   # noqa: E402
import app.models                       # noqa: F401,E402  (đăng ký bảng nghiệp vụ)

# Tầng dữ liệu (mart_/dim_/stg_/fact_/sync_state) khai báo trên MỘT declarative_base
# KHÁC — `app.data_pipeline.db.Base`. Thiếu dòng này là bỏ sót 13 bảng: DB vẫn mở
# được, đăng nhập được, nhưng Dashboard dịch tễ và Phân tích & Dự báo trắng trơn.
try:
    from app.data_pipeline.db import Base as PipelineBase   # noqa: E402
    import app.data_pipeline.models                         # noqa: F401,E402
except Exception:                                           # noqa: BLE001
    PipelineBase = None


def _cac_bang() -> dict:
    """Toàn bộ bảng khai báo trong code: nghiệp vụ + tầng dữ liệu."""
    tables = dict(Base.metadata.tables)
    if PipelineBase is not None:
        tables.update(PipelineBase.metadata.tables)
    return tables


# ── Tiện ích ─────────────────────────────────────────────────────────────────

def _kieu_sql(col) -> str:
    """Chuỗi kiểu dữ liệu theo phương ngữ đang dùng (SQLite)."""
    try:
        return col.type.compile(dialect=engine.dialect)
    except Exception:                                   # noqa: BLE001
        return "TEXT"


def _mac_dinh(col) -> str | None:
    """Mệnh đề DEFAULT cho ALTER TABLE, nếu suy ra được từ khai báo."""
    if col.server_default is not None:
        arg = getattr(col.server_default, "arg", None)
        if arg is not None:
            return str(arg)
    d = col.default
    if d is not None and getattr(d, "is_scalar", False):
        v = d.arg
        if isinstance(v, bool):
            return "1" if v else "0"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str):
            return "'" + v.replace("'", "''") + "'"
    return None


def _duong_dan_db() -> Path | None:
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return None
    return Path(engine.url.database or "")


# ── So sánh ──────────────────────────────────────────────────────────────────

def _khao_sat():
    """Trả về (bảng_thiếu, cột_thiếu, canh_báo) — chưa đụng vào DB."""
    insp = inspect(engine)
    co_trong_db = set(insp.get_table_names())

    bang_thieu: list[str] = []
    cot_thieu: list[tuple[str, str, str]] = []      # (bảng, câu ALTER, mô tả)
    canh_bao: list[str] = []

    for ten, bang in _cac_bang().items():
        if ten not in co_trong_db:
            bang_thieu.append(ten)
            continue

        thuc_te = {c["name"]: c for c in insp.get_columns(ten)}
        for col in bang.columns:
            if col.name in thuc_te:
                continue
            kieu = _kieu_sql(col)
            mac_dinh = _mac_dinh(col)
            # SQLite từ chối ADD COLUMN NOT NULL mà không có DEFAULT.
            if not col.nullable and mac_dinh is None:
                canh_bao.append(
                    f"{ten}.{col.name}: khai báo NOT NULL nhưng không có giá trị mặc "
                    f"định — SQLite không thêm được. Hãy đặt default trong model, "
                    f"hoặc thêm cột cho phép NULL rồi cập nhật dữ liệu.")
                continue
            cau = f"ALTER TABLE {ten} ADD COLUMN {col.name} {kieu}"
            if mac_dinh is not None:
                cau += f" DEFAULT {mac_dinh}"
                if not col.nullable:
                    cau += " NOT NULL"
            cot_thieu.append((ten, cau, f"{ten}.{col.name} ({kieu})"))

        # Cột thừa / lệch kiểu: chỉ báo, KHÔNG tự xoá — dữ liệu là của bệnh viện.
        trong_model = {c.name for c in bang.columns}
        thua = sorted(set(thuc_te) - trong_model)
        if thua:
            canh_bao.append(
                f"{ten}: DB còn cột không có trong code: {', '.join(thua)} "
                f"(vô hại, để nguyên; muốn bỏ thì phải chép lại bảng).")

    return bang_thieu, cot_thieu, canh_bao


# ── Chạy ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Nâng cấp lược đồ DB cho máy đã chạy trước đó.")
    ap.add_argument("--ap-dung", action="store_true",
                    help="Thực thi thay đổi (mặc định chỉ in kế hoạch).")
    ap.add_argument("--khong-sao-luu", action="store_true",
                    help="Bỏ qua bước sao lưu file DB trước khi sửa.")
    args = ap.parse_args()

    db = _duong_dan_db()
    print(f"DB: {engine.url}")
    if db is not None and not db.exists():
        print(f"✗ Không thấy file {db}. Máy này chưa từng chạy — "
              f"hãy dùng: python scripts/khoi_tao_moi.py")
        return 1

    bang_thieu, cot_thieu, canh_bao = _khao_sat()

    # View của Tầng 2/Tầng 3 phải được kiểm ngay cả khi bảng đã đủ: chúng không
    # nằm trong Base.metadata nên _khao_sat() không thấy, mà thiếu chúng thì
    # Dashboard hiện "0 mã có mẫu số" mà không báo lỗi. Tạo view không đụng dữ
    # liệu nên làm luôn, không cần --ap-dung.
    try:
        from app.data_pipeline.views import tao_views
        kq_view = tao_views(engine)
    except Exception as exc:                                # noqa: BLE001
        kq_view = {"(bỏ qua)": str(exc)}
    for ten, tt in kq_view.items():
        print(("✓ " if tt == "đã tạo" else "! ") + f"view {ten}: {tt}")

    if not bang_thieu and not cot_thieu and not canh_bao:
        print("✓ Lược đồ DB đã khớp mã nguồn, không cần làm gì thêm.")
        return 0

    print()
    if bang_thieu:
        print(f"Bảng còn thiếu ({len(bang_thieu)}):")
        for t in sorted(bang_thieu):
            print(f"  + {t}")
    if cot_thieu:
        print(f"Cột còn thiếu ({len(cot_thieu)}):")
        for _, _, mo_ta in cot_thieu:
            print(f"  + {mo_ta}")
    if canh_bao:
        print("Cần xử lý tay:")
        for c in canh_bao:
            print(f"  ! {c}")

    if not args.ap_dung:
        print("\n→ Đây mới là kế hoạch. Chạy lại với --ap-dung để thực thi.")
        return 0

    if db is not None and not args.khong_sao_luu:
        luu = db.with_name(f"{db.stem}.saoluu_{datetime.now():%Y%m%d_%H%M%S}{db.suffix}")
        shutil.copy2(db, luu)
        print(f"\n✓ Đã sao lưu: {luu.name}")

    # 1) Bảng còn thiếu — create_all của cả hai metadata.
    if bang_thieu:
        Base.metadata.create_all(bind=engine)
        if PipelineBase is not None:
            PipelineBase.metadata.create_all(bind=engine)
        print(f"✓ Đã tạo {len(bang_thieu)} bảng.")

    # 2) Cột còn thiếu — ALTER TABLE từng cột một.
    ok = 0
    with engine.begin() as conn:
        for _, cau, mo_ta in cot_thieu:
            try:
                conn.execute(text(cau))
                print(f"✓ {mo_ta}")
                ok += 1
            except Exception as exc:                    # noqa: BLE001
                print(f"✗ {mo_ta}: {exc}")
    if cot_thieu:
        print(f"✓ Thêm {ok}/{len(cot_thieu)} cột.")

    print("\nXong. Khởi động lại backend rồi kiểm tra lại màn hình liên quan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
