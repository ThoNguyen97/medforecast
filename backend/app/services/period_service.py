"""Mốc thời gian, số ca và quy mô danh mục — NGUỒN DUY NHẤT cho mọi KPI.

Đặt tại: backend/app/services/period_service.py

-----------------------------------------------------------------------------
VÌ SAO CÓ FILE NÀY

Trước G1, mỗi endpoint tự quyết định "tháng hiện tại là tháng nào" và tự chọn
bảng để đếm số ca. Hai quyết định đó được lặp lại ở ba chỗ với ba cách khác
nhau, và cả ba đều sai theo cùng một kiểu:

    _latest_rec = db.query(func.max(DiseaseCase.recorded_at)).scalar()

`max(recorded_at)` rơi vào KỲ ĐANG MỞ. Tháng 9/2026 mới có 3 ca trong khi
tháng 8 có 341 ca, nên phép so sánh cho ra tăng trưởng 6500% — và con số đó
đi thẳng vào hàm đánh giá mức nguy cơ, khiến dashboard luôn báo "Cao".

Từ G1: mốc thời gian lấy từ `mart_monthly_cases_by_block` với
`is_complete = 1`, và mọi số ca đều đọc từ mart đó. Một chỗ duy nhất, một quy
tắc duy nhất.

-----------------------------------------------------------------------------
VÌ SAO ĐẾM SỐ CA Ở MỨC NHÓM CHỨ KHÔNG CỘNG TỪ MÃ

Một lượt khám mang J01 (chính) và J06 (phụ) — cả hai cùng thuộc J00-J06 — sẽ
bị đếm hai lần nếu cộng số ca các mã con. Thủ tục bên HIS đã đếm DISTINCT ở mức
nhóm và đẩy sẵn xuống; mart giữ nguyên con số đó. Vì vậy MỌI phép đếm ở đây đi
qua mart với `region = 'TOAN_QUOC'`, không bao giờ cộng từ `fact_disease_case`
hay `disease_cases`.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

TOAN_QUOC = "TOAN_QUOC"

# Ngưỡng mặc định — chỉ dùng khi system_config chưa có khoá dss.thresholds.
# Giá trị thật đến từ Đ9-C: trung vị chu kỳ nhập của 1.992 mã bổ sung đều.
DEFAULT_THRESHOLDS: Dict[str, Any] = {
    "doi_red_days": 18,
    "doi_amber_days": 36,
    "horizon_days": 30,
    "fefo_window_days": 30,
    "active_period_lookback": 3,
    "focus_min_resp_share": 25,
    "overstock_factor": 2,
    "incoming_stock_considered": False,
}


# ─────────────────────────────────────────────────────────────────────────────
# Cấu hình
# ─────────────────────────────────────────────────────────────────────────────

def get_thresholds(db: Session) -> Dict[str, Any]:
    """Đọc ngưỡng từ system_config['dss.thresholds'].

    Không có thì trả mặc định và ghi cảnh báo — KHÔNG ném lỗi, để dashboard vẫn
    lên được trên môi trường chưa chạy G1_03.
    """
    row = db.execute(text(
        "SELECT config_value FROM system_config WHERE config_key = 'dss.thresholds'"
    )).first()
    if not row or not row[0]:
        logger.warning("Chưa có system_config['dss.thresholds'] — dùng ngưỡng mặc định "
                       "18/36. Chạy G1_03_LOCAL_cau_hinh.sql để ghi ngưỡng thật.")
        return dict(DEFAULT_THRESHOLDS)
    try:
        cfg = json.loads(row[0])
    except (TypeError, ValueError):
        logger.error("system_config['dss.thresholds'] không phải JSON hợp lệ — dùng mặc định.")
        return dict(DEFAULT_THRESHOLDS)
    out = dict(DEFAULT_THRESHOLDS)
    out.update({k: v for k, v in cfg.items() if v is not None})
    return out


def _has(db: Session, name: str) -> bool:
    """Bảng hoặc view đã tồn tại chưa. Dùng để các endpoint không vỡ khi chạy
    trên DB chưa qua G1."""
    r = db.execute(text(
        "SELECT 1 FROM sqlite_master WHERE name = :n AND type IN ('table','view')"
    ), {"n": name}).first()
    return r is not None


# ─────────────────────────────────────────────────────────────────────────────
# Mốc thời gian
# ─────────────────────────────────────────────────────────────────────────────

def get_period_anchor(db: Session) -> Dict[str, Optional[str]]:
    """Mốc thời gian chuẩn của toàn hệ thống.

    last_closed_period  kỳ ĐÃ CHỐT gần nhất (is_complete = 1) — mọi KPI neo vào đây
    prev_closed_period  kỳ đã chốt liền trước — mẫu số của xu hướng
    open_period         kỳ đang mở (is_complete = 0), hiển thị riêng với nhãn
                        "chưa chốt"; KHÔNG đưa vào bất kỳ phép so sánh nào
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


