"""
Dashboard API endpoints.

Provides aggregated metrics for the MedForecast AI dashboard, including
overview KPIs, supply/demand time-series data, risk status breakdown, and
critical alerts.

All responses are cached in Redis for 5 minutes (CACHE_TTL = 300 seconds).
If Redis is unavailable the endpoints fall back to live database queries
without raising an error.

Routes
------
GET /api/v1/dashboard/overview        – KPI summary (totals, risk counts)
GET /api/v1/dashboard/risk-status     – Safe / low / critical stock counts
GET /api/v1/dashboard/critical-alerts – Top unresolved critical alerts
GET /api/v1/dashboard/v2              – Toàn bộ màn hình Tổng quan (Tuần 3, DSS)
GET /api/v1/dashboard/v2/forecast     – Ŷ_g ba khối + khoảng (cache theo dấu vân tay)
"""

import json
import logging
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.alert import Alert
from app.models.disease_forecast import DiseaseForecast
from app.models.inventory import Inventory
from app.models.medical_supply import MedicalSupply
from app.models.user import User
from app.services import dss_dashboard, dss_runner, period_service as ps

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])

# ── Redis caching ─────────────────────────────────────────────────────────────

CACHE_TTL = 300  # 5 minutes
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_redis_client: Optional[Any] = None


