"""Forecast Analysis API — Module Phân tích & Dự báo theo Smart Medical spec.

Cung cấp endpoints:
- GET  /api/v1/forecast/diseases         danh sách bệnh có data
- GET  /api/v1/forecast/regions          danh sách khu vực có data
- POST /api/v1/forecast/analyze          chạy phân tích + dự báo cho 1 (bệnh, khu vực, tháng)
- GET  /api/v1/forecast/history          lịch sử dự báo gần đây kèm độ lệch
- POST /api/v1/forecast/{id}/actual      cập nhật số ca thực tế để tính sai số
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.disease_case import DiseaseCase
from app.utils.icd_groups import NHOM_ICD, dieu_kien_benh
from app.models.disease_forecast import DiseaseForecast
from app.models.environmental_data import EnvironmentalData
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["forecast-analysis"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    disease_type: str = Field(..., description="Loại bệnh (key hoặc tiếng Việt)")
    region: Optional[str] = Field(None, description="Khu vực, None = toàn thành phố")
    target_month: int = Field(..., ge=1, le=12)
    target_year: int = Field(..., ge=2020, le=2100)
    save: bool = Field(
        False,
        description=(
            "True = GHI NHẬN kết quả vào DB (nút \"Ghi nhận dự báo\"). "
            "False = chỉ tính và trả về để xem, KHÔNG ghi gì."
        ),
    )
    overwrite: bool = Field(
        False,
        description=(
            "Chỉ có tác dụng khi save=True: cho phép ghi đè bản đã ghi nhận "
            "trước đó của cùng khóa (nhóm bệnh, khu vực, tháng)."
        ),
    )
    chi_tai_ban_da_luu: bool = Field(
        False,
        description=(
            "Nội bộ (dùng cho POST /forecast/saved): chỉ nạp lại bản đã ghi "
            "nhận, không chạy mô hình. Chưa có thì trả found=False."
        ),
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _norm_disease(d: str) -> str:
    """Map Vietnamese disease name → ICD code if needed (4 bệnh hô hấp)."""
    map_vi = {
        # NHÓM ICD — đơn vị phân tích chính từ 08/2026 (đề cương + backtest)
        "Nhiễm khuẩn cấp đường hô hấp trên": "J00-J06",
        "Cúm và viêm phổi": "J09-J18",
        "Nhiễm khuẩn cấp đường hô hấp dưới khác": "J20-J22",
        # Mã lẻ — tương thích dữ liệu/API cũ
        "Viêm phế quản cấp": "J20",
        "Nhiễm trùng đường hô hấp trên cấp": "J06",
        "Nhiễm trùng hô hấp trên cấp": "J06",
        "Viêm họng cấp": "J02",
        "Viêm xoang cấp": "J01",
    }
    s = d.strip()
    return map_vi.get(s, s)


def _disease_label(d: str) -> str:
    labels = {
        **NHOM_ICD,
        "J20": "Viêm phế quản cấp",
        "J06": "Nhiễm trùng đường hô hấp trên cấp",
        "J02": "Viêm họng cấp",
        "J01": "Viêm xoang cấp",
    }
    return labels.get(d, d)


def _classify_risk(predicted: int, baseline: float) -> tuple[str, float]:
    """Trả về (risk_level, increase_pct) theo spec 5.6."""
    if baseline <= 0:
        return "low", 0.0
    increase = (predicted - baseline) / baseline * 100
    if increase > 50:
        return "very_high", increase
    if increase > 25:
        return "high", increase
    if increase >= 10:
        return "medium", increase
    return "low", increase


def _risk_label(level: str) -> str:
    return {
        "low": "Thấp",
        "medium": "Trung bình",
        "high": "Cao",
        "very_high": "Rất cao",
    }.get(level, "—")


def _query_cases(
    db: Session,
    disease: str,
    region: Optional[str],
    year: int,
    month: int,
) -> int:
    """Tổng ca bệnh trong tháng cho disease + region.

    region là tỉnh/thành (DiseaseCase.location).
    """
    q = db.query(func.coalesce(func.sum(DiseaseCase.case_count), 0)).filter(
        dieu_kien_benh(DiseaseCase, disease),
        extract("year", DiseaseCase.recorded_at) == year,
        extract("month", DiseaseCase.recorded_at) == month,
    )
    if region:
        from app.utils.province_alias import province_aliases
        aliases = province_aliases(region)
        q = q.filter(DiseaseCase.location.in_(aliases))
    return int(q.scalar() or 0)


def _query_saved_forecast(
    db: Session,
    disease: str,
    region: Optional[str],
    year: int,
    month: int,
) -> Optional[int]:
    """Lấy dự báo đã lưu từ bảng DiseaseForecast cho tháng/năm cụ thể.
    
    Trả về None nếu không tìm thấy dự báo đã lưu.
    Nếu có nhiều dự báo cho cùng tháng, lấy dự báo mới nhất (forecast_date gần nhất).
    """
    forecast_month_date = date(year, month, 1)
    
    q = db.query(DiseaseForecast.predicted_cases).filter(
        DiseaseForecast.icd_code == disease,
        DiseaseForecast.forecast_month == forecast_month_date,
    )
    
    if region:
        from app.utils.province_alias import province_aliases
        aliases = province_aliases(region)
        q = q.filter(DiseaseForecast.location.in_(aliases))
    else:
        # Toàn quốc: location == None hoặc "Toàn quốc"
        q = q.filter(
            (DiseaseForecast.location.is_(None)) | 
            (DiseaseForecast.location == "Toàn quốc")
        )
    
    # Lấy dự báo mới nhất nếu có nhiều
    q = q.order_by(DiseaseForecast.forecast_date.desc())
    result = q.first()
    
    return result[0] if result else None


def _query_weather(
    db: Session,
    region: Optional[str],
    year: int,
    month: int,
) -> Dict[str, Optional[float]]:
    """Trung bình các yếu tố thời tiết tháng đó."""
    q = db.query(
        func.avg(EnvironmentalData.temperature),
        func.avg(EnvironmentalData.humidity),
        func.avg(EnvironmentalData.rainfall),
        func.avg(EnvironmentalData.air_quality_index),
        func.avg(EnvironmentalData.pm25),
    ).filter(
        extract("year", EnvironmentalData.recorded_at) == year,
        extract("month", EnvironmentalData.recorded_at) == month,
    )
    if region:
        from app.utils.province_alias import province_aliases
        aliases = province_aliases(region)
        q = q.filter(EnvironmentalData.location.in_(aliases))
    row = q.first()

    def f(v):
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    return {
        "temp": f(row[0]) if row else None,
        "humidity": f(row[1]) if row else None,
        "rainfall": f(row[2]) if row else None,
        "aqi": f(row[3]) if row else None,
        "pm25": f(row[4]) if row else None,
    }


def _weather_factor(
    forecast_w: Dict[str, Optional[float]],
    history_w: Dict[str, Optional[float]],
) -> tuple[float, list[str]]:
    """Tính hệ số thời tiết và sinh các bullet giải thích.

    Logic đơn giản: mỗi yếu tố lệch >10% so với lịch sử → ảnh hưởng ±5-15% lên hệ số.
    """
    factor = 1.0
    bullets: list[str] = []

    def diff_pct(curr: Optional[float], hist: Optional[float]) -> Optional[float]:
        if curr is None or hist is None or hist == 0:
            return None
        return (curr - hist) / hist * 100

    # Các bullet dưới nói về BỆNH HÔ HẤP — bản trước là văn mẫu sốt xuất huyết
    # (muỗi/lăng quăng), sai bệnh học với đề tài. Mốc mùa vụ trích từ dữ liệu
    # thật 2019–2026: đáy T4–T6, đỉnh T10–T11, biên độ 1,7–2,2 lần
    # (sql_his/06_danh_gia_du_lieu.sql mục 4b).

    # Mưa
    rain_d = diff_pct(forecast_w.get("rainfall"), history_w.get("rainfall"))
    if rain_d is not None and abs(rain_d) >= 10:
        factor *= 1 + (rain_d / 100) * 0.15
        sign = "tăng" if rain_d > 0 else "giảm"
        bullets.append(
            f"Lượng mưa {sign} {abs(rain_d):.0f}% so với cùng kỳ — "
            + ("mùa mưa người dân ở trong nhà nhiều hơn, không gian kín làm "
               "virus hô hấp dễ lây; dữ liệu 2019–2026 cho thấy số ca vào đỉnh "
               "T10–T11 cuối mùa mưa." if rain_d > 0 else
               "thời tiết khô hanh hơn cùng kỳ, giai đoạn này số ca hô hấp "
               "thường ở vùng đáy (T4–T6 theo dữ liệu lịch sử).")
        )

    # Nhiệt độ + độ ẩm
    temp = forecast_w.get("temp")
    hum = forecast_w.get("humidity")
    if temp is not None and hum is not None:
        if 26 <= temp <= 30 and 75 <= hum <= 85:
            factor *= 1.1
            bullets.append(
                f"Độ ẩm {hum:.0f}% và nhiệt độ {temp:.0f}°C — điều kiện virus "
                "hô hấp tồn tại lâu trong không khí và trên bề mặt, lây lan "
                "thuận lợi trong môi trường đông người."
            )
        elif temp > 35:
            factor *= 0.9
            bullets.append(
                f"Nắng nóng {temp:.0f}°C — các tháng khô nóng số ca nhiễm khuẩn "
                "hô hấp thường giảm về vùng đáy theo mùa vụ đo được."
            )

    # AQI / PM2.5
    aqi = forecast_w.get("aqi")
    if aqi is not None and aqi > 100:
        factor *= 1.05
        bullets.append(
            f"AQI {aqi:.0f} ở mức kém — bụi mịn kích ứng niêm mạc đường thở, "
            "làm nặng thêm nhóm viêm phế quản và viêm phổi."
        )

    return round(factor, 3), bullets


def _pearson_coefficients(correlation_rows: list[dict]) -> Dict[str, Optional[float]]:
    """Tính hệ số tương quan Pearson giữa số ca và mỗi yếu tố thời tiết.

    Trả về dict có 5 key: temp, humidity, rainfall, aqi, pm25.
    Mỗi value là số trong [-1, 1] (làm tròn 3 chữ số), hoặc None nếu thiếu data.
    """
    factors = ("temp", "humidity", "rainfall", "aqi", "pm25")
    result: Dict[str, Optional[float]] = {}

    for f in factors:
        # Cặp (cases, factor) — bỏ qua điểm thiếu dữ liệu
        pairs = [
            (float(r["cases"]), float(r[f]))
            for r in correlation_rows
            if r.get(f) is not None and r.get("cases") is not None
        ]
        if len(pairs) < 2:
            result[f] = None
            continue

        n = len(pairs)
        x_vals = [p[0] for p in pairs]
        y_vals = [p[1] for p in pairs]
        mean_x = sum(x_vals) / n
        mean_y = sum(y_vals) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
        den_x = (sum((x - mean_x) ** 2 for x in x_vals)) ** 0.5
        den_y = (sum((y - mean_y) ** 2 for y in y_vals)) ** 0.5
        denom = den_x * den_y
        result[f] = round(num / denom, 3) if denom > 0 else None

    return result


def _trend_factor(
    db: Session, disease: str, region: Optional[str], target_year: int, target_month: int
) -> tuple[float, Optional[str]]:
    """Hệ số xu hướng = ca tháng gần nhất / TB 3 tháng trước đó."""
    months_back = []
    for i in range(1, 7):
        y = target_year
        m = target_month - i
        while m <= 0:
            m += 12
            y -= 1
        months_back.append((y, m))

    counts = [_query_cases(db, disease, region, y, m) for (y, m) in months_back]
    last1 = counts[0]
    avg_prev = mean(counts[1:4]) if len(counts) >= 4 and any(c > 0 for c in counts[1:4]) else 0

    if avg_prev <= 0:
        return 1.0, None

    factor = last1 / avg_prev
    factor = max(0.5, min(2.5, factor))  # clamp

    explanation: Optional[str] = None
    # Chuỗi 3 tháng tăng liên tiếp?
    if all(counts[i] > counts[i + 1] for i in range(3)):
        change = (counts[0] - counts[2]) / max(counts[2], 1) * 100
        explanation = (
            f"Xu hướng 3 tháng tăng mạnh — Tốc độ lây lan gia tăng {change:.0f}% "
            f"so với 3 tháng trước."
        )

    return round(factor, 3), explanation


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/diseases")
async def list_diseases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, str]]:
    """Danh sách BỆNH cho combobox = ba NHÓM ICD của đề tài.

    Vì sao không trả 20 mã lẻ nữa: đề cương chốt dự báo cấp nhóm, và backtest
    trên dữ liệu thật cho thấy chuỗi mã lẻ thưa làm mô hình mất ổn định
    (bottom-up MASE 483 trên mã thưa). Mã lẻ vẫn nằm trong dữ liệu — API này
    chỉ quyết định NGƯỜI DÙNG chọn gì.
    """
    return [{"key": k, "label": v} for k, v in NHOM_ICD.items()]


@router.get("/regions")
async def list_regions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[str]:
    rows = db.query(DiseaseCase.location).distinct().order_by(DiseaseCase.location).all()
    return [r[0] for r in rows if r[0]]


# ── ML model: train + dự báo (MonthlyForecaster từ database) ──────────────────


class TrainRequest(BaseModel):
    region: Optional[str] = Field(
        None, description="Khu vực train. None = gộp toàn quốc."
    )


class MLAnalyzeRequest(BaseModel):
    disease_type: str = Field(..., description="Mã ICD (J20/J06/J02/J01) hoặc tên VN")
    region: Optional[str] = Field(None, description="Khu vực, None = toàn quốc")
    target_month: int = Field(..., ge=1, le=12)
    target_year: int = Field(..., ge=2020, le=2100)


@router.post("/train")
async def train_models(
    payload: TrainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Train MonthlyForecaster cho 4 bệnh hô hấp từ dữ liệu trong database.

    Học tương quan thời tiết (nguồn Open-Meteo trong environmental_data) +
    xu hướng. Trả về độ chính xác (MAE/RMSE/MAPE/R²) cho từng bệnh.
    """
    from app.ai_engine.db_forecasting_service import DBForecastingService

    region = payload.region.strip() if payload.region and payload.region != "all" else None
    service = DBForecastingService(db)
    results = service.train_all(region=region)

    trained = [k for k, v in results.items() if v.get("status") == "trained"]
    logger.info(
        "ML train by user=%s region=%s: trained=%s",
        current_user.username, region or "toàn quốc", trained,
    )
    return {
        "status": "ok",
        "region": region or "Toàn quốc",
        "trained_count": len(trained),
        "models": results,
        "trained_at": datetime.now().isoformat(),
    }


