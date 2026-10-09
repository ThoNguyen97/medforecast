"""Thành viên ETS Holt-Winters của ensemble (cần statsmodels).

Xu hướng cộng giảm chấn, mùa cộng 12, khớp trên log1p(cases); tháng COVID nội suy vì ETS cần chuỗi liên tục.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_OBS = 24   # hai chu kỳ mùa


class EtsForecaster:
    """Holt-Winters cộng, xu hướng giảm chấn, mùa 12, trên log1p."""
    name = "ets"
    fitted = False

    def __init__(self, exclude_covid: bool = True, smearing: bool = False):
        self.exclude_covid = exclude_covid
        self.smearing = smearing
        self._res = None
        self._smear = 1.0

    def fit(self, df: pd.DataFrame):
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        y = df["cases"].to_numpy(float)
        if len(y) < MIN_OBS:
            raise ValueError(f"chuỗi {len(y)} tháng < {MIN_OBS}, quá ngắn cho ETS mùa 12")
        t = np.log1p(y)
        if self.exclude_covid and "is_covid" in df:
            cov = df["is_covid"].to_numpy(bool)
            if cov.any() and (~cov).sum() >= 14:
                s = pd.Series(t).where(~cov)
                t = s.interpolate(limit_direction="both").to_numpy()
        model = ExponentialSmoothing(t, trend="add", damped_trend=True,
                                     seasonal="add", seasonal_periods=12,
                                     initialization_method="estimated")
        self._res = model.fit(optimized=True)
        if self.smearing:
            r = np.asarray(self._res.resid, float)[12:]
            r = r[np.isfinite(r)]
            self._smear = float(np.mean(np.exp(r))) if len(r) else 1.0
        self.fitted = True
        return self

    def predict(self, next_month: int) -> float:   # noqa: ARG002
        if self._res is None:
            raise RuntimeError("ETS chưa fit")
        eta = float(np.ravel(self._res.forecast(1))[0])
        pred = np.expm1(eta) * self._smear
        if not np.isfinite(pred):
            raise ValueError(f"ETS trả giá trị không hữu hạn: {pred}")
        return float(max(0.0, pred))