def _get_redis() -> Optional[Any]:
    """
    Return a Redis client, or None if Redis is unavailable.

    Connection is attempted once; subsequent calls reuse the cached client.
    A failed connection (Redis not running) is swallowed so the API still works.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis  # type: ignore

        client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        client.ping()  # validate connectivity
        _redis_client = client
        logger.info("Redis connected for dashboard caching.")
    except Exception as exc:
        logger.warning("Redis unavailable – dashboard caching disabled. Reason: %s", exc)
        _redis_client = None
    return _redis_client


def _cache_get(key: str) -> Optional[Any]:
    """Return cached value for *key*, or None on cache miss / Redis unavailable."""
    client = _get_redis()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.debug("Cache GET failed for key=%s: %s", key, exc)
        return None


def _cache_set(key: str, value: Any) -> None:
    """Store *value* under *key* with CACHE_TTL expiry.  Silently fails if Redis is down."""
    client = _get_redis()
    if client is None:
        return
    try:
        client.setex(key, CACHE_TTL, json.dumps(value, default=str))
    except Exception as exc:
        logger.debug("Cache SET failed for key=%s: %s", key, exc)


def invalidate_dashboard_cache() -> None:
    """Xoá toàn bộ cache dashboard:* — gọi sau khi data thay đổi (forecast,
    recommendation, alert) để dashboard phản ánh ngay thay vì chờ TTL 5 phút.
    Silently fails nếu Redis không sẵn.
    """
    client = _get_redis()
    if client is None:
        return
    try:
        keys = client.keys("dashboard:*")
        if keys:
            client.delete(*keys)
            logger.info("Invalidated %d dashboard cache keys", len(keys))
    except Exception as exc:
        logger.debug("Cache invalidate failed: %s", exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

# ── GỠ Ở G2 ──────────────────────────────────────────────────────────────────
#
# Ba hàm đã bị xoá khỏi đây:
#
#   _stock_risk_level(current_stock, safety_stock)
#   _severity_from_shortage(current_stock, safety_stock)
#   _sync_alerts_with_inventory(db)
#
# Cả ba so `current_stock` với `Inventory.safety_stock`. G0 đã cắt đoạn ghi
# ngược cột đó, và 5.007/5.041 dòng inventory có safety_stock = 0 — nên điều
# kiện `current_stock >= safety_stock` luôn đúng.
#
# Hàm thứ ba là nghiêm trọng nhất: nó GỌI db.commit() trên mỗi request GET và
# đặt alert.is_resolved = True. Hậu quả đã xảy ra: 47/47 cảnh báo bị đóng, 0
# còn mở. Một endpoint đọc dữ liệu không được phép ghi dữ liệu.
#
# Thay thế: phân mức theo DOI = S_usable / d_daily với ngưỡng thực nghiệm
# 18/36 ngày (Đ9: trung vị chu kỳ nhập 18 ngày), tính trong dss_alerts và
# chuyển về hợp đồng JSON cũ trong dss_runner. Không lưu trạng thái, nên
# không có gì để đóng sai.
# ─────────────────────────────────────────────────────────────────────────────


def _enrich_alert(alert: Alert) -> Dict:
    """Serialize an Alert ORM object to a plain dict for JSON serialisation.

    Hiện tại không còn endpoint nào dùng (critical-alerts đã chuyển sang
    đọc thẳng từ Inventory). Giữ lại helper để có thể tái dùng.
    """
    return {
        "id": alert.id,
        "supply_id": alert.supply_id,
        "supply_name": alert.supply.name if alert.supply else None,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "current_stock": alert.current_stock,
        "required_stock": alert.required_stock,
        "shortage_date": str(alert.shortage_date) if alert.shortage_date else None,
        "message": alert.message,
        "is_resolved": alert.is_resolved,
        "created_at": str(alert.created_at),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/overview")
async def get_dashboard_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """KPI tổng quan.

    ── G1·DSS ─────────────────────────────────────────────────────────────
    Ba thay đổi so với bản trước:

    • MẪU SỐ. `total_supplies` nay là DANH MỤC CÒN HOẠT ĐỘNG (~1.900 mã, có
      xuất trong 3 kỳ gần nhất), không phải toàn bộ 5.041 mã — trong đó gần
      4/5 là mã đã ngừng dùng. Mọi tỷ lệ phần trăm chia cho mẫu số này.

    • PHÂN MỨC TỒN KHO. Trước đây dựa trên `safety_stock`, cột đã bị vô hiệu
      hoá ở G0 (nó là dấu vết số lần bấm nút, không phải tồn an toàn), nên
      phép đếm cũ nay luôn trả 0. Thay bằng đếm theo DOI.
      Mã không có mẫu số nhu cầu → 'grey', KHÔNG phải 'safe'.

    • Ổ DỊCH. Trước đây đếm `disease_type` có ca trong 7 ngày gần nhất từ
      `disease_cases` — luôn ra 0 vì dữ liệu bệnh viện trễ 1-2 tháng. Nay là
      số nhóm ICD có số ca kỳ đã chốt CAO HƠN kỳ liền trước.
    ─────────────────────────────────────────────────────────────────────── """
    cache_key = "dashboard:overview"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    anchor = ps.get_period_anchor(db)
    last_closed = anchor["last_closed_period"]
    cat = ps.catalogue_counts(db)
    # G2: một nguồn chân lý duy nhất cho mọi con số tồn kho trên dashboard.
    # `ps.stock_signal_counts` là bản tạm của G1 (không FEFO, đọc thẳng
    # inventory). `dss_runner.stock_signal` dùng cùng lõi với /risk-status và
    # /critical-alerts nên ba chỗ không thể lệch nhau nữa.
    signal = dss_runner.stock_signal(db)
    blocks = ps.cases_by_block(db, last_closed)

    # Giá trị tồn kho — giữ lại cho tương thích giao diện hiện tại.
    # KHÔNG phải chỉ số y tế và sẽ bỏ ở G5 (xem hợp đồng dashboard v2).
    value_rows = (
        db.query(Inventory.current_stock, MedicalSupply.unit_price)
        .join(MedicalSupply, Inventory.supply_id == MedicalSupply.id)
        .all()
    )
    total_inventory_value = sum(
        float(r.current_stock or 0) * float(r.unit_price)
        for r in value_rows if r.unit_price is not None
    )

    predicted_demand_30d = int(
        db.query(func.coalesce(func.sum(DiseaseForecast.predicted_cases), 0))
        .filter(
            DiseaseForecast.forecast_date >= date.today(),
            DiseaseForecast.forecast_date <= date.today() + timedelta(days=30),
        )
        .scalar() or 0
    )

    outbreaks = sum(1 for b in blocks
                    if (b.get("trend_pct") or 0) > 0 and b["cases_last_closed"] > 0)

    # MẪU SỐ. Hai mẫu số khác nhau, đừng trộn:
    #   active (~1.900 mã) — mẫu số của mọi tỷ lệ tồn kho
    #   focus  (~555 mã)   — mẫu số của các thẻ DỊCH TỄ: chỉ tập này có tỷ
    #                        trọng hô hấp ≥ 25%, tức tập mà mô hình dịch tễ
    #                        thật sự lái được nhu cầu. Dùng active cho thẻ dịch
    #                        tễ sẽ pha loãng tín hiệu bằng 1.345 mã thuốc bệnh
    #                        mạn mà dự báo hô hấp không nói gì về chúng.
    mau_so = cat["active"] or cat["total"] or 1
    mau_so_dich_te = cat["focus"] or mau_so
    canh_bao = signal["red"] + signal["amber"] + signal["zero_stock"]

    result = {
        # ── khoá cũ, giữ nguyên tên để giao diện hiện tại không vỡ ──
        "total_supplies": cat["active"],
        "total_inventory_value": round(total_inventory_value, 2),
        "high_risk_shortages": signal["red"],
        "predicted_demand_30d": predicted_demand_30d,
        "disease_outbreaks": outbreaks,
        "safe_stock_items": signal["green"],
        "low_stock_items": signal["amber"],
        "critical_risk_items": signal["red"] + signal["zero_stock"],
        "supply_risk_percentage": round(100.0 * canh_bao / mau_so, 2),
        # ── khoá mới ──
        "last_closed_period": last_closed,
        "open_period": anchor["open_period"],
        "catalogue": cat,
        "catalogue_basis": {
            "ty_le_ton_kho_mau_so": mau_so,
            "ty_le_dich_te_mau_so": mau_so_dich_te,
            "nguon": "v_supply_active / v_supply_focus",
        },
        "focus_risk_percentage": round(100.0 * canh_bao / mau_so_dich_te, 2),
        "stock_signal": signal,
        "assumptions_note": "Tồn kho tính trên hàng hiện có, chưa trừ hàng đang về.",
    }
    _cache_set(cache_key, result)
    return result


@router.get("/risk-status")
async def get_risk_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Phân bố danh mục theo mức rủi ro tồn kho.

    ── G2·DSS ─────────────────────────────────────────────────────────────
    Bản cũ so `current_stock` với `Inventory.safety_stock` — cột đã bị vô
    hiệu ở G0, 5.007/5.041 dòng bằng 0, nên mọi mã đều ra 'safe'.

    Bản này phân mức theo SỐ NGÀY ĐÁP ỨNG:

        DOI = S_usable / d_daily

        Đỏ    DOI ≤ 18 ngày   (Đ9: trung vị chu kỳ nhập của bệnh viện)
        Vàng  DOI ≤ 36 ngày   (hai chu kỳ)
        Xanh  DOI > 36 ngày
        Xám   không có mẫu số hoặc không có dữ liệu tồn — KHÔNG phải 'safe'

    Nhãn Xám có khoá riêng `grey_count` / `grey_items`. Dồn nó vào `safe` là
    điều tệ nhất có thể làm ở đây: hàng nghìn mã chưa có định mức sẽ hiện
    màu xanh và dashboard trông rất đẹp mà hoàn toàn vô nghĩa.

    Hợp đồng JSON cũ giữ nguyên. Riêng `safety_stock` trong từng mục nay là
    NGƯỠNG TỒN ỨNG VỚI 18 NGÀY (`d_daily × 18`) — một con số có nghĩa, thay
    cho cột đã đóng băng.
    ─────────────────────────────────────────────────────────────────────── """
    cache_key = "dashboard:risk-status"
    cached = _cache_get(cache_key)
    if cached:
        logger.debug("Cache hit: %s", cache_key)
        return cached

    result = dss_runner.risk_status_payload(db)
    _cache_set(cache_key, result)
    return result


