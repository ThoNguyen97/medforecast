"""Mô hình dự báo chuỗi tháng trên numpy/pandas; SARIMAX/ETS tự thêm nếu có statsmodels.

Giao diện chung: fit(df[month, cases, is_covid]), predict(next_month) -> float; cờ `fitted` và tên `name`.
"""
from __future__ import annotations
import logging
from typing import Dict, List
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _arrays(df: pd.DataFrame):
    y = df["cases"].to_numpy(dtype=float)
    m = df["month"].to_numpy(dtype=int)
    cov = (df["is_covid"].to_numpy(dtype=bool) if "is_covid" in df
           else np.zeros(len(y), dtype=bool))
    return y, m, cov


def _smear_factor(resid_log: np.ndarray) -> float:
    """Hệ số Duan mean(exp(ε)) trên phần dư thang log; 1 nếu không đủ phần dư."""
    r = np.asarray(resid_log, float)
    r = r[np.isfinite(r)]
    if len(r) < 3:
        return 1.0
    # Chặn ngoại lai để một tháng bất thường không thổi phồng hệ số.
    r = np.clip(r, -3.0, 3.0)
    return float(np.mean(np.exp(r)))


def _ridge_standardized(X: np.ndarray, t: np.ndarray, lam: float):
    """Ridge phạt trên cột đã chuẩn hoá (trừ cột chặn 0); trả beta trên thang gốc."""
    Xs = X.copy()
    mu = Xs[:, 1:].mean(axis=0)
    sd = Xs[:, 1:].std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    Xs[:, 1:] = (Xs[:, 1:] - mu) / sd
    p = Xs.shape[1]
    I = np.eye(p); I[0, 0] = 0.0
    beta_s = np.linalg.solve(Xs.T @ Xs + lam * I, Xs.T @ t)
    # b_j = b_s_j / sd_j ; b_0 = b_s_0 − Σ b_j×mu_j
    beta = np.empty(p)
    beta[1:] = beta_s[1:] / sd
    beta[0] = beta_s[0] - float(np.dot(beta[1:], mu))
    return beta


class SeasonalNaiveForecaster:
    """Dự báo = số ca cùng tháng của năm gần nhất có dữ liệu."""
    name = "seasonal_naive"
    fitted = False
    def fit(self, df):
        self._df = df.reset_index(drop=True)
        self.fitted = True
        return self
    def predict(self, next_month: int) -> float:
        same = self._df[self._df["month"] == next_month]["cases"]
        if len(same):
            return max(0.0, float(same.iloc[-1]))
        return max(0.0, float(self._df["cases"].iloc[-1])) if len(self._df) else 0.0


class SeasonalTrendForecaster:
    """Mức + hệ số mùa nhân + xu hướng tuyến tính giảm chấn, ước lượng trên tháng không COVID."""
    name = "seasonal_trend"
    fitted = False

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
        # Hệ số mùa không chuẩn hoá về trung bình 1: chuẩn hoá cho walk-forward kém hơn ở 2/3 nhóm.
        self.sfac = {}
        for m in range(1, 13):
            sel = use & (mo == m)
            self.sfac[m] = (y[sel].mean() / base_mean) if sel.any() and y[sel].mean() > 0 else 1.0
        s_of = np.array([self.sfac[m] for m in mo])
        des = np.where(s_of > 0, y / s_of, y)
        xi, di = idx[use], des[use]
        if len(xi) >= 3:
            self.slope, self.intercept = np.polyfit(xi, di, 1)
        else:
            self.slope, self.intercept = 0.0, (di.mean() if len(di) else base_mean)
        self._last_fit_idx = xi.max() if len(xi) else (self.n - 1)
        self.fitted = True
        return self

    def predict(self, next_month: int) -> float:
        idx = self.n
        horizon = idx - self._last_fit_idx
        eff = self._last_fit_idx + sum(self.damping ** k for k in range(1, int(max(1, horizon)) + 1))
        level = self.intercept + self.slope * eff
        pred = level * self.sfac.get(next_month, 1.0)
        return float(max(0.0, pred))


