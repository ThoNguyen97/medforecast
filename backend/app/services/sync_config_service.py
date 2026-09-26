# -*- coding: utf-8 -*-
"""Cấu hình kết nối MEDFORECAST_DW (STA) lưu trong system_config, ưu tiên hơn biến môi trường PIPELINE_*.
Mật khẩu mã hoá Fernet với khoá dẫn xuất từ SECRET_KEY (cần thuận nghịch để kết nối);
API không bao giờ trả mật khẩu về client.
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

# Hồ sơ câu SQL: app đọc view nào từ nguồn.
SQL_PROFILES = {
    "sta": {"case": "case_sta.sql", "inventory": "inventory_sta.sql",
            "case_group": "case_group_sta.sql"},
}

MAC_DINH = {
    "source": "sqlserver",
    "host": "localhost",
    "port": 1433,
    "instance": "",            # instance có tên: khi đặt thì bỏ port
    "database": "MEDFORECAST_DW",
    "auth": "windows",         # windows (Trusted_Connection) | sql (UID/PWD)
    "username": "medforecast_app",
    "driver": "ODBC Driver 18 for SQL Server",
    "trust_cert": True,        # chấp nhận chứng chỉ tự ký
    "sql_profile": "sta",
    "lookback_months": 3,      # số kỳ nạp lại mỗi lần đồng bộ
}

# 7 view ứng dụng đọc; kiểm tra kết nối duyệt đủ cả 7.
VIEW_UNG_DUNG = [
    ("vw_MedForecast_CaBenh",          "ca bệnh theo mã ICD"),
    ("vw_MedForecast_CaBenhNhom",      "số ca theo nhóm ICD"),
    ("vw_MedForecast_TonKho",          "tồn kho + danh mục"),
    ("vw_MedForecast_TieuHaoTong",     "tiêu hao toàn viện (Tầng 2/3)"),
    ("vw_MedForecast_CaBenhPhanCap",   "ca bệnh theo rổ chăm sóc (Tầng 2)"),
    ("vw_MedForecast_TieuHaoPhanCap",  "tiêu hao theo rổ chăm sóc (Tầng 2)"),
    ("vw_MedForecast_TonKhoLo_MoiNhat", "tồn kho theo lô — ảnh chụp mới nhất (FEFO)"),
]


# ── Mã hoá mật khẩu ──
def _fernet():
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())
    return Fernet(key)


def _ma_hoa(mat_khau: str) -> str:
    return _fernet().encrypt(mat_khau.encode("utf-8")).decode("ascii")


def _giai_ma(ban_ma: str) -> str:
    return _fernet().decrypt(ban_ma.encode("ascii")).decode("utf-8")


# ── Đọc / ghi cấu hình ──
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
    """Cấu hình cho client: không kèm mật khẩu, chỉ báo đã đặt hay chưa."""
    cfg = {**MAC_DINH, **(_doc_tho(db) or {})}
    cfg["has_password"] = bool(cfg.pop("password_enc", ""))
    cfg["da_luu_trong_db"] = _doc_tho(db) is not None
    return cfg


def save_config(db: Session, payload: dict, user_id: Optional[int]) -> dict:
    """Lưu cấu hình; mật khẩu rỗng thì giữ mật khẩu đã lưu."""
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
                           description="Kết nối CSDL MEDFORECAST_DW trên STA "
                                       "(mật khẩu đã mã hoá nếu dùng SQL auth)")
        db.add(row)
    row.config_value = json.dumps(moi, ensure_ascii=False)
    row.updated_by = user_id
    db.commit()
    return get_config(db)


# ── Dựng chuỗi kết nối ──
# Thứ tự ưu tiên khi driver cấu hình không có trên máy (IM002).
DRIVER_UU_TIEN = [
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 13 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
]


def driver_kha_dung(driver_cau_hinh: str) -> tuple[str, bool]:
    """Trả (driver dùng thật, có phải tên đã cấu hình); thiếu driver thì lấy theo DRIVER_UU_TIEN."""
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
    """Dùng Windows Authentication khi `auth = windows` hoặc không có cả username lẫn mật khẩu."""
    if str(cfg.get("auth", "")).lower() == "windows":
        return True
    return not cfg.get("username") and not cfg.get("password_enc")


def _chuoi_ket_noi(cfg: dict) -> str:
    """URL SQLAlchemy qua odbc_connect + quote_plus, an toàn với mật khẩu chứa ký tự đặc biệt."""
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
    """Connector theo cấu hình trong DB; None nếu chưa lưu."""
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


# ── Thử kết nối ──
def test_connection(db: Session, payload: dict) -> dict:
    """Thử kết nối bằng cấu hình chưa lưu, trả kết quả từng bước; mật khẩu rỗng thì dùng mật khẩu đã lưu."""
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
            steps.append({"name": "Kết nối SQL Server", "ok": True,
                          "detail": f"Đăng nhập được ({cach}), database: {ten_db}"})
            try:
                so_bang = c.execute(text(
                    "SELECT COUNT(*) FROM sys.tables WHERE name LIKE 'MF[_]%'")).scalar()
                goi_y_quyen = ("" if so_bang >= 9 else
                               " → Đăng nhập được nhưng không thấy bảng: user trong DB chưa được cấp "
                               "quyền SELECT. Chạy phần GRANT trong sql_his/sta/*.sql, hoặc chọn "
                               "Windows Authentication.")
                steps.append({"name": "Bảng MF_* trong MEDFORECAST_DW", "ok": so_bang >= 9,
                              "detail": f"{so_bang} bảng dbo.MF_* (cần ≥ 9 bảng nghiệp vụ){goi_y_quyen}"})
            except Exception as e:  # noqa: BLE001
                steps.append({"name": "Bảng MF_* trong MEDFORECAST_DW", "ok": False,
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
                                     "phần GRANT trong sql_his/sta/*.sql")
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
            goi_y = (" → Sai tài khoản/mật khẩu; kiểm tra tài khoản medforecast_app "
                     "trên STA hoặc chọn Windows Authentication.")
        elif "timeout" in loi.lower() or "TCP" in loi:
            goi_y = (" → Không tới được SQL Server: kiểm tra địa chỉ/port máy chủ STA, "
                     "tên instance và TCP/IP đã bật trên máy chủ.")
        steps.append({"name": "Kết nối SQL Server", "ok": False,
                      "detail": loi[:300] + goi_y})
    return {"ok": ok, "steps": steps}
