"""Nạp bốn luồng dữ liệu DSS từ STA về DB local.

Đặt tại: backend/app/data_pipeline/dss_loader.py

    vw_MedForecast_TieuHaoTong        →  fact_usage_total
    vw_MedForecast_CaBenhPhanCap      →  fact_cases_by_care_level
    vw_MedForecast_TieuHaoPhanCap     →  fact_usage_by_care_level
    vw_MedForecast_TonKhoLo_MoiNhat   →  fact_inventory_lot        (cho FEFO)

Ba luồng đầu theo KỲ (`period`), nạp tăng dần được. Luồng thứ tư là ẢNH CHỤP
tồn kho (`snapshot_date`) — không có khái niệm kỳ, và một ảnh chụp mới làm ảnh
chụp cũ hết giá trị. Cả bốn đều xoá-rồi-chèn theo khoá phân vùng của mình.

-----------------------------------------------------------------------------
VÌ SAO LÀ MODULE RIÊNG, KHÔNG SỬA pipeline.py

`DataPipeline` hiện có 508 dòng và một transaction duy nhất bao trọn staging →
dim → fact → mart. Thêm ba luồng vào giữa nghĩa là một lỗi ở luồng mới sẽ
rollback cả phần ca bệnh vốn đang chạy tốt — đúng kiểu lỗi im lặng mà chính
`_build_weather_mart` đã phải viết chú thích dài để tránh.

Module này chạy độc lập, có transaction riêng, và được gọi SAU khi pipeline
chính xong. Hỏng thì chỉ ba bảng mới rỗng, mọi thứ khác nguyên vẹn.

-----------------------------------------------------------------------------
CƠ CHẾ NẠP: XOÁ-RỒI-CHÈN THEO TỪNG KỲ

Mỗi kỳ (`period`) có trong dữ liệu vừa kéo về sẽ bị XOÁ SẠCH bên local rồi chèn
lại. Chạy lại mười lần cũng ra đúng một kết quả, và dữ liệu về muộn của tháng cũ
được cập nhật đúng thay vì cộng thêm.

KHÔNG dùng INSERT OR REPLACE: nếu bên nguồn một dòng biến mất (ví dụ toa bị huỷ
sau khi đã đồng bộ) thì REPLACE vẫn để lại dòng cũ, còn xoá-theo-kỳ thì không.

Các kỳ KHÔNG có trong lần kéo này được giữ nguyên — nên nạp tăng dần an toàn.
"""
from __future__ import annotations

import logging
import re
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).parent / "sql"

# Số kỳ lùi lại khi nạp tăng dần. Dữ liệu tiêu hao gần như không đổi sau khi
# chốt tháng, nhưng toa bị huỷ muộn thì có — lùi 3 kỳ cho chắc.
LOOKBACK_MONTHS = int(os.environ.get("DSS_LOOKBACK_MONTHS", "3"))
INSERT_CHUNK = 1000


# ─────────────────────────────────────────────────────────────────────────────
# Đặc tả ba luồng
# ─────────────────────────────────────────────────────────────────────────────