class PoissonTrendForecaster:
    """Hồi quy log1p(ca) ~ xu hướng + tháng, Ridge trên cột chuẩn hoá, tháng không COVID."""
    name = "poisson_trend"
    fitted = False

    def __init__(self, exclude_covid: bool = True, lam: float = 10.0,
                 smearing: bool = False):
        self.exclude_covid = exclude_covid
        self.lam = lam
        self.smearing = smearing
        self._smear = 1.0

    def _design(self, idx, months):
        n = len(idx)
        X = [np.ones(n), idx / 12.0]
        for m in range(2, 13):
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
        try:
            self.beta = _ridge_standardized(X, t, self.lam)
        except np.linalg.LinAlgError:
            self.beta = np.zeros(p); self.beta[0] = t.mean() if len(t) else 0.0
        self._smear = _smear_factor(t - X @ self.beta) if self.smearing else 1.0
        self.fitted = True
        return self

    def predict(self, next_month: int) -> float:
        X = self._design(np.array([float(self.n)]), np.array([next_month]))
        eta = float(np.ravel(X @ self.beta)[0])   # numpy ≥ 2 không cho float() mảng (1,)
        pred = np.exp(eta) * self._smear - 1.0
        return float(max(0.0, pred))


class HarmonicPoissonForecaster:
    """Hồi quy log1p với mùa điều hòa sin/cos, tuỳ chọn thời tiết trễ (cột temp, humidity, rainfall)."""
    WCOLS = ["temp", "humidity", "rainfall"]
    fitted = False

    def __init__(self, use_weather: bool = False, weather_lags=(1, 2),
                 exclude_covid: bool = True, lam: float = 10.0,
                 smearing: bool = False):
        self.use_weather = use_weather
        self.weather_lags = tuple(weather_lags)
        self.exclude_covid = exclude_covid
        self.lam = lam
        self.smearing = smearing
        self._smear = 1.0

    @property
    def name(self) -> str:
        return "harmonic_poisson_weather" if self._has_w_stored() else "harmonic_poisson"

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
            self.fitted = True
            return self
        try:
            self.beta = _ridge_standardized(X, t, self.lam)
            self._smear = _smear_factor(t - X @ self.beta) if self.smearing else 1.0
        except np.linalg.LinAlgError:
            self.beta = None
            self._fallback = float(t.mean())
        self.fitted = True
        return self

    def predict(self, next_month: int) -> float:
        if self.beta is None:
            return float(max(0.0, np.expm1(getattr(self, "_fallback", 0.0))))
        i = self.n
        row = [1.0, i / max(1, self.n),
               np.sin(2 * np.pi * next_month / 12.0),
               np.cos(2 * np.pi * next_month / 12.0)]
        if self._has_w_stored():
            for c in self.WCOLS:
                for L in self.weather_lags:
                    j = i - L
                    val = self._w_hist[c][j] if 0 <= j < self.n else np.nan
                    dev = (0.0 if (val is None or np.isnan(val))
                           else (val - self._w_mean[c]) / self._w_std[c])
                    row.append(dev)
        if len(row) != len(self.beta):
            raise ValueError(f"HarmonicPoisson: đặc trưng {len(row)} ≠ beta {len(self.beta)}")
        eta = float(np.asarray(row) @ self.beta)
        pred = np.exp(eta) * self._smear - 1.0
        return float(max(0.0, pred))

    def _has_w_stored(self) -> bool:
        return bool(getattr(self, "_w_hist", {}))


