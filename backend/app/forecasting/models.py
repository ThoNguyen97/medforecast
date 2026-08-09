"""Các mô hình dự báo chuỗi tháng (numpy/pandas thuần, chạy với dữ liệu nhỏ).

Giao diện chung:
    m.fit(df)            df có cột [month(int 1-12), cases(float), is_covid(bool)]
    m.predict(next_month)  -> float (dự báo 1 bước tới)

SARIMAX là tùy chọn: build_default_ensemble() tự thêm nếu statsmodels có sẵn.
"""
from __future__ import annotations
from typing import List, Optional
import numpy as np
import pandas as pd


def _arrays(df: pd.DataFrame):
    y = df["cases"].to_numpy(dtype=float)
    m = df["month"].to_numpy(dtype=int)
    cov = (df["is_covid"].to_numpy(dtype=bool) if "is_covid" in df
           else np.zeros(len(y), dtype=bool))
    return y, m, cov


class NaiveForecaster:
    """Dự báo = giá trị tháng gần nhất."""
    def fit(self, df):
        self._last = float(df["cases"].iloc[-1]) if len(df) else 0.0
        return self
    def predict(self, next_month: int) -> float:
        return max(0.0, self._last)


class SeasonalNaiveForecaster:
    """Dự báo = số ca cùng tháng của năm gần nhất có dữ liệu."""
    def fit(self, df):
        self._df = df.reset_index(drop=True)
        return self
    def predict(self, next_month: int) -> float:
        same = self._df[self._df["month"] == next_month]["cases"]
        if len(same):
            return max(0.0, float(same.iloc[-1]))
        return max(0.0, float(self._df["cases"].iloc[-1])) if len(self._df) else 0.0


class SeasonalTrendForecaster:
    """Mức + hệ số mùa (nhân) + xu hướng tuyến tính có giảm dần.

    Ước lượng hệ số mùa và xu hướng trên các tháng KHÔNG COVID để tránh méo.
    """
    def __init__(self, exclude_covid: bool = True, damping: float = 0.9):
        self.exclude_covid = exclude_covid
        self.damping = damping

    def fit(self, df):
        y, mo, cov = _arrays(df)
        self.n = len(y)
        idx = np.arange(self.n, dtype=float)
        use = ~cov if (self.exclude_covid and (~cov).sum() >= 6) else np.ones(self.n, bool)
        base_mean = y[use].mean() if use.any() else (y.mean() if self.n else 0.0)
        base_mean = base_mean if base_mean > 0 else 1.0
        # hệ số mùa theo tháng (nhân)
        self.sfac = {}
        for m in range(1, 13):
            sel = use & (mo == m)
            self.sfac[m] = (y[sel].mean() / base_mean) if sel.any() and y[sel].mean() > 0 else 1.0
        s_of = np.array([self.sfac[m] for m in mo])
        des = np.where(s_of > 0, y / s_of, y)
        # xu hướng tuyến tính trên chuỗi đã khử mùa (chỉ dùng non-covid)
        xi, di = idx[use], des[use]
        if len(xi) >= 3:
            self.slope, self.intercept = np.polyfit(xi, di, 1)
        else:
            self.slope, self.intercept = 0.0, (di.mean() if len(di) else base_mean)
        self._last_fit_idx = xi.max() if len(xi) else (self.n - 1)
        return self

    def predict(self, next_month: int) -> float:
        idx = self.n  # bước kế tiếp
        # giảm dần độ ngoại suy của xu hướng để tránh trôi
        horizon = idx - self._last_fit_idx
        eff = self._last_fit_idx + sum(self.damping ** k for k in range(1, int(max(1, horizon)) + 1))
        level = self.intercept + self.slope * eff
        pred = level * self.sfac.get(next_month, 1.0)
        return float(max(0.0, pred))


class PoissonTrendForecaster:
    """Hồi quy log-tuyến tính (xấp xỉ Poisson): log1p(ca) ~ xu hướng + tháng.

    Có chính quy hóa Ridge nhẹ. Ước lượng trên tháng không COVID.
    """
    def __init__(self, exclude_covid: bool = True, lam: float = 1.0):
        self.exclude_covid = exclude_covid
        self.lam = lam

    def _design(self, idx, months):
        n = len(idx)
        X = [np.ones(n), idx / 12.0]
        for m in range(2, 13):               # tháng 1 làm mốc
            X.append((months == m).astype(float))
        return np.vstack(X).T

    def fit(self, df):
        y, mo, cov = _arrays(df)
        self.n = len(y)
        idx = np.arange(self.n, dtype=float)
        use = ~cov if (self.exclude_covid and (~cov).sum() >= 14) else np.ones(self.n, bool)
        X = self._design(idx[use], mo[use])
        t = np.log1p(y[use])
        p = X.shape[1]
        I = np.eye(p); I[0, 0] = 0.0
        try:
            self.beta = np.linalg.solve(X.T @ X + self.lam * I, X.T @ t)
        except np.linalg.LinAlgError:
            self.beta = np.zeros(p); self.beta[0] = t.mean() if len(t) else 0.0
        return self

    def predict(self, next_month: int) -> float:
        X = self._design(np.array([float(self.n)]), np.array([next_month]))
        pred = np.expm1(float(X @ self.beta))
        return float(max(0.0, pred))