FLOWS: Dict[str, Dict[str, Any]] = {
    "usage_total": {
        "sql_file": "usage_total_sta.sql",
        "table": "fact_usage_total",
        # cột local  ←  cột nguồn
        "map": {
            "period":             "__period__",
            "supply_code":        "supply_code",
            "supply_name":        "supply_name",
            "supply_unit":        "supply_unit",
            "is_vtyt":            "is_vtyt",
            "so_luong_toan_vien": "so_luong_toan_vien",
            "so_luong_hohap":     "so_luong_hohap",
            "d_baseline_thang":   "d_baseline_thang",
            "ty_trong_hohap":     "ty_trong_hohap",
            "so_dong_toa":        "so_dong_toa",
            "so_luot":            "so_luot",
        },
        "numeric": ["so_luong_toan_vien", "so_luong_hohap", "d_baseline_thang",
                    "ty_trong_hohap", "so_dong_toa", "so_luot", "is_vtyt"],
        # Chỉ những cột CỘNG ĐƯỢC. `d_baseline_thang` và `ty_trong_hohap` là
        # đại lượng dẫn xuất — cộng hai dòng trùng sẽ ra gấp đôi tỷ trọng.
        "sum": ["so_luong_toan_vien", "so_luong_hohap", "so_dong_toa", "so_luot"],
        "required": ["supply_code", "so_luong_toan_vien"],
    },
    "cases_care_level": {
        "sql_file": "cases_care_level_sta.sql",
        "table": "fact_cases_by_care_level",
        "map": {
            "period":     "__period__",
            "block_code": "disease_group",
            "ro":         "ro",
            "cases":      "cases",
        },
        "numeric": ["cases"],
        "sum": ["cases"],
        "required": ["block_code", "ro", "cases"],
    },
    "usage_care_level": {
        "sql_file": "usage_care_level_sta.sql",
        "table": "fact_usage_by_care_level",
        "map": {
            "period":      "__period__",
            "block_code":  "disease_group",
            "ro":          "ro",
            "supply_code": "supply_code",
            "is_vtyt":     "is_vtyt",
            "quantity":    "so_luong",
            "line_count":  "so_dong_toa",
        },
        "numeric": ["quantity", "line_count", "is_vtyt"],
        "sum": ["quantity", "line_count"],
        "required": ["block_code", "ro", "supply_code", "quantity"],
    },
    # LUỒNG THỨ TƯ — không theo kỳ, mà theo ẢNH CHỤP TỒN KHO.
    # `partition` nói cho `load_flow` biết xoá-rồi-chèn theo cột nào. Ba luồng
    # trên dùng `period`; luồng này dùng `snapshot_date`, vì tồn kho không có
    # khái niệm kỳ và một ảnh chụp mới làm ảnh chụp cũ hết giá trị.
    "inventory_lot": {
        "sql_file": "inventory_lot_sta.sql",
        "table": "fact_inventory_lot",
        "partition": "snapshot_date",
        "map": {
            "snapshot_date": "__snapshot__",
            "supply_code":   "supply_code",
            "lot_id":        "lot_id",
            "lot_code":      "lot_code",
            "expiry_date":   "expiry_date",
            "co_han_dung":   "co_han_dung",
            "quantity":      "quantity",
            "so_kho":        "so_kho",
            "don_gia_mua":   "don_gia_mua",
            "don_gia_thau":  "don_gia_thau",
            "don_gia_von":   "don_gia_von",
        },
        "numeric": ["lot_id", "co_han_dung", "quantity",
                    "don_gia_mua", "don_gia_thau", "don_gia_von"],
        # CHỈ `quantity`. `lot_id` là khoá; ba cột đơn giá và `co_han_dung` là
        # thuộc tính của lô — cộng chúng lại là vô nghĩa.
        "sum": ["quantity"],
        "required": ["supply_code", "quantity"],
        # Giữ CẢ dòng lot_id = 0 (tồn không tra được lô). Lọc bỏ sẽ làm tổng
        # tồn theo lô nhỏ hơn tổng tồn thật → hiện "hụt hàng" giả.
    },
}

# Thứ tự nạp. Ba luồng theo kỳ trước, ảnh chụp tồn kho sau — thứ tự này không
# bắt buộc về mặt kỹ thuật (các luồng độc lập) nhưng giữ cho log dễ đọc.
THU_TU_NAP = ("usage_total", "cases_care_level", "usage_care_level", "inventory_lot")

RO_HOP_LE = {"NGT", "NT1", "NT2", "NT3", "NT0"}


# ─────────────────────────────────────────────────────────────────────────────
# DDL — hai bảng phân cấp có thể chưa tồn tại
# ─────────────────────────────────────────────────────────────────────────────

