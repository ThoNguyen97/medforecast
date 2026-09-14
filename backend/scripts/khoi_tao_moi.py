"""DỰNG HỆ THỐNG TỪ CLONE SẠCH — một lệnh, không cần DB của máy khác (11/09/2026).

    cd backend
    python scripts/khoi_tao_moi.py

Vì sao cần: `backend/.env` và `backend/data/*.db` nằm trong .gitignore (mật khẩu
HIS và dữ liệu bệnh viện KHÔNG được đưa lên git), nên `git clone` xong là thư mục
trống — backend tự tạo một DB rỗng, không có tài khoản nào, đăng nhập trả 401.
Script này lấp đúng khoảng trống đó:

  1. Tạo `.env` từ `.env.example` nếu chưa có, sinh SECRET_KEY ngẫu nhiên.
  2. Tạo toàn bộ bảng (nghiệp vụ + tầng dữ liệu mart/fact) trong CÙNG một file DB.
  3. Tạo tài khoản quản trị (mặc định admin / admin123 — ĐỔI ngay sau khi đăng nhập).
  4. Nạp bộ dữ liệu đóng gói `dataset/v1` (số ca theo tháng + thời tiết) vào các
     bảng mart/fact, để Tầng 1 (dự báo) chạy được ngay mà không cần kết nối HIS.

Sau khi chạy, máy mới có: đăng nhập, trang Dữ liệu bệnh, Phân tích & Dự báo,
và Dashboard phần dịch tễ (số ca, xu hướng, dự báo, chất lượng mô hình).
Phần vật tư — tồn kho, DOI, Cảnh báo thiếu hụt — cần dữ liệu kho của bệnh viện,
chỉ có được sau khi cấu hình kết nối HIS/STA rồi bấm Đồng bộ (bộ dữ liệu công bố
không chứa dữ liệu vật tư).

Tuỳ chọn:
    --data ../dataset/v1     thư mục bộ dữ liệu
    --no-data                chỉ tạo bảng + tài khoản, không nạp dữ liệu
    --username / --password  tài khoản quản trị khác mặc định
    --reset                  xoá dữ liệu dịch tễ cũ trước khi nạp (mặc định: có nạp là ghi đè)
"""
from __future__ import annotations

import argparse
import csv
import secrets
import sys
from datetime import date, datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

TOAN_QUOC = "TOAN_QUOC"
TINH_MAC_DINH = "TP. Hồ Chí Minh"   # tên CHUẨN, khớp dropdown/master + Open-Meteo


# ── 1. .env ──────────────────────────────────────────────────────────────────

def tao_env(backend: Path) -> str:
    env = backend / ".env"
    if env.exists():
        return f"đã có {env.name}, giữ nguyên"
    mau = backend / ".env.example"
    if not mau.exists():
        return f"CHƯA có {env.name} và không thấy .env.example — dùng cấu hình mặc định"
    noi_dung = mau.read_text(encoding="utf-8").replace(
        "SECRET_KEY=doi-khoa-nay-truoc-khi-trien-khai", f"SECRET_KEY={secrets.token_urlsafe(48)}")
    env.write_text(noi_dung, encoding="utf-8")
    return f"đã tạo {env.name} từ .env.example (SECRET_KEY sinh ngẫu nhiên)"


# ── 2. bảng ──────────────────────────────────────────────────────────────────

