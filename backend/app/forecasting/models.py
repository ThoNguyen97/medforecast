"""Các mô hình dự báo chuỗi tháng (numpy/pandas thuần, chạy với dữ liệu nhỏ).

Giao diện chung:
    m.fit(df)              df có cột [month(int 1-12), cases(float), is_covid(bool)]
    m.predict(next_month)  -> float (dự báo 1 bước tới)
    m.fitted               True sau khi fit thành công (Ensemble dựa vào cờ này)
    m.name                 tên ngắn, ghi vào bản ghi "thành viên đã đóng góp"

SARIMAX là tùy chọn: build_default_ensemble() tự thêm nếu statsmodels có sẵn.

Sửa 11/09/2026 (xem RaSoat_MoHinh_MedForecast_2026-09-09.md):
  M6  Ensemble ghi lại thành viên nào đã đóng góp, cảnh báo khi một thành viên
      rớt, và KHÔNG gọi predict trên thành viên chưa fit thành công.
  M8  Smearing (Duan 1983) có sẵn nhưng TẮT mặc định. Giả thuyết ban đầu là
      expm1(E[log1p Y]) cho trung vị → hụt. ĐO THẬT (walk-forward 3 nhóm, mức
      nhóm, 11/09/2026) cho thấy ngược lại: ensemble vốn đã dự báo THỪA
      (MPE +13…+18%), smearing chỉ nhân thêm ≥1 nên đẩy lệch lên +30%. Giữ mã
      để đối chứng, không bật.
  M10 Chuẩn hoá cột trước Ridge — BẬT, với λ dò lại. λ=1 cũ được "ngầm hiệu
      chuẩn" cho thang chưa chuẩn hoá; chuẩn hoá xong mà giữ λ=1 thì tệ hơn ở
      cả 3 nhóm. Dò λ∈{3,10,30,100,300}: λ=10 thắng hoặc hoà bản cũ ở mọi ô
      (Harm 0,81→0,78 / 0,75→0,69 / 0,75→0,76; Poisson 1,12→1,06 / 0,87→0,73
      / 1,07→0,93). λ≥30 giết J09-J18 (dịch chuyển mức nền 3,66×, phạt xu hướng
      mạnh thì không theo kịp: MPE −29…−48%). λ tối ưu KHÁC NHAU theo nhóm
      (J00-J06≈100, J09-J18≈10, J20-J22≈30) — dò theo nhóm là bước tiếp theo.
  M14 ĐÃ THỬ VÀ HOÀN TÁC — xem chú thích trong SeasonalTrendForecaster.fit.
"""
from __future__ import annotations
import logging
from typing import Dict, List, Optional
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
    """Hệ số Duan: mean(exp(ε)) trên phần dư thang log. ≥ 1 khi phần dư có
    phương sai; = 1 nếu không có phần dư để ước lượng."""
    r = np.asarray(resid_log, float)
    r = r[np.isfinite(r)]
    if len(r) < 3:
        return 1.0
    # chặn ngoại lai cực đoan để một tháng bất thường không thổi phồng cả chuỗi
    r = np.clip(r, -3.0, 3.0)
    return float(np.mean(np.exp(r)))


def _ridge_standardized(X: np.ndarray, t: np.ndarray, lam: float):
    """Ridge với cột (trừ cột chặn, cột 0) đã chuẩn hoá về mean 0 / sd 1.

    Trả (beta_goc, mu, sd): beta trên thang GỐC để predict không cần chuẩn hoá
    lại, nhưng hình phạt đã được áp trên thang chuẩn hoá — đó là điểm khác
    biệt so với bản cũ.
    """
    Xs = X.copy()
    mu = Xs[:, 1:].mean(axis=0)
    sd = Xs[:, 1:].std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    Xs[:, 1:] = (Xs[:, 1:] - mu) / sd
    p = Xs.shape[1]
    I = np.eye(p); I[0, 0] = 0.0
    beta_s = np.linalg.solve(Xs.T @ Xs + lam * I, Xs.T @ t)
    # quy về thang gốc: b_j = b_s_j / sd_j ; b_0 = b_s_0 − Σ b_j·mu_j
    beta = np.empty(p)
    beta[1:] = beta_s[1:] / sd
    beta[0] = beta_s[0] - float(np.dot(beta[1:], mu))
    return beta


