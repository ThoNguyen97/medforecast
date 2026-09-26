"""Tầng 3: tồn hữu dụng FEFO, số ngày đáp ứng (DOI) và cảnh báo bốn màu.
d_eff = D_i / horizon_days; S_usable = Σ_b clamp(d_eff·ngày_còn_hạn_b − C_{b−1}, 0, q_b)
DOI = S_usable / d_eff; Đỏ ≤ 18 ngày (trung vị chu kỳ nhập), Vàng ≤ 36, Xanh > 36, Xám không đo được
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

THRESHOLDS_DEFAULT: Dict[str, Any] = {
    "doi_red_days": 18,          # trung vị chu kỳ nhập
    "doi_amber_days": 36,        # hai chu kỳ
    "horizon_days": 30,
    "fefo_window_days": 30,      # chỉ để thống kê s_expiring, không đổi s_usable
}

# Lý do màu Xám; phải khớp union type `GreyReason` ở dashboardV2.ts.
GREY_NO_NORM = "no_norm"
GREY_NO_FORECAST = "no_forecast"
GREY_NO_STOCK_DATA = "no_stock_data"
GREY_PERIOD_NOT_CLOSED = "period_not_closed"


def _has(db: Session, name: str) -> bool:
    return bool(db.execute(
        text("SELECT 1 FROM sqlite_master WHERE name = :n LIMIT 1"),
        {"n": name}).first())


def get_thresholds(db: Session) -> Dict[str, Any]:
    out = dict(THRESHOLDS_DEFAULT)
    r = db.execute(text("SELECT config_value FROM system_config "
                        "WHERE config_key = 'dss.thresholds'")).scalar()
    if r:
        try:
            out.update(json.loads(r))
        except Exception:                                 # noqa: BLE001
            logger.warning("dss.thresholds không phải JSON hợp lệ — dùng mặc định.")
    return out


def _parse_date(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:len(f) + 2].strip(), f).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "")).date()
    except Exception:                                     # noqa: BLE001
        return None


# ── Tồn hữu dụng theo FEFO ──

def usable_stock_fefo(lots: List[Tuple[float, Optional[date]]],
                      d_daily: float,   # tốc độ tiêu thụ/ngày — nơi gọi truyền d_eff
                      hom_nay: Optional[date] = None,
                      fefo_window_days: int = 30) -> Dict[str, Any]:
    """Tồn hữu dụng theo FEFO: sắp lô theo hạn dùng, u_b = clamp(d_daily·ngày_còn_hạn_b − C_{b−1}, 0, q_b).
    Lô không có hạn dùng được coi là hữu dụng toàn bộ; trả kèm `so_lo_khong_han`.
    """
    hom_nay = hom_nay or date.today()
    tong_ton = float(sum(max(0.0, q) for q, _ in lots))
    so_lo_khong_han = sum(1 for _, e in lots if e is None)

    if d_daily <= 0:
        # Không có mẫu số thì trả tồn thô, nơi gọi gán Xám.
        return {"s_usable": tong_ton, "s_total": tong_ton, "s_expiring": 0.0,
                "fefo_ap_dung": False, "so_lo": len(lots),
                "so_lo_khong_han": so_lo_khong_han}

    if so_lo_khong_han == len(lots):
        return {"s_usable": tong_ton, "s_total": tong_ton, "s_expiring": 0.0,
                "fefo_ap_dung": False, "so_lo": len(lots),
                "so_lo_khong_han": so_lo_khong_han}

    XA = 10 ** 6
    sap = sorted(((float(max(0.0, q)),
                   (e - hom_nay).days if e else XA) for q, e in lots),
                 key=lambda x: x[1])

    C = 0.0
    het_han_som = 0.0
    for q, ngay in sap:
        if q <= 0:
            continue
        if ngay <= 0:                                # đã hết hạn
            het_han_som += q
            continue
        D_e = d_daily * float(ngay)
        u = min(q, max(0.0, D_e - C))
        C += u
        if ngay <= fefo_window_days:
            het_han_som += (q - u)

    return {"s_usable": round(C, 3), "s_total": round(tong_ton, 3),
            "s_expiring": round(het_han_som, 3), "fefo_ap_dung": True,
            "so_lo": len(lots), "so_lo_khong_han": so_lo_khong_han}


def _lots_by_code(db: Session) -> Tuple[Dict[str, List[Tuple[float, Optional[date]]]], str]:
    """Tồn kho theo lô cho mọi mã, trả (bảng lô, tên nguồn).
    Ưu tiên ảnh chụp mới nhất của `fact_inventory_lot` (có hạn dùng), lùi về `inventory`.
    """
    out: Dict[str, List[Tuple[float, Optional[date]]]] = {}

    if _has(db, "fact_inventory_lot"):
        moi_nhat = db.execute(text(
            "SELECT MAX(snapshot_date) FROM fact_inventory_lot")).scalar()
        if moi_nhat:
            rows = db.execute(text(
                "SELECT supply_code AS code, quantity AS q, expiry_date AS e, "
                "       co_han_dung AS ch "
                "FROM   fact_inventory_lot WHERE snapshot_date = :d"),
                {"d": moi_nhat}).fetchall()
            for r in rows:
                # `co_han_dung = 0`: HIS không tra được lô, bỏ qua `expiry_date`.
                han = _parse_date(r.e) if int(r.ch or 0) == 1 else None
                out.setdefault(r.code, []).append((float(r.q or 0), han))
            if out:
                return out, f"fact_inventory_lot@{moi_nhat}"

    if _has(db, "inventory") and _has(db, "medical_supplies"):
        rows = db.execute(text(
            "SELECT m.supply_code AS code, i.current_stock AS q, "
            "       i.expiry_date AS e "
            "FROM   inventory i JOIN medical_supplies m ON m.id = i.supply_id")).fetchall()
        for r in rows:
            out.setdefault(r.code, []).append((float(r.q or 0), _parse_date(r.e)))
        return out, "inventory"

    return out, "khong_co"


# ── Gán nhãn ──

def classify(doi: Optional[float], red_days: float, amber_days: float) -> str:
    if doi is None:
        return "grey"
    if doi <= red_days:
        return "red"
    if doi <= amber_days:
        return "amber"
    return "green"


# ── Bảng cảnh báo ──

def ngay_neo(db: Session) -> Tuple[date, str]:
    """Ngày "hôm nay" cho FEFO, trả (ngày, nguồn): ảnh chụp lô mới nhất, rồi cuối kỳ đã chốt, rồi date.today().
    Neo vào dữ liệu để số lô hết hạn không tăng giả tạo theo đồng hồ hệ thống.
    """
    if _has(db, "fact_inventory_lot"):
        v = db.execute(text("SELECT MAX(snapshot_date) FROM fact_inventory_lot")).scalar()
        d = _parse_date(v) if v else None
        if d:
            return d, f"snapshot:{d.isoformat()}"
    try:
        from app.services.period_service import get_period_anchor
        ky = (get_period_anchor(db) or {}).get("last_closed_period")
        if ky:
            y, m = int(ky[:4]), int(ky[5:7])
            d = (date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)) - timedelta(days=1)
            return d, f"closed_period:{ky}"
    except Exception:  # noqa: BLE001 — fallback, không được làm hỏng cảnh báo
        pass
    return date.today(), "today"


def alert_rows(db: Session,
               demand: Optional[Dict[str, float]] = None,
               only_focus: bool = False,
               hom_nay: Optional[date] = None) -> Dict[str, Any]:
    """Một dòng cho mỗi mã thuốc: S_usable, D_forecast, DOI, nhãn màu.
    `demand` là {supply_code: nhu cầu trong horizon_days} từ `dss_demand.demand_by_supply()`,
    mẫu số duy nhất của DOI; mã không có D_i nhận Xám `no_forecast`.
    """
    th = get_thresholds(db)
    red_days = float(th["doi_red_days"])
    amber_days = float(th["doi_amber_days"])
    horizon = int(th.get("horizon_days", 30))
    fefo_win = int(th.get("fefo_window_days", 30))
    if hom_nay is None:
        hom_nay, nguon_ngay = ngay_neo(db)
    else:
        nguon_ngay = "param"

    co_ton = _has(db, "fact_inventory_lot") or _has(db, "inventory")
    if not (_has(db, "v_supply_daily_demand") and co_ton
            and _has(db, "medical_supplies")):
        return {"rows": [], "tong_hop": {}, "san_sang": False,
                "ly_do": ("Thiếu v_supply_daily_demand, medical_supplies, hoặc cả "
                          "fact_inventory_lot và inventory.")}

    loc_focus = ""
    if only_focus and _has(db, "v_supply_focus"):
        loc_focus = "AND d.supply_code IN (SELECT supply_code FROM v_supply_focus)"

    rows = db.execute(text(f"""
        SELECT  d.supply_code                       AS supply_code,
                MAX(m.ten_hoat_chat)                AS ten,
                MAX(m.unit)                         AS don_vi,
                MAX(m.group_name)                   AS nhom,
                MAX(m.category)                     AS danh_muc,
                MAX(d.d_daily)                      AS d_daily,
                MAX(d.d_daily_hohap)                AS d_daily_hohap,
                MAX(d.ty_trong_hohap)               AS ty_trong_hohap,
                COUNT(i.id)                         AS so_dong_ton
        FROM    v_supply_daily_demand d
        JOIN    medical_supplies      m ON m.supply_code = d.supply_code
        LEFT JOIN inventory           i ON i.supply_id   = m.id
        WHERE   1 = 1 {loc_focus}
        GROUP BY d.supply_code
    """)).fetchall()

    lots_by_code, nguon_ton = _lots_by_code(db)

    demand = demand or {}
    out: List[Dict[str, Any]] = []
    dem = {"red": 0, "amber": 0, "green": 0, "grey": 0}
    ly_do_xam: Dict[str, int] = {}
    fefo_that = 0
    for r in rows:
        code = r.supply_code
        lots = lots_by_code.get(code, [])
        d_daily = float(r.d_daily or 0)
        d_forecast = demand.get(code)

        # Mẫu số duy nhất là nhu cầu dự báo mỗi ngày; không có D_i → Xám.
        d_eff = (float(d_forecast) / float(horizon)
                 if d_forecast is not None and float(d_forecast) > 0 and horizon > 0
                 else 0.0)

        st = usable_stock_fefo(lots, d_eff, hom_nay, fefo_win)
        if st["fefo_ap_dung"]:
            fefo_that += 1
        s_usable = float(st["s_usable"])

        doi: Optional[float] = None
        ly_do: Optional[str] = None

        if not lots:
            ly_do = GREY_NO_STOCK_DATA
        elif d_eff <= 0:
            # Không xuất trong 12 kỳ → no_norm; còn xuất mà chưa có D_i → no_forecast.
            ly_do = GREY_NO_NORM if d_daily <= 0 else GREY_NO_FORECAST
        elif s_usable <= 0:
            # Tồn 0 và có nhu cầu → Đỏ.
            doi = 0.0
        else:
            doi = s_usable / d_eff

        muc = classify(doi, red_days, amber_days)
        if muc == "grey":
            ly_do = ly_do or GREY_NO_FORECAST
            ly_do_xam[ly_do] = ly_do_xam.get(ly_do, 0) + 1
        dem[muc] += 1

        delta = (round(max(0.0, float(d_forecast) - s_usable), 3)
                 if d_forecast is not None else None)

        out.append({
            "supply_code": code, "ten": r.ten, "don_vi": r.don_vi, "nhom": r.nhom,
            "danh_muc": r.danh_muc or "Khác",
            "s_total": st["s_total"], "s_usable": s_usable,
            "s_expiring": st["s_expiring"],
            "fefo_ap_dung": st["fefo_ap_dung"],
            "nguon_ton_kho": nguon_ton,
            "so_lo": st["so_lo"], "so_lo_khong_han": st["so_lo_khong_han"],
            "d_daily": round(d_daily, 4),
            "d_eff": round(d_eff, 4),
            "d_forecast": (round(float(d_forecast), 3)
                           if d_forecast is not None else None),
            "delta_need": delta,
            "doi": (round(doi, 1) if doi is not None else None),
            "het_hang": bool(lots) and s_usable <= 0 and d_eff > 0,
            "muc": muc, "ly_do_xam": ly_do,
            "ty_trong_hohap": r.ty_trong_hohap,
        })

    out.sort(key=lambda x: (x["doi"] if x["doi"] is not None else 10 ** 9))
    do_dat = dem["red"] + dem["amber"] + dem["green"]
    return {
        "rows": out,
        "tong_hop": {
            **dem,
            "do_duoc": do_dat,
            "tong_ma": len(out),
            "nguong": {"red_days": red_days, "amber_days": amber_days},
            "horizon_days": horizon,
            "co_nhu_cau_du_bao": bool(demand),
            "nguon_ton_kho": nguon_ton,
            "as_of": hom_nay.isoformat(),
            "as_of_nguon": nguon_ngay,
            "so_ma_ap_dung_fefo": fefo_that,
            "fefo_toan_bo": fefo_that == len(out) and len(out) > 0,
            "ly_do_xam": ly_do_xam,
        },
        "san_sang": True,
        "canh_bao": _canh_bao(len(out), fefo_that, bool(demand), dem, nguon_ton),
    }


def _canh_bao(tong: int, fefo_that: int, co_demand: bool,
              dem: Dict[str, int], nguon_ton: str = "") -> List[str]:
    cb: List[str] = []
    if tong == 0:
        cb.append("Không có mã nào có mẫu số — fact_usage_total chưa được nạp.")
        return cb
    if fefo_that == 0:
        cb.append(f"CHƯA áp được FEFO cho mã nào (nguồn tồn kho: {nguon_ton or 'không rõ'}) "
                  "— không có hạn dùng nào đọc được. S_usable đang bằng tồn hiện có. "
                  "Bấm «Nạp dữ liệu DW» ở trang Dữ liệu bệnh.")
    elif fefo_that < tong:
        khong_ton = dem.get("grey", 0)
        khong_han = tong - fefo_that - khong_ton
        msg = f"{fefo_that}/{tong} mã có lô tồn kèm hạn dùng (đã áp FEFO)"
        if khong_ton:
            msg += f"; {khong_ton} mã không có dòng tồn kho → Xám"
        if khong_han > 0:
            msg += f"; {khong_han} mã có tồn nhưng lô không có hạn dùng (S_usable = tồn hiện có)"
        cb.append(msg + ".")
    if not co_demand:
        cb.append("Chưa có nhu cầu dự báo kỳ tới (Tầng 2): không có mẫu số nên "
                  "toàn bộ mã về màu Xám, cột nhu cầu và thiếu hụt để trống. "
                  "Ghi nhận dự báo ở trang Phân tích để đo lại.")
    if dem["grey"] > 0.5 * tong:
        cb.append(f"{dem['grey']}/{tong} mã màu Xám — phần lớn danh mục chưa "
                  f"đo được, đừng đọc các tỷ lệ % như thể đại diện cả kho.")
    return cb
