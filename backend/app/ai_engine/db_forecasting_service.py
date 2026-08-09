"""
DB Forecasting Service — train mô hình dự báo theo tháng TRỰC TIẾP từ database.

Khác với ForecastingService (đọc CSV) và forecast_analysis.py (heuristic thuần),
service này:
- Đọc số ca bệnh theo tháng từ bảng disease_cases (4 bệnh ICD: J20, J06, J02, J01)
- Ghép dữ liệu thời tiết thật từ bảng environmental_data (nguồn Open-Meteo)
- Train MonthlyForecaster cho từng bệnh → học tương quan thời tiết + xu hướng
- Tính & lưu độ chính xác (MAE, RMSE, MAPE, R²) cho mỗi bệnh

Dữ liệu được gộp TOÀN QUỐC (cộng tất cả tỉnh/thành theo tháng) khi region=None,
hoặc lọc theo 1 tỉnh nếu truyền region.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.disease_case import DiseaseCase
from app.models.environmental_data import EnvironmentalData
from app.utils.province_alias import province_aliases

from .monthly_forecaster import MonthlyForecaster

logger = logging.getLogger(__name__)

# 4 bệnh hô hấp dùng cho dự báo
DISEASE_ICDS: List[str] = ["J20", "J06", "J02", "J01"]

ICD_LABELS: Dict[str, str] = {
    "J20": "Viêm phế quản cấp",
    "J06": "Nhiễm trùng đường hô hấp trên cấp",
    "J02": "Viêm họng cấp",
    "J01": "Viêm xoang cấp",
}


class DBForecastingService:
    """Train & dự báo MonthlyForecaster từ dữ liệu trong database."""

    def __init__(self, db: Session):
        self.db = db

    # ── Đọc dữ liệu từ DB ────────────────────────────────────────────────

    def _load_monthly_cases(
        self, icd_code: str, region: Optional[str]
    ) -> pd.DataFrame:
        """Số ca theo tháng cho 1 bệnh.

        Returns DataFrame [YearMonth(Period), year, month, total_cases].
        Gộp tất cả tỉnh nếu region=None.
        """
        q = self.db.query(
            extract("year", DiseaseCase.recorded_at).label("year"),
            extract("month", DiseaseCase.recorded_at).label("month"),
            func.sum(DiseaseCase.case_count).label("total_cases"),
        ).filter(DiseaseCase.icd_code == icd_code)

        if region:
            q = q.filter(DiseaseCase.location.in_(province_aliases(region)))

        q = q.group_by("year", "month").order_by("year", "month")
        rows = q.all()

        records = [
            {
                "year": int(r.year),
                "month": int(r.month),
                "total_cases": float(r.total_cases or 0),
            }
            for r in rows
        ]
        df = pd.DataFrame(records)
        if not df.empty:
            df["YearMonth"] = df.apply(
                lambda x: pd.Period(year=int(x["year"]), month=int(x["month"]), freq="M"),
                axis=1,
            )
        return df

    def _load_monthly_weather(self, region: Optional[str]) -> pd.DataFrame:
        """Thời tiết trung bình theo tháng (nguồn Open-Meteo trong environmental_data).

        Returns DataFrame [YearMonth(Period), temp, humidity, rainfall, aqi].
        """
        q = self.db.query(
            extract("year", EnvironmentalData.recorded_at).label("year"),
            extract("month", EnvironmentalData.recorded_at).label("month"),
            func.avg(EnvironmentalData.temperature).label("temp"),
            func.avg(EnvironmentalData.humidity).label("humidity"),
            func.avg(EnvironmentalData.rainfall).label("rainfall"),
            func.avg(EnvironmentalData.air_quality_index).label("aqi"),
        )
        if region:
            q = q.filter(EnvironmentalData.location.in_(province_aliases(region)))

        q = q.group_by("year", "month").order_by("year", "month")
        rows = q.all()

        records = []
        for r in rows:
            records.append(
                {
                    "year": int(r.year),
                    "month": int(r.month),
                    "temp": float(r.temp) if r.temp is not None else None,
                    "humidity": float(r.humidity) if r.humidity is not None else None,
                    "rainfall": float(r.rainfall) if r.rainfall is not None else None,
                    "aqi": float(r.aqi) if r.aqi is not None else None,
                }
            )
        df = pd.DataFrame(records)
        if not df.empty:
            df["YearMonth"] = df.apply(
                lambda x: pd.Period(year=int(x["year"]), month=int(x["month"]), freq="M"),
                axis=1,
            )
        return df

    # ── Train ────────────────────────────────────────────────────────────

    def train_all(
        self, region: Optional[str] = None, version: str = "latest"
    ) -> Dict[str, dict]:
        """Train mô hình cho cả 4 bệnh. Trả về metrics từng bệnh.

        version: hậu tố file model. Mặc định 'latest'. Nếu region được truyền,
        dùng version riêng để không đè model toàn quốc.
        """
        weather_df = self._load_monthly_weather(region)
        results: Dict[str, dict] = {}

        for icd in DISEASE_ICDS:
            cases_df = self._load_monthly_cases(icd, region)
            n_months = len(cases_df)

            if n_months < 4:
                results[icd] = {
                    "status": "skipped",
                    "reason": f"Chỉ có {n_months} tháng dữ liệu (cần ≥ 4)",
                    "disease_label": ICD_LABELS.get(icd, icd),
                    "n_samples": n_months,
                }
                continue

            try:
                forecaster = MonthlyForecaster(disease_type=icd)
                metrics = forecaster.train(cases_df, weather_df)
                forecaster.save(version=self._version_for(region, version))

                results[icd] = {
                    "status": "trained",
                    "disease_label": ICD_LABELS.get(icd, icd),
                    "mae": round(metrics.get("mae", 0), 2),
                    "rmse": round(metrics.get("rmse", 0), 2),
                    "mape": round(metrics.get("mape", 0), 2),
                    "r2": round(metrics.get("r2", 0), 3),
                    "n_samples": metrics.get("n_samples", 0),
                    "weather_correlations": {
                        k: round(v, 3)
                        for k, v in (metrics.get("weather_correlations") or {}).items()
                    },
                }
                logger.info(
                    "Trained %s: MAE=%.1f R²=%.3f (n=%d)",
                    icd, metrics.get("mae", 0), metrics.get("r2", 0),
                    metrics.get("n_samples", 0),
                )
            except Exception as exc:
                logger.error("Train %s failed: %s", icd, exc)
                results[icd] = {
                    "status": "error",
                    "reason": str(exc),
                    "disease_label": ICD_LABELS.get(icd, icd),
                }

        return results

    @staticmethod
    def _version_for(region: Optional[str], version: str) -> str:
        """Sinh version có gắn region để model các tỉnh không đè nhau."""
        if not region:
            return version
        safe = "".join(c for c in region if c.isalnum())[:20] or "region"
        return f"{version}_{safe}"

    # ── Predict ──────────────────────────────────────────────────────────

    def analyze(
        self,
        icd_code: str,
        target_month: int,
        target_year: int,
        region: Optional[str] = None,
        forecast_weather: Optional[Dict[str, float]] = None,
    ) -> dict:
        """Train trong bộ nhớ + dự báo ngay trong 1 lần gọi.

        Dùng cho luồng "bấm Phân tích là train + dự báo luôn" — không cần
        lưu/đọc file model, luôn dùng dữ liệu mới nhất trong DB.
        """
        cases_df = self._load_monthly_cases(icd_code, region)
        n_months = len(cases_df)
        if n_months < 4:
            raise ValueError(
                f"Chỉ có {n_months} tháng dữ liệu cho {icd_code} "
                f"(cần ≥ 4 tháng để huấn luyện)."
            )

        weather_df = self._load_monthly_weather(region)

        # Train mô hình ngay trên dữ liệu hiện tại
        forecaster = MonthlyForecaster(disease_type=icd_code)
        forecaster.train(cases_df, weather_df)

        # Lấy thống kê gần đây để dự báo
        prev_month_cases, same_month_prev_year, recent_3m = self._recent_stats(
            cases_df, target_month, target_year
        )
        if forecast_weather is None:
            forecast_weather = self._weather_estimate_for_month(region, target_month)

        result = forecaster.predict(
            prev_month_cases=prev_month_cases,
            prev_month_weather=forecast_weather,
            forecast_weather=forecast_weather,
            target_month=target_month,
            same_month_prev_year_cases=same_month_prev_year,
            recent_3month_avg=recent_3m,
        )
        result["disease_label"] = ICD_LABELS.get(icd_code, icd_code)
        result["region"] = region or "Toàn quốc"
        result["target_year"] = target_year
        result["forecast_weather"] = forecast_weather
        return result

    def predict(
        self,
        icd_code: str,
        target_month: int,
        target_year: int,
        region: Optional[str] = None,
        forecast_weather: Optional[Dict[str, float]] = None,
        version: str = "latest",
    ) -> dict:
        """Dự báo 1 bệnh bằng model đã train. Tự load model từ disk."""
        forecaster = MonthlyForecaster(disease_type=icd_code)
        loaded = forecaster.load(version=self._version_for(region, version))
        if not loaded:
            raise FileNotFoundError(
                f"Chưa có model cho {icd_code}"
                f"{' khu vực ' + region if region else ''}. "
                f"Hãy train trước (POST /forecast/train)."
            )

        # Lấy số ca tháng trước + cùng kỳ năm trước + TB 3 tháng từ DB
        cases_df = self._load_monthly_cases(icd_code, region)
        prev_month_cases, same_month_prev_year, recent_3m = self._recent_stats(
            cases_df, target_month, target_year
        )

        # Thời tiết dự báo: nếu không truyền, dùng trung bình lịch sử cùng tháng
        if forecast_weather is None:
            forecast_weather = self._weather_estimate_for_month(region, target_month)

        result = forecaster.predict(
            prev_month_cases=prev_month_cases,
            prev_month_weather=forecast_weather,
            forecast_weather=forecast_weather,
            target_month=target_month,
            same_month_prev_year_cases=same_month_prev_year,
            recent_3month_avg=recent_3m,
        )
        result["disease_label"] = ICD_LABELS.get(icd_code, icd_code)
        result["region"] = region or "Toàn quốc"
        result["target_year"] = target_year
        result["forecast_weather"] = forecast_weather
        return result

    @staticmethod
    def _recent_stats(cases_df: pd.DataFrame, target_month: int, target_year: int):
        """Trả về (prev_month_cases, same_month_prev_year, recent_3month_avg)."""
        if cases_df.empty:
            return 0, None, None

        df = cases_df.sort_values("YearMonth").reset_index(drop=True)

        # Tháng trước target
        pm = target_month - 1 or 12
        py = target_year if target_month > 1 else target_year - 1
        prev = df[(df["year"] == py) & (df["month"] == pm)]["total_cases"]
        prev_month_cases = int(prev.iloc[0]) if len(prev) else int(df["total_cases"].iloc[-1])

        # Cùng kỳ năm trước
        same = df[(df["year"] == target_year - 1) & (df["month"] == target_month)]["total_cases"]
        same_month_prev_year = int(same.iloc[0]) if len(same) else None

        # TB 3 tháng gần nhất (so với target)
        recent = df.tail(3)["total_cases"]
        recent_3month_avg = float(recent.mean()) if len(recent) else None

        return prev_month_cases, same_month_prev_year, recent_3month_avg

    def _weather_estimate_for_month(
        self, region: Optional[str], month: int
    ) -> Dict[str, float]:
        """Ước tính thời tiết tháng từ trung bình lịch sử Open-Meteo cùng tháng."""
        weather_df = self._load_monthly_weather(region)
        if weather_df.empty:
            return {}
        same = weather_df[weather_df["month"] == month]
        src = same if len(same) else weather_df
        return {
            "temp": float(src["temp"].mean()) if src["temp"].notna().any() else None,
            "humidity": float(src["humidity"].mean()) if src["humidity"].notna().any() else None,
            "rainfall": float(src["rainfall"].mean()) if src["rainfall"].notna().any() else None,
            "aqi": float(src["aqi"].mean()) if src["aqi"].notna().any() else None,
        }
