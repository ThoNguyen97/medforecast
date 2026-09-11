"""SARIMAX (tùy chọn) — chỉ hoạt động nếu đã cài `statsmodels`.

build_default_ensemble() tự thử import lớp này; nếu statsmodels chưa cài thì bỏ qua
(mô hình numpy vẫn chạy). Dùng biến thời tiết (có độ trễ) làm exogenous nếu có.

Sửa 11/09/2026:
  M8  smearing trên phần dư thang log (bỏ 13 quan sát đầu — chu kỳ mùa + sai
      phân — vì phần dư ở đó chưa ổn định).
  M6  cờ `fitted` + `name` để Ensemble ghi lại ai đóng góp; `_ok=False` sau
      fit lỗi nghĩa là KHÔNG dự báo — không âm thầm trả trung bình 6 tháng
      như bản cũ (giá trị đó không phải SARIMAX, không được mang tên SARIMAX).
  Ghi chú: is_covid KHÔNG phải exog ở đây. Các thành viên khác dùng nó để
  loại tháng COVID; SARIMAX (có sai phân) chịu được cú sốc mức nền hơn. Nếu
  muốn thêm làm exog thì đo lại — không thêm mà không đo.
"""
from __future__ import annotations
from typing import Optional
import numpy as np
import pandas as pd

WCOLS = ["temp", "humidity", "rainfall"]
BURN_IN = 13   # s + d = 12 + 1


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
        if not (self.use_weather and all(c in df.columns for c in WCOLS)):
            return None
        if df[WCOLS].notna().sum().min() < 12:
            return None                                   # chưa đủ thời tiết
        cols = []
        for c in WCOLS:
            v = pd.to_numeric(df[c], errors="coerce").shift(self.weather_lag)
            v = v.fillna(v.mean() if v.notna().any() else 0.0)
            cols.append(v.to_numpy(float))
        return np.column_stack(cols)

    def fit(self, df: pd.DataFrame):
        self._ok = False
        self.fitted = False
        try:
            from statsmodels.tsa.statespace.sarimax import SARIMAX  # lazy
            y = np.log1p(df["cases"].to_numpy(float))
            exog = self._exog(df)
            self._used_exog = exog is not None
            self._last_exog = exog[-1:] if exog is not None else None
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
            self.fitted = False               # Ensemble sẽ bỏ qua và ghi lý do
            raise
        return self

    def predict(self, next_month: int) -> float:
        if not self._ok:
            raise RuntimeError("SARIMAX chưa fit thành công")
        fc = self._res.forecast(steps=1, exog=self._last_exog)
        eta = float(np.asarray(fc)[0])
        return float(max(0.0, np.exp(eta) * self._smear - 1.0))