DDL = [
    """
    CREATE TABLE IF NOT EXISTS fact_cases_by_care_level (
        period     VARCHAR(7)  NOT NULL,
        block_code VARCHAR(20) NOT NULL,
        ro         VARCHAR(4)  NOT NULL,
        cases      INTEGER     NOT NULL,
        PRIMARY KEY (period, block_code, ro)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_usage_by_care_level (
        period      VARCHAR(7)  NOT NULL,
        block_code  VARCHAR(20) NOT NULL,
        ro          VARCHAR(4)  NOT NULL,
        supply_code VARCHAR(60) NOT NULL,
        is_vtyt     INTEGER     NOT NULL DEFAULT 0,
        quantity    FLOAT       NOT NULL,
        line_count  INTEGER,
        PRIMARY KEY (period, block_code, ro, supply_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_usage_total (
        period              VARCHAR(7)  NOT NULL,
        supply_code         VARCHAR(60) NOT NULL,
        supply_name         VARCHAR(500),
        supply_unit         VARCHAR(40),
        is_vtyt             INTEGER NOT NULL DEFAULT 0,
        so_luong_toan_vien  FLOAT   NOT NULL,
        so_luong_hohap      FLOAT   NOT NULL DEFAULT 0,
        d_baseline_thang    FLOAT,
        ty_trong_hohap      FLOAT,
        so_dong_toa         INTEGER,
        so_luot             INTEGER,
        PRIMARY KEY (period, supply_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_inventory_lot (
        snapshot_date TEXT        NOT NULL,
        supply_code   VARCHAR(60) NOT NULL,
        lot_id        INTEGER     NOT NULL DEFAULT 0,
        lot_code      VARCHAR(60),
        expiry_date   TEXT,
        co_han_dung   INTEGER     NOT NULL DEFAULT 0,
        quantity      FLOAT       NOT NULL,
        so_kho        VARCHAR(60),
        don_gia_mua   FLOAT,
        don_gia_thau  FLOAT,
        don_gia_von   FLOAT,
        PRIMARY KEY (snapshot_date, supply_code, lot_id, so_kho)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fil_supply ON fact_inventory_lot (supply_code, expiry_date)",
    "CREATE INDEX IF NOT EXISTS ix_fut_supply  ON fact_usage_total (supply_code, period)",
    "CREATE INDEX IF NOT EXISTS ix_fucl_supply ON fact_usage_by_care_level (supply_code, period)",
]


def ensure_tables(db) -> None:
    """Tạo ba bảng đích nếu chưa có. Chạy lại vô hại."""
    for stmt in DDL:
        db.execute(text(stmt))
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Tiện ích
# ─────────────────────────────────────────────────────────────────────────────

def _period_key(v: Any) -> Optional[str]:
    """Bên STA `Period` là kiểu date (ngày 01 của tháng). Đưa về 'YYYY-MM'.

    Chấp nhận cả chuỗi 'YYYY-MM-DD', 'YYYY-MM' và 'MM/YYYY' để không phụ thuộc
    driver ODBC trả kiểu gì.
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (datetime, date)):
        return f"{v.year:04d}-{v.month:02d}"
    s = str(v).strip()
    if not s:
        return None
    if "/" in s:                                  # 'MM/YYYY'
        try:
            mm, yyyy = s.split("/")
            return f"{int(yyyy):04d}-{int(mm):02d}"
        except Exception:
            return None
    s = s.replace("T", " ").split(" ")[0]         # '2026-08-01 00:00:00'
    parts = s.split("-")
    if len(parts) >= 2:
        try:
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}"
        except Exception:
            return None
    return None


