# -*- coding: utf-8 -*-
"""Cấu hình kết nối CSDL nghiên cứu MEDFORECAST_DW lưu trong DB — sửa từ Quản trị.

NGUỒN DỮ LIỆU (từ 23/09/2026): bệnh viện chạy thủ tục nội bộ khử định danh rồi
bàn giao SNAPSHOT database MEDFORECAST_DW (12 bảng MF_*). Snapshot được khôi
phục trên SQL Server cục bộ của máy trạm nghiên cứu; ứng dụng đọc 7 view
vw_MedForecast_* tại đó — không còn kết nối mạng tới HIS hay máy chủ STA.

VÌ SAO LƯU TRONG DB THAY VÌ .env
.env đòi hỏi người vận hành SSH vào máy chủ, sửa file, khởi động lại backend —
ba việc mà nhân viên CNTT bệnh viện không muốn làm mỗi lần đổi mật khẩu DB.
Lưu trong bảng system_config thì admin đổi ngay trên giao diện, có nút thử kết
nối trước khi lưu, và lần đồng bộ sau tự dùng cấu hình mới, không cần restart.

THỨ TỰ ƯU TIÊN khi build pipeline:
    1. Cấu hình trong DB (nếu admin đã lưu)
    2. Biến môi trường PIPELINE_* trong .env (cách cũ, vẫn chạy)
Nhờ vậy máy dev chưa có gì trong DB vẫn chạy như trước.

MẬT KHẨU không nằm dạng chữ thường trong DB: mã hoá Fernet với khoá dẫn xuất
từ SECRET_KEY của app (sha256 → urlsafe-b64). Đây là mã hoá thuận nghịch —
buộc phải thế vì lúc kết nối cần mật khẩu gốc — nên bảo vệ thật sự nằm ở việc
giữ SECRET_KEY ngoài DB. Ai đọc trộm được bảng system_config vẫn không dùng
được mật khẩu nếu không có SECRET_KEY. API trả về client KHÔNG BAO GIỜ kèm
mật khẩu, kể cả dạng đã mã hoá.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Optional
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app.config import settings
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

CONFIG_KEY = "his_sync.connection"

# Hai "hồ sơ" câu SQL — quyết định app đọc VIEW nào từ nguồn
SQL_PROFILES = {
    # DB trung chuyển MEDFORECAST_DW bên STAGING (khuyến nghị, mặc định)
    "sta": {"case": "case_sta.sql", "inventory": "inventory_sta.sql",
            "case_group": "case_group_sta.sql"},
    # 09/09/2026 — đã bỏ profile "mssql". Nó trỏ vào case_mssql.sql /
    # inventory_mssql.sql, hai file truy vấn schema GIẢ ĐỊNH không tồn tại
    # trong HIS thật; chọn nó từ giao diện là chắc chắn lỗi
    # "Invalid object name 'KhamBenh'". Xem _archive/sql_schema_cu/.
}

MAC_DINH = {
    "source": "sqlserver",     # chỉ còn sqlserver (nguồn tệp CSV đã bỏ 23/09/2026)
    "host": "localhost",       # SQL Server cục bộ chứa snapshot MEDFORECAST_DW
    "port": 1433,
    "instance": "",            # instance có tên (localhost\SQLEXPRESS) — khi đặt thì bỏ port
    "database": "MEDFORECAST_DW",
    "auth": "windows",         # windows (Trusted_Connection) | sql (UID/PWD)
    "username": "medforecast_app",
    "driver": "ODBC Driver 18 for SQL Server",
    "trust_cert": True,        # chứng chỉ tự ký của SQL Server cục bộ
    "sql_profile": "sta",
    "lookback_months": 3,      # số kỳ nạp lại mỗi lần (snapshot đóng băng: 0 cũng đủ)
}

# 7 view ứng dụng đọc + nhãn (kiểm tra kết nối phải đủ cả 7, không chỉ 3)
VIEW_UNG_DUNG = [
    ("vw_MedForecast_CaBenh",          "ca bệnh theo mã ICD"),
    ("vw_MedForecast_CaBenhNhom",      "số ca theo nhóm ICD"),
    ("vw_MedForecast_TonKho",          "tồn kho + danh mục"),
    ("vw_MedForecast_TieuHaoTong",     "tiêu hao toàn viện (Tầng 2/3)"),
    ("vw_MedForecast_CaBenhPhanCap",   "ca bệnh theo rổ chăm sóc (Tầng 2)"),
    ("vw_MedForecast_TieuHaoPhanCap",  "tiêu hao theo rổ chăm sóc (Tầng 2)"),
    ("vw_MedForecast_TonKhoLo_MoiNhat", "tồn kho theo lô — ảnh chụp mới nhất (FEFO)"),
]


# ── Mã hoá mật khẩu ──────────────────────────────────────────────────────────
def _fernet():
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())
    return Fernet(key)


def _ma_hoa(mat_khau: str) -> str:
    return _fernet().encrypt(mat_khau.encode("utf-8")).decode("ascii")


def _giai_ma(ban_ma: str) -> str:
    return _fernet().decrypt(ban_ma.encode("ascii")).decode("utf-8")


# ── Đọc / ghi cấu hình ───────────────────────────────────────────────────────
def _doc_tho(db: Session) -> Optional[dict]:
    row = (db.query(SystemConfig)
             .filter(SystemConfig.config_key == CONFIG_KEY).first())
    if not row:
        return None
    try:
        return json.loads(row.config_value)
    except (ValueError, TypeError):
        logger.warning("Cấu hình %s trong DB không phải JSON hợp lệ — bỏ qua.",
                       CONFIG_KEY)
        return None


def get_config(db: Session) -> dict:
    """Cấu hình cho client: KHÔNG kèm mật khẩu, chỉ báo đã đặt hay chưa."""
    cfg = {**MAC_DINH, **(_doc_tho(db) or {})}
    cfg["has_password"] = bool(cfg.pop("password_enc", ""))
    cfg["da_luu_trong_db"] = _doc_tho(db) is not None
    return cfg


def save_config(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """Lưu cấu hình. Mật khẩu rỗng = GIỮ mật khẩu cũ (để sửa host mà không
    phải gõ lại mật khẩu)."""
    cu = _doc_tho(db) or {}
    moi = {k: payload[k] for k in MAC_DINH if k in payload}

    if moi.get("sql_profile") not in SQL_PROFILES:
        moi["sql_profile"] = "sta"
    moi["lookback_months"] = max(0, int(moi.get("lookback_months", 3)))
    moi["port"] = int(moi.get("port") or 1433)
    for k in ("host", "instance", "database", "username", "driver"):
        moi[k] = str(moi.get(k, "")).strip()
    moi["auth"] = "windows" if str(moi.get("auth", "")).lower() == "windows" else "sql"
    moi["driver"], _ = driver_kha_dung(moi.get("driver") or MAC_DINH["driver"])
    moi["source"] = "sqlserver"

    mat_khau = (payload.get("password") or "").strip()
    if mat_khau:
        moi["password_enc"] = _ma_hoa(mat_khau)
    elif cu.get("password_enc"):
        moi["password_enc"] = cu["password_enc"]

    row = (db.query(SystemConfig)
             .filter(SystemConfig.config_key == CONFIG_KEY).first())
    if row is None:
        row = SystemConfig(config_key=CONFIG_KEY,
                           description="Kết nối CSDL nghiên cứu MEDFORECAST_DW "
                                       "cục bộ (mật khẩu đã mã hoá nếu dùng SQL auth)")
        db.add(row)
    row.config_value = json.dumps(moi, ensure_ascii=False)
    row.updated_by = user_id
    db.commit()
    return get_config(db)


# ── Dựng chuỗi kết nối ───────────────────────────────────────────────────────
# Thứ tự ưu tiên khi tên driver trong cấu hình KHÔNG có trên máy (lỗi IM002
# "Data source name not found and no default driver specified").
DRIVER_UU_TIEN = [
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 13 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
]


def driver_kha_dung(driver_cau_hinh: str) -> tuple[str, bool]:
    """Trả (tên driver dùng thật, có phải tên đã cấu hình không).

    Máy nào cài bản nào không đoán được: máy trạm hay chỉ có Driver 17, máy
    mới hay có 18. Nếu tên đã lưu không nằm trong pyodbc.drivers() thì lấy
    driver SQL Server tốt nhất đang có — kết nối được quan trọng hơn đúng số
    phiên bản. Không có pyodbc (VM kiểm thử) thì trả nguyên tên cấu hình.
    """
    try:
        import pyodbc
        co = list(pyodbc.drivers())
    except Exception:  # noqa: BLE001
        return driver_cau_hinh, True
    if driver_cau_hinh in co:
        return driver_cau_hinh, True
    for d in DRIVER_UU_TIEN:
        if d in co:
            return d, False
    sql_drv = [d for d in co if "SQL Server" in d]
    return (sql_drv[0], False) if sql_drv else (driver_cau_hinh, True)


def dung_windows_auth(cfg: dict) -> bool:
    """Windows Authentication khi admin chọn `auth = windows`, HOẶC khi không có
    username lẫn mật khẩu (SQL Server cục bộ trên máy trạm mặc định chỉ bật
    Windows auth — không bắt người dùng tạo login SQL chỉ để chạy đồ án)."""
    if str(cfg.get("auth", "")).lower() == "windows":
        return True
    return not cfg.get("username") and not cfg.get("password_enc")


def _chuoi_ket_noi(cfg: dict) -> str:
    """Dựng qua odbc_connect + quote_plus: mật khẩu chứa @ ; \\ % gì cũng an
    toàn — dán thẳng vào URL SQLAlchemy thì mấy ký tự đó phá cú pháp.

    `auth = windows`  → Trusted_Connection=yes (không UID/PWD)
    `auth = sql`      → UID/PWD như trước
    """
    if cfg.get("instance"):
        server = f"{cfg['host']}\\{cfg['instance']}"      # instance có tên: bỏ port
    else:
        server = f"{cfg['host']},{cfg.get('port', 1433)}"
    driver, _ = driver_kha_dung(cfg.get("driver") or MAC_DINH["driver"])
    odbc = (f"DRIVER={{{driver}}};SERVER={server};"
            f"DATABASE={cfg['database']};")
    if dung_windows_auth(cfg):
        odbc += "Trusted_Connection=yes;"
    else:
        odbc += (f"UID={cfg['username']};"
                 f"PWD={_giai_ma(cfg['password_enc'])};")
    if cfg.get("trust_cert", True):
        odbc += "TrustServerCertificate=yes;"
    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc)


def build_connector(db: Session):
    """Connector theo cấu hình DB, hoặc None nếu admin chưa lưu gì.

    None nghĩa là: quay về cách cũ (biến môi trường PIPELINE_*).
    """
    cfg = _doc_tho(db)
    if not cfg:
        return None

    can = ["host", "database"]
    if not dung_windows_auth(cfg):
        can += ["username", "password_enc"]
    thieu = [k for k in can if not cfg.get(k)]
    if thieu:
        raise RuntimeError(
            f"Cấu hình kết nối MEDFORECAST_DW trong DB thiếu: {', '.join(thieu)}. "
            "Vào Quản trị → Nguồn dữ liệu (CSDL DW) để bổ sung.")

    from app.data_pipeline.connectors import SqlServerConnector, _load_sql
    ho_so = SQL_PROFILES.get(cfg.get("sql_profile", "sta"), SQL_PROFILES["sta"])
    return SqlServerConnector(
        _chuoi_ket_noi(cfg),
        case_sql=_load_sql(ho_so["case"]),
        inventory_sql=_load_sql(ho_so["inventory"]),
        case_group_sql=_load_sql(ho_so["case_group"]) if ho_so["case_group"] else "",
    )


# ── Thử kết nối ──────────────────────────────────────────────────────────────
def test_connection(db: Session, payload: dict) -> dict:
    """Thử kết nối bằng cấu hình vừa nhập (CHƯA lưu). Mật khẩu rỗng thì mượn
    mật khẩu đã lưu — admin thử lại sau khi đổi host không phải gõ lại.

    Trả về từng bước để giao diện chỉ đúng chỗ hỏng thay vì một câu
    'kết nối thất bại' vô dụng.
    """
    cfg = {**MAC_DINH, **{k: v for k, v in payload.items() if v is not None}}
    mat_khau = (payload.get("password") or "").strip()
    if mat_khau:
        cfg["password_enc"] = _ma_hoa(mat_khau)
    else:
        cu = _doc_tho(db) or {}
        cfg["password_enc"] = cu.get("password_enc", "")
    if not dung_windows_auth(cfg) and not cfg.get("password_enc"):
        return {"ok": False, "steps": [
            {"name": "Mật khẩu", "ok": False,
             "detail": "SQL auth cần mật khẩu: chưa nhập và trong DB cũng chưa lưu "
                       "(hoặc chọn Windows Authentication)."}]}

    steps, ok = [], True
    driver_that, dung_ten = driver_kha_dung(cfg.get("driver") or MAC_DINH["driver"])
    if not dung_ten:
        steps.append({"name": "Driver ODBC", "ok": True,
                      "detail": (f"Máy không có '{cfg.get('driver')}' — dùng '{driver_that}' "
                                 "đang cài. Lưu cấu hình để ghi nhớ driver này.")})
        cfg["driver"] = driver_that
    try:
        from sqlalchemy import create_engine, text
        eng = create_engine(_chuoi_ket_noi(cfg), pool_pre_ping=True,
                            connect_args={"timeout": 10})
        with eng.connect() as c:
            ten_db = c.execute(text("SELECT DB_NAME()")).scalar()
            cach = "Windows Authentication" if dung_windows_auth(cfg) else f"SQL auth ({cfg.get('username')})"
            steps.append({"name": "Kết nối SQL Server cục bộ", "ok": True,
                          "detail": f"Đăng nhập được ({cach}), database: {ten_db}"})
            # Snapshot bàn giao: 12 bảng MF_* + mốc chốt trong MF_Watermark
            try:
                so_bang = c.execute(text(
                    "SELECT COUNT(*) FROM sys.tables WHERE name LIKE 'MF[_]%'")).scalar()
                goi_y_quyen = ("" if so_bang >= 9 else
                               " → Đăng nhập được nhưng không thấy bảng: user trong DB chưa được cấp "
                               "quyền (thường gặp sau RESTORE: user mồ côi). Chạy "
                               "sql_his/khoi_phuc_snapshot/01_quyen_sau_restore.sql, hoặc chọn "
                               "Windows Authentication.")
                steps.append({"name": "Bảng MF_* trong snapshot", "ok": so_bang >= 9,
                              "detail": f"{so_bang} bảng dbo.MF_* (cần ≥ 9 bảng nghiệp vụ){goi_y_quyen}"})
            except Exception as e:  # noqa: BLE001
                steps.append({"name": "Bảng MF_* trong snapshot", "ok": False,
                              "detail": f"Không đọc được sys.tables: {str(e)[:120]}"})
            try:
                wm = c.execute(text(
                    "SELECT CONVERT(varchar(10), MAX(MocDaDay), 120), "
                    "       CONVERT(varchar(19), MAX(LanChayCuoi), 120) "
                    "FROM dbo.MF_Watermark")).fetchone()
                moc, lan = (wm[0], wm[1]) if wm else (None, None)
                steps.append({"name": "Mốc dữ liệu bệnh viện chốt", "ok": bool(moc),
                              "detail": (f"Snapshot chốt tới kỳ {moc[:7]} (thủ tục chạy lần cuối {lan})"
                                         if moc else "MF_Watermark chưa có mốc")})
            except Exception as e:  # noqa: BLE001
                steps.append({"name": "Mốc dữ liệu bệnh viện chốt", "ok": False,
                              "detail": f"Không đọc được MF_Watermark: {str(e)[:120]}"})
            ho_so = SQL_PROFILES.get(cfg.get("sql_profile", "sta"),
                                     SQL_PROFILES["sta"])
            if ho_so is SQL_PROFILES["sta"]:
                for view, nhan in VIEW_UNG_DUNG:
                    try:
                        n = c.execute(
                            text(f"SELECT COUNT(*) FROM dbo.{view}")).scalar()
                        steps.append({
                            "name": nhan, "ok": bool(n),
                            "detail": (f"{view}: {n:,} dòng" if n else
                                       f"{view} RỖNG — kho trung gian chưa được "
                                       "cập nhật")})
                        ok = ok and bool(n)
                    except Exception as e:
                        ok = False
                        loi_v = str(e)
                        if "permission was denied" in loi_v:
                            loi_v = ("SELECT bị từ chối — cấp quyền bằng "
                                     "sql_his/khoi_phuc_snapshot/01_quyen_sau_restore.sql")
                        steps.append({"name": nhan, "ok": False,
                                      "detail": f"Không đọc được {view}: {loi_v[:150]}"})
        eng.dispose()
    except Exception as e:
        ok = False
        loi = str(e)
        goi_y = ""
        if "IM002" in loi or "driver" in loi.lower():
            try:
                import pyodbc
                co = ", ".join(d for d in pyodbc.drivers() if "SQL Server" in d) or "không có"
            except Exception:  # noqa: BLE001
                co = "không kiểm tra được (thiếu pyodbc)"
            goi_y = (f" → Tên driver '{cfg.get('driver')}' không có trên máy; driver SQL Server "
                     f"đang cài: {co}. Chọn đúng tên trong ô Driver ODBC hoặc cài ODBC Driver 18.")
        elif "Login failed" in loi:
            goi_y = (" → Sai tài khoản/mật khẩu; SQL Server cục bộ thường chỉ bật "
                     "Windows Authentication — chọn auth = windows.")
        elif "timeout" in loi.lower() or "TCP" in loi:
            goi_y = (" → Không tới được SQL Server: kiểm tra dịch vụ đã chạy, tên "
                     "instance (localhost\\SQLEXPRESS), TCP/IP đã bật trong Configuration Manager.")
        steps.append({"name": "Kết nối SQL Server cục bộ", "ok": False,
                      "detail": loi[:300] + goi_y})
    return {"ok": ok, "steps": steps}
