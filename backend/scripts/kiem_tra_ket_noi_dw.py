#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm tra kết nối tới CSDL nghiên cứu MEDFORECAST_DW (SQL Server cục bộ)
TRƯỚC khi bấm "Nạp dữ liệu DW".

    cd backend
    python scripts/kiem_tra_ket_noi_dw.py            # theo cấu hình đã lưu trong app
    python scripts/kiem_tra_ket_noi_dw.py --env      # theo PIPELINE_SQLSERVER_CONN trong .env

Nguồn dữ liệu (từ 23/09/2026): bệnh viện chạy thủ tục nội bộ khử định danh rồi
bàn giao SNAPSHOT database MEDFORECAST_DW (12 bảng dbo.MF_*). Snapshot được
khôi phục trên SQL Server cục bộ của máy trạm nghiên cứu. Ứng dụng KHÔNG nối
tới HIS hay máy chủ trung gian nào — chỉ đọc 7 view vw_MedForecast_* tại đây.

Sáu phép thử, mỗi phép in rõ hỏng ở đâu và sửa thế nào:
    1. Cấu hình kết nối (DB app → .env)       4. 12 bảng dbo.MF_* của snapshot
    2. Driver ODBC trên máy                    5. 7 view ứng dụng đọc (có dòng)
    3. Đăng nhập SQL Server cục bộ             6. Mốc dữ liệu bệnh viện chốt (MF_Watermark)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OK, LOI = "  [OK]  ", "  [LỖI] "
loi = 0

BANG_SNAPSHOT = [
    "MF_CaBenh_Nhom", "MF_CaBenh_PhanCap", "MF_CaBenh_VatTu", "MF_TieuHao_PhanCap",
    "MF_TieuHao_Tong", "MF_TonKho", "MF_TonKho_Lo", "MF_MapVatTu",
    "MF_Watermark", "MF_SyncLog",
]
BANG_KHONG_DUNG = ["MF_LichSuNhap", "MF_VatTu_ThuocTinh"]   # mua sắm — app không đọc


def bao_loi(msg: str, cach_sua: str = "") -> None:
    global loi
    loi += 1
    print(LOI + msg)
    for dong in cach_sua.strip().splitlines():
        print("         " + dong.strip())


def _che_mat_khau(chuoi: str) -> str:
    ra = re.sub(r"(?i)(PWD|PASSWORD)=([^;]*)", r"\1=***", chuoi)
    ra = re.sub(r"(?i)(odbc_connect=)(.*)", r"\1<đã che>", ra)
    if "://" in ra and "@" in ra:
        dau, cuoi = ra.split("://", 1)
        if ":" in cuoi.split("@")[0]:
            ra = f"{dau}://{cuoi.split(':', 1)[0]}:***@" + cuoi.split("@", 1)[1]
    return ra


def _url_tu_env() -> str:
    conn = os.environ.get("PIPELINE_SQLSERVER_CONN", "").strip()
    if not conn:
        return ""
    if "://" not in conn:
        from urllib.parse import quote_plus
        conn = "mssql+pyodbc:///?odbc_connect=" + quote_plus(conn)
    return conn


