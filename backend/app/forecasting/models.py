"""Các mô hình dự báo chuỗi tháng (numpy/pandas thuần, chạy với dữ liệu nhỏ).

Giao diện chung:
    m.fit(df)              df có cột [month(int 1-12), cases(float), is_covid(bool)]
    m.predict(next_month)  -> float (dự báo 1 bước tới)
    m.fitted               True sau khi fit thành công (Ensemble dựa vào cờ này)
    m.name                 tên ngắn, ghi vào bản ghi "thành viên đã đóng góp"

SARIMAX/ETS là tùy chọn: build_default_ensemble() tự thêm nếu statsmodels có sẵn.

- Smearing (Duan 1983) có sẵn nhưng tắt mặc định: ensemble đã có xu hướng dự báo
  thừa, smearing (hệ số ≥ 1) làm lệch dương tăng thêm.
- Ridge phạt trên cột đã chuẩn hoá; λ = 10 chọn bằng walk-forward trên 3 nhóm
  (λ lớn làm mô hình không theo kịp dịch chuyển mức nền của J09-J18).
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
    """Hệ số Duan mean(exp(ε)) trên phần dư thang log; = 1 nếu không đủ phần dư."""
    r = np.asarray(resid_log, float)
    r = r[np.isfinite(r)]
    if len(r) < 3:
        return 1.0
    # Chặn ngoại lai để một tháng bất thường không thổi phồng cả chuỗi.
    r = np.clip(r, -3.0, 3.0)
    return float(np.mean(np.exp(r)))


def _ridge_standardized(X: np.ndarray, t: np.ndarray, lam: float):
    """Ridge với cột (trừ cột chặn, cột 0) đã chuẩn hoá về mean 0 / sd 1.

    Trả beta trên thang gốc để predict không cần chuẩn hoá lại; hình phạt được áp
    trên thang chuẩn hoá.
    """
    Xs = X.copy()
    mu = Xs[:, 1:].mean(axis=0)
    sd = Xs[:, 1:].std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    Xs[:, 1:] = (Xs[:, 1:] - mu) / sd
    p = Xs.shape[1]
    I = np.eye(p); I[0, 0] = 0.0
    beta_s = np.linalg.solve(Xs.T @ Xs + lam * I, Xs.T @ t)
    # Quy về thang gốc: b_j = b_s_j / sd_j ; b_0 = b_s_0 − Σ b_j·mu_j
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
    """Mức + hệ số mùa (nhân) + xu hướng tuyến tính có giảm dần.

    Ước lượng hệ số mùa và xu hướng trên các tháng không COVID để tránh méo.
    Thang đo gốc (không log) nên không cần smearing.
    """
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
        # Hệ số mùa theo tháng (nhân), ước lượng một lượt, không chuẩn hoá về trung bình 1:
        # chuẩn hoá + ước lượng lại sau khử xu hướng cho kết quả walk-forward kém hơn ở 2/3 nhóm.
        self.sfac = {}
        for m in range(1, 13):
            sel = use & (mo == m)
            self.sfac[m] = (y[sel].mean() / base_mean) if sel.any() and y[sel].mean() > 0 else 1.0
        s_of = np.array([self.sfac[m] for m in mo])
        des = np.where(s_of > 0, y / s_of, y)
        # Xu hướng tuyến tính trên chuỗi đã khử mùa (chỉ tháng không COVID).
        xi, di = idx[use], des[use]
        if len(xi) >= 3:
            self.slope, self.intercept = np.polyfit(xi, di, 1)
        else:
            self.slope, self.intercept = 0.0, (di.mean() if len(di) else base_mean)
        self._last_fit_idx = xi.max() if len(xi) else (self.n - 1)
        self.fitted = True
        return self

    def predict(self, next_month: int) -> float:
        idx = self.n  # bước kế tiếp
        # Giảm chấn ngoại suy xu hướng để tránh trôi.
        horizon = idx - self._last_fit_idx
        eff = self._last_fit_idx + sum(self.damping ** k for k in range(1, int(max(1, horizon)) + 1))
        level = self.intercept + self.slope * eff
        pred = level * self.sfac.get(next_month, 1.0)
        return float(max(0.0, pred))


class PoissonTrendForecaster:
    """Hồi quy log-tuyến tính (xấp xỉ Poisson): log1p(ca) ~ xu hướng + tháng.

    Ridge trên cột đã chuẩn hoá, ước lượng trên tháng không COVID.
    Thang log nên smearing (nếu bật) chuyển trung vị về kỳ vọng.
    """
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
        try:
            self.beta = _ridge_standardized(X, t, self.lam)
        except np.linalg.LinAlgError:
            self.beta = np.zeros(p); self.beta[0] = t.mean() if len(t) else 0.0
        self._smear = _smear_factor(t - X @ self.beta) if self.smearing else 1.0
        self.fitted = True
        return self

    def predict(self, next_month: int) -> float:
        X = self._design(np.array([float(self.n)]), np.array([next_month]))
        eta = float(np.ravel(X @ self.beta)[0])   # numpy ≥ 2.x: float(mảng (1,)) là lỗi
        pred = np.exp(eta) * self._smear - 1.0
        return float(max(0.0, pred))


class HarmonicPoissonForecaster:
    """Hồi quy log-tuyến tính (Poisson xấp xỉ) với mùa dạng điều hòa (sin/cos),
    tùy chọn thêm biến thời tiết có độ trễ.

    Ít tham số, hợp dữ liệu nhỏ. Thời tiết dùng ở độ trễ nên không rò rỉ tương lai
    (bệnh bùng sau đợt thời tiết). Thang log, smearing tùy chọn.

    df cần cột: month(int), cases(float), is_covid(bool),
                và nếu use_weather: temp, humidity, rainfall (có thể NaN).
    """
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
        i = self.n  # bước kế tiếp
        row = [1.0, i / max(1, self.n),
               np.sin(2 * np.pi * next_month / 12.0),
               np.cos(2 * np.pi * next_month / 12.0)]
        if self._has_w_stored():
            for c in self.WCOLS:
                for L in self.weather_lags:
                    j = i - L                      # lag từ dữ liệu đã quan sát
                    val = self._w_hist[c][j] if 0 <= j < self.n else np.nan
                    dev = (0.0 if (val is None or np.isnan(val))
                           else (val - self._w_mean[c]) / self._w_std[c])
                    row.append(dev)
        # Lệch số chiều đặc trưng/beta là lỗi lập trình: báo lỗi thay vì cắt ngắn.
        if len(row) != len(self.beta):
            raise ValueError(f"HarmonicPoisson: đặc trưng {len(row)} ≠ beta {len(self.beta)}")
        eta = float(np.asarray(row) @ self.beta)
        pred = np.exp(eta) * self._smear - 1.0
        return float(max(0.0, pred))

    def _has_w_stored(self) -> bool:
        return bool(getattr(self, "_w_hist", {}))


class Ensemble:
    """Trung bình đều các thành viên đã fit thành công.

    Sau mỗi lần predict:
        .members_used   tên các thành viên góp giá trị vào trung bình
        .members_failed {tên: lý do} các thành viên rớt ở fit hoặc predict
    Trọng số thích ứng nằm ở lớp trên (combine.AdaptiveCombiner).
    """
    name = "ensemble"

    def __init__(self, members: List):
        self.members = members
        self.members_used: List[str] = []
        self.members_failed: Dict[str, str] = {}

    # Dự báo thành viên vượt PLAUSIBLE_FACTOR × max lịch sử bị coi là rớt (ghi lý do):
    # SARIMAX không hội tụ có thể trả giá trị cực lớn, phá cả trung bình.
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
                logger.warning("Ensemble: thành viên %s rớt khi fit — %s",
                               getattr(m, "name", type(m).__name__), exc)
        return self

    def predict_members(self, next_month: int) -> Dict[str, float]:
        """Dự báo của từng thành viên hợp lệ; thành viên rớt/phi lý bị loại và ghi lý do.

        Trọng số do combine.AdaptiveCombiner quyết định.
        """
        out: Dict[str, float] = {}
        for m in self.members:
            nm = getattr(m, "name", type(m).__name__)
            if not getattr(m, "fitted", False):
                continue                                      # đã ghi ở fit()
            try:
                v = float(m.predict(next_month))
                if not np.isfinite(v):
                    raise ValueError(f"giá trị không hữu hạn: {v}")
                if v > self._plausible_max:
                    raise ValueError(f"phi lý: {v:.0f} > {self.PLAUSIBLE_FACTOR:.0f}× max lịch sử ({self._y_max:.0f})")
                out[nm] = v
            except Exception as exc:                          # noqa: BLE001
                self.members_failed[nm] = f"predict: {exc}"
                logger.warning("Ensemble: thành viên %s rớt khi predict — %s", nm, exc)
        self.members_used = list(out.keys())
        return out

    def predict(self, next_month: int) -> float:
        """Trung bình đều, dùng ở mức mã; mức nhóm dùng `group_forecast` với trọng số thích ứng."""
        vals = self.predict_members(next_month)
        if not vals:
            logger.error("Ensemble: KHÔNG thành viên nào dự báo được — trả 0.")
            return 0.0
        return float(np.mean(list(vals.values())))

    def describe(self) -> dict:
        """Bản ghi để lưu kèm kết quả: thành viên khai báo / đã dùng / đã rớt."""
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
    """SeasonalTrend + PoissonTrend (+ HarmonicPoisson thời tiết nếu use_weather;
    + SARIMAX, ETS nếu có statsmodels).

    App và backtest dựng qua `group_forecast.make_ensemble(df, cfg)` để tham số đọc
    từ PRODUCTION_CONFIG.
    """
    members = [SeasonalTrendForecaster(),
               PoissonTrendForecaster(lam=lam, smearing=smearing)]
    if use_weather:
        members.append(HarmonicPoissonForecaster(use_weather=True, lam=lam,
                                                 smearing=smearing))
    if _has_statsmodels():
        try:
            from .sarimax_opt import SarimaxForecaster  # tùy chọn
            members.append(SarimaxForecaster(use_weather=use_weather,
                                             smearing=smearing))
        except Exception:
            pass
        if use_ets:
            try:
                from .ets_opt import EtsForecaster       # tuỳ chọn
                members.append(EtsForecaster(smearing=smearing))
            except Exception:
                pass
    return Ensemble(members)


def has_enough_weather(df: pd.DataFrame, min_months: int) -> bool:
    """Chuỗi có đủ tháng thời tiết để bật thành viên thời tiết không."""
    return ("temp" in df.columns) and int(df["temp"].notna().sum()) >= min_months


