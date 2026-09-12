"""RESPONSE CHO DASHBOARD CŨ + đếm tín hiệu tồn kho — một nguồn chân lý cho DOI.

Đặt tại: backend/app/services/dss_runner.py

Tầng 3 (dss_alerts) → các hàm `*_payload()` giữ HỢP ĐỒNG JSON cũ của
/dashboard/risk-status, /critical-alerts, /care-level, và `stock_signal()` cho
/overview, /summary. Trang Tổng quan mới dùng dss_dashboard (v2).

11/09/2026 (M12): `run_forecast_cycle` và `demand_vs_stock_payload` — vốn gọi
`topdown.py` (Ridge riêng, chưa từng có trong bảng so sánh) — đã gỡ; Tầng 1
duy nhất là `group_forecast.forecast_group_next` qua dss_dashboard. topdown.py
chuyển vào _archive/ai_engine_cu/.

ÁNH XẠ NHÃN MỚI VỀ TÊN CŨ

Giao diện cũ đọc `safe / low / critical`. Tầng 3 sinh ra bốn nhãn
`green / amber / red / grey`. Ánh xạ:

    green  → safe        DOI > 36 ngày
    amber  → low         18 < DOI ≤ 36
    red    → critical    DOI ≤ 18
    grey   → (khoá mới)  không đo được — KHÔNG dồn vào safe
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import dss_alerts, dss_demand

logger = logging.getLogger(__name__)

# Nhãn DOI → tên cũ mà giao diện đang đọc
MUC_SANG_TEN_CU = {"green": "safe", "amber": "low", "red": "critical",
                   "grey": "grey"}


# ─────────────────────────────────────────────────────────────────────────────
# Đếm tín hiệu tồn kho — MỘT nguồn chân lý cho mọi thẻ KPI
# ─────────────────────────────────────────────────────────────────────────────

def stock_signal(db: Session) -> Dict[str, Any]:
    """Đếm theo DOI, cùng khuôn với `period_service.stock_signal_counts()` cũ.

    Khác bản trong `period_service` ở hai điểm: dùng FEFO khi có dữ liệu lô, và
    tách `zero_stock` bằng chính nhãn của Tầng 3 thay vì tự đếm lại. Giữ đúng
    tên khoá cũ để `assess_overall_risk()` và các thẻ KPI không phải sửa.
    """
    trong = {"red": 0, "amber": 0, "green": 0, "grey": 0, "zero_stock": 0,
             "measured": 0, "basis": "chua_du_du_lieu"}
    try:
        al = dss_alerts.alert_rows(db)
    except Exception as exc:                                  # noqa: BLE001
        logger.warning("Không đếm được tín hiệu tồn kho: %s", exc)
        return trong
    if not al.get("san_sang"):
        return trong

    t = al["tong_hop"]
    zero = sum(1 for r in al["rows"] if (r["doi"] == 0.0))
    out = {
        "red": t.get("red", 0), "amber": t.get("amber", 0),
        "green": t.get("green", 0), "grey": t.get("grey", 0),
        "zero_stock": zero,
        "measured": t.get("do_duoc", 0),
        "basis": "doi_fefo" if t.get("fefo_toan_bo") else "doi_ton_tong",
        "nguong": t.get("nguong"),
        "nguon_ton_kho": t.get("nguon_ton_kho"),
        "ly_do_xam": t.get("ly_do_xam", {}),
    }
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Response cho từng endpoint — giữ nguyên hợp đồng JSON cũ
# ─────────────────────────────────────────────────────────────────────────────

def risk_status_payload(db: Session) -> Dict[str, Any]:
    """Thay cho vòng lặp `_stock_risk_level` trên `Inventory.safety_stock`.

    Khoá cũ giữ nguyên: `total_items`, `safe_count`/`low_count`/`critical_count`,
    ba khoá `*_percentage`, và ba danh sách `safe_items`/`low_items`/
    `critical_items`. Mỗi phần tử vẫn có `current_stock` và `safety_stock` để
    bảng cũ không vỡ cột — nhưng `safety_stock` nay là **ngưỡng tồn tương ứng
    18 ngày** (`d_daily × 18`), một con số CÓ nghĩa, thay cho cột đã đóng băng.
    """
    al = dss_alerts.alert_rows(db)
    if not al.get("san_sang"):
        return {"total_items": 0, "safe_count": 0, "low_count": 0,
                "critical_count": 0, "grey_count": 0,
                "safe_percentage": 0.0, "low_percentage": 0.0,
                "critical_percentage": 0.0, "grey_percentage": 0.0,
                "safe_items": [], "low_items": [], "critical_items": [],
                "grey_items": [], "san_sang": False,
                "ly_do": al.get("ly_do"), "canh_bao": []}

    th = dss_alerts.get_thresholds(db)
    red_days = float(th["doi_red_days"])
    gio: Dict[str, List[Dict]] = {"safe": [], "low": [], "critical": [], "grey": []}

    for r in al["rows"]:
        ten_cu = MUC_SANG_TEN_CU.get(r["muc"], "grey")
        gio[ten_cu].append({
            # ── khoá cũ ──
            "inventory_id": None,          # nay tổng hợp theo MÃ, không theo dòng kho
            "supply_id": None,
            "supply_name": r["ten"],
            "category": r["nhom"],
            "current_stock": r["s_total"],
            "safety_stock": round(r["d_daily"] * red_days, 2),
            "risk_level": ten_cu,
            # ── khoá mới ──
            "supply_code": r["supply_code"],
            "unit": r["don_vi"],
            "s_usable": r["s_usable"],
            "s_expiring": r["s_expiring"],
            "d_daily": r["d_daily"],
            "doi": r["doi"],
            "muc": r["muc"],
            "ly_do_xam": r["ly_do_xam"],
            "fefo_ap_dung": r["fefo_ap_dung"],
            "ty_trong_hohap": r["ty_trong_hohap"],
        })

    tong = len(al["rows"])
    def _pct(n: int) -> float:
        return round(100.0 * n / tong, 2) if tong else 0.0

    return {
        "total_items": tong,
        "safe_count": len(gio["safe"]),
        "low_count": len(gio["low"]),
        "critical_count": len(gio["critical"]),
        "grey_count": len(gio["grey"]),
        "safe_percentage": _pct(len(gio["safe"])),
        "low_percentage": _pct(len(gio["low"])),
        "critical_percentage": _pct(len(gio["critical"])),
        "grey_percentage": _pct(len(gio["grey"])),
        "safe_items": gio["safe"],
        "low_items": gio["low"],
        "critical_items": gio["critical"],
        "grey_items": gio["grey"],
        # ── khoá mới ──
        "san_sang": True,
        "nguong_ngay": al["tong_hop"]["nguong"],
        "co_so": "DOI = S_usable / d_daily · Đỏ ≤ 18 · Vàng ≤ 36 · Xanh > 36 ngày",
        "nguon_ton_kho": al["tong_hop"].get("nguon_ton_kho"),
        "canh_bao": al.get("canh_bao", []),
    }


def critical_alerts_payload(db: Session, limit: int = 10) -> Dict[str, Any]:
    """Danh sách mã nguy cấp. CHỈ ĐỌC — không ghi gì vào bảng `alerts`.

    Bản cũ gọi `_sync_alerts_with_inventory()` rồi mới đọc, tức là một endpoint
    GET có tác dụng phụ ghi dữ liệu. Đó chính là lỗi đã đóng sạch 47 cảnh báo.
    Ở đây danh sách được TÍNH mỗi lần gọi từ DOI, không lưu trạng thái, nên
    không có gì để mà đóng sai.

    Chỉ trả mã Đỏ và Vàng — Xám không phải "sắp hết", nó là "chưa đo được".
    """
    al = dss_alerts.alert_rows(db)
    if not al.get("san_sang"):
        return {"alerts": [], "total_returned": 0, "limit": limit,
                "severity_summary": {"critical": 0, "high": 0, "medium": 0},
                "san_sang": False, "ly_do": al.get("ly_do")}

    items: List[Dict] = []
    for r in al["rows"]:
        if r["muc"] not in ("red", "amber"):
            continue
        # critical = hết hàng thật hoặc dưới 1/3 ngưỡng đỏ; high = còn lại của đỏ.
        if r["muc"] == "red":
            sev = "critical" if (r["doi"] or 0) <= 6 else "high"
        else:
            sev = "medium"
        items.append({
            # ── khoá cũ ──
            "id": r["supply_code"],
            "supply_id": None,
            "supply_name": r["ten"],
            "alert_type": "low_stock",
            "severity": sev,
            "current_stock": r["s_usable"],
            "required_stock": r["d_forecast"] if r["d_forecast"] is not None
                              else round(r["d_daily"] * 18, 2),
            "shortage_date": None,
            "message": (f"DOI {r['doi']} ngày · cần thêm {r['delta_need']} {r['don_vi'] or ''}"
                        if r["delta_need"] is not None
                        else f"DOI {r['doi']} ngày"),
            "is_resolved": False,
            "created_at": None,
            # ── khoá mới ──
            "supply_code": r["supply_code"],
            "unit": r["don_vi"],
            "doi": r["doi"],
            "muc": r["muc"],
            "s_usable": r["s_usable"],
            "s_expiring": r["s_expiring"],
            "d_forecast": r["d_forecast"],
            "delta_need": r["delta_need"],
            "fefo_ap_dung": r["fefo_ap_dung"],
        })

    thu_tu = {"critical": 0, "high": 1, "medium": 2}
    items.sort(key=lambda x: (thu_tu.get(x["severity"], 9),
                              x["doi"] if x["doi"] is not None else 10 ** 9))

    dem = {"critical": 0, "high": 0, "medium": 0}
    for it in items:
        dem[it["severity"]] = dem.get(it["severity"], 0) + 1

    return {
        "alerts": items[:limit],
        "total_returned": min(limit, len(items)),
        "limit": limit,
        "severity_summary": dem,
        # ── khoá mới ──
        "total_matched": len(items),
        "san_sang": True,
        "co_so": "DOI ≤ 18 ngày (Đỏ) và ≤ 36 ngày (Vàng)",
        "chi_doc": True,
        "canh_bao": al.get("canh_bao", []),
    }


def care_level_payload(db: Session) -> Dict[str, Any]:
    """Tỷ trọng phân cấp chăm sóc p̂(g,c) cho biểu đồ Tầng 2.

    Trả kèm `chan_doan_dinh_muc` để giao diện nói được sự thật: nhóm nào
    thiếu định mức thực nghiệm, rổ nào phải dùng định mức gộp vì mẫu nhỏ.
    """
    shares = dss_demand.care_level_shares(db)
    cua_so = {}
    if dss_alerts._has(db, "v_care_level_share"):
        r = db.execute(text("SELECT MIN(tu_ky) AS tu, MAX(den_ky) AS den, "
                            "MAX(so_ky) AS so_ky FROM v_care_level_share")).first()
        if r:
            cua_so = {"tu_ky": r.tu, "den_ky": r.den, "so_ky": r.so_ky}
    return {
        "shares": [{"block_code": g, "ro": ro, "share_pct": round(p * 100, 2)}
                   for g, d in shares.items() for ro, p in sorted(d.items())],
        "cua_so": cua_so,
        "ten_ro": dss_demand.RO_LABEL,
        "chan_doan_dinh_muc": dss_demand.chan_doan_dinh_muc(db),
        "ghi_chu": ("p̂(g,c) tính trên cửa sổ trượt 12 kỳ từ 2025-04 (Đ11: đứt gãy "
                    "chế độ ghi nhận đầu 2025), rổ mẫu nhỏ đã co ngót."),
    }
