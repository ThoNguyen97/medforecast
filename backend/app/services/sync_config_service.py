# -*- coding: utf-8 -*-
"""Cấu hình kết nối HIS/STA lưu trong DB — sửa được từ màn hình Quản trị.

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
    # Đọc thẳng schema eHospital (chỉ dành cho môi trường thử — app KHÔNG
    # bao giờ nên nối thẳng PROD thật)
    "mssql": {"case": "case_mssql.sql", "inventory": "inventory_mssql.sql",
              "case_group": ""},
}

MAC_DINH = {
    "source": "file",          # file | sqlserver
    "host": "",
    "port": 1433,
    "instance": "",            # instance có tên (MÁY\STA) — khi đặt thì bỏ port
    "database": "MEDFORECAST_DW",
    "username": "medforecast_app",
    "driver": "ODBC Driver 18 for SQL Server",
    "trust_cert": True,        # chứng chỉ tự ký trong mạng nội bộ
    "sql_profile": "sta",
    "lookback_months": 3,      # phải khớp @SoThangLuiLai của thủ tục bên PROD
}


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

    mat_khau = (payload.get("password") or "").strip()
    if mat_khau:
        moi["password_enc"] = _ma_hoa(mat_khau)
    elif cu.get("password_enc"):
        moi["password_enc"] = cu["password_enc"]

    row = (db.query(SystemConfig)
             .filter(SystemConfig.config_key == CONFIG_KEY).first())
    if row is None:
        row = SystemConfig(config_key=CONFIG_KEY,
                           description="Kết nối nguồn dữ liệu HIS/STA "
                                       "(mật khẩu đã mã hoá)")
        db.add(row)
    row.config_value = json.dumps(moi, ensure_ascii=False)
    row.updated_by = user_id
    db.commit()
    return get_config(db)


# ── Dựng chuỗi kết nối ───────────────────────────────────────────────────────
def _chuoi_ket_noi(cfg: dict) -> str:
    """Dựng qua odbc_connect + quote_plus: mật khẩu chứa @ ; \\ % gì cũng an
    toàn — dán thẳng vào URL SQLAlchemy thì mấy ký tự đó phá cú pháp."""
    if cfg.get("instance"):
        server = f"{cfg['host']}\\{cfg['instance']}"      # instance có tên: bỏ port
    else:
        server = f"{cfg['host']},{cfg.get('port', 1433)}"
    odbc = (f"DRIVER={{{cfg['driver']}}};SERVER={server};"
            f"DATABASE={cfg['database']};UID={cfg['username']};"
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

    if cfg.get("source") != "sqlserver":
        from app.data_pipeline.connectors import FileConnector
        import os
        return FileConnector(os.environ.get("PIPELINE_DATA_DIR", "../data"))

    thieu = [k for k in ("host", "database", "username", "password_enc")
             if not cfg.get(k)]
    if thieu:
        raise RuntimeError(
            f"Cấu hình kết nối HIS trong DB thiếu: {', '.join(thieu)}. "
            "Vào Quản trị → Kết nối HIS để bổ sung.")

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
        if not cu.get("password_enc"):
            return {"ok": False, "steps": [
                {"name": "Mật khẩu", "ok": False,
                 "detail": "Chưa nhập mật khẩu và trong DB cũng chưa lưu."}]}
        cfg["password_enc"] = cu["password_enc"]

    steps, ok = [], True
    try:
        from sqlalchemy import create_engine, text
        eng = create_engine(_chuoi_ket_noi(cfg), pool_pre_ping=True,
                            connect_args={"timeout": 10})
        with eng.connect() as c:
            ten_db = c.execute(text("SELECT DB_NAME()")).scalar()
            steps.append({"name": "Kết nối máy chủ", "ok": True,
                          "detail": f"Đăng nhập được, database: {ten_db}"})
            ho_so = SQL_PROFILES.get(cfg.get("sql_profile", "sta"),
                                     SQL_PROFILES["sta"])
            if ho_so is SQL_PROFILES["sta"]:
                views = [("vw_MedForecast_CaBenh", "ca bệnh + vật tư"),
                         ("vw_MedForecast_CaBenhNhom", "số ca theo nhóm"),
                         ("vw_MedForecast_TonKho", "tồn kho")]
                for view, nhan in views:
                    try:
                        n = c.execute(
                            text(f"SELECT COUNT(*) FROM dbo.{view}")).scalar()
                        steps.append({
                            "name": nhan, "ok": bool(n),
                            "detail": (f"{view}: {n:,} dòng" if n else
                                       f"{view} RỖNG — chạy thủ tục đồng bộ "
                                       "bên PROD trước")})
                        ok = ok and bool(n)
                    except Exception as e:
                        ok = False
                        steps.append({"name": nhan, "ok": False,
                                      "detail": f"Không đọc được {view}: "
                                                f"{str(e)[:150]}"})
        eng.dispose()
    except Exception as e:
        ok = False
        loi = str(e)
        goi_y = ""
        if "IM002" in loi or "driver" in loi.lower():
            goi_y = " → Máy chủ backend chưa cài ODBC Driver cho SQL Server."
        elif "Login failed" in loi:
            goi_y = " → Sai tài khoản/mật khẩu, hoặc login chưa được tạo trên STA."
        elif "timeout" in loi.lower() or "TCP" in loi:
            goi_y = " → Không tới được máy chủ: kiểm tra tường lửa/VPN, tên máy, port."
        steps.append({"name": "Kết nối máy chủ", "ok": False,
                      "detail": loi[:300] + goi_y})
    return {"ok": ok, "steps": steps}
