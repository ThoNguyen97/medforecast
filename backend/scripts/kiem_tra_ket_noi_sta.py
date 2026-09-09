#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm tra kết nối tới DB trung chuyển STA TRƯỚC khi chạy đồng bộ thật.

    cd backend
    python scripts/kiem_tra_ket_noi_sta.py

Chạy 7 phép thử, mỗi phép in rõ hỏng ở đâu và sửa thế nào. Đồng bộ thật mất vài
phút và ghi vào DB; chạy cái này trước để hỏng thì hỏng trong 5 giây.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OK, LOI = "  [OK]  ", "  [LỖI] "
loi = 0


def bao_loi(msg: str, cach_sua: str = "") -> None:
    global loi
    loi += 1
    print(LOI + msg)
    if cach_sua:
        for dong in cach_sua.strip().splitlines():
            print("         " + dong.strip())


DRIVER_MAC_DINH = "ODBC Driver 17 for SQL Server"


def _che_mat_khau(chuoi: str) -> str:
    """Che mật khẩu ở CẢ HAI định dạng.

    Bản trước chỉ che dạng URL `scheme://user:pass@host` — nên với chuỗi ODBC
    (`...;PWD=...;`) nó IN THẲNG mật khẩu ra terminal. Terminal thì được chụp
    ảnh, dán vào chat, đưa vào báo cáo.
    """
    import re as _re
    ra = _re.sub(r"(?i)(PWD|PASSWORD)=([^;]*)", r"\1=***", chuoi)
    ra = _re.sub(r"(?i)(odbc_connect=)(.*)", r"\1<đã che>", ra)
    if "://" in ra and "@" in ra:
        dau, cuoi = ra.split("://", 1)
        if ":" in cuoi.split("@")[0]:
            u = cuoi.split(":", 1)[0]
            ra = f"{dau}://{u}:***@" + cuoi.split("@", 1)[1]
    return ra


def _chuan_hoa_url(chuoi: str):
    """Nhận chuỗi ODBC hoặc URL SQLAlchemy, trả về URL SQLAlchemy dùng được.

    -------------------------------------------------------------------------
    VÌ SAO CẦN HÀM NÀY

    `.env` thường ghi chuỗi theo định dạng ODBC:

        SERVER=172.16.1.48;DATABASE=MEDFORECAST_DW;UID=...;PWD=...;

    Đưa thẳng vào `create_engine()` sẽ ra "Could not parse SQLAlchemy URL" —
    một lỗi TRÔNG NHƯ lỗi mạng hoặc lỗi quyền, nhưng thực ra chỉ là sai định
    dạng chuỗi. Chính `sync_config_service._chuoi_ket_noi()` đã bọc đúng cách
    (`mssql+pyodbc:///?odbc_connect=` + quote_plus); hàm này làm điều tương tự
    cho biến môi trường, để script kiểm và ứng dụng không lệch nhau.

    Cũng chèn `DRIVER=` nếu chuỗi thiếu — pyodbc bắt buộc phải có, và chuỗi
    trong `.env` rất hay thiếu vì SSMS không cần nó.
    """
    from urllib.parse import quote_plus
    ghi_chu = []
    chuoi = (chuoi or "").strip()
    if not chuoi:
        return chuoi, ghi_chu

    if "://" in chuoi:                       # đã là URL SQLAlchemy
        return chuoi, ghi_chu

    if "=" not in chuoi or ";" not in chuoi:
        ghi_chu.append("Chuỗi không giống định dạng ODBC lẫn URL SQLAlchemy — "
                       "để nguyên và thử kết nối.")
        return chuoi, ghi_chu

    odbc = chuoi if chuoi.endswith(";") else chuoi + ";"
    if "driver=" not in odbc.lower():
        odbc = f"DRIVER={{{DRIVER_MAC_DINH}}};" + odbc
        ghi_chu.append(f"Chuỗi thiếu DRIVER= — đã chèn '{DRIVER_MAC_DINH}'. "
                       "Nên ghi rõ trong .env để không phụ thuộc máy.")
    ghi_chu.append("Định dạng ODBC — đã bọc qua odbc_connect (giống "
                   "sync_config_service._chuoi_ket_noi).")
    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc), ghi_chu