class HarmonicPoissonForecaster:
    """Hồi quy log-tuyến tính (Poisson xấp xỉ) với mùa dạng ĐIỀU HÒA (sin/cos)
    + tùy chọn biến THỜI TIẾT có ĐỘ TRỄ.

    Ưu điểm: ít tham số (hợp dữ liệu nhỏ). Thời tiết dùng ở độ trễ (lag) nên
    KHÔNG rò rỉ tương lai — đúng dịch tễ (bệnh bùng sau đợt thời tiết).

    df cần cột: month(int), cases(float), is_covid(bool),
                và nếu use_weather: temp, humidity, rainfall (có thể NaN).
    """
    WCOLS = ["temp", "humidity", "rainfall"]

    def __init__(self, use_weather: bool = False, weather_lags=(1, 2),
                 exclude_covid: bool = True, lam: float = 1.0):
        self.use_weather = use_weather
        self.weather_lags = tuple(weather_lags)
        self.exclude_covid = exclude_covid
        self.lam = lam

    def _has_w(self, df) -> bool:
        return self.use_weather and all(c in df.columns for c in self.WCOLS)

    def fit(self, df):
        df = df.reset_index(drop=True)
        y = df["cases"].to_numpy(float)
        mo = df["month"].to_numpy(int)
        cov = (df["is_covid"].to_numpy(bool) if "is_covid" in df
               else np.zeros(len(y), bool))
        self.n = len(y)
        self._w_hist = {}
        self._w_mean, self._w_std = {}, {}
        has_w = self._has_w(df)
        if has_w:
            for c in self.WCOLS:
                v = pd.to_numeric(df[c], errors="coerce").to_numpy(float)
                self._w_hist[c] = v
                good = v[~np.isnan(v)]
                self._w_mean[c] = float(good.mean()) if len(good) else 0.0
                sd = float(good.std()) if len(good) else 1.0
                self._w_std[c] = sd if sd > 0 else 1.0
        max_lag = max(self.weather_lags) if has_w else 0

        def feat_row(i, month_i):
            row = [1.0, i / max(1, self.n),
                   np.sin(2 * np.pi * month_i / 12.0),
                   np.cos(2 * np.pi * month_i / 12.0)]
            if has_w:
                for c in self.WCOLS:
                    for L in self.weather_lags:
                        j = i - L
                        val = self._w_hist[c][j] if 0 <= j < self.n else np.nan
                        dev = (0.0 if (val is None or np.isnan(val))
                               else (val - self._w_mean[c]) / self._w_std[c])
                        row.append(dev)
            return row

        X, t = [], []
        for i in range(len(df)):
            if i < max_lag:
                continue
            if self.exclude_covid and cov[i] and (~cov).sum() >= max_lag + 6:
                continue
            X.append(feat_row(i, int(mo[i])))
            t.append(np.log1p(y[i]))
        X = np.array(X, float); t = np.array(t, float)
        self._nfeat = X.shape[1] if X.ndim == 2 and len(X) else 4
        if len(t) < self._nfeat + 1:
            self.beta = None
            self._fallback = float(np.log1p(np.mean(y))) if len(y) else 0.0
            return self
        I = np.eye(self._nfeat); I[0, 0] = 0.0
        try:
            self.beta = np.linalg.solve(X.T @ X + self.lam * I, X.T @ t)
        except np.linalg.LinAlgError:
            self.beta = None
            self._fallback = float(t.mean())
        return self

    def predict(self, next_month: int) -> float:
        if self.beta is None:
            return float(max(0.0, np.expm1(getattr(self, "_fallback", 0.0))))
        i = self.n  # bước kế tiếp
        row = [1.0, i / max(1, self.n),
               np.sin(2 * np.pi * next_month / 12.0),
               np.cos(2 * np.pi * next_month / 12.0)]
        if self._has_w_stored():
            for c in self.WCOLS:
                for L in self.weather_lags:
                    j = i - L                      # lag từ dữ liệu ĐÃ QUAN SÁT
                    val = self._w_hist[c][j] if 0 <= j < self.n else np.nan
                    dev = (0.0 if (val is None or np.isnan(val))
                           else (val - self._w_mean[c]) / self._w_std[c])
                    row.append(dev)
        pred = np.expm1(float(np.array(row[:len(self.beta)]) @ self.beta[:len(row)]))
        return float(max(0.0, pred))

    def _has_w_stored(self) -> bool:
        return bool(getattr(self, "_w_hist", {}))


class Ensemble:
    """Trung bình hóa nhiều mô hình (giảm phương sai)."""
    def __init__(self, members: List):
        self.members = members
    def fit(self, df):
        for m in self.members:
            try:
                m.fit(df)
            except Exception:
                pass
        return self
    def predict(self, next_month: int) -> float:
        vals = []
        for m in self.members:
            try:
                vals.append(m.predict(next_month))
            except Exception:
                pass
        return float(np.mean(vals)) if vals else 0.0


def _has_statsmodels() -> bool:
    try:
        import statsmodels.api  # noqa: F401
        return True
    except Exception:
        return False


def build_default_ensemble(use_weather: bool = False) -> Ensemble:
    """SeasonalTrend + PoissonTrend (+ Harmonic-thời-tiết nếu use_weather; + SARIMAX nếu có statsmodels)."""
    members = [SeasonalTrendForecaster(), PoissonTrendForecaster()]
    if use_weather:
        members.append(HarmonicPoissonForecaster(use_weather=True))
    if _has_statsmodels():
        try:
            from .sarimax_opt import SarimaxForecaster  # tùy chọn
            members.append(SarimaxForecaster())
        except Exception:
            pass
    return Ensemble(members)