def _ngay_key(v: Any) -> Optional[str]:
    """Đưa một ngày bất kỳ về chuỗi 'YYYY-MM-DD'.

    Cần vì SQLite so sánh ngày theo thứ tự chuỗi — '2026-9-1' sẽ đứng SAU
    '2026-10-01' nếu không đệm số 0, và FEFO sẽ sắp lô sai thứ tự hạn dùng.
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    if not s:
        return None
    s = s.replace("T", " ").split(" ")[0]
    if "/" in s:                                   # 'DD/MM/YYYY'
        try:
            d_, m_, y_ = s.split("/")
            return f"{int(y_):04d}-{int(m_):02d}-{int(d_):02d}"
        except Exception:
            return None
    parts = s.split("-")
    if len(parts) == 3:
        try:
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        except Exception:
            return None
    return None


def _shift(period: str, months: int) -> Optional[str]:
    try:
        y, m = period.split("-")
        total = int(y) * 12 + (int(m) - 1) + months
        return f"{total // 12:04d}-{total % 12 + 1:02d}" if total >= 0 else None
    except Exception:
        return None


_RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_RE_LINE_COMMENT = re.compile(r"--[^\n]*")


def _bo_chu_thich(sql: str) -> str:
    """Bóc chú thích /* */ và -- khỏi câu SQL TRƯỚC khi dùng.

    11/09/2026 — lỗi thật gặp ở lần Đồng bộ đầu tiên qua giao diện:
      - inventory_lot_sta.sql không có tham số, nhưng chú thích đầu file viết
        "VÌ SAO LUỒNG NÀY KHÔNG CÓ :since_date" → `":since_date" in sql` đúng →
        truyền 1 tham số cho câu có 0 dấu hỏi.
      - usage_total_sta.sql có :since_date ở WHERE VÀ trong chú thích →
        SQLAlchemy text() đổi cả hai thành `?`, pyodbc bóc chú thích rồi mới
        đếm → "1 marker, 2 parameters".
    Hai luồng còn lại chạy được chỉ vì chú thích của chúng tình cờ không nhắc
    tới tham số. Bóc chú thích ở đây là cách duy nhất để tác giả file SQL được
    tự do viết chú thích.
    """
    sql = _RE_BLOCK_COMMENT.sub(" ", sql)
    sql = _RE_LINE_COMMENT.sub(" ", sql)
    return sql.strip()


def _load_sql(filename: str) -> str:
    path = SQL_DIR / filename
    try:
        return _bo_chu_thich(path.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.error("Không đọc được câu SQL %s: %s", path, exc)
        return ""


def _watermark(db, table: str) -> Optional[str]:
    """Kỳ lớn nhất đã nạp cho bảng này."""
    try:
        r = db.execute(text(f"SELECT MAX(period) FROM {table}")).scalar()
        return r or None
    except Exception:
        return None


def _num(v, default=0.0):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        return float(v)
    except Exception:
        return default


# ─────────────────────────────────────────────────────────────────────────────
# Nạp một luồng
# ─────────────────────────────────────────────────────────────────────────────

def _fetch(connector, sql: str, since_period: Optional[str]) -> pd.DataFrame:
    """Đọc từ STA qua chính engine của SqlServerConnector.

    Dùng lại `_read()` của connector để thừa hưởng pool_pre_ping, timeout và
    đọc theo lô — thay vì mở một đường kết nối thứ hai với cấu hình khác.
    """
    if not sql.strip():
        return pd.DataFrame()
    params: Dict[str, Any] = {}
    if ":since_date" in sql:
        params["since_date"] = f"{since_period}-01" if since_period else "1900-01-01"
    return connector._read(sql, params)      # noqa: SLF001 — cùng gói, có chủ đích


def _prepare(df: pd.DataFrame, spec: Dict[str, Any]) -> pd.DataFrame:
    """Đổi tên cột theo hợp đồng local, sinh `period`, ép kiểu, loại dòng hỏng."""
    if df is None or df.empty:
        return pd.DataFrame(columns=list(spec["map"].keys()))

    df = df.copy()
    # Chuẩn hoá tên cột về chữ thường để không phụ thuộc cách driver trả về
    lower = {c.lower(): c for c in df.columns}

    out = pd.DataFrame(index=df.index)
    for local_col, src_col in spec["map"].items():
        if src_col == "__period__":
            src = lower.get("period") or lower.get("month")
            out["period"] = df[src].map(_period_key) if src else None
        elif src_col == "__snapshot__":
            # Ảnh chụp tồn kho: bên STA cột là NgaySnapshot (kiểu date).
            src = lower.get("ngaysnapshot") or lower.get("snapshot_date")
            out["snapshot_date"] = df[src].map(_ngay_key) if src else None
        else:
            src = lower.get(src_col.lower())
            out[local_col] = df[src] if src else None
    # Hạn dùng phải về chuỗi 'YYYY-MM-DD' để so sánh được bên SQLite.
    if "expiry_date" in out.columns:
        out["expiry_date"] = out["expiry_date"].map(_ngay_key)

    for c in spec["numeric"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")

    truoc = len(out)
    khoa_pv = spec.get("partition", "period")
    out = out[out[khoa_pv].notna()]
    for c in spec["required"]:
        if c in out.columns:
            out = out[out[c].notna()]
            if out[c].dtype == object:
                out = out[out[c].astype(str).str.strip() != ""]
    bo = truoc - len(out)
    if bo:
        logger.warning("%s: loại %d/%d dòng thiếu khoá hoặc thiếu giá trị bắt buộc.",
                       spec["table"], bo, truoc)

    # Rổ chăm sóc lạ → dồn về NT0 thay vì để lọt vào bảng với giá trị vô nghĩa.
    if "ro" in out.columns:
        la = ~out["ro"].astype(str).isin(RO_HOP_LE)
        if la.any():
            logger.warning("%s: %d dòng có rổ chăm sóc ngoài {NGT,NT1,NT2,NT3,NT0} "
                           "— dồn về NT0.", spec["table"], int(la.sum()))
            out.loc[la, "ro"] = "NT0"

    if "is_vtyt" in out.columns:
        out["is_vtyt"] = out["is_vtyt"].fillna(0).astype(int).clip(0, 1)

    # Khử trùng khoá: nguồn không nên có trùng, nhưng nếu có thì cộng lại còn
    # hơn để INSERT vỡ vì PRIMARY KEY giữa chừng.
    keys = [c for c in ("period", "snapshot_date", "block_code", "ro",
                        "supply_code", "lot_id", "so_kho") if c in out.columns]
    if keys and out.duplicated(subset=keys).any():
        n = int(out.duplicated(subset=keys).sum())
        logger.warning("%s: %d dòng trùng khoá từ nguồn — gộp lại.", spec["table"], n)
        # Cột được cộng = spec["sum"], trừ đi mọi cột đang làm khoá. Không lấy
        # từ spec["numeric"]: "numeric" nói KIỂU, "sum" nói CỘNG ĐƯỢC HAY KHÔNG.
        so = [c for c in spec.get("sum", []) if c in out.columns and c not in keys]
        chu = [c for c in out.columns if c not in keys + so]
        out = (out.groupby(keys, as_index=False)
                  .agg({**{c: "sum" for c in so}, **{c: "first" for c in chu}}))

    return out


def _replace_periods(db, table: str, df: pd.DataFrame, cols: Sequence[str],
                     khoa: str = "period") -> int:
    """XOÁ SẠCH các giá trị phân vùng có trong `df` rồi CHÈN LẠI. Idempotent.

    `khoa` là 'period' cho ba luồng theo kỳ, 'snapshot_date' cho luồng tồn kho
    theo lô. Nguyên tắc giống nhau: xoá đúng những lát dữ liệu vừa kéo về, giữ
    nguyên các lát khác — nên nạp tăng dần an toàn, và chạy lại mười lần cũng
    ra đúng một kết quả.
    """
    if df.empty:
        return 0
    periods = sorted(df[khoa].dropna().unique().tolist())
    for i in range(0, len(periods), 500):          # SQLite giới hạn số tham số
        lo = periods[i:i + 500]
        ph = ",".join(f":p{j}" for j in range(len(lo)))
        db.execute(text(f"DELETE FROM {table} WHERE {khoa} IN ({ph})"),
                   {f"p{j}": v for j, v in enumerate(lo)})

    cols = list(cols)
    ph = ",".join(f":{c}" for c in cols)
    stmt = text(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph})")
    recs = df[cols].where(pd.notna(df[cols]), None).to_dict("records")
    for i in range(0, len(recs), INSERT_CHUNK):
        db.execute(stmt, recs[i:i + INSERT_CHUNK])
    return len(recs)


def load_flow(db, connector, flow: str, full: bool = False) -> Dict[str, Any]:
    spec = FLOWS[flow]
    sql = _load_sql(spec["sql_file"])
    if not sql:
        return {"flow": flow, "status": "skipped",
                "message": f"Không có {spec['sql_file']} trong {SQL_DIR}"}

    khoa_pv = spec.get("partition", "period")

    since = None
    if khoa_pv == "period" and not full:
        wm = _watermark(db, spec["table"])
        since = _shift(wm, -LOOKBACK_MONTHS) if wm else None

    try:
        raw = _fetch(connector, sql, since)
    except Exception as exc:                          # noqa: BLE001
        msg = str(exc)
        if "Invalid column name" in msg and flow == "usage_total":
            # 11/09/2026 — dấu hiệu view vw_MedForecast_TieuHaoTong đang ở bản
            # 9 cột (Phase0_01) thay vì 12 cột (G1_01). Nói thẳng cách sửa.
            raise RuntimeError(
                "vw_MedForecast_TieuHaoTong thiếu cột — view đang ở bản cũ. "
                "Chạy lại sql_his/phase0/G1_01_STA_sua_bang.sql trên STA. "
                f"Lỗi gốc: {msg[:200]}") from exc
        raise
    df = _prepare(raw, spec)
    n = _replace_periods(db, spec["table"], df, list(spec["map"].keys()), khoa_pv)
    db.commit()

    periods = sorted(df[khoa_pv].unique().tolist()) if not df.empty else []
    logger.info("%s: nạp %d dòng cho %d kỳ (%s → %s)", spec["table"], n, len(periods),
                periods[0] if periods else "-", periods[-1] if periods else "-")
    return {
        "flow": flow, "status": "ok", "table": spec["table"],
        "rows": n, "periods": len(periods), "since": since,
        "partition": khoa_pv,
        "min_period": periods[0] if periods else None,
        "max_period": periods[-1] if periods else None,
    }


def load_all(db, connector, full: bool = False) -> Dict[str, Any]:
    """Nạp cả ba luồng. Một luồng hỏng không chặn hai luồng còn lại."""
    ensure_tables(db)
    ket_qua = []
    for flow in THU_TU_NAP:
        try:
            ket_qua.append(load_flow(db, connector, flow, full=full))
        except Exception as exc:                      # noqa: BLE001
            db.rollback()
            logger.exception("Luồng %s lỗi", flow)
            ket_qua.append({"flow": flow, "status": "failed", "message": str(exc)})
    return {"flows": ket_qua,
            "ok": sum(1 for r in ket_qua if r["status"] == "ok"),
            "failed": sum(1 for r in ket_qua if r["status"] == "failed")}