def _kiem_nguon_cau_hinh_ung_dung() -> None:
    """Kiểm CHÍNH nguồn cấu hình mà run_dss_load.py dùng.

    -------------------------------------------------------------------------
    HAI NGUỒN CẤU HÌNH, ĐỪNG LẪN

        biến môi trường .env   →  DataPipeline (nút "Đồng bộ HIS")
        system_config          →  run_dss_load.py, qua build_connector()
                                  ('his_sync.connection', mật khẩu đã mã hoá)

    Phần 1 của script này chỉ kiểm nguồn thứ nhất. Nhưng bốn luồng DSS đọc
    nguồn THỨ HAI. Hai nguồn có thể trỏ về hai máy chủ khác nhau — và khi đó
    script báo xanh trong khi ETL vẫn hỏng, hoặc ngược lại.
    """
    print("\n=== 5. Nguồn cấu hình mà run_dss_load.py dùng ===")
    try:
        from app.database import SessionLocal
        from app.services import sync_config_service as scs
    except Exception as exc:                                # noqa: BLE001
        bao_loi(f"Không nạp được app.services.sync_config_service: {exc}")
        return

    db = SessionLocal()
    try:
        try:
            cfg = scs.get_config(db)
        except Exception as exc:                            # noqa: BLE001
            bao_loi(f"Không đọc được system_config['his_sync.connection']: {exc}",
                    "Mở Quản trị → Kết nối HIS trên giao diện và lưu lại một lần.")
            return
        if not cfg:
            bao_loi("system_config['his_sync.connection'] chưa có.",
                    "run_dss_load.py sẽ không dựng được kết nối.")
            return
        print(OK + f"nguồn = {cfg.get('source')} · "
                   f"{cfg.get('host')}:{cfg.get('port')} · "
                   f"db {cfg.get('database')} · driver {cfg.get('driver')}")
        if cfg.get("source") != "sqlserver":
            bao_loi(f"source = '{cfg.get('source')}' — bốn luồng DSS chỉ đọc "
                    "được từ STA (SQL Server).")

        env_host = ""
        import re as _re
        m = _re.search(r"(?i)SERVER=([^;,\\]+)",
                       os.environ.get("PIPELINE_SQLSERVER_CONN", ""))
        if m:
            env_host = m.group(1).strip()
        if env_host and cfg.get("host") and env_host != str(cfg["host"]):
            bao_loi(f"HAI NGUỒN TRỎ HAI MÁY KHÁC NHAU: .env → {env_host}, "
                    f"system_config → {cfg['host']}",
                    "Nút 'Đồng bộ HIS' và run_dss_load.py sẽ đọc hai nơi khác nhau.")
        elif env_host:
            print(OK + f"hai nguồn cùng trỏ về {env_host}")

        try:
            c = scs.build_connector(db)
            print(OK + f"build_connector() dựng được, name = {c.name}")
        except Exception as exc:                            # noqa: BLE001
            bao_loi(f"build_connector() lỗi: {str(exc)[:160]}",
                    "Đây chính là lỗi run_dss_load.py sẽ gặp. Sửa ở Quản trị → "
                    "Kết nối HIS, hoặc kiểm mật khẩu đã mã hoá.")
    finally:
        db.close()