def _url_tu_app() -> tuple[str, dict]:
    """Chuỗi kết nối đúng như nút 'Nạp dữ liệu DW' sẽ dùng (cấu hình trong DB app)."""
    from app.database import SessionLocal
    from app.services import sync_config_service as scs
    db = SessionLocal()
    try:
        cfg = scs._doc_tho(db)                        # noqa: SLF001 — script chẩn đoán
        if not cfg:
            return "", {}
        cfg = {**scs.MAC_DINH, **cfg}
        return scs._chuoi_ket_noi(cfg), cfg           # noqa: SLF001
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", action="store_true",
                    help="dùng PIPELINE_SQLSERVER_CONN trong .env thay vì cấu hình trong app")
    a = ap.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        print("  (không có python-dotenv — đọc thẳng biến môi trường)")

    # ── 1. Cấu hình ──────────────────────────────────────────────────────
    print("\n=== 1. Cấu hình kết nối ===")
    url, cfg = "", {}
    if not a.env:
        try:
            url, cfg = _url_tu_app()
        except Exception as e:  # noqa: BLE001
            bao_loi(f"Không đọc được cấu hình trong DB app: {e}")
        if url:
            server = cfg["host"] + (f"\\{cfg['instance']}" if cfg.get("instance") else f",{cfg.get('port', 1433)}")
            from app.services.sync_config_service import dung_windows_auth
            cach = "Windows Authentication" if dung_windows_auth(cfg) else f"SQL auth ({cfg.get('username')})"
            print(OK + f"cấu hình trong app: SERVER={server} · DATABASE={cfg['database']} · {cach} · driver='{cfg['driver']}'")
            if cfg["host"] not in ("localhost", "127.0.0.1", ".", "(local)") and not cfg["host"].lower().startswith(os.environ.get("COMPUTERNAME", "\0").lower()):
                print(f"         chú ý: host '{cfg['host']}' không phải máy cục bộ — snapshot MEDFORECAST_DW phải nằm trên SQL Server của máy này.")
        else:
            print("         (app chưa lưu cấu hình — thử .env)")
    if not url:
        url = _url_tu_env()
        if url:
            print(OK + f".env: {_che_mat_khau(os.environ.get('PIPELINE_SQLSERVER_CONN', ''))}")
        else:
            bao_loi("Không có cấu hình nào.",
                    """Cách 1: Quản trị → Nguồn dữ liệu (CSDL DW) → nhập localhost (hoặc localhost\\SQLEXPRESS),
                       chọn Windows Authentication → Kiểm tra kết nối → Lưu.
                       Cách 2: đặt PIPELINE_SQLSERVER_CONN trong backend/.env, ví dụ
                       DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=MEDFORECAST_DW;Trusted_Connection=yes;TrustServerCertificate=yes""")
            return ket_luan()

    # ── 2. Driver ODBC ───────────────────────────────────────────────────
    print("\n=== 2. Driver ODBC ===")
    try:
        import pyodbc
        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        if drivers:
            print(OK + f"driver có sẵn: {', '.join(drivers)}")
            if cfg and cfg.get("driver") not in drivers:
                from app.services.sync_config_service import driver_kha_dung
                dung, _ = driver_kha_dung(cfg["driver"])
                print(f"         cấu hình ghi '{cfg['driver']}' — máy không có, app sẽ tự dùng '{dung}'.")
        else:
            bao_loi("Máy chưa có ODBC Driver for SQL Server.",
                    "Cài 'ODBC Driver 18 for SQL Server' (Microsoft) rồi chạy lại.")
    except ImportError:
        bao_loi("Thiếu gói pyodbc.", "pip install pyodbc")

    # ── 3–6. Kết nối và đọc snapshot ─────────────────────────────────────
    print("\n=== 3. Đăng nhập SQL Server cục bộ ===")
    try:
        from sqlalchemy import create_engine, text
        eng = create_engine(url, pool_pre_ping=True, connect_args={"timeout": 10})
        with eng.connect() as c:
            ten_db = c.execute(text("SELECT DB_NAME()")).scalar()
            may = c.execute(text("SELECT @@SERVERNAME")).scalar()
            print(OK + f"đăng nhập được: server={may} · database={ten_db}")
            if ten_db != "MEDFORECAST_DW":
                bao_loi(f"Đang ở database '{ten_db}', không phải MEDFORECAST_DW.",
                        "Khôi phục snapshot với đúng tên MEDFORECAST_DW, hoặc sửa DATABASE trong cấu hình.")

            print("\n=== 4. 12 bảng dbo.MF_* của snapshot ===")
            co = {r[0] for r in c.execute(text(
                "SELECT name FROM sys.tables WHERE name LIKE 'MF[_]%'")).fetchall()}
            thieu = [b for b in BANG_SNAPSHOT if b not in co]
            if thieu:
                bao_loi(f"Thiếu bảng: {', '.join(thieu)}",
                        "Snapshot bàn giao không đầy đủ — kiểm tra lại bản .bak/.bacpac đã khôi phục.")
            else:
                print(OK + f"đủ {len(BANG_SNAPSHOT)} bảng nghiệp vụ + vận hành")
            for b in BANG_SNAPSHOT + [x for x in BANG_KHONG_DUNG if x in co]:
                if b in co:
                    n = c.execute(text(f"SELECT COUNT(*) FROM dbo.[{b}]")).scalar()
                    ghi = "  (không dùng — phân hệ mua sắm cũ)" if b in BANG_KHONG_DUNG else ""
                    print(f"         {b:<22} {n:>10,} dòng{ghi}")

            print("\n=== 5. 7 view ứng dụng đọc ===")
            from app.services.sync_config_service import VIEW_UNG_DUNG
            for view, nhan in VIEW_UNG_DUNG:
                try:
                    n = c.execute(text(f"SELECT COUNT(*) FROM dbo.{view}")).scalar()
                    if n:
                        print(OK + f"{view}: {n:,} dòng ({nhan})")
                    else:
                        bao_loi(f"{view} RỖNG ({nhan}).",
                                "Bảng nguồn tương ứng trong snapshot không có dữ liệu — hỏi lại bên bàn giao.")
                except Exception as e:  # noqa: BLE001
                    bao_loi(f"Không đọc được {view}: {str(e)[:150]}",
                            "Chạy lại sql_his/khoi_phuc_snapshot/*.sql để tạo view (CREATE OR ALTER, chạy lại vô hại).")

            print("\n=== 6. Mốc dữ liệu bệnh viện chốt ===")
            try:
                rows = c.execute(text(
                    "SELECT TenLuong, CONVERT(varchar(10), MocDaDay, 120) AS Moc, "
                    "       CONVERT(varchar(19), LanChayCuoi, 120) AS Lan "
                    "FROM dbo.MF_Watermark ORDER BY TenLuong")).fetchall()
                if rows and any(r.Moc for r in rows):
                    for r in rows:
                        print(OK + f"{r.TenLuong:<16} snapshot chốt tới kỳ {(r.Moc or '—')[:7]} · thủ tục chạy lần cuối {r.Lan or '—'}")
                else:
                    bao_loi("MF_Watermark chưa có mốc nào.",
                            "Không chặn việc nạp, nhưng Tổng quan sẽ không hiện 'Mốc dữ liệu bệnh viện chốt'.")
            except Exception as e:  # noqa: BLE001
                bao_loi(f"Không đọc được MF_Watermark: {str(e)[:150]}")
        eng.dispose()
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        goi_y = ""
        if "IM002" in msg or "driver" in msg.lower():
            goi_y = "Cài ODBC Driver 18 for SQL Server; tên driver trong cấu hình phải khớp mục 2."
        elif "Login failed" in msg:
            goi_y = ("SQL Server cục bộ thường chỉ bật Windows Authentication → chọn auth = windows.\n"
                     "Nếu muốn SQL auth: bật Mixed Mode và tạo login medforecast_app.")
        elif "timeout" in msg.lower() or "TCP" in msg or "08001" in msg:
            goi_y = ("Dịch vụ SQL Server đã chạy? Instance có tên (localhost\\SQLEXPRESS)?\n"
                     "TCP/IP đã bật trong SQL Server Configuration Manager?")
        bao_loi(f"Không kết nối được: {msg[:300]}", goi_y)

    return ket_luan()


def ket_luan() -> int:
    print()
    if loi == 0:
        print("=== TẤT CẢ ĐỀU ĐẠT — nạp dữ liệu được rồi ===")
        print("    Giao diện: Tổng quan → Nạp dữ liệu DW    (hoặc)")
        print("    python scripts/run_dss_load.py --full")
        return 0
    print(f"=== CÒN {loi} VẤN ĐỀ — sửa xong hãy nạp dữ liệu ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())