@router.post("/ml-analyze")
async def ml_analyze_forecast(
    payload: MLAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Dự báo số ca bằng mô hình ML (MonthlyForecaster).

    Tự huấn luyện mô hình trên dữ liệu mới nhất trong DB rồi dự báo ngay,
    nên kết quả luôn phản ánh dữ liệu hiện tại (không cần bước train riêng).
    """
    from app.ai_engine.db_forecasting_service import DBForecastingService

    disease = _norm_disease(payload.disease_type)
    region = payload.region.strip() if payload.region and payload.region != "all" else None
    service = DBForecastingService(db)

    try:
        result = service.analyze(
            icd_code=disease,
            target_month=payload.target_month,
            target_year=payload.target_year,
            region=region,
        )
    except ValueError as exc:
        # Không đủ dữ liệu để train
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        logger.error("ML analyze failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Lỗi dự báo ML: {exc}")

    metrics = result.get("model_metrics", {}) or {}
    # Tính mức nguy cơ dựa trên SỐ CA AI vs ca nền (để khớp với số hiển thị)
    baseline_val = (result.get("formula_details", {}) or {}).get("baseline", 0) or 0
    risk_level, increase_pct = _classify_risk(
        result.get("predicted_cases", 0), float(baseline_val)
    )
    return {
        "disease_type": disease,
        "disease_label": result.get("disease_label"),
        "region": result.get("region"),
        "target_month": payload.target_month,
        "target_year": payload.target_year,
        "predicted_cases": result.get("predicted_cases"),
        "confidence_lower": result.get("confidence_lower"),
        "confidence_upper": result.get("confidence_upper"),
        "risk_level": risk_level,
        "risk_label": _risk_label(risk_level),
        "increase_pct": round(increase_pct, 1),
        "formula_details": result.get("formula_details"),
        "forecast_weather": result.get("forecast_weather"),
        "accuracy": {
            "mae": round(metrics.get("mae", 0), 2),
            "rmse": round(metrics.get("rmse", 0), 2),
            "mape": round(metrics.get("mape", 0), 2),
            "r2": round(metrics.get("r2", 0), 3),
            "n_samples": metrics.get("n_samples", 0),
        },
    }


@router.post("/analyze")
async def analyze_forecast(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Chạy pipeline dự báo theo công thức 5.5.

    Output trả về đủ data cho 4 biểu đồ + giải thích.
    """
    disease = _norm_disease(payload.disease_type)
    region = payload.region.strip() if payload.region and payload.region != "all" else None

    chi_tai = payload.chi_tai_ban_da_luu
    # Chế độ chỉ-nạp không bao giờ ghi DB (bảo vệ luôn cả trường hợp gọi API
    # trực tiếp với cả hai cờ — khối ghi DB cần dữ liệu chỉ có khi đã tính).
    luu_lai = payload.save and not chi_tai
    forecast_date = date(payload.target_year, payload.target_month, 1)
    disease_name_label = _disease_label(disease)

    # ── Bản ĐÃ GHI NHẬN của đúng khóa (nhóm bệnh, khu vực, tháng) ──────────
    # Ba tiêu chí này gộp thành MỘT khóa: mỗi khóa chỉ giữ tối đa 1 bản dự báo
    # đã ghi nhận.
    cached = (
        db.query(DiseaseForecast)
        .filter(
            DiseaseForecast.icd_code == disease,
            DiseaseForecast.forecast_month == forecast_date,
            DiseaseForecast.location == region,
        )
        .order_by(DiseaseForecast.created_at.desc())
        .first()
    )

    # Chế độ CHỈ NẠP (mở trang / đổi bộ lọc): lấy lại bản đã ghi nhận, tuyệt
    # đối KHÔNG chạy mô hình. Chưa ghi nhận thì báo found=False để giao diện
    # để trống, chờ người dùng bấm "Phân tích".
    if chi_tai and cached is None:
        return {"found": False, "forecast": None}

    # Ghi nhận nhưng kỳ này đã có bản trước đó → trả 409 để giao diện hỏi
    # "đã có dự báo trước đó, ghi đè không?" thay vì lặng lẽ ghi chồng.
    if luu_lai and cached is not None and not payload.overwrite:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "da_ghi_nhan",
                "message": (
                    f"Kỳ này đã có dự báo được ghi nhận lúc "
                    f"{cached.created_at.strftime('%d/%m/%Y %H:%M') if cached.created_at else '—'}"
                    f" ({cached.predicted_cases} ca). Ghi đè bản cũ?"
                ),
                "forecast_id": cached.id,
                "predicted_cases": cached.predicted_cases,
                "recorded_at": cached.created_at.isoformat() if cached.created_at else None,
            },
        )

    # Chỉ dùng lại số liệu đã lưu khi đang ở chế độ chỉ-nạp. Bấm "Phân tích"
    # là luôn chạy lại mô hình, kể cả khi kỳ đó đã ghi nhận.
    dung_ban_da_luu = chi_tai and cached is not None

    if not dung_ban_da_luu:
        # ── Tính số ca dự báo ────────────────────────────────────────────────
        # Khi chọn 1 khu vực cụ thể → tính trực tiếp.
        # Khi "Toàn quốc" (region=None) → forecast RIÊNG từng tỉnh rồi CỘNG lại,
        # để tổng toàn quốc luôn ≥ từng tỉnh (tránh nghịch lý weather pha loãng).
        def _compute_one_region(reg: Optional[str]):
            """Trả về (predicted, baseline, weather_factor, trend_factor,
            forecast_w, history_w_avg, weather_bullets, trend_bullet, baseline_years)."""
            b_years: list[int] = []
            b_counts: list[int] = []
            for back in range(1, 6):
                yy = payload.target_year - back
                cc = _query_cases(db, disease, reg, yy, payload.target_month)
                if cc > 0:
                    b_years.append(yy)
                    b_counts.append(cc)
            base = mean(b_counts) if b_counts else 0.0

            fw = _query_weather(db, reg, payload.target_year, payload.target_month)
            hw_list = [_query_weather(db, reg, yy, payload.target_month) for yy in b_years]

            def _avg(field: str) -> Optional[float]:
                vals = [w[field] for w in hw_list if w[field] is not None]
                return mean(vals) if vals else None

            hw_avg = {f: _avg(f) for f in ("temp", "humidity", "rainfall", "aqi", "pm25")}
            wf, wb = _weather_factor(fw, hw_avg)
            tf, tb = _trend_factor(db, disease, reg, payload.target_year, payload.target_month)
            pred = int(round(base * wf * tf)) if base else 0
            return pred, base, wf, tf, fw, hw_avg, wb, tb, b_years

        if region is None:
            # Toàn quốc = Σ forecast từng tỉnh có data
            provinces = [
                r[0] for r in db.query(DiseaseCase.location)
                .filter(dieu_kien_benh(DiseaseCase, disease))
                .distinct().all()
                if r[0]
            ]
            predicted = 0
            baseline = 0.0
            baseline_years_set: set[int] = set()
            # Lưu dự báo từng tỉnh để hiển thị bảng "Dữ liệu ca bệnh gần đây"
            per_province: list[dict] = []
            # Dùng weather/trend của tỉnh có nhiều ca nhất để hiển thị giải thích
            rep = None
            rep_cases = -1
            for prov in provinces:
                (p, b, wf, tf, fw, hw, wb, tb, byrs) = _compute_one_region(prov)
                predicted += p
                baseline += b
                baseline_years_set.update(byrs)
                per_province.append({
                    "location": prov,
                    "predicted": p,
                    "baseline": b,
                    "weather_factor": wf,
                    "trend_factor": tf,
                })
                if b > rep_cases:
                    rep_cases = b
                    rep = (wf, tf, fw, hw, wb, tb)
            baseline_years = sorted(baseline_years_set)
            if rep:
                weather_factor, trend_factor, forecast_w, history_w_avg, weather_bullets, trend_bullet = rep
            else:
                weather_factor, trend_factor = 1.0, 1.0
                forecast_w = _query_weather(db, None, payload.target_year, payload.target_month)
                history_w_avg = {f: None for f in ("temp", "humidity", "rainfall", "aqi", "pm25")}
                weather_bullets, trend_bullet = [], None
        else:
            (predicted, baseline, weather_factor, trend_factor, forecast_w,
             history_w_avg, weather_bullets, trend_bullet, baseline_years) = _compute_one_region(region)
            per_province = []

        # predicted đã được tính ở trên (theo từng khu vực hoặc cộng dồn toàn quốc)
        # ── Ghi đè bằng mô hình ML (MonthlyForecaster) ────────────────────────
        # Tự huấn luyện trên dữ liệu mới nhất + dự báo. Nếu thất bại (thiếu data)
        # thì giữ nguyên số heuristic ở trên làm fallback.
        model_used = "multivariate_v1"
        ml_accuracy: Dict[str, Any] | None = None
        try:
            from app.ai_engine.db_forecasting_service import DBForecastingService

            ml_result = DBForecastingService(db).analyze(
                icd_code=disease,
                target_month=payload.target_month,
                target_year=payload.target_year,
                region=region,
            )
            predicted = int(ml_result["predicted_cases"])
            fd = ml_result.get("formula_details", {}) or {}
            # Ưu tiên baseline/hệ số từ mô hình để hiển thị nhất quán
            baseline = float(fd.get("baseline", baseline) or baseline)
            weather_factor = float(fd.get("weather_factor", weather_factor) or weather_factor)
            trend_factor = float(fd.get("trend_factor", trend_factor) or trend_factor)
            model_used = "monthly_forecaster_ml"
            m = ml_result.get("model_metrics", {}) or {}
            ml_accuracy = {
                "mae": round(m.get("mae", 0), 2),
                "rmse": round(m.get("rmse", 0), 2),
                "mape": round(m.get("mape", 0), 2),
                "r2": round(m.get("r2", 0), 3),
                "n_samples": m.get("n_samples", 0),
            }
        except Exception as exc:
            logger.warning("ML forecast unavailable, fallback heuristic: %s", exc)

        # ── Engine CHÍNH: ensemble NHÓM đã kiểm chứng walk-forward (09/08/2026) ──
        # Heuristic cùng-kỳ và MonthlyForecaster phía trên chỉ còn là fallback: cả
        # hai tựa vào trung bình nhiều năm nên bị dịch chuyển mức nền kéo tụt
        # (đo thật trên T6/2026: dự báo 65 ca cho tháng thực tế ~110 — hụt ~40%).
        # Ensemble học xu hướng + mùa vụ + thời tiết trên toàn chuỗi, CÙNG engine
        # với trang Kế hoạch nhập kho — hai màn hình thống nhất một con số.
        try:
            from app.services.group_ensemble_service import du_bao_nhom
            kq_ens = du_bao_nhom(db, disease, region,
                                 payload.target_year, payload.target_month)
            if kq_ens is not None:
                predicted = kq_ens["predicted"]
                model_used = kq_ens["model_used"]
                if kq_ens.get("accuracy"):
                    a = kq_ens["accuracy"]
                    ml_accuracy = {
                        "mae": a["mae"], "rmse": a["mae"],  # rmse không đo ở bản nhanh
                        "mape": a["wape"], "r2": 0,
                        "n_samples": a["n_steps"],
                        "accuracy_pct": a["accuracy_pct"],
                    }
        except Exception:
            logger.exception("Ensemble nhóm lỗi — dùng dự báo fallback")
    else:
        # Dùng lại kết quả mô hình đã lưu — không tính toán lại.
        predicted = cached.predicted_cases
        baseline = float(cached.baseline_cases or 0)
        weather_factor = float(cached.weather_factor or 1.0)
        trend_factor = float(cached.trend_factor or 1.0)
        model_used = cached.model_used or "cached"
        ml_accuracy = None
        if cached.model_accuracy_mae is not None:
            ml_accuracy = {
                "mae": cached.model_accuracy_mae,
                "rmse": cached.model_accuracy_rmse,
                "mape": cached.model_accuracy_mape,
                "r2": 0,
                "n_samples": 0,
            }
        baseline_years = [
            y for y in range(payload.target_year - 5, payload.target_year)
            if _query_cases(db, disease, region, y, payload.target_month) > 0
        ]
        forecast_w = _query_weather(
            db, region, payload.target_year, payload.target_month
        )
        _hw_list = [
            _query_weather(db, region, y, payload.target_month)
            for y in baseline_years
        ]

        def _cached_avg(field: str) -> Optional[float]:
            vals = [w[field] for w in _hw_list if w[field] is not None]
            return mean(vals) if vals else None

        history_w_avg = {
            f: _cached_avg(f) for f in ("temp", "humidity", "rainfall", "aqi", "pm25")
        }
        weather_bullets = [cached.explanation] if cached.explanation else []
        trend_bullet = None

    risk_level, increase_pct = _classify_risk(predicted, baseline)

    # 5. Build các series cho biểu đồ
    # 5a. Forecast vs actual qua các năm: data theo từng tháng (T1..T_target) cho mỗi năm
    # Với năm target, trả về CẢ HAI: actual và forecast để frontend hiển thị 2 đường riêng
    years_to_show = sorted(set(baseline_years + [payload.target_year]))
    chart_main: list[dict] = []
    for m in range(1, payload.target_month + 1):
        row: Dict[str, Any] = {"month": f"T{m}"}
        for y in years_to_show:
            if y == payload.target_year:
                # Năm dự báo: trả về cả actual và forecast
                actual_cases = _query_cases(db, disease, region, y, m)
                row[f"{y}_actual"] = actual_cases
                
                if m == payload.target_month:
                    # Tháng target: dùng predicted hiện tại
                    row[f"{y}_forecast"] = predicted
                else:
                    # Các tháng trước: lấy dự báo đã lưu, nếu không có thì dùng 0
                    saved_forecast = _query_saved_forecast(db, disease, region, y, m)
                    row[f"{y}_forecast"] = saved_forecast if saved_forecast is not None else 0
            else:
                # Các năm khác: chỉ trả về số ca thực tế
                row[str(y)] = _query_cases(db, disease, region, y, m)
        chart_main.append(row)

    # 5b. So sánh cùng kỳ (bar chart) — số ca tháng target qua các năm
    comparison: list[dict] = []
    for y in years_to_show:
        if y == payload.target_year:
            comparison.append({"year": y, "value": predicted, "is_forecast": True})
        else:
            comparison.append(
                {
                    "year": y,
                    "value": _query_cases(db, disease, region, y, payload.target_month),
                    "is_forecast": False,
                }
            )

    # 5c. Xu hướng năm hiện tại đến tháng trước
    trend_curr_year: list[dict] = []
    for m in range(1, payload.target_month):
        trend_curr_year.append(
            {
                "month": f"T{m}",
                "value": _query_cases(db, disease, region, payload.target_year, m),
            }
        )

    # 5d. Tương quan thời tiết & dịch bệnh — qua các năm cho cùng tháng
    correlation: list[dict] = []
    for y in years_to_show:
        cases = (
            predicted if y == payload.target_year
            else _query_cases(db, disease, region, y, payload.target_month)
        )
        w = (
            forecast_w if y == payload.target_year
            else _query_weather(db, region, y, payload.target_month)
        )
        correlation.append(
            {
                "year": y,
                "cases": cases,
                "temp": w.get("temp"),
                "humidity": w.get("humidity"),
                "rainfall": w.get("rainfall"),
                "aqi": w.get("aqi"),
                "pm25": w.get("pm25"),
                "is_forecast": y == payload.target_year,
            }
        )

    # 5e. Hệ số tương quan Pearson giữa số ca và mỗi yếu tố thời tiết.
    # Dùng để hiển thị bên cạnh biểu đồ (spec 5.2 #4 — Phân tích tương quan).
    correlation_coefficients = _pearson_coefficients(correlation)

    # 6. Giải thích mô hình (bullets)
    explanation_bullets = list(weather_bullets)
    if trend_bullet:
        explanation_bullets.append(trend_bullet)
    if not explanation_bullets:
        explanation_bullets.append(
            "Không phát hiện yếu tố bất thường — dự báo ổn định theo xu hướng cơ sở."
        )

    explanation_text = " | ".join(explanation_bullets)[:1000]

    if luu_lai:
        # 7. GHI NHẬN dự báo — chỉ chạy khi người dùng bấm "Ghi nhận dự báo".
        #    Bấm "Phân tích" chỉ tính để xem, không đụng gì tới DB.
        forecast_date = date(payload.target_year, payload.target_month, 1)
        disease_name_label = _disease_label(disease)

        # Xóa các forecast cũ cho cùng (bệnh, tháng, khu vực) để tránh cộng dồn
        # khi user bấm "Phân tích" nhiều lần — mỗi tháng × bệnh × khu vực chỉ giữ
        # 1 forecast mới nhất.
        old_forecasts = (
            db.query(DiseaseForecast)
            .filter(
                DiseaseForecast.icd_code == disease,
                DiseaseForecast.forecast_month == forecast_date,
                DiseaseForecast.location == region,
            )
            .all()
        )
        if old_forecasts:
            # Xoá supply_requirements liên kết để không leak FK
            from app.models.supply_requirement import SupplyRequirement
            old_ids = [f.id for f in old_forecasts]
            db.query(SupplyRequirement).filter(
                SupplyRequirement.forecast_id.in_(old_ids)
            ).delete(synchronize_session=False)
            for fc in old_forecasts:
                db.delete(fc)
            db.flush()
            logger.info(
                "Deleted %d stale forecast(s) for %s/%s/%s before re-saving",
                len(old_forecasts), disease, forecast_date, region,
            )

        saved = DiseaseForecast(
            forecast_month=forecast_date,
            forecast_date=forecast_date,
            icd_code=disease,
            disease_name=disease_name_label,
            disease_type="respiratory",
            location=region,
            predicted_cases=predicted,
            confidence_lower=int(predicted * 0.85),
            confidence_upper=int(predicted * 1.15),
            model_used=model_used,
            baseline_cases=int(baseline),
            weather_factor=weather_factor,
            trend_factor=trend_factor,
            risk_level=risk_level,
            explanation=explanation_text,
            forecast_period_days=30,
            created_by=current_user.username,
        )
        if ml_accuracy:
            saved.model_accuracy_mae = ml_accuracy["mae"]
            saved.model_accuracy_rmse = ml_accuracy["rmse"]
            saved.model_accuracy_mape = ml_accuracy["mape"]
        db.add(saved)
        db.commit()
        db.refresh(saved)

        # Khi phân tích TOÀN QUỐC: lưu thêm dự báo của TỪNG TỈNH để bảng "Dữ liệu
        # ca bệnh gần đây" hiển thị dự báo theo khu vực (không chỉ con số tổng).
        if region is None and per_province:
            for pp in per_province:
                loc = pp["location"]
                pred_p = pp["predicted"]
                base_p = pp["baseline"]
                rl_p, _ = _classify_risk(pred_p, base_p)
                # Xoá forecast cũ của tỉnh này cho cùng tháng/bệnh
                old_p = (
                    db.query(DiseaseForecast)
                    .filter(
                        DiseaseForecast.icd_code == disease,
                        DiseaseForecast.forecast_month == forecast_date,
                        DiseaseForecast.location == loc,
                    )
                    .all()
                )
                for fc in old_p:
                    db.delete(fc)
                db.add(DiseaseForecast(
                    forecast_month=forecast_date,
                    forecast_date=forecast_date,
                    icd_code=disease,
                    disease_name=disease_name_label,
                    disease_type="respiratory",
                    location=loc,
                    predicted_cases=pred_p,
                    confidence_lower=int(pred_p * 0.85),
                    confidence_upper=int(pred_p * 1.15),
                    model_used=model_used,
                    baseline_cases=int(base_p),
                    weather_factor=pp["weather_factor"],
                    trend_factor=pp["trend_factor"],
                    risk_level=rl_p,
                    forecast_period_days=30,
                    created_by=current_user.username,
                ))
            db.commit()

        # Khi phân tích TOÀN QUỐC: lưu thêm dự báo cho TỪNG TỈNH để bảng
        # "Dữ liệu ca bệnh gần đây" hiển thị số dự báo riêng từng khu vực.
        if region is None:
            try:
                from app.ai_engine.db_forecasting_service import DBForecastingService
                from app.models.supply_requirement import SupplyRequirement

                svc = DBForecastingService(db)
                provinces_to_forecast = [
                    r[0] for r in db.query(DiseaseCase.location)
                    .filter(dieu_kien_benh(DiseaseCase, disease))
                    .distinct().all()
                    if r[0]
                ]
                for prov in provinces_to_forecast:
                    try:
                        pr = svc.analyze(
                            icd_code=disease,
                            target_month=payload.target_month,
                            target_year=payload.target_year,
                            region=prov,
                        )
                        p_pred = int(pr["predicted_cases"])
                        p_fd = pr.get("formula_details", {}) or {}
                        p_base = float(p_fd.get("baseline", 0) or 0)
                        p_risk, _ = _classify_risk(p_pred, p_base)
                        p_m = pr.get("model_metrics", {}) or {}
                    except Exception:
                        continue

                    # Xoá forecast cũ của tỉnh này (cùng bệnh, tháng)
                    old_prov = (
                        db.query(DiseaseForecast)
                        .filter(
                            DiseaseForecast.icd_code == disease,
                            DiseaseForecast.forecast_month == forecast_date,
                            DiseaseForecast.location == prov,
                        )
                        .all()
                    )
                    if old_prov:
                        old_ids = [f.id for f in old_prov]
                        db.query(SupplyRequirement).filter(
                            SupplyRequirement.forecast_id.in_(old_ids)
                        ).delete(synchronize_session=False)
                        for fc in old_prov:
                            db.delete(fc)
                        db.flush()

                    db.add(DiseaseForecast(
                        forecast_month=forecast_date,
                        forecast_date=forecast_date,
                        icd_code=disease,
                        disease_name=disease_name_label,
                        disease_type="respiratory",
                        location=prov,
                        predicted_cases=p_pred,
                        confidence_lower=int(p_pred * 0.85),
                        confidence_upper=int(p_pred * 1.15),
                        model_used=model_used,
                        baseline_cases=int(p_base),
                        risk_level=p_risk,
                        forecast_period_days=30,
                        created_by=current_user.username,
                        model_accuracy_mape=round(p_m.get("mape", 0), 2) if p_m else None,
                    ))
                db.commit()
            except Exception as exc:
                logger.warning("Per-province forecast save failed: %s", exc)
                db.rollback()

        # Spec 5 → Bước 5: tự sinh supply_requirements để Module 7 (/alerts) có data
        try:
            from app.services.supply_requirement_service import SupplyRequirementService

            SupplyRequirementService(db).generate_requirements_for_forecast(saved.id)
        except Exception as exc:
            # Không block kết quả forecast nếu việc sinh requirement gặp lỗi
            logger.warning(
                "Failed to auto-generate supply requirements for forecast %s: %s",
                saved.id,
                exc,
            )

        # Spec 5 → Bước 6: tự sinh alerts từ shortage hiện tại để Dashboard có cảnh báo
        try:
            from datetime import timedelta as _timedelta
            from app.services.alert_service import AlertModule

            AlertModule(db).check_and_generate_alerts(
                start_date=date.today(),
                end_date=date.today() + _timedelta(days=60),
            )
        except Exception as exc:
            logger.warning(
                "Failed to auto-generate alerts for forecast %s: %s",
                saved.id,
                exc,
            )

        # Invalidate dashboard cache → dashboard cập nhật ngay (không chờ TTL 5')
        try:
            from app.api.v1.dashboard import invalidate_dashboard_cache

            invalidate_dashboard_cache()
        except Exception as exc:
            logger.debug("Dashboard cache invalidate skipped: %s", exc)
    else:
        # Không ghi nhận lần này: chế độ chỉ-nạp thì trả lại chính bản đã ghi
        # nhận; còn vừa bấm "Phân tích" thì chưa có bản nào (saved = None).
        saved = cached if dung_ban_da_luu else None

    return {
        "found": True,
        "forecast": {
            "id": saved.id if saved is not None else None,
            "predicted_cases": predicted,
            "baseline": int(baseline),
            "increase_pct": round(increase_pct, 1),
            "risk_level": risk_level,
            "risk_label": _risk_label(risk_level),
            "weather_factor": weather_factor,
            "trend_factor": trend_factor,
            "disease_type": disease,
            "disease_label": _disease_label(disease),
            "region": region or "Toàn thành phố",
            "target_month": payload.target_month,
            "target_year": payload.target_year,
            "model_used": model_used,
            # Kết quả này đã được ghi nhận vào DB hay mới chỉ là bản xem trước.
            "is_recorded": saved is not None,
            "recorded_at": (
                saved.created_at.isoformat()
                if saved is not None and saved.created_at
                else None
            ),
        },
        "accuracy": ml_accuracy,
        "explanation_bullets": explanation_bullets,
        "weather": {
            "forecast": forecast_w,
            "history_avg": history_w_avg,
        },
        "charts": {
            "main": chart_main,            # T1..T_target qua các năm
            "comparison": comparison,      # Bar chart — số ca tháng target qua các năm
            "trend_current_year": trend_curr_year,  # Line — xu hướng tháng đầu năm
            "correlation": correlation,    # Combo — số ca + thời tiết qua các năm
            "correlation_coefficients": correlation_coefficients,  # Pearson r cho 5 yếu tố
            "years": years_to_show,
        },
    }


