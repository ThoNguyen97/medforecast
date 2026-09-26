"""Nạp bốn luồng DSS từ view STA về DB local (ba luồng theo kỳ, một ảnh chụp tồn kho theo lô).

Mỗi luồng một transaction riêng, ghi kiểu xoá-rồi-chèn theo khoá phân vùng nên idempotent
và dòng bị huỷ bên nguồn cũng biến mất bên local.
"""
from __future__ import annotations

import logging
import re
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).parent / "sql"

# Số kỳ lùi khi nạp tăng dần, bắt toa huỷ muộn sau chốt tháng.
LOOKBACK_MONTHS = int(os.environ.get("DSS_LOOKBACK_MONTHS", "3"))
INSERT_CHUNK = 1000


# ── Đặc tả các luồng ──
FLOWS: Dict[str, Dict[str, Any]] = {
    "usage_total": {
        "sql_file": "usage_total_sta.sql",
        "table": "fact_usage_total",
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
        # Chỉ cột cộng được; d_baseline_thang, ty_trong_hohap là dẫn xuất.
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
    # `partition` đổi khoá xoá-rồi-chèn từ `period` sang `snapshot_date`.
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
        "sum": ["quantity"],
        # Giữ dòng lot_id = 0 (tồn không tra được lô), bỏ thì sinh cảnh báo thiếu hụt giả.
        "required": ["supply_code", "quantity"],
    },
}

# Các luồng độc lập, thứ tự chỉ để log dễ đọc.
THU_TU_NAP = ("usage_total", "cases_care_level", "usage_care_level", "inventory_lot")

RO_HOP_LE = {"NGT", "NT1", "NT2", "NT3", "NT0"}


# ── DDL: bốn bảng fact nằm ngoài Base.metadata ──
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
    """Tạo bốn bảng đích và index nếu chưa có."""
    for stmt in DDL:
        db.execute(text(stmt))
    db.commit()


# ── Tiện ích ──
def _period_key(v: Any) -> Optional[str]:
    """Đưa date hoặc chuỗi 'YYYY-MM-DD' / 'YYYY-MM' / 'MM/YYYY' về 'YYYY-MM'."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (datetime, date)):
        return f"{v.year:04d}-{v.month:02d}"
    s = str(v).strip()
    if not s:
        return None
    if "/" in s:
        try:
            mm, yyyy = s.split("/")
            return f"{int(yyyy):04d}-{int(mm):02d}"
        except Exception:
            return None
    s = s.replace("T", " ").split(" ")[0]
    parts = s.split("-")
    if len(parts) >= 2:
        try:
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}"
        except Exception:
            return None
    return None


def _ngay_key(v: Any) -> Optional[str]:
    """Đưa ngày bất kỳ về 'YYYY-MM-DD' có đệm số 0, vì SQLite so sánh ngày theo chuỗi."""
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
    if "/" in s:
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
    """Bóc chú thích /* */ và -- khỏi câu SQL, tránh text() coi `:ten` trong chú thích là tham số."""
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


# ── Nạp một luồng ──
def _fetch(connector, sql: str, since_period: Optional[str]) -> pd.DataFrame:
    """Đọc từ STA qua `_read()` của connector để dùng chung engine, timeout và đọc theo lô."""
    if not sql.strip():
        return pd.DataFrame()
    params: Dict[str, Any] = {}
    if ":since_date" in sql:
        params["since_date"] = f"{since_period}-01" if since_period else "1900-01-01"
    return connector._read(sql, params)      # noqa: SLF001


def _prepare(df: pd.DataFrame, spec: Dict[str, Any]) -> pd.DataFrame:
    """Đổi tên cột theo hợp đồng local, sinh `period`, ép kiểu, loại dòng hỏng."""
    if df is None or df.empty:
        return pd.DataFrame(columns=list(spec["map"].keys()))

    df = df.copy()
    # Tên cột về chữ thường vì driver trả về không nhất quán.
    lower = {c.lower(): c for c in df.columns}

    out = pd.DataFrame(index=df.index)
    for local_col, src_col in spec["map"].items():
        if src_col == "__period__":
            src = lower.get("period") or lower.get("month")
            out["period"] = df[src].map(_period_key) if src else None
        elif src_col == "__snapshot__":
            src = lower.get("ngaysnapshot") or lower.get("snapshot_date")
            out["snapshot_date"] = df[src].map(_ngay_key) if src else None
        else:
            src = lower.get(src_col.lower())
            out[local_col] = df[src] if src else None
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

    # Rổ chăm sóc ngoài danh mục dồn về NT0.
    if "ro" in out.columns:
        la = ~out["ro"].astype(str).isin(RO_HOP_LE)
        if la.any():
            logger.warning("%s: %d dòng có rổ chăm sóc ngoài {NGT,NT1,NT2,NT3,NT0} "
                           "— dồn về NT0.", spec["table"], int(la.sum()))
            out.loc[la, "ro"] = "NT0"

    if "is_vtyt" in out.columns:
        out["is_vtyt"] = out["is_vtyt"].fillna(0).astype(int).clip(0, 1)

    # Gộp dòng trùng khoá thay vì để INSERT vi phạm PRIMARY KEY giữa chừng.
    keys = [c for c in ("period", "snapshot_date", "block_code", "ro",
                        "supply_code", "lot_id", "so_kho") if c in out.columns]
    if keys and out.duplicated(subset=keys).any():
        n = int(out.duplicated(subset=keys).sum())
        logger.warning("%s: %d dòng trùng khoá từ nguồn — gộp lại.", spec["table"], n)
        so = [c for c in spec.get("sum", []) if c in out.columns and c not in keys]
        chu = [c for c in out.columns if c not in keys + so]
        out = (out.groupby(keys, as_index=False)
                  .agg({**{c: "sum" for c in so}, **{c: "first" for c in chu}}))

    return out


def _replace_periods(db, table: str, df: pd.DataFrame, cols: Sequence[str],
                     khoa: str = "period") -> int:
    """Xoá các phân vùng `khoa` có trong `df` rồi chèn lại; phân vùng khác giữ nguyên."""
    if df.empty:
        return 0
    periods = sorted(df[khoa].dropna().unique().tolist())
    for i in range(0, len(periods), 500):          # giới hạn số tham số của SQLite
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
            raise RuntimeError(
                "vw_MedForecast_TieuHaoTong thiếu cột. "
                "Chạy lại sql_his/sta/03_bang_tieu_hao_tong.sql trên STA. "
                f"Lỗi gốc: {msg[:200]}") from exc
        raise
    df = _prepare(raw, spec)
    # Một giao dịch: INSERT lỗi thì rollback, không để lát dữ liệu trống.
    try:
        n = _replace_periods(db, spec["table"], df, list(spec["map"].keys()), khoa_pv)
        db.commit()
    except Exception:
        db.rollback()
        raise

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
    """Nạp bốn luồng; luồng lỗi không chặn luồng khác, lỗi trả trong `flows[i].message`."""
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