def main() -> int:
    # Nạp backend/.env giống hệt cách app nạp
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        print("  (không có python-dotenv — đọc thẳng biến môi trường)")

    print("\n=== 1. Biến môi trường ===")
    nguon = os.environ.get("PIPELINE_SOURCE", "file")
    if nguon != "sqlserver":
        bao_loi(f"PIPELINE_SOURCE = '{nguon}', app vẫn đang đọc file CSV.",
                "Đặt PIPELINE_SOURCE=sqlserver trong backend/.env")
    else:
        print(OK + "PIPELINE_SOURCE = sqlserver")

    conn = os.environ.get("PIPELINE_SQLSERVER_CONN", "")
    if not conn:
        bao_loi("Thiếu PIPELINE_SQLSERVER_CONN.",
                "Xem backend/.env.STA.mau")
        return ket_luan()
    conn, ghi_chu_chuan_hoa = _chuan_hoa_url(conn)
    print(OK + f"chuỗi kết nối = {_che_mat_khau(conn)}")
    for g in ghi_chu_chuan_hoa:
        print("        " + g)

    for bien, ten_file in [("PIPELINE_CASE_SQL_FILE", "case_sta.sql"),
                           ("PIPELINE_INVENTORY_SQL_FILE", "inventory_sta.sql")]:
        gt = os.environ.get(bien, "")
        if gt != ten_file:
            bao_loi(f"{bien} = '{gt}' (nên là '{ten_file}')")
        else:
            print(OK + f"{bien} = {gt}")

    nhom_sql = os.environ.get("PIPELINE_CASE_GROUP_SQL_FILE", "")
    if nhom_sql != "case_group_sta.sql":
        bao_loi(f"PIPELINE_CASE_GROUP_SQL_FILE = '{nhom_sql}' — THIẾU.",
                """Không có dòng này thì số ca mức NHÓM bị cộng dồn từ các mã con.
                   Một lượt khám mang J01 (chính) + J06 (phụ) — cả hai cùng nhóm
                   J00-J06 — sẽ bị đếm hai lần. Đo thật: lệch 181 ca.
                   Thêm vào .env:  PIPELINE_CASE_GROUP_SQL_FILE=case_group_sta.sql""")
    else:
        print(OK + "PIPELINE_CASE_GROUP_SQL_FILE = case_group_sta.sql")

    print("\n=== 2. Driver ODBC ===")
    try:
        import pyodbc
    except ImportError:
        bao_loi("Chưa cài pyodbc.", "pip install pyodbc")
        return ket_luan()
    ds = pyodbc.drivers()
    sql_drivers = [d for d in ds if "SQL Server" in d]
    if not sql_drivers:
        bao_loi("Máy chưa cài driver ODBC cho SQL Server.",
                """Tải 'Microsoft ODBC Driver 18 for SQL Server' từ trang Microsoft.
                   Gói unixodbc/pyodbc KHÔNG bao gồm driver thật.""")
    else:
        print(OK + f"driver có sẵn: {', '.join(sql_drivers)}")
        import re
        m = re.search(r"driver=([^&]+)", conn, re.I)
        if m:
            yc = m.group(1).replace("+", " ")
            if yc not in ds:
                bao_loi(f"Chuỗi kết nối yêu cầu '{yc}' nhưng máy không có.",
                        f"Sửa driver= trong .env thành một trong: {', '.join(sql_drivers)}")
            else:
                print(OK + f"driver yêu cầu '{yc}' khớp với máy")

    print("\n=== 3. Kết nối và đọc dữ liệu ===")
    from sqlalchemy import create_engine, text
    try:
        eng = create_engine(conn, pool_pre_ping=True, connect_args={"timeout": 15})
        with eng.connect() as c:
            db = c.execute(text("SELECT DB_NAME()")).scalar()
            print(OK + f"kết nối được, đang ở database: {db}")
            if db != "MEDFORECAST_DW":
                bao_loi(f"Đang nối vào '{db}', không phải MEDFORECAST_DW.",
                        "Sửa phần tên database ở cuối chuỗi kết nối.")

            # Ba view CŨ (luồng ca bệnh + tồn kho) và ba view MỚI của DSS.
            # Trước đây script chỉ kiểm ba view cũ, nên nó vẫn báo xanh trong khi
            # ba view DSS chưa tồn tại hoặc chưa được GRANT — rồi run_dss_load.py
            # mới hỏng. Kiểm ở đây để biết sớm hơn một bước.
            for view, nhan in [("vw_MedForecast_CaBenh", "ca bệnh + vật tư"),
                               ("vw_MedForecast_CaBenhNhom", "số ca theo NHÓM"),
                               ("vw_MedForecast_TonKho", "tồn kho"),
                               ("vw_MedForecast_TieuHaoTong", "DSS · tiêu hao toàn viện"),
                               ("vw_MedForecast_CaBenhPhanCap", "DSS · ca bệnh theo rổ chăm sóc"),
                               ("vw_MedForecast_TieuHaoPhanCap", "DSS · tiêu hao theo rổ chăm sóc"),
                               ("vw_MedForecast_TonKhoLo_MoiNhat", "DSS · tồn kho theo lô (cho FEFO)")]:
                try:
                    n = c.execute(text(f"SELECT COUNT(*) FROM dbo.{view}")).scalar()
                    if n and n > 0:
                        print(OK + f"{view}: {n:,} dòng ({nhan})")
                    else:
                        goi_y = ("Chạy lại thủ tục bên PROD: "
                                 "EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1;")
                        if "TieuHaoTong" in view:
                            goi_y = "EXEC dbo.usp_MedForecast_DayTieuHaoToanVien @SoThang = 24;"
                        elif "PhanCap" in view:
                            goi_y = ("EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1; "
                                     "(cần bản v3 có khối #CapDot)")
                        elif "TonKhoLo" in view:
                            goi_y = "EXEC dbo.usp_MedForecast_DayKhoCungUng;"
                        bao_loi(f"{view} RỖNG.", goi_y)
                except Exception as e:
                    bao_loi(f"Không đọc được {view}: {str(e)[:120]}",
                            """Thiếu view (chạy lại script 01) hoặc tài khoản chưa được
                               GRANT SELECT (xem cuối script 01).""")

            print("\n=== 4. Cột nhóm bệnh ===")
            try:
                r = c.execute(text(
                    "SELECT COUNT(DISTINCT disease_group) AS n, "
                    "SUM(CASE WHEN disease_group IS NULL THEN 1 ELSE 0 END) AS thieu "
                    "FROM dbo.vw_MedForecast_CaBenh")).one()
                if r.n >= 3 and r.thieu == 0:
                    print(OK + f"có {r.n} nhóm ICD, không dòng nào thiếu nhóm")
                else:
                    bao_loi(f"có {r.n} nhóm, {r.thieu} dòng thiếu disease_group.",
                            "Chạy lại thủ tục 03 bản mới nhất rồi nạp lại toàn bộ.")
            except Exception as e:
                bao_loi(f"View chưa có cột disease_group: {str(e)[:120]}",
                        "Chạy lại script 01 (có ALTER TABLE nâng cấp bảng cũ) rồi script 03.")

            print("\n=== 5. Độ tươi dữ liệu ===")
            try:
                r = c.execute(text(
                    "SELECT TOP 1 KetThuc, SoDongCaBenh, TongSoCa, TrangThai "
                    "FROM dbo.MF_SyncLog ORDER BY Id DESC")).one()
                print(OK + f"lần đẩy gần nhất: {r.KetThuc} — {r.SoDongCaBenh:,} dòng, "
                           f"{r.TongSoCa:,} ca, trạng thái '{r.TrangThai}'")
                if r.TrangThai != "ok":
                    bao_loi("Lần đẩy gần nhất KHÔNG thành công.",
                            "Xem cột ThongDiep trong MF_SyncLog.")
            except Exception:
                print("  (chưa đọc được MF_SyncLog — không bắt buộc)")
    except Exception as e:
        bao_loi(f"Không kết nối được: {str(e)[:250]}",
                """Kiểm theo thứ tự:
                   - Máy có ping tới được máy chủ STA không (tường lửa, VPN)
                   - Instance có tên thì viết @host\\TEN_INSTANCE, không kèm :1433
                   - SQL Server đã bật xác thực SQL (không phải chỉ Windows Auth)
                   - Login medforecast_app đã tạo chưa (phần cuối script 01,
                     đang bị chú thích — phải bỏ chú thích và chạy)""")

    _kiem_nguon_cau_hinh_ung_dung()

    return ket_luan()


def ket_luan() -> int:
    print()
    if loi == 0:
        print("=== TẤT CẢ ĐỀU ĐẠT — chạy đồng bộ được rồi ===")
        print("    python -m app.data_pipeline.run --source sqlserver --full")
        return 0
    print(f"=== CÒN {loi} VẤN ĐỀ — sửa xong hãy chạy đồng bộ ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())
