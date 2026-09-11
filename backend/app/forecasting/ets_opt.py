"""ETS Holt–Winters (tuỳ chọn, cần statsmodels) — thành viên thứ năm của ensemble.

Vì sao thêm (11/09/2026): ba thành viên numpy đều là hồi quy có mùa trên
log1p; SARIMAX là ARIMA. Chưa có thành viên làm mượt hàm mũ — họ mô hình mà
với chuỗi tháng có mùa vụ mạnh và mức nền trôi (COVID 2020–2021, dịch chuyển
chế độ ghi nhận 2025) thường bám mức nền gần đây tốt hơn hồi quy toàn lịch
sử. Thêm với tư cách ứng viên; trọng số thích ứng (combine.py) sẽ tự hạ nếu
nó không giúp, và bảng thanhvien.csv/ket_hop.csv ghi lại bằng chứng.

Cấu hình: xu hướng cộng có giảm chấn (damped) + mùa cộng 12 tháng, khớp trên
log1p(cases) để phương sai ổn định và không âm; bỏ tháng COVID khỏi ước lượng
bằng cách nội suy (ETS cần chuỗi liên tục, không bỏ hàng được).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_OBS = 24   # ≥ 2 chu kỳ mùa


class EtsForecaster:
    """Holt–Winters cộng, xu hướng giảm chấn, mùa 12, trên log1p."""
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

    def predict(self, next_month: int) -> float:   # noqa: ARG002 — mùa đã nằm trong trạng thái
        if self._res is None:
            raise RuntimeError("ETS chưa fit")
        eta = float(np.ravel(self._res.forecast(1))[0])
        pred = np.expm1(eta) * self._smear
        if not np.isfinite(pred):
            raise ValueError(f"ETS trả giá trị không hữu hạn: {pred}")
        return float(max(0.0, pred))
