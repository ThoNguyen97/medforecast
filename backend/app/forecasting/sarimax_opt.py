"""SARIMAX (tùy chọn) — chỉ hoạt động nếu đã cài `statsmodels`.

build_default_ensemble() tự thử import lớp này; nếu statsmodels chưa cài thì bỏ qua
(mô hình numpy vẫn chạy). Dùng biến thời tiết (có độ trễ) làm exogenous nếu có.
"""
from __future__ import annotations
from typing import Optional
import numpy as np
import pandas as pd

WCOLS = ["temp", "humidity", "rainfall"]


class SarimaxForecaster:
    """SARIMAX(1,1,1)(1,0,0,12) trên log1p(cases), exog = thời tiết trễ 1 tháng.

    An toàn: mọi lỗi (thiếu thư viện, không hội tụ) → fallback trung bình gần đây,
    không làm hỏng ensemble.
    """
    def __init__(self, use_weather: bool = True, weather_lag: int = 1):
        self.use_weather = use_weather
        self.weather_lag = weather_lag
        self._ok = False

    def _exog(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        if not (self.use_weather and all(c in df.columns for c in WCOLS)):
            return None
        cols = []
        for c in WCOLS:
            v = pd.to_numeric(df[c], errors="coerce").shift(self.weather_lag)
            v = v.fillna(v.mean() if v.notna().any() else 0.0)
            cols.append(v.to_numpy(float))
        return np.column_stack(cols)

    def fit(self, df: pd.DataFrame):
        self._fallback = float(df["cases"].tail(6).mean()) if len(df) else 0.0
        try:
            from statsmodels.tsa.statespace.sarimax import SARIMAX  # lazy
            y = np.log1p(df["cases"].to_numpy(float))
            exog = self._exog(df)
            self._last_exog = exog[-1:] if exog is not None else None
            model = SARIMAX(y, exog=exog, order=(1, 1, 1),
                            seasonal_order=(1, 0, 0, 12),
                            enforce_stationarity=False, enforce_invertibility=False)
            self._res = model.fit(disp=False)
            self._ok = True
        except Exception:
            self._ok = False
        return self

    def predict(self, next_month: int) -> float:
        if not self._ok:
            return float(max(0.0, self._fallback))
        try:
            fc = self._res.forecast(steps=1, exog=self._last_exog)
            return float(max(0.0, np.expm1(float(np.asarray(fc)[0]))))
        except Exception:
            return float(max(0.0, self._fallback))
