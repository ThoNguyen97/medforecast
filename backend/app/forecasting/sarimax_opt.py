"""Thành viên SARIMAX của ensemble (cần statsmodels), thời tiết trễ làm exog.

Fit lỗi thì predict báo lỗi để Ensemble ghi lý do; không dùng is_covid làm exog vì sai phân đã chịu được cú sốc mức nền.
"""
from __future__ import annotations
from typing import Optional
import numpy as np
import pandas as pd

WCOLS = ["temp", "humidity", "rainfall"]
BURN_IN = 13   # s + d
MIN_OBS = 26   # hai chu kỳ mùa + sai phân


class SarimaxForecaster:
    """SARIMAX(1,1,1)(1,0,0,12) trên log1p(cases), exog = thời tiết trễ 1 tháng."""
    fitted = False

    def __init__(self, use_weather: bool = True, weather_lag: int = 1,
                 smearing: bool = True):
        self.use_weather = use_weather
        self.weather_lag = weather_lag
        self.smearing = smearing
        self._ok = False
        self._smear = 1.0
        self._used_exog = False

    @property
    def name(self) -> str:
        return "sarimax_weather" if self._used_exog else "sarimax"

    def _exog(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        """Thời tiết trễ 1 tháng chuẩn hoá z-score; exog thô làm hệ số phình khi không hội tụ và exp() thổi dự báo."""
        if not (self.use_weather and all(c in df.columns for c in WCOLS)):
            return None
        if df[WCOLS].notna().sum().min() < 12:
            return None
        cols, last = [], []
        self._ex_mu, self._ex_sd = [], []
        for c in WCOLS:
            raw = pd.to_numeric(df[c], errors="coerce")
            v = raw.shift(self.weather_lag)
            v = v.fillna(v.mean() if v.notna().any() else 0.0).to_numpy(float)
            mu, sd = float(v.mean()), float(v.std())
            sd = sd if sd > 0 else 1.0
            self._ex_mu.append(mu); self._ex_sd.append(sd)
            cols.append((v - mu) / sd)
            # Bước dự báo n cần w[n − lag] = dòng thứ `lag` từ cuối, chưa shift.
            r_last = raw.iloc[-self.weather_lag] if len(raw) >= self.weather_lag else np.nan
            r_last = float(r_last) if pd.notna(r_last) else mu
            last.append((r_last - mu) / sd)
        self._last_exog_next = np.asarray(last, float)[None, :]
        return np.column_stack(cols)

    def fit(self, df: pd.DataFrame):
        self._ok = False
        self.fitted = False
        try:
            from statsmodels.tsa.statespace.sarimax import SARIMAX
            y = np.log1p(df["cases"].to_numpy(float))
            if len(y) < MIN_OBS:
                # statsmodels ném IndexError khó hiểu trên chuỗi ngắn.
                raise ValueError(f"chuỗi {len(y)} tháng < {MIN_OBS}, quá ngắn cho SARIMAX mùa 12")
            exog = self._exog(df)
            self._used_exog = exog is not None
            self._last_exog = self._last_exog_next if exog is not None else None
            model = SARIMAX(y, exog=exog, order=(1, 1, 1),
                            seasonal_order=(1, 0, 0, 12),
                            enforce_stationarity=False, enforce_invertibility=False)
            self._res = model.fit(disp=False)
            resid = np.asarray(self._res.resid, float)
            if self.smearing and len(resid) > BURN_IN + 3:
                r = np.clip(resid[BURN_IN:], -3.0, 3.0)
                self._smear = float(np.mean(np.exp(r)))
            else:
                self._smear = 1.0
            self._ok = True
            self.fitted = True
        except Exception:
            self._ok = False
            self.fitted = False
            raise
        return self

    def predict(self, next_month: int) -> float:
        if not self._ok:
            raise RuntimeError("SARIMAX chưa fit thành công")
        fc = self._res.forecast(steps=1, exog=self._last_exog)
        eta = float(np.asarray(fc)[0])
        return float(max(0.0, np.exp(eta) * self._smear - 1.0))
