"""ỨNG VIÊN ĐỐI CHỨNG — XGBoost và Prophet (tuỳ chọn, chỉ để đo; 11/09/2026).

Vì sao có file này: câu hỏi "sao không thử XGBoost / Prophet" phải được trả
lời bằng số đo trên cùng giao thức walk-forward, không phải bằng lập luận.
Hai lớp dưới đây theo đúng giao diện thành viên (fit/predict/name/fitted) để
cắm vào bench (`combine_effect` / `replay`) và chấm y hệt các thành viên khác.

KHÔNG nằm trong `build_default_ensemble` trừ khi `cfg.use_xgb` / `cfg.use_prophet`
bật — và chỉ bật khi ket_hop.csv chứng minh có ích.

XGBoost: hồi quy cây trên đặc trưng [lag1, lag2, lag3, lag12, tháng (sin/cos),
xu hướng, thời tiết trễ 1–2] ở thang log1p; tham số nhỏ vì chuỗi ~70–90 điểm.
Prophet: mùa năm + xu hướng đứt gãy tự phát hiện, trên log1p; không thêm
regressor để so "Prophet mặc định" như thường được nêu.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WCOLS = ["temp", "humidity", "rainfall"]
LAGS = (1, 2, 3, 12)


class XgbForecaster:
    name = "xgb"
    fitted = False
    MIN_OBS = 30

    def __init__(self, use_weather: bool = True, n_estimators: int = 200,
                 max_depth: int = 3, learning_rate: float = 0.05):
        self.use_weather = use_weather
        self.params = dict(n_estimators=n_estimators, max_depth=max_depth,
                           learning_rate=learning_rate, subsample=0.9,
                           colsample_bytree=0.9, min_child_weight=2,
                           reg_lambda=1.0, objective="reg:squarederror",
                           random_state=0, verbosity=0)

    def _features(self, y_log: np.ndarray, months: np.ndarray, w: np.ndarray | None,
                  i: int) -> list[float] | None:
        """Đặc trưng cho quan sát i (dùng y trước i, thời tiết trễ)."""
        if i < max(LAGS):
            return None
        f = [y_log[i - L] for L in LAGS]
        m = months[i]
        f += [np.sin(2 * np.pi * m / 12), np.cos(2 * np.pi * m / 12), i / 12.0]
        if w is not None:
            for L in (1, 2):
                f += list(w[i - L])
        return f

    def fit(self, df: pd.DataFrame):
        from xgboost import XGBRegressor
        y = df["cases"].to_numpy(float)
        if len(y) < self.MIN_OBS:
            raise ValueError(f"chuỗi {len(y)} tháng < {self.MIN_OBS}, quá ngắn cho XGBoost")
        y_log = np.log1p(y)
        months = df["month"].to_numpy(int)
        w = None
        if self.use_weather and all(c in df.columns for c in WCOLS) and df[WCOLS].notna().sum().min() >= 12:
            w = df[WCOLS].apply(pd.to_numeric, errors="coerce").ffill().bfill().to_numpy(float)
            self._w_mu, self._w_sd = w.mean(0), w.std(0) + 1e-9
            w = (w - self._w_mu) / self._w_sd
        X, t = [], []
        for i in range(len(y)):
            f = self._features(y_log, months, w, i)
            if f is not None and (w is None or i >= 2):
                X.append(f); t.append(y_log[i])
        self.model = XGBRegressor(**self.params).fit(np.asarray(X), np.asarray(t))
        self._y_log, self._months, self._w = y_log, months, w
        self.fitted = True
        return self

    def predict(self, next_month: int) -> float:
        i = len(self._y_log)
        y_ext = np.append(self._y_log, 0.0); m_ext = np.append(self._months, next_month)
        w_ext = None if self._w is None else np.vstack([self._w, self._w[-1]])
        f = self._features(y_ext, m_ext, w_ext, i)
        pred = float(np.expm1(self.model.predict(np.asarray([f]))[0]))
        return float(max(0.0, pred))


class ProphetForecaster:
    name = "prophet"
    fitted = False
    MIN_OBS = 24

    def __init__(self, exclude_covid: bool = True):
        self.exclude_covid = exclude_covid

    def fit(self, df: pd.DataFrame):
        import logging
        logging.getLogger("prophet").setLevel(logging.ERROR)
        logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
        from prophet import Prophet
        y = df["cases"].to_numpy(float)
        if len(y) < self.MIN_OBS:
            raise ValueError(f"chuỗi {len(y)} tháng < {self.MIN_OBS}, quá ngắn cho Prophet")
        ds = pd.to_datetime(df["period"].astype(str) + "-01")
        d = pd.DataFrame({"ds": ds, "y": np.log1p(y)})
        if self.exclude_covid and "is_covid" in df:
            d = d[~df["is_covid"].to_numpy(bool)]
        self.model = Prophet(yearly_seasonality=True, weekly_seasonality=False,
                             daily_seasonality=False, seasonality_mode="additive",
                             changepoint_prior_scale=0.05)
        self.model.fit(d)
        self._last = ds.iloc[-1]
        self.fitted = True
        return self

    def predict(self, next_month: int) -> float:   # noqa: ARG002
        nxt = (self._last + pd.offsets.MonthBegin(1))
        fc = self.model.predict(pd.DataFrame({"ds": [nxt]}))
        pred = float(np.expm1(fc["yhat"].iloc[0]))
        return float(max(0.0, pred))