@router.get("/critical-alerts")
async def get_critical_alerts_dashboard(
    limit: int = Query(10, ge=1, le=50, description="Số cảnh báo tối đa trả về"),
    refresh: bool = Query(False, description="Bỏ qua cache, tính lại từ dữ liệu mới nhất"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Danh sách vật tư nguy cấp theo DOI. CHỈ ĐỌC.

    ── G2·DSS ─────────────────────────────────────────────────────────────
    Bản cũ gọi `_sync_alerts_with_inventory(db)` rồi mới đọc — tức một
    endpoint GET có tác dụng phụ GHI dữ liệu, và chính nó đã đóng sạch
    47/47 cảnh báo. Hàm đó đã bị gỡ.

    Danh sách ở đây được TÍNH mỗi lần gọi từ DOI, không lưu trạng thái, nên
    không có gì để mà đóng sai. Endpoint này KHÔNG ghi vào bảng `alerts`.

    Chỉ trả mã Đỏ và Vàng. Xám không phải "sắp hết" mà là "chưa đo được" —
    trộn vào đây sẽ chôn vùi cảnh báo thật.

        severity = "critical"  DOI ≤ 6 ngày   (dưới 1/3 ngưỡng đỏ)
        severity = "high"      6 < DOI ≤ 18
        severity = "medium"    18 < DOI ≤ 36
    ─────────────────────────────────────────────────────────────────────── """
    cache_key = f"dashboard:critical-alerts:{limit}"
    if not refresh:
        cached = _cache_get(cache_key)
        if cached:
            logger.debug("Cache hit: %s", cache_key)
            return cached

    result = dss_runner.critical_alerts_payload(db, limit=limit)
    _cache_set(cache_key, result)
    return result


# ── Smart Medical Dashboard Summary ──────────────────────────────────────────
@router.get("/summary")
async def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """KPI tổng hợp cho Dashboard.

    ── G1·DSS ─────────────────────────────────────────────────────────────
    Bản cũ neo "tháng hiện tại" vào `max(DiseaseCase.recorded_at)`, tức KỲ
    ĐANG MỞ. Tháng 9/2026 mới có 3 ca trong khi tháng 8 có 341 ca, nên

        predicted_trend_pct = (198 − 3) / 3 = 6500%

    và con số đó đi thẳng vào `_classify_risk(6500, 17)` → luôn trả "Cao".

    Bản này neo vào KỲ ĐÃ CHỐT gần nhất (`is_complete = 1`) lấy từ
    `mart_monthly_cases_by_block`, và mọi số ca đều đọc từ mart đó — không
    còn chạm vào bảng `disease_cases`.

    Kỳ đang mở vẫn trả về, nhưng ở trường riêng `open_period_cases` kèm nhãn
    "chưa chốt", và KHÔNG tham gia bất kỳ phép so sánh nào.
    ─────────────────────────────────────────────────────────────────────── """
    anchor = ps.get_period_anchor(db)
    last_closed = anchor["last_closed_period"]
    prev_closed = anchor["prev_closed_period"]
    open_period = anchor["open_period"]

    total_current = ps.cases_in_period(db, last_closed)
    total_prev = ps.cases_in_period(db, prev_closed)
    cases_trend = ps.trend_pct(db, last_closed, prev_closed)

    # Dự báo cho kỳ kế tiếp kỳ đã chốt.
    # Chỉ cộng các dòng CÓ location: dòng location = NULL chính là tổng các
    # tỉnh, gộp vào sẽ đếm gấp đôi.
    next_period = ps.shift_period(last_closed, 1)
    predicted_next = 0
    if next_period:
        y, mo = int(next_period[:4]), int(next_period[5:7])
        predicted_next = int(
            db.query(func.coalesce(func.sum(DiseaseForecast.predicted_cases), 0))
            .filter(
                extract("year", DiseaseForecast.forecast_date) == y,
                extract("month", DiseaseForecast.forecast_date) == mo,
                DiseaseForecast.location.isnot(None),
            )
            .scalar() or 0
        )
    predicted_trend = (
        round(100.0 * (predicted_next - total_current) / total_current, 1)
        if total_current > 0 else 0.0
    )

    signal = dss_runner.stock_signal(db)
    cat = ps.catalogue_counts(db)
    risk = ps.assess_overall_risk(cases_trend, signal["red"], signal["amber"])

    return {
        # ── khoá cũ, giữ nguyên tên ──
        "total_cases_current": total_current,
        "cases_trend_pct": cases_trend,
        "predicted_cases_next_month": predicted_next,
        "predicted_trend_pct": predicted_trend,
        "shortage_supplies_count": signal["red"],
        "overall_risk": risk["level"],
        "as_of": last_closed,
        # ── khoá mới ──
        "last_closed_period": last_closed,
        "prev_closed_period": prev_closed,
        "open_period": open_period,
        "open_period_cases": ps.cases_in_period(db, open_period),
        "open_period_note": "Kỳ chưa chốt — không tính vào xu hướng.",
        "total_cases_prev": total_prev,
        "forecast_period": next_period,
        "blocks": ps.cases_by_block(db, last_closed),
        "catalogue": cat,
        "stock_signal": signal,
        "overall_risk_basis": risk["basis"],
        "overall_risk_is_provisional": risk["is_provisional"],
    }


@router.get("/case-trend")
async def get_case_trend(
    months: int = Query(6, ge=3, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Xu hướng ca bệnh theo tháng, năm nay so với năm trước.

    ── G1·DSS ─────────────────────────────────────────────────────────────
    Đọc từ `mart_monthly_cases_by_block` (region = 'TOAN_QUOC'), kết thúc ở
    KỲ ĐÃ CHỐT gần nhất. Bản cũ đọc `disease_cases` và neo vào
    `max(recorded_at)`, nên cột cuối biểu đồ luôn tụt gần 0 vì đó là kỳ đang
    thu thập dở.

    Số ca ở mức NHÓM đã được đếm DISTINCT bên HIS. Không cộng từ mã con: một
    lượt mang J01 và J06 (cùng thuộc J00-J06) sẽ bị đếm hai lần.
    ─────────────────────────────────────────────────────────────────────── """
    anchor = ps.get_period_anchor(db)
    last_closed = anchor["last_closed_period"]
    if not last_closed:
        return {"this_year": [], "last_year": [], "last_closed_period": None}

    series = ps.case_series(db, n_periods=months, end_period=last_closed)
    this_year, last_year = [], []
    for row in series:
        period = row["period"]
        label = f"T{int(period[5:7])}"
        this_year.append({"month": label, "period": period,
                          "value": row["cases"], "is_complete": row["is_complete"]})
        last_year.append({"month": label,
                          "period": ps.shift_period(period, -12),
                          "value": ps.cases_in_period(db, ps.shift_period(period, -12))})

    return {
        "this_year": this_year,
        "last_year": last_year,
        "last_closed_period": last_closed,
        "open_period": anchor["open_period"],
        "source": "mart_monthly_cases_by_block",
    }


@router.get("/care-level")
async def get_care_level_mix(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Tỷ trọng phân cấp chăm sóc p̂(g,c) — biểu đồ Tầng 2.

    ── G2·DSS ─────────────────────────────────────────────────────────────
    Endpoint MỚI, thêm vào chứ không thay gì cả, nên không thể làm vỡ giao
    diện hiện tại.

    Trả kèm `chan_doan_dinh_muc`: chừng nào `disease_supply_norms` còn cùng
    một `quantity_per_case` ở cả ba mức nặng thì biểu đồ này là MÔ TẢ DỮ
    LIỆU, không phải một yếu tố làm dự báo chính xác hơn. Giao diện phải
    đọc cờ đó và nói đúng như vậy.

    Cửa sổ tính: 12 kỳ trượt từ 2025-04 (Đ11 phát hiện đứt gãy chế độ ghi
    nhận đầu 2025 — cấp 2 đi từ 0,12% lên 50,7%).
    ─────────────────────────────────────────────────────────────────────── """
    cache_key = "dashboard:care-level"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    result = dss_runner.care_level_payload(db)
    _cache_set(cache_key, result)
    return result


# ── Dashboard v2 (Tuần 3 · 11/09/2026) ───────────────────────────────────────
#
# Hai endpoint thay cho bốn endpoint cũ (summary / case-trend / demand-vs-stock
# / critical-alerts) mà trang Dashboard đang gọi. Bốn endpoint cũ GIỮ NGUYÊN
# cho tới khi các trang khác thôi dùng — chúng vẫn đúng, chỉ là mỗi cái một
# mốc thời gian, một cách đếm. v2 đọc một lần, một mốc, một cách đếm.
#
# Không đi qua cache Redis: v2 đã tự cache phần đắt (dự báo) trong SQLite
# theo dấu vân tay dữ liệu; phần còn lại là vài truy vấn nhỏ.

@router.get("/v2")
def get_dashboard_v2(
    focus: bool = Query(True, description="Tập trọng tâm (tỷ trọng hô hấp ≥ 25%) hay toàn danh mục"),
    level: Optional[str] = Query(None, description="Lọc bảng cảnh báo: red | amber | green | grey; bỏ trống = Đỏ + Vàng"),
    limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Mọi thứ trang Tổng quan cần, trừ việc khớp mô hình dự báo.

    Nếu dự báo kỳ tới đã có trong cache (xem `/v2/forecast`) thì Tầng 2 chạy
    và bảng cảnh báo có cột `d_forecast` / `delta_need`; chưa có thì hai cột
    ấy để None và `demand.ready = false` — giao diện phải nói "đang tính",
    không được hiện 0.
    """
    try:
        return dss_dashboard.overview_payload(db, focus=focus, level=level, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/v2/alerts")
def get_dashboard_v2_alerts(
    focus: bool = Query(True, description="Tập trọng tâm (tỷ trọng hô hấp ≥ 25%) hay toàn danh mục"),
    level: Optional[str] = Query(None, description="red | amber | green | grey; bỏ trống = mọi mức"),
    q: Optional[str] = Query(None, description="Lọc theo mã hoặc tên hoạt chất"),
    danh_muc: Optional[str] = Query(None, description="Lọc theo danh mục"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Trang Cảnh báo thiếu hụt (12/09/2026).

    CÙNG chuỗi Tầng 1 → 2 → 3 với `/v2` — cùng dự báo, cùng định mức thực
    nghiệm, cùng ngưỡng `dss.thresholds` — chỉ khác là trả toàn bộ dòng có
    phân trang thay vì top-8. Trước đây trang này gọi một service riêng đọc
    định mức nhập tay × tỷ lệ Nhẹ/TB/Nặng, nên hai trang ra hai con số khác
    nhau về cùng một mã; service đó đã chuyển sang _archive/.
    """
    try:
        return dss_dashboard.alerts_payload(db, focus=focus, level=level, q=q,
                                            danh_muc=danh_muc, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/v2/forecast")
def get_dashboard_v2_forecast(
    force: bool = Query(False, description="Bỏ cache, khớp lại mô hình"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Ŷ_g cho ba khối bằng ensemble PRODUCTION_CONFIG (cùng trang Kế hoạch).

    Lần đầu cho một bộ dữ liệu có thể mất vài chục giây (dựng khoảng thực
    nghiệm cần ~25 lần khớp mỗi khối). Kết quả lưu `dss_forecast_cache`, khoá
    theo dấu vân tay (chuỗi ca + thời tiết + cấu hình) nên đồng bộ xong là
    khoá tự đổi, không cần xoá cache tay.
    """
    return dss_dashboard.forecast_payload(db, compute=True, force=force)


@router.get("/v2/forecast/history")
def get_dashboard_v2_forecast_history(
    limit: int = Query(60, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Sổ theo dõi mô hình trong vận hành (Tuần 4c): mỗi lần app khớp mô hình
    là một dòng; kỳ đích chốt thì tự điền thực tế và sai số. Khác backtest —
    đây là con số màn hình đã hiện vào thời điểm đó."""
    return dss_dashboard.forecast_history(db, limit=limit)