def tao_bang() -> str:
    from app.database import Base, engine
    import app.models  # noqa: F401 — đăng ký model vào metadata
    Base.metadata.create_all(bind=engine)
    n_app = len(Base.metadata.tables)
    from app.data_pipeline.db import init_db as pipeline_init_db, get_db_url
    pipeline_init_db()
    from app.data_pipeline.db import Base as PBase
    # Sáu bảng tự quản + bốn view: create_all không biết tới chúng. Không dựng
    # ở đây thì DB mới chỉ có 29/35 bảng và 0 view — Dashboard sẽ hiện
    # "0 mã có mẫu số" mà không báo lỗi gì.
    from app.data_pipeline.views import dam_bao_luoc_do, VIEWS
    kq = dam_bao_luoc_do(engine)
    n_view = sum(1 for k, v in kq.items() if k in VIEWS and v == "đã tạo")
    from sqlalchemy import text as _text
    with engine.connect() as _c:
        n_bang = _c.execute(_text(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'")).scalar() or 0
    ghi_chu = ""
    if n_view < len(VIEWS):
        ghi_chu = (" — %d view chờ dữ liệu vật tư, tự tạo sau lần đồng bộ HIS đầu tiên"
                   % (len(VIEWS) - n_view))
    return (f"{n_bang} bảng ({n_app} nghiệp vụ + {len(PBase.metadata.tables)} tầng dữ "
            f"liệu + 6 tự quản) + {n_view}/{len(VIEWS)} view{ghi_chu} "
            f"trong {get_db_url()}")


# ── 3. tài khoản ─────────────────────────────────────────────────────────────

def tao_admin(username: str, password: str, email: str) -> str:
    from app.database import SessionLocal
    from app.models.user import User
    from app.core.security import get_password_hash
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            return f"tài khoản '{username}' đã có, không tạo lại"
        db.add(User(username=username, email=email,
                    password_hash=get_password_hash(password),
                    full_name="System Administrator", role="Administrator",
                    is_active=True))
        db.commit()
        return f"đã tạo '{username}' / '{password}' — ĐỔI MẬT KHẨU sau khi đăng nhập"
    finally:
        db.close()


# ── 4. dữ liệu ───────────────────────────────────────────────────────────────

def _doc_csv(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _so(v, mac_dinh=None):
    if v is None or str(v).strip() == "":
        return mac_dinh
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except ValueError:
        return mac_dinh


def _bool(v) -> int:
    return 1 if str(v).strip().lower() in ("1", "true", "yes") else 0


def nap_du_lieu(data_dir: Path) -> list[str]:
    """Nạp dataset/v1 vào mart/fact + bảng nghiệp vụ disease_cases.

    Ghi đè: xoá sạch các bảng này rồi nạp lại, vì đây là thao tác KHỞI TẠO —
    trộn nửa cũ nửa mới sẽ cho ra chuỗi thời gian sai mà không ai thấy.
    """
    from sqlalchemy import text
    from app.database import SessionLocal

    nhom = _doc_csv(data_dir / "nhom_thang.csv")
    ma = _doc_csv(data_dir / "ma_thang.csv")
    ty_trong = _doc_csv(data_dir / "ty_trong_co_dinh.csv")
    p_dim = data_dir / "dim_icd.csv"
    dim = _doc_csv(p_dim) if p_dim.exists() else []
    ten_khoi = {r["block_code"]: r.get("block_name") or r["block_code"] for r in dim}
    ten_ma = {r["icd_code"]: (r.get("icd_name") or r["icd_code"]) for r in dim}

    ghi = []
    db = SessionLocal()
    try:
        for t in ("mart_monthly_cases_by_block", "mart_monthly_weather",
                  "mart_icd_share_in_block", "fact_disease_case", "dim_icd",
                  "dim_region", "disease_cases", "environmental_data"):
            db.execute(text(f"DELETE FROM {t}"))

        db.execute(text("INSERT INTO dim_region (region) VALUES (:r)"), {"r": TOAN_QUOC})

        for r in dim:
            db.execute(text(
                "INSERT INTO dim_icd (icd_code, icd_name, block_code, block_name, is_target) "
                "VALUES (:c, :n, :b, :bn, :t)"),
                {"c": r["icd_code"], "n": r.get("icd_name") or "", "b": r["block_code"],
                 "bn": r.get("block_name") or "", "t": _bool(r.get("is_target", 1))})
        ghi.append(f"dim_icd {len(dim)} mã")

        for r in nhom:
            db.execute(text(
                "INSERT INTO mart_monthly_cases_by_block "
                "(period, year, month, block_code, block_name, region, cases, is_covid, is_complete) "
                "VALUES (:p, :y, :m, :b, :bn, :r, :c, :cv, :ic)"),
                {"p": r["period"], "y": _so(r["year"]), "m": _so(r["month"]),
                 "b": r["block_code"], "bn": ten_khoi.get(r["block_code"], r["block_code"]),
                 "r": TOAN_QUOC, "c": _so(r["cases"], 0),
                 "cv": _bool(r.get("is_covid")), "ic": _bool(r.get("is_complete"))})
        ghi.append(f"mart_monthly_cases_by_block {len(nhom)} dòng")

        thoi_tiet = {}
        for r in nhom:
            if r["period"] not in thoi_tiet and _so(r.get("temp")) is not None:
                thoi_tiet[r["period"]] = r
        for p, r in sorted(thoi_tiet.items()):
            db.execute(text(
                "INSERT INTO mart_monthly_weather (period, year, month, region, temp, humidity, rainfall) "
                "VALUES (:p, :y, :m, :r, :t, :h, :rain)"),
                {"p": p, "y": _so(r["year"]), "m": _so(r["month"]), "r": TOAN_QUOC,
                 "t": _so(r.get("temp")), "h": _so(r.get("humidity")), "rain": _so(r.get("rainfall"))})
            db.execute(text(
                "INSERT INTO environmental_data (recorded_at, location, temperature, humidity, "
                "rainfall, data_source) VALUES (:d, :loc, :t, :h, :rain, 'dataset/v1')"),
                {"d": f"{p}-01 00:00:00", "loc": TINH_MAC_DINH,
                 "t": _so(r.get("temp")), "h": _so(r.get("humidity")), "rain": _so(r.get("rainfall"))})
        ghi.append(f"mart_monthly_weather + environmental_data {len(thoi_tiet)} tháng")

        for r in ty_trong:
            db.execute(text(
                "INSERT INTO mart_icd_share_in_block (block_code, icd_code, region, share) "
                "VALUES (:b, :c, :r, :s)"),
                {"b": r["block_code"], "c": r["icd_code"], "r": TOAN_QUOC, "s": _so(r["share"], 0)})
        ghi.append(f"mart_icd_share_in_block {len(ty_trong)} dòng")

        for r in ma:
            ngay = f"{r['period']}-01"
            db.execute(text(
                "INSERT INTO fact_disease_case "
                "(period, year, month, recorded_date, icd_code, block_code, region, cases, is_covid, is_complete) "
                "VALUES (:p, :y, :m, :d, :c, :b, :r, :n, :cv, :ic)"),
                {"p": r["period"], "y": _so(r["year"]), "m": _so(r["month"]), "d": ngay,
                 "c": r["icd_code"], "b": r["block_code"], "r": TOAN_QUOC,
                 "n": _so(r["cases"], 0), "cv": _bool(r.get("is_covid")),
                 "ic": _bool(r.get("is_complete"))})
            db.execute(text(
                "INSERT INTO disease_cases (recorded_at, recorded_date, icd_code, disease_name, "
                "disease_group, disease_type, case_count, location, data_source) "
                "VALUES (:dt, :d, :c, :dn, :g, 'respiratory', :n, :loc, 'dataset/v1')"),
                {"dt": f"{ngay} 00:00:00", "d": ngay, "c": r["icd_code"],
                 "dn": ten_ma.get(r["icd_code"], r["icd_code"]), "g": r["block_code"],
                 "n": _so(r["cases"], 0), "loc": TINH_MAC_DINH})
        ghi.append(f"fact_disease_case + disease_cases {len(ma)} dòng")

        db.commit()
        return ghi
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── chạy ─────────────────────────────────────────────────────────────────────

def _dem_du_lieu_cu() -> str:
    """Mô tả ngắn dữ liệu đang có trong DB, "" nếu DB còn trống."""
    from sqlalchemy import text
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        phan = []
        for bang, nhan in (("disease_cases", "số ca"), ("fact_usage_total", "tiêu hao"),
                           ("fact_inventory_snapshot", "tồn kho")):
            try:
                n = db.execute(text(f"SELECT COUNT(*) FROM {bang}")).scalar() or 0
            except Exception:                               # noqa: BLE001
                n = 0
            if n:
                phan.append(f"{nhan} {n} dòng")
        return "; ".join(phan)
    finally:
        db.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(BACKEND_DIR.parent / "dataset" / "v1"))
    ap.add_argument("--no-data", action="store_true", help="chỉ tạo bảng + tài khoản")
    ap.add_argument("--ghi-de-du-lieu", action="store_true",
                    help="nạp dataset dù DB đã có dữ liệu (XOÁ disease_cases, "
                         "environmental_data và mart/fact hiện có)")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default="admin123")
    ap.add_argument("--email", default="admin@example.com")
    args = ap.parse_args(argv)

    print("MedForecast — khởi tạo hệ thống trên máy mới\n" + "─" * 60)
    print("1) Cấu hình   :", tao_env(BACKEND_DIR))

    # .env vừa tạo phải được nạp TRƯỚC khi import app.config (settings đọc một lần)
    try:
        from dotenv import load_dotenv
        load_dotenv(BACKEND_DIR / ".env")
    except ImportError:
        pass

    print("2) Bảng dữ liệu:", tao_bang())
    print("3) Tài khoản  :", tao_admin(args.username, args.password, args.email))

    if args.no_data:
        print("4) Dữ liệu    : bỏ qua (--no-data)")
    else:
        d = Path(args.data)
        # Máy đã chạy và đã đồng bộ HIS: nạp dataset sẽ XOÁ số ca thật rồi thay
        # bằng 938 dòng của bản công bố — mất dữ liệu mà không ai thấy. Chặn lại.
        dang_co = _dem_du_lieu_cu()
        if dang_co and not args.ghi_de_du_lieu:
            print(f"4) Dữ liệu    : DB đã có dữ liệu ({dang_co}) — KHÔNG nạp dataset "
                  f"để tránh xoá số liệu thật.")
            print("                Máy đã chạy trước đó mà thiếu bảng: "
                  "python -m scripts.nang_cap_db --ap-dung rồi đồng bộ lại từ HIS.")
            print("                Thật sự muốn thay bằng bản công bố: thêm --ghi-de-du-lieu.")
        elif not (d / "nhom_thang.csv").exists():
            print(f"4) Dữ liệu    : KHÔNG thấy {d}/nhom_thang.csv — bỏ qua. "
                  f"Dùng --data để chỉ đúng thư mục dataset.")
        else:
            for dong in nap_du_lieu(d):
                print("4) Dữ liệu    :", dong)

    print("─" * 60)
    print("Xong. Khởi động:  uvicorn app.main:app --reload")
    print("Đăng nhập:", args.username, "/", args.password, "— đổi mật khẩu ngay.")
    print()
    print("CHẠY ĐƯỢC NGAY : Dữ liệu bệnh · Phân tích & Dự báo · Dashboard (số ca,")
    print("                 xu hướng, dự báo kỳ tới, chất lượng mô hình).")
    print("CẦN HIS        : Tồn kho, DOI, Cảnh báo thiếu hụt — vào Quản trị →")
    print("                 Kết nối HIS, nhập thông tin STA rồi bấm Đồng bộ.")
    print("                 Bộ dữ liệu công bố không chứa dữ liệu vật tư.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
