"""VÒNG KHÉP KÍN: DỰ BÁO → NHU CẦU → CẢNH BÁO, VÀ CÁC RESPONSE CHO DASHBOARD.

Đặt tại: backend/app/services/dss_runner.py

    topdown.forecast()          Ŷ_tổng → Ŷ_g          (Tầng 1)
        → dss_demand            Ŷ_g → Ŷ_g,c → D_i     (Tầng 2)
            → dss_alerts        D_i, S_usable → DOI   (Tầng 3)

=============================================================================
VÌ SAO CẦN MODULE NÀY

Ba module tầng đều thuần chức năng, nhưng chúng nói hai "thứ tiếng" khác nhau:
`topdown` mở kết nối sqlite3 chỉ-đọc bằng đường dẫn file, còn `dss_demand` và
`dss_alerts` nhận một `Session` của SQLAlchemy. Chỗ nối phải nằm ở đâu đó —
đặt trong endpoint thì mỗi endpoint lại nối một kiểu.

Quan trọng hơn: các hàm `*_payload()` ở dưới giữ nguyên HỢP ĐỒNG JSON cũ của
dashboard. Nhờ vậy `dashboard.py` chỉ còn vài dòng gọi hàm, và phần logic
chuyển đổi nằm ở đây — nơi có thể kiểm thử được mà không cần dựng cả FastAPI.

=============================================================================
ÁNH XẠ NHÃN MỚI VỀ TÊN CŨ

Giao diện hiện tại đọc `safe / low / critical`. Tầng 3 sinh ra bốn nhãn
`green / amber / red / grey`. Ánh xạ:

    green  → safe        DOI > 36 ngày
    amber  → low         18 < DOI ≤ 36
    red    → critical    DOI ≤ 18
    grey   → (khoá mới)  không đo được — KHÔNG dồn vào safe

Nhãn Xám phải có khoá riêng. Dồn nó vào `safe` là điều tệ nhất có thể làm ở
đây: hàng nghìn mã chưa có định mức sẽ hiện màu xanh và dashboard trông rất
đẹp mà hoàn toàn vô nghĩa.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import dss_alerts, dss_demand

logger = logging.getLogger(__name__)

# Nhãn DOI → tên cũ mà giao diện đang đọc
MUC_SANG_TEN_CU = {"green": "safe", "amber": "low", "red": "critical",
                   "grey": "grey"}


def _db_path(db: Session) -> str:
    """Đường dẫn file SQLite của session hiện tại.

    `topdown` cần đường dẫn file (nó tự mở kết nối chỉ-đọc riêng để chắc chắn
    không ghi gì trong lúc huấn luyện). Lấy từ chính engine đang dùng thay vì
    viết cứng, để môi trường dev và production không lệch nhau.
    """
    url = db.get_bind().url
    if url.database:
        return str(url.database)
    raise RuntimeError("Không lấy được đường dẫn DB từ session — "
                       "topdown chỉ hỗ trợ SQLite.")


# ─────────────────────────────────────────────────────────────────────────────
# BƯỚC 4 · vòng khép kín
# ─────────────────────────────────────────────────────────────────────────────

def run_forecast_cycle(db: Session,
                       horizon: int = 1,
                       save_accuracy: bool = True,
                       only_focus: bool = False) -> Dict[str, Any]:
    """Chạy trọn ba tầng, trả về mọi thứ dashboard cần.

    `horizon` là tầm dự báo dùng để tính nhu cầu. Mặc định 1 (kỳ kế tiếp kỳ đã
    chốt) vì đó là kỳ mà quyết định cấp phát nhắm vào; h=2 và h=3 vẫn được tính
    và trả về trong `du_bao` để giao diện vẽ đường dự báo.

    Một tầng hỏng KHÔNG chặn hai tầng còn lại: Tầng 3 (DOI) vẫn tính được mà
    không cần dự báo, vì mẫu số lấy từ tiêu hao 12 kỳ đã qua. Trả về `loi` để
    nơi gọi biết phần nào thiếu.
    """
    from app.forecasting import topdown

    ket: Dict[str, Any] = {"loi": [], "chay_luc": date.today().isoformat()}

    # ── Tầng 1
    du_bao_nhom: Dict[str, float] = {}
    try:
        cfg = topdown.Config(db_path=_db_path(db))
        bt = topdown.backtest(cfg)
        fc = topdown.forecast(cfg, bt)
        df = fc["du_bao"]

        ket["ky_neo"] = fc["ky_neo"]
        ket["ty_trong_nhom"] = fc["ty_trong"].to_dict("records")
        ket["du_bao"] = df.to_dict("records")
        ket["do_chinh_xac"] = topdown.summarise(bt).to_dict("records")
        ket["do_phu_khoang"] = topdown.interval_coverage(
            bt, cfg.interval_level).to_dict("records")
        ket["ghi_chu_khoang"] = fc["ghi_chu"]

        chon = df[(df["muc"] == "NHOM") & (df["h"] == horizon)]
        du_bao_nhom = {r.block_code: float(r.diem) for r in chon.itertuples()}
        tong = df[(df["muc"] == "TONG") & (df["h"] == horizon)]
        if not tong.empty:
            ket["du_bao_tong"] = {
                "period": str(tong.iloc[0]["period"]),
                "diem": float(tong.iloc[0]["diem"]),
                "lo": float(tong.iloc[0]["lo"]),
                "hi": float(tong.iloc[0]["hi"]),
                "muc_tin_cay": cfg.interval_level,
            }

        if save_accuracy:
            n = topdown.save_accuracy(
                cfg, bt, ghi_chu=f"dss_runner · h={horizon} · Tầng A Ridge, không thời tiết")
            ket["so_dong_do_chinh_xac_da_ghi"] = n
    except Exception as exc:                                  # noqa: BLE001
        logger.exception("Tầng 1 lỗi")
        ket["loi"].append(f"Tầng 1 (dự báo): {exc}")

    # ── Tầng 2
    nhu_cau: Dict[str, float] = {}
    try:
        th = dss_alerts.get_thresholds(db)
        dm = dss_demand.demand_by_supply(
            db, du_bao_nhom, horizon_days=int(th.get("horizon_days", 30)))
        nhu_cau = {r["supply_code"]: r["d_forecast"] for r in dm["rows"]}
        ket["nhu_cau"] = {
            "so_ma": dm["so_ma"],
            "horizon_days": dm["horizon_days"],
            "nhom_thieu_p_hat": dm["nhom_thieu_p_hat"],
            "nhom_thieu_dinh_muc": dm["nhom_thieu_dinh_muc"],
            "chan_doan_dinh_muc": dm["chan_doan_dinh_muc"],
        }
        ket["_rows_nhu_cau"] = dm["rows"]
    except Exception as exc:                                  # noqa: BLE001
        logger.exception("Tầng 2 lỗi")
        ket["loi"].append(f"Tầng 2 (quy đổi): {exc}")

    # ── Tầng 3
    try:
        al = dss_alerts.alert_rows(db, demand=nhu_cau, only_focus=only_focus)
        ket["canh_bao"] = al
    except Exception as exc:                                  # noqa: BLE001
        logger.exception("Tầng 3 lỗi")
        ket["loi"].append(f"Tầng 3 (DOI): {exc}")

    return ket


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


def demand_vs_stock_payload(db: Session, top_n: int = 5,
                            only_focus: bool = True) -> List[Dict[str, Any]]:
    """Top N mã có nhu cầu dự báo cao nhất, kèm tồn hữu dụng.

    Đây là chỗ ba tầng gặp nhau. Mặc định giới hạn ở TẬP TRỌNG TÂM (~555 mã có
    tỷ trọng hô hấp ≥ 25%): xếp hạng trên toàn danh mục thì đầu bảng sẽ toàn
    dịch truyền và thuốc bệnh mạn — đúng về số lượng nhưng không phải thứ mô
    hình dịch tễ nói được điều gì về nó.

    Khoá cũ giữ nguyên: `supply_id`, `supply_name`, `unit`, `demand`, `stock`.
    """
    chu_ky = run_forecast_cycle(db, horizon=1, save_accuracy=False,
                                only_focus=only_focus)
    al = chu_ky.get("canh_bao") or {}
    rows = al.get("rows") or []
    if not rows:
        logger.warning("demand-vs-stock rỗng. Lỗi: %s", chu_ky.get("loi"))
        return []

    co_nc = [r for r in rows if r["d_forecast"] is not None]
    co_nc.sort(key=lambda r: -(r["d_forecast"] or 0))

    out: List[Dict[str, Any]] = []
    for r in co_nc[:top_n]:
        out.append({
            # ── khoá cũ ──
            "supply_id": r["supply_code"],
            "supply_name": r["ten"],
            "unit": r["don_vi"],
            "demand": int(round(r["d_forecast"] or 0)),
            "stock": int(round(r["s_usable"])),
            # ── khoá mới ──
            "supply_code": r["supply_code"],
            "s_total": r["s_total"],
            "s_usable": r["s_usable"],
            "delta_need": r["delta_need"],
            "doi": r["doi"],
            "muc": r["muc"],
            "ty_trong_hohap": r["ty_trong_hohap"],
        })
    return out


def care_level_payload(db: Session) -> Dict[str, Any]:
    """Tỷ trọng phân cấp chăm sóc p̂(g,c) cho biểu đồ Tầng 2.

    Trả kèm `chan_doan_dinh_muc` để giao diện nói được sự thật: chừng nào định
    mức chưa phân biệt theo độ nặng thì biểu đồ này là mô tả dữ liệu, không
    phải một yếu tố làm dự báo chính xác hơn.
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
        "anh_xa_ro_do_nang": dss_demand.RO_SEVERITY,
        "chan_doan_dinh_muc": dss_demand.chan_doan_dinh_muc(db),
        "ghi_chu": ("p̂(g,c) tính trên cửa sổ trượt 12 kỳ từ 2025-04 (Đ11: đứt gãy "
                    "chế độ ghi nhận đầu 2025), rổ mẫu nhỏ đã co ngót."),
    }
