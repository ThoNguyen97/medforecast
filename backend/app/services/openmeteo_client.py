"""Open-Meteo public API client.

Open-Meteo (https://open-meteo.com) cung cấp dữ liệu thời tiết miễn phí cho mục
đích phi thương mại, không cần API key, có CORS, license CC BY 4.0.

Module này wrap 3 API:
- Forecast API:        https://api.open-meteo.com/v1/forecast
- Historical Archive:  https://archive-api.open-meteo.com/v1/archive
- Air Quality:         https://air-quality-api.open-meteo.com/v1/air-quality

Toạ độ tỉnh/thành VN được hard-code (không gọi geocoding để tránh dependency).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


# Toạ độ trung tâm cho các tỉnh/thành phổ biến tại VN (đủ cho demo TP.HCM + lân cận)
PROVINCE_COORDS: Dict[str, Tuple[float, float]] = {
    "TP. Hồ Chí Minh": (10.7769, 106.7009),
    "Thành phố Hồ Chí Minh": (10.7769, 106.7009),
    "Hồ Chí Minh": (10.7769, 106.7009),
    "Hà Nội": (21.0285, 105.8542),
    "Đà Nẵng": (16.0544, 108.2022),
    "Bình Dương": (11.1733, 106.6660),
    "Đồng Nai": (10.9447, 106.8244),
    "Long An": (10.6957, 106.2431),
    "Bà Rịa - Vũng Tàu": (10.5417, 107.2429),
    "Tây Ninh": (11.3677, 106.1199),
    "Tiền Giang": (10.4493, 106.3420),
    "Cần Thơ": (10.0452, 105.7469),
}

# Endpoints
URL_FORECAST = "https://api.open-meteo.com/v1/forecast"
URL_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
URL_AIR_QUALITY = "https://air-quality-api.open-meteo.com/v1/air-quality"

DEFAULT_TIMEOUT = 15


class OpenMeteoClient:
    """Client gọi Open-Meteo public API."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def lookup_coords(province: str) -> Optional[Tuple[float, float]]:
        """Tìm lat/lon từ tên tỉnh/thành (case-insensitive, fuzzy)."""
        if not province:
            return None
        key = province.strip()
        if key in PROVINCE_COORDS:
            return PROVINCE_COORDS[key]
        # Fallback: bỏ qua dấu tiếng Việt (đơn giản) và so sánh case-insensitive
        norm = key.lower()
        for name, coords in PROVINCE_COORDS.items():
            if name.lower() == norm or norm in name.lower() or name.lower() in norm:
                return coords
        return None

    def _get(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug("Open-Meteo GET %s params=%s", url, params)
        resp = requests.get(url, params=params, timeout=self.timeout)
        if not resp.ok:
            raise RuntimeError(
                f"Open-Meteo {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json()

    # ── Forecast (16-day) ──────────────────────────────────────────────────

    def get_daily_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 16,
    ) -> List[Dict[str, Any]]:
        """Forecast hằng ngày (max 16 ngày).

        Returns list[{date, temp_max, temp_min, temp_mean, rainfall, humidity}]
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join([
                "temperature_2m_max",
                "temperature_2m_min",
                "temperature_2m_mean",
                "precipitation_sum",
                "relative_humidity_2m_max",
                "relative_humidity_2m_min",
            ]),
            "timezone": "Asia/Bangkok",
            "forecast_days": min(max(forecast_days, 1), 16),
        }
        data = self._get(URL_FORECAST, params)
        daily = data.get("daily", {}) or {}
        times = daily.get("time", [])
        out: List[Dict[str, Any]] = []
        for i, t in enumerate(times):
            tmax = _safe_get(daily, "temperature_2m_max", i)
            tmin = _safe_get(daily, "temperature_2m_min", i)
            tmean = _safe_get(daily, "temperature_2m_mean", i)
            if tmean is None and tmax is not None and tmin is not None:
                tmean = (tmax + tmin) / 2
            hmax = _safe_get(daily, "relative_humidity_2m_max", i)
            hmin = _safe_get(daily, "relative_humidity_2m_min", i)
            hmean = None
            if hmax is not None and hmin is not None:
                hmean = (hmax + hmin) / 2
            out.append({
                "date": t,
                "temperature": tmean,
                "temperature_max": tmax,
                "temperature_min": tmin,
                "humidity": hmean,
                "rainfall": _safe_get(daily, "precipitation_sum", i),
            })
        return out

    # ── Historical archive ─────────────────────────────────────────────────

    def get_historical_daily(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """Lịch sử hằng ngày (đến ~80 năm).

        Returns list[{date, temperature, humidity, rainfall}]
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": ",".join([
                "temperature_2m_mean",
                "relative_humidity_2m_mean",
                "precipitation_sum",
            ]),
            "timezone": "Asia/Bangkok",
        }
        data = self._get(URL_ARCHIVE, params)
        daily = data.get("daily", {}) or {}
        times = daily.get("time", [])
        return [
            {
                "date": t,
                "temperature": _safe_get(daily, "temperature_2m_mean", i),
                "humidity": _safe_get(daily, "relative_humidity_2m_mean", i),
                "rainfall": _safe_get(daily, "precipitation_sum", i),
            }
            for i, t in enumerate(times)
        ]

    # ── Air Quality ────────────────────────────────────────────────────────

    def get_air_quality_daily(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 5,
        past_days: int = 0,
    ) -> List[Dict[str, Any]]:
        """AQI + PM2.5 hằng ngày (aggregated từ hourly).
        
        Note: forecast_days và past_days bị giới hạn bởi API.
        Để lấy historical data dài hơn, dùng get_air_quality_historical().
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "us_aqi,pm2_5",
            "timezone": "Asia/Bangkok",
            "forecast_days": min(max(forecast_days, 1), 7),
            "past_days": max(past_days, 0),
        }
        data = self._get(URL_AIR_QUALITY, params)
        return self._aggregate_hourly_to_daily(data)

    def get_air_quality_historical(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """AQI + PM2.5 historical data cho date range cụ thể."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "us_aqi,pm2_5",
            "timezone": "Asia/Bangkok",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        data = self._get(URL_AIR_QUALITY, params)
        return self._aggregate_hourly_to_daily(data)

    def _aggregate_hourly_to_daily(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """AQI + PM2.5 hằng ngày (aggregated từ hourly).
        
        Note: forecast_days và past_days bị giới hạn bởi API.
        Để lấy historical data dài hơn, dùng get_air_quality_historical().
        """
        hourly = data.get("hourly", {}) or {}
        times = hourly.get("time", [])
        aqis = hourly.get("us_aqi", []) or []
        pm25s = hourly.get("pm2_5", []) or []

        # Aggregate hourly → daily (mean)
        buckets: Dict[str, Dict[str, List[float]]] = {}
        for t, aqi, pm in zip(times, aqis, pm25s):
            day = t.split("T")[0] if "T" in t else t
            b = buckets.setdefault(day, {"aqi": [], "pm25": []})
            if aqi is not None:
                b["aqi"].append(float(aqi))
            if pm is not None:
                b["pm25"].append(float(pm))

        out: List[Dict[str, Any]] = []
        for day in sorted(buckets):
            b = buckets[day]
            out.append({
                "date": day,
                "aqi": int(round(sum(b["aqi"]) / len(b["aqi"]))) if b["aqi"] else None,
                "pm25": round(sum(b["pm25"]) / len(b["pm25"]), 2) if b["pm25"] else None,
            })
        return out

    # ── Combined: monthly aggregate cho 1 tháng ────────────────────────────

    def get_monthly_estimate(
        self,
        latitude: float,
        longitude: float,
        target_month: int,
        target_year: int,
    ) -> Dict[str, Any]:
        """Trả về thời tiết trung bình cho 1 tháng cụ thể.

        Tự động chọn:
        - Tháng đã qua / hiện tại đã có data → dùng archive API
        - Tháng tương lai → dùng forecast nếu trong 16 ngày, ngược lại
          dùng cùng tháng năm trước (long-range climatology).
        """
        today = date.today()
        # Mục tiêu: đầu tháng → cuối tháng
        from calendar import monthrange
        first = date(target_year, target_month, 1)
        last = date(target_year, target_month, monthrange(target_year, target_month)[1])

        if last < today:
            # Hoàn toàn trong quá khứ → archive
            return self._aggregate(self.get_historical_daily(latitude, longitude, first, last))

        if first > today + timedelta(days=16):
            # Quá xa tương lai → fallback dùng cùng tháng năm trước
            prev_first = date(target_year - 1, target_month, 1)
            prev_last = date(target_year - 1, target_month, monthrange(target_year - 1, target_month)[1])
            agg = self._aggregate(self.get_historical_daily(latitude, longitude, prev_first, prev_last))
            agg["source"] = "open-meteo-archive-prev-year"
            return agg

        # Hỗn hợp: archive cho phần đã qua + forecast cho phần còn lại
        merged: List[Dict[str, Any]] = []
        if first < today:
            try:
                merged += self.get_historical_daily(latitude, longitude, first, today - timedelta(days=1))
            except Exception as exc:
                logger.warning("Archive partial fetch failed: %s", exc)
        try:
            forecast = self.get_daily_forecast(latitude, longitude, forecast_days=16)
            for d in forecast:
                if first.isoformat() <= d["date"] <= last.isoformat():
                    merged.append(d)
        except Exception as exc:
            logger.warning("Forecast partial fetch failed: %s", exc)

        agg = self._aggregate(merged)
        agg["source"] = "open-meteo-mixed"
        return agg

    @staticmethod
    def _aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not rows:
            return {"temp": None, "humidity": None, "rainfall": None, "days": 0}
        temps = [r.get("temperature") for r in rows if r.get("temperature") is not None]
        hums = [r.get("humidity") for r in rows if r.get("humidity") is not None]
        rains = [r.get("rainfall") for r in rows if r.get("rainfall") is not None]
        return {
            "temp": round(sum(temps) / len(temps), 2) if temps else None,
            "humidity": round(sum(hums) / len(hums), 2) if hums else None,
            "rainfall": round(sum(rains), 2) if rains else None,  # Σ mưa cả tháng
            "days": len(rows),
            "source": "open-meteo",
        }


def _safe_get(d: Dict[str, List[Any]], key: str, idx: int) -> Optional[float]:
    """Lấy phần tử thứ idx của d[key] nếu tồn tại + không null."""
    arr = d.get(key)
    if not arr or idx >= len(arr):
        return None
    v = arr[idx]
    return float(v) if v is not None else None