# ─────────────────────────────────────────────────────────────────────────────
# Số ca — luôn từ mart, luôn region = TOAN_QUOC
# ─────────────────────────────────────────────────────────────────────────────

def cases_in_period(db: Session, period: Optional[str],
                    block_code: Optional[str] = None) -> int:
    """Tổng số ca của một kỳ. Cộng qua các NHÓM (mỗi nhóm đã đếm DISTINCT sẵn).

    Cộng qua nhóm vẫn có thể đếm trùng một lượt mang mã ở HAI nhóm khác nhau
    (ví dụ J06 + J20). Đây là lựa chọn có chủ ý: dự báo chạy theo từng nhóm, và
    tổng chỉ để hiển thị. Khi cần con số tuyệt đối, dùng `cases_by_block`.
    """
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
    """Chuỗi số ca `n_periods` kỳ, kết thúc ở kỳ đã chốt gần nhất.

    Trả cả `is_complete` để giao diện gắn nhãn "chưa chốt" thay vì vẽ một cột
    tụt xuống gần 0 mà không giải thích gì.
    """
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
    """Xu hướng giữa hai kỳ ĐÃ CHỐT. Trả 0.0 khi không tính được.

    Vì cả hai kỳ đều đã chốt, con số này không thể nhảy lên hàng nghìn phần trăm
    như bản cũ. Nếu vẫn thấy |trend| > 100 thì đó là biến động thật của dịch,
    không phải lỗi mốc thời gian.
    """
    now = cases_in_period(db, period)
    before = cases_in_period(db, prev_period)
    if before <= 0:
        return 0.0
    return round(100.0 * (now - before) / before, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Quy mô danh mục — mẫu số ĐÚNG của mọi tỷ lệ phần trăm
# ─────────────────────────────────────────────────────────────────────────────

def catalogue_counts(db: Session) -> Dict[str, int]:
    """Ba mẫu số, đừng trộn lẫn.

    total   toàn bộ danh mục (~5.041) — phần lớn là mã đã ngừng dùng
    active  còn hoạt động (~1.900)    — MẪU SỐ của mọi tỷ lệ trên dashboard
    focus   tập trọng tâm (~555)      — mã có tỷ trọng hô hấp ≥ 25%, tức tập mà
            mô hình dịch tễ thật sự lái được nhu cầu
    """
    out = {"total": 0, "active": 0, "focus": 0}
    if _has(db, "dim_supply"):
        out["total"] = int(db.execute(text("SELECT COUNT(*) FROM dim_supply")).scalar() or 0)
    if _has(db, "v_supply_active"):
        out["active"] = int(db.execute(text("SELECT COUNT(*) FROM v_supply_active")).scalar() or 0)
    if _has(db, "v_supply_focus"):
        out["focus"] = int(db.execute(text("SELECT COUNT(*) FROM v_supply_focus")).scalar() or 0)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Đếm cảnh báo tồn kho — BẢN TẠM CỦA G1
# ─────────────────────────────────────────────────────────────────────────────

def stock_signal_counts(db: Session) -> Dict[str, Any]:
    """Đếm sơ bộ theo DOI, dùng cho các thẻ KPI ở G1.

    ⚠ ĐÂY LÀ BẢN TẠM. Bản đầy đủ thuộc G4 và sẽ khác ở ba điểm:
        • tồn hữu dụng theo FEFO (loại lô hết hạn trong cửa sổ bảo vệ)
        • tách `level_reason` ba nhánh — đặc biệt là "tồn = 0 do đã ngừng dùng",
          nhóm chiếm tới 25,8% danh mục và KHÔNG phải là hàng sắp hết
        • ngưỡng riêng theo từng mã (chu kỳ nhập của chính mã đó)

    Ở G1 chỉ cần một con số trung thực để thay cho phép đếm cũ dựa trên
    `safety_stock` — cột đó nay đã bị vô hiệu hoá nên phép đếm cũ luôn trả 0.

        DOI = tồn hiện có / nhu cầu trung bình ngày (toàn viện, 12 kỳ gần nhất)

    Mã không có mẫu số (chưa có tiêu hao) → 'grey', KHÔNG phải 'green'. Nếu để
    rơi vào green thì hàng nghìn mã không có định mức sẽ hiện màu xanh và
    dashboard trông rất đẹp mà hoàn toàn vô nghĩa.
    """
    empty = {"red": 0, "amber": 0, "green": 0, "grey": 0, "zero_stock": 0,
             "measured": 0, "basis": "chua_du_du_lieu"}
    if not (_has(db, "v_supply_daily_demand") and _has(db, "inventory")
            and _has(db, "medical_supplies")):
        return empty

    th = get_thresholds(db)
    red_days = float(th["doi_red_days"])
    amber_days = float(th["doi_amber_days"])

    rows = db.execute(text(
        """
        SELECT  d.supply_code,
                d.d_daily                              AS d_daily,
                COALESCE(SUM(i.current_stock), 0)      AS stock,
                COUNT(i.id)                            AS n_inv
        FROM    v_supply_daily_demand d
        JOIN    medical_supplies m ON m.supply_code = d.supply_code
        LEFT JOIN inventory      i ON i.supply_id    = m.id
        GROUP BY d.supply_code, d.d_daily
        """)).fetchall()

    c = {"red": 0, "amber": 0, "green": 0, "grey": 0, "zero_stock": 0}
    for r in rows:
        d_daily = float(r.d_daily or 0)
        stock = float(r.stock or 0)
        if r.n_inv == 0 or d_daily <= 0:
            c["grey"] += 1
            continue
        if stock <= 0:
            # Tách riêng: phần lớn nhóm này là hàng đã ngừng dùng, không phải
            # hàng sắp hết. G4 phân biệt bằng level_reason.
            c["zero_stock"] += 1
            continue
        doi = stock / d_daily
        if doi <= red_days:
            c["red"] += 1
        elif doi <= amber_days:
            c["amber"] += 1
        else:
            c["green"] += 1

    c["measured"] = c["red"] + c["amber"] + c["green"] + c["zero_stock"]
    c["basis"] = "doi_tam_thoi_G1"
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Mức nguy cơ chung
# ─────────────────────────────────────────────────────────────────────────────

def assess_overall_risk(trend_pct_value: Optional[float],
                        red_count: int, amber_count: int) -> Dict[str, Any]:
    """Thay cho `_classify_risk` cũ trong dashboard.py.

    Hàm cũ KHÔNG sai về quy tắc — nó sai vì ĐẦU VÀO: nhận
    `predicted_trend_pct = 6500` (do so kỳ đang mở với kỳ đã chốt) nên luôn trả
    "Cao". Ở đây đầu vào là xu hướng giữa hai kỳ ĐÃ CHỐT, và ngưỡng tồn kho lấy
    từ đếm DOI thay vì từ `safety_stock` đã bị vô hiệu hoá.

    Vẫn là quy tắc do người đặt, chưa phải suy ra từ dữ liệu — nên trả kèm
    `basis` để giao diện nói rõ căn cứ. G2 sẽ thay bằng so sánh với khoảng dự
    báo, lúc đó "Cao" mới có nghĩa thống kê.
    """
    t = float(trend_pct_value or 0.0)
    if t >= 15 and red_count >= 5:
        level = "Cao"
    elif t >= 5 or red_count >= 2 or amber_count >= 20:
        level = "Trung bình"
    else:
        level = "Thấp"
    return {
        "level": level,
        "basis": (f"xu hướng {t:+.1f}% giữa hai kỳ đã chốt · "
                  f"{red_count} mã đỏ, {amber_count} mã vàng theo DOI tạm thời"),
        "is_provisional": True,
    }