@router.post("/saved")
async def load_saved_forecast(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Nạp lại bản dự báo ĐÃ GHI NHẬN theo khóa (nhóm bệnh, khu vực, tháng).

    Dùng khi mở trang Phân tích & Dự báo hoặc khi đổi bộ lọc: chỉ đọc, KHÔNG
    chạy mô hình và KHÔNG ghi gì vào DB. Chưa ghi nhận thì trả
    ``{"found": false}`` để giao diện để trống, chờ bấm "Phân tích".
    """
    payload.chi_tai_ban_da_luu = True
    payload.save = False
    payload.overwrite = False
    return await analyze_forecast(payload, db, current_user)


@router.get("/history")
async def get_forecast_history(
    limit: int = Query(10, ge=1, le=1000),
    disease_type: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None, description="Lọc từ tháng dự báo >= ngày này"),
    end_date: Optional[date] = Query(None, description="Lọc đến tháng dự báo <= ngày này"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Lịch sử dự báo gần đây kèm độ lệch (nếu đã có actual)."""
    q = db.query(DiseaseForecast).order_by(DiseaseForecast.created_at.desc())
    if disease_type:
        q = q.filter(DiseaseForecast.icd_code == _norm_disease(disease_type))
    if region:
        from app.utils.province_alias import province_aliases
        q = q.filter(DiseaseForecast.location.in_(province_aliases(region)))
    # Lọc theo khoảng thời gian dự báo (forecast_month = đầu tháng)
    if start_date:
        q = q.filter(DiseaseForecast.forecast_month >= start_date.replace(day=1))
    if end_date:
        q = q.filter(DiseaseForecast.forecast_month <= end_date)
    rows = q.limit(limit).all()

    out = []
    for r in rows:
        actual = r.actual_cases
        deviation = None
        if actual is not None and actual > 0:
            deviation = round((r.predicted_cases - actual) / actual * 100, 1)
        out.append(
            {
                "id": r.id,
                "month": r.forecast_date.strftime("%m/%Y"),
                "disease_type": r.icd_code,
                "icd_code": r.icd_code,
                "disease_label": r.disease_name or _disease_label(r.icd_code),
                "region": r.location or "Toàn thành phố",
                "predicted_cases": r.predicted_cases,
                "actual_cases": actual,
                "deviation_pct": deviation,
                "risk_level": r.risk_level,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return out


class ActualUpdateRequest(BaseModel):
    actual_cases: int = Field(..., ge=0)


@router.post("/{forecast_id}/actual")
async def update_actual(
    forecast_id: int,
    payload: ActualUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Nhập số ca thực tế để tính độ lệch dự báo."""
    fc = db.query(DiseaseForecast).filter(DiseaseForecast.id == forecast_id).first()
    if not fc:
        raise HTTPException(status_code=404, detail="Forecast not found")

    fc.actual_cases = payload.actual_cases
    if payload.actual_cases > 0:
        fc.deviation_pct = round(
            (fc.predicted_cases - payload.actual_cases) / payload.actual_cases * 100, 2
        )
    db.commit()
    db.refresh(fc)
    return {
        "id": fc.id,
        "predicted_cases": fc.predicted_cases,
        "actual_cases": fc.actual_cases,
        "deviation_pct": float(fc.deviation_pct) if fc.deviation_pct is not None else None,
    }


@router.post("/{forecast_id}/export")
async def export_forecast_pdf(
    forecast_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xuất PDF báo cáo dự báo cho 1 bản ghi đã lưu (spec 5.2 #10)."""
    from datetime import datetime as _dt
    from fastapi.responses import Response
    import io

    fc = db.query(DiseaseForecast).filter(DiseaseForecast.id == forecast_id).first()
    if not fc:
        raise HTTPException(status_code=404, detail="Forecast not found")

    # Dùng helper từ reports module để có font Unicode
    from app.api.v1 import reports as _reports

    _reports._register_unicode_fonts()
    PDF_FONT_BOLD = _reports.PDF_FONT_BOLD
    _get_reportlab = _reports._get_reportlab
    _patch_styles_for_unicode = _reports._patch_styles_for_unicode
    _base_table_style = _reports._base_table_style

    colors, A4, _landscape, getSampleStyleSheet, cm, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer = _get_reportlab()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    _patch_styles_for_unicode(styles)
    base_style = _base_table_style(colors)

    risk_label_map = {"low": "Thấp", "medium": "Trung bình", "high": "Cao", "very_high": "Rất cao"}
    disease_label = fc.disease_name or _disease_label(fc.icd_code)
    region_text = fc.location or "Toàn thành phố"
    month_label = fc.forecast_date.strftime("%m/%Y") if fc.forecast_date else "—"

    story = [
        Paragraph(f"Báo cáo dự báo dịch bệnh - {month_label}", styles["Title"]),
        Paragraph(
            f"Tạo lúc: {_dt.now().strftime('%d/%m/%Y %H:%M')} | "
            f"Người tạo: {fc.created_by or current_user.username}",
            styles["Italic"],
        ),
        Spacer(1, 0.5 * cm),
    ]

    # I. Thông tin dự báo
    story.append(Paragraph("<b>I. Thông tin dự báo</b>", styles["Heading2"]))
    info_table = Table(
        [
            ["Trường", "Giá trị"],
            ["Bệnh", disease_label],
            ["Khu vực", region_text],
            ["Kỳ dự báo", month_label],
            ["Số ca dự báo", f"{fc.predicted_cases:,}"],
            ["Ca nền (TB cùng kỳ)", f"{int(fc.baseline_cases or 0):,}"],
            ["Hệ số thời tiết", f"{float(fc.weather_factor or 1):.3f}"],
            ["Hệ số xu hướng", f"{float(fc.trend_factor or 1):.3f}"],
            ["Mức nguy cơ", risk_label_map.get(fc.risk_level or "", "—")],
            [
                "Khoảng tin cậy",
                f"{int(fc.confidence_lower or 0):,} - {int(fc.confidence_upper or 0):,}",
            ],
        ],
        colWidths=[6 * cm, 11 * cm],
        repeatRows=1,
    )
    style_info = list(base_style)
    # Highlight risk row
    risk_row = 8  # 0=header, 1..7 above, risk = row 8
    risk_color = {
        "low": colors.HexColor("#16A34A"),
        "medium": colors.HexColor("#D97706"),
        "high": colors.HexColor("#DC2626"),
        "very_high": colors.HexColor("#B91C1C"),
    }.get(fc.risk_level or "", colors.black)
    style_info.append(("TEXTCOLOR", (1, risk_row), (1, risk_row), risk_color))
    style_info.append(("FONTNAME", (1, risk_row), (1, risk_row), PDF_FONT_BOLD))
    info_table.setStyle(TableStyle(style_info))
    story.append(info_table)
    story.append(Spacer(1, 0.4 * cm))

    # II. Giải thích mô hình
    story.append(Paragraph("<b>II. Giải thích mô hình</b>", styles["Heading2"]))
    explanation = fc.explanation or "Không có giải thích."
    # Nếu có nhiều bullet ngăn cách " | " thì tách
    bullets = [b.strip() for b in (explanation or "").split("|") if b.strip()]
    if not bullets:
        bullets = [explanation]
    for b in bullets:
        story.append(Paragraph(f"• {b}", styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    # III. So sánh thực tế (nếu đã có)
    story.append(Paragraph("<b>III. Đánh giá độ chính xác</b>", styles["Heading2"]))
    if fc.actual_cases is not None:
        cmp_table = Table(
            [
                ["Số ca dự báo", "Số ca thực tế", "Độ lệch"],
                [
                    f"{fc.predicted_cases:,}",
                    f"{int(fc.actual_cases):,}",
                    f"{float(fc.deviation_pct or 0):+.1f}%",
                ],
            ],
            colWidths=[5 * cm, 5 * cm, 4 * cm],
            repeatRows=1,
        )
        cmp_table.setStyle(TableStyle(base_style))
        story.append(cmp_table)
    else:
        story.append(Paragraph(
            "Chưa có số ca thực tế để đánh giá. Hãy nhập số ca thực tế "
            "để hệ thống tính độ lệch.",
            styles["Normal"],
        ))

    doc.build(story)
    buf.seek(0)
    filename = f"forecast_{fc.id}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