class Ensemble:
    """Trung bình đều các thành viên đã fit thành công; ghi `members_used` và `members_failed` {tên: lý do}."""
    name = "ensemble"

    def __init__(self, members: List):
        self.members = members
        self.members_used: List[str] = []
        self.members_failed: Dict[str, str] = {}

    # Dự báo vượt PLAUSIBLE_FACTOR × max lịch sử bị coi là rớt, vì SARIMAX không hội tụ trả giá trị cực lớn.
    PLAUSIBLE_FACTOR = 5.0

    def fit(self, df):
        self.members_failed = {}
        y = df["cases"].to_numpy(float) if "cases" in df else np.array([0.0])
        self._y_max = float(np.nanmax(y)) if len(y) else 0.0
        self._plausible_max = max(self.PLAUSIBLE_FACTOR * self._y_max, 10.0)
        for m in self.members:
            m.fitted = False
            try:
                m.fit(df)
            except Exception as exc:                          # noqa: BLE001
                m.fitted = False
                self.members_failed[getattr(m, "name", type(m).__name__)] = f"fit: {exc}"
                logger.warning("Ensemble: thành viên %s rớt khi fit, %s",
                               getattr(m, "name", type(m).__name__), exc)
        return self

    def predict_members(self, next_month: int) -> Dict[str, float]:
        """Dự báo từng thành viên hợp lệ; thành viên rớt hoặc phi lý bị loại và ghi lý do."""
        out: Dict[str, float] = {}
        for m in self.members:
            nm = getattr(m, "name", type(m).__name__)
            if not getattr(m, "fitted", False):
                continue
            try:
                v = float(m.predict(next_month))
                if not np.isfinite(v):
                    raise ValueError(f"giá trị không hữu hạn: {v}")
                if v > self._plausible_max:
                    raise ValueError(f"phi lý: {v:.0f} > {self.PLAUSIBLE_FACTOR:.0f}× max lịch sử ({self._y_max:.0f})")
                out[nm] = v
            except Exception as exc:                          # noqa: BLE001
                self.members_failed[nm] = f"predict: {exc}"
                logger.warning("Ensemble: thành viên %s rớt khi predict, %s", nm, exc)
        self.members_used = list(out.keys())
        return out

    def predict(self, next_month: int) -> float:
        """Trung bình đều, dùng ở mức mã."""
        vals = self.predict_members(next_month)
        if not vals:
            logger.error("Ensemble: KHÔNG thành viên nào dự báo được, trả 0.")
            return 0.0
        return float(np.mean(list(vals.values())))

    def describe(self) -> dict:
        """Thành viên khai báo / đã dùng / đã rớt."""
        return {
            "members": [getattr(m, "name", type(m).__name__) for m in self.members],
            "members_used": list(self.members_used),
            "members_failed": dict(self.members_failed),
        }


def _has_statsmodels() -> bool:
    try:
        import statsmodels.api  # noqa: F401
        return True
    except Exception:
        return False


def build_default_ensemble(use_weather: bool = False, smearing: bool = False,
                           lam: float = 10.0, use_ets: bool = False) -> Ensemble:
    """SeasonalTrend + PoissonTrend, thêm HarmonicPoisson nếu use_weather, SARIMAX/ETS nếu có statsmodels."""
    members = [SeasonalTrendForecaster(),
               PoissonTrendForecaster(lam=lam, smearing=smearing)]
    if use_weather:
        members.append(HarmonicPoissonForecaster(use_weather=True, lam=lam,
                                                 smearing=smearing))
    if _has_statsmodels():
        try:
            from .sarimax_opt import SarimaxForecaster
            members.append(SarimaxForecaster(use_weather=use_weather,
                                             smearing=smearing))
        except Exception:
            pass
        if use_ets:
            try:
                from .ets_opt import EtsForecaster
                members.append(EtsForecaster(smearing=smearing))
            except Exception:
                pass
    return Ensemble(members)


def has_enough_weather(df: pd.DataFrame, min_months: int) -> bool:
    """Đủ tháng thời tiết để bật thành viên thời tiết."""
    return ("temp" in df.columns) and int(df["temp"].notna().sum()) >= min_months


