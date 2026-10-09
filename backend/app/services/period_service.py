"""Mốc thời gian, số ca và quy mô danh mục: nguồn duy nhất cho mọi KPI.
Mốc lấy từ mart kỳ đã chốt (is_complete = 1); kỳ đang mở không dùng để so sánh.
Số ca đếm ở mức nhóm qua mart (đã DISTINCT phía HIS), không cộng từ mã con.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

TOAN_QUOC = "TOAN_QUOC"


def _has(db: Session, name: str) -> bool:
    """Bảng hoặc view đã tồn tại chưa."""
    r = db.execute(text(
        "SELECT 1 FROM sqlite_master WHERE name = :n AND type IN ('table','view')"
    ), {"n": name}).first()
    return r is not None


# Mốc thời gian

def get_period_anchor(db: Session) -> Dict[str, Optional[str]]:
    """Mốc thời gian chuẩn: last_closed_period (KPI neo vào đây), prev_closed_period (mẫu số xu hướng),
    open_period (kỳ đang mở, không đưa vào so sánh).
    """
    if not _has(db, "mart_monthly_cases_by_block"):
        return {"last_closed_period": None, "prev_closed_period": None, "open_period": None}

    closed = db.execute(text(
        "SELECT DISTINCT period FROM mart_monthly_cases_by_block "
        "WHERE is_complete = 1 ORDER BY period DESC LIMIT 2"
    )).fetchall()
    open_row = db.execute(text(
        "SELECT MAX(period) FROM mart_monthly_cases_by_block WHERE is_complete = 0"
    )).first()

    return {
        "last_closed_period": closed[0][0] if len(closed) >= 1 else None,
        "prev_closed_period": closed[1][0] if len(closed) >= 2 else None,
        "open_period": open_row[0] if open_row and open_row[0] else None,
    }


def shift_period(period: Optional[str], months: int) -> Optional[str]:
    """'YYYY-MM' dịch đi `months` tháng (âm = lùi)."""
    if not period:
        return None
    try:
        y, m = str(period).split("-")
        total = int(y) * 12 + (int(m) - 1) + months
        if total < 0:
            return None
        return f"{total // 12:04d}-{total % 12 + 1:02d}"
    except Exception:
        return None


# Số ca (từ mart, region = TOAN_QUOC)

def cases_in_period(db: Session, period: Optional[str],
                    block_code: Optional[str] = None) -> int:
    """Tổng số ca một kỳ cộng qua các nhóm; một lượt mang mã ở hai nhóm có thể đếm trùng, chỉ để hiển thị."""
    if not period or not _has(db, "mart_monthly_cases_by_block"):
        return 0
    sql = ("SELECT COALESCE(SUM(cases), 0) FROM mart_monthly_cases_by_block "
           "WHERE period = :p AND region = :r")
    params: Dict[str, Any] = {"p": period, "r": TOAN_QUOC}
    if block_code:
        sql += " AND block_code = :b"
        params["b"] = block_code
    return int(db.execute(text(sql), params).scalar() or 0)


def cases_by_block(db: Session, period: Optional[str]) -> List[Dict[str, Any]]:
    """Số ca từng nhóm ICD trong một kỳ, kèm kỳ trước và xu hướng."""
    if not period or not _has(db, "mart_monthly_cases_by_block"):
        return []
    prev = shift_period(period, -1)
    rows = db.execute(text(
        """
        SELECT  b.block_code,
                MAX(b.block_name)                                     AS block_name,
                COALESCE(SUM(CASE WHEN b.period = :p THEN b.cases END), 0)    AS cases_now,
                COALESCE(SUM(CASE WHEN b.period = :q THEN b.cases END), 0)    AS cases_prev
        FROM    mart_monthly_cases_by_block b
        WHERE   b.region = :r AND b.period IN (:p, :q)
        GROUP BY b.block_code
        ORDER BY b.block_code
        """), {"p": period, "q": prev, "r": TOAN_QUOC}).fetchall()

    out = []
    for r in rows:
        now, before = int(r.cases_now), int(r.cases_prev)
        out.append({
            "block_code": r.block_code,
            "block_name": r.block_name,
            "cases_last_closed": now,
            "cases_prev": before,
            "trend_pct": round(100.0 * (now - before) / before, 1) if before > 0 else None,
        })
    return out


def case_series(db: Session, n_periods: int = 6,
                end_period: Optional[str] = None) -> List[Dict[str, Any]]:
    """Chuỗi số ca `n_periods` kỳ kết thúc ở kỳ đã chốt gần nhất, kèm `is_complete`."""
    if not _has(db, "mart_monthly_cases_by_block"):
        return []
    if end_period is None:
        end_period = get_period_anchor(db)["last_closed_period"]
    if not end_period:
        return []
    start = shift_period(end_period, -(n_periods - 1))
    rows = db.execute(text(
        """
        SELECT  period,
                SUM(cases)    AS cases,
                MIN(is_complete) AS is_complete
        FROM    mart_monthly_cases_by_block
        WHERE   region = :r AND period >= :s AND period <= :e
        GROUP BY period
        ORDER BY period
        """), {"r": TOAN_QUOC, "s": start, "e": end_period}).fetchall()
    return [{"period": r.period, "cases": int(r.cases or 0),
             "is_complete": bool(r.is_complete)} for r in rows]


def trend_pct(db: Session, period: Optional[str],
              prev_period: Optional[str]) -> float:
    """Xu hướng (%) giữa hai kỳ đã chốt; 0.0 khi không tính được."""
    now = cases_in_period(db, period)
    before = cases_in_period(db, prev_period)
    if before <= 0:
        return 0.0
    return round(100.0 * (now - before) / before, 1)


# Quy mô danh mục (mẫu số của các tỷ lệ phần trăm)

def catalogue_counts(db: Session) -> Dict[str, int]:
    """Ba mẫu số quy mô danh mục: total (toàn bộ), active (còn hoạt động), focus (tỷ trọng hô hấp ≥ 25%)."""
    out = {"total": 0, "active": 0, "focus": 0}
    if _has(db, "dim_supply"):
        out["total"] = int(db.execute(text("SELECT COUNT(*) FROM dim_supply")).scalar() or 0)
    if _has(db, "v_supply_active"):
        out["active"] = int(db.execute(text("SELECT COUNT(*) FROM v_supply_active")).scalar() or 0)
    if _has(db, "v_supply_focus"):
        out["focus"] = int(db.execute(text("SELECT COUNT(*) FROM v_supply_focus")).scalar() or 0)
    return out


# Mức cảnh báo vận hành

# Cùng thang màu với `AlertLevel` ở frontend để mỗi màu chỉ mang một nghĩa.
NHAN_MUC_CANH_BAO: Dict[str, str] = {
    "red": "NGUY CẤP",
    "amber": "CẢNH BÁO",
    "green": "AN TOÀN",
    "grey": "CHƯA ĐỦ DỮ LIỆU",
}


def danh_gia_muc_canh_bao(
    counts: Dict[str, Any],
    thresholds: Optional[Dict[str, Any]] = None,
    period: Optional[str] = None,
) -> Dict[str, Any]:
    """Mức cảnh báo vận hành từ bộ đếm DOI của Tầng 3: không mã nào đo được thì grey, có Đỏ thì red,
    có Vàng thì amber, còn lại green. `counts` nhận dict của `dss_dashboard._counts` hoặc `tong_hop` của `alert_rows`.
    """
    red = int(counts.get("red") or 0)
    amber = int(counts.get("amber") or 0)
    do_duoc = int(counts.get("measured", counts.get("do_duoc")) or 0)

    if do_duoc <= 0:
        muc = "grey"
    elif red > 0:
        muc = "red"
    elif amber > 0:
        muc = "amber"
    else:
        muc = "green"

    th = thresholds or {}
    red_days = float(th.get("red_days") or 0)
    amber_days = float(th.get("amber_days") or 0)

    if muc == "grey":
        chi_tiet = ("Không mã nào đo được DOI, thiếu định mức, dự báo kỳ tới "
                    "hoặc ảnh chụp tồn kho.")
    else:
        chi_tiet = (f"{red} mã Đỏ, {amber} mã Vàng trên {do_duoc} mã đo được "
                    f"(Đỏ ≤ {red_days:.0f} ngày, Vàng ≤ {amber_days:.0f} ngày)")

    ky = f" trên kỳ chốt {period}" if period else " trên kỳ chốt"
    return {
        "level": muc,
        "label": NHAN_MUC_CANH_BAO[muc],
        "basis": "Đánh giá theo số ngày đáp ứng kho (DOI)" + ky,
        "detail": chi_tiet,
        "red": red,
        "amber": amber,
        "measured": do_duoc,
    }