class NaiveForecaster:
    """Dự báo = giá trị tháng gần nhất."""
    name = "naive"
    fitted = False
    def fit(self, df):
        self._last = float(df["cases"].iloc[-1]) if len(df) else 0.0
        self.fitted = True
        return self
    def predict(self, next_month: int) -> float:
        return max(0.0, self._last)


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

    Ước lượng hệ số mùa và xu hướng trên các tháng KHÔNG COVID để tránh méo.
    Thang đo: TRUNG BÌNH (không biến đổi log) — không cần smearing.
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
        # hệ số mùa theo tháng (nhân) — một lượt, KHÔNG chuẩn hoá.
        # 11/09/2026: đã thử chuẩn hoá về trung bình 1 + ước lượng lại sau khi
        # khử xu hướng (M14). Đo walk-forward 3 nhóm: tệ hơn ở 2/3 (J00-J06
        # RelMAE 1,23→1,51; J20-J22 0,98→1,20), chỉ J09-J18 tốt hơn. Giữ bản cũ.
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
        self.fitted = True
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

    Ridge trên cột ĐÃ CHUẨN HOÁ (M10). Ước lượng trên tháng không COVID.
    Thang đo: log → cần smearing (M8) để trả kỳ vọng thay vì trung vị.
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
    """Hồi quy log-tuyến tính (Poisson xấp xỉ) với mùa dạng ĐIỀU HÒA (sin/cos)
    + tùy chọn biến THỜI TIẾT có ĐỘ TRỄ.

    Ưu điểm: ít tham số (hợp dữ liệu nhỏ). Thời tiết dùng ở độ trễ (lag) nên
    KHÔNG rò rỉ tương lai — đúng dịch tễ (bệnh bùng sau đợt thời tiết).
    Thang đo: log → smearing (M8).

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
                    j = i - L                      # lag từ dữ liệu ĐÃ QUAN SÁT
                    val = self._w_hist[c][j] if 0 <= j < self.n else np.nan
                    dev = (0.0 if (val is None or np.isnan(val))
                           else (val - self._w_mean[c]) / self._w_std[c])
                    row.append(dev)
        # Bản cũ cắt ngắn âm thầm khi lệch chiều (row[:len(beta)] @ beta[:len(row)]).
        # Lệch chiều là lỗi lập trình — phải nổ ra, không được đoán bừa.
        if len(row) != len(self.beta):
            raise ValueError(f"HarmonicPoisson: đặc trưng {len(row)} ≠ beta {len(self.beta)}")
        eta = float(np.asarray(row) @ self.beta)
        pred = np.exp(eta) * self._smear - 1.0
        return float(max(0.0, pred))

    def _has_w_stored(self) -> bool:
        return bool(getattr(self, "_w_hist", {}))


class Ensemble:
    """Trung bình ĐỀU các thành viên đã fit thành công (giảm phương sai).

    M6: ghi lại ai đóng góp. Sau mỗi lần predict:
        .members_used   tên các thành viên góp giá trị vào trung bình
        .members_failed {tên: lý do} các thành viên rớt ở fit hoặc predict
    Không có trọng số thích ứng — một thành viên tồi bị LÀM LOÃNG chứ không
    bị hạ trọng số. Nếu cần trọng số nghịch đảo MSE thì làm ở lớp trên với
    kết quả backtest, không giấu vào đây.
    """
    name = "ensemble"

    def __init__(self, members: List):
        self.members = members
        self.members_used: List[str] = []
        self.members_failed: Dict[str, str] = {}

    # Dự báo của một thành viên vượt quá PLAUSIBLE_FACTOR × max lịch sử thì bị
    # coi là rớt (ghi lý do), không đưa vào trung bình. 11/09/2026: SARIMAX
    # không hội tụ cho 10^7 ở J20-J22 và 10^45 ở mã thưa J09-J18 — một giá trị
    # như vậy lọt vào np.mean là phá cả ensemble. Đây chính là "hạ trọng số
    # mô hình tồi" mà tài liệu cũ tưởng đã có; giờ mới có thật, và minh bạch.
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
        """Dự báo của TỪNG thành viên còn đứng (M12). Thành viên rớt / phi lý
        bị loại và ghi lý do như trước. Lớp kết hợp (combine.AdaptiveCombiner)
        quyết định trọng số — không phải việc của ensemble."""
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
        """Trung bình ĐỀU — giữ cho mức mã và cho tương thích. Mức nhóm dùng
        `group_forecast.py` với trọng số thích ứng."""
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
    """SeasonalTrend + PoissonTrend (+ Harmonic-thời-tiết nếu use_weather;
    + SARIMAX nếu có statsmodels).

    Trong app và backtest, luôn dựng qua `group_forecast.make_ensemble(df, cfg)`
    để tham số đọc từ PRODUCTION_CONFIG; gọi thẳng không tham số là cấu hình
    "thời tiết tắt".
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
                from .ets_opt import EtsForecaster       # tuỳ chọn (M12)
                members.append(EtsForecaster(smearing=smearing))
            except Exception:
                pass
    return Ensemble(members)


def has_enough_weather(df: pd.DataFrame, min_months: int) -> bool:
    """Chuỗi có đủ tháng thời tiết để bật thành viên thời tiết không."""
    return ("temp" in df.columns) and int(df["temp"].notna().sum()) >= min_months


