"""Cấu hình sản xuất duy nhất của tầng dự báo; backtest và service cùng đọc PRODUCTION_CONFIG."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class ForecastConfig:
    # ── Thành viên ensemble ──
    use_weather: bool = True
    """Thêm HarmonicPoisson(thời tiết) vào ensemble và cho SARIMAX dùng exog."""
    weather_min_months: int = 12
    """Dưới ngưỡng này coi như chưa có thời tiết, tự tắt."""
    smearing: bool = False
    """Hiệu chỉnh Duan cho mô hình khớp trên log1p; tắt vì làm lệch dương tăng thêm."""
    ridge_lam: float = 10.0
    """Hình phạt Ridge trên biến đã chuẩn hoá, chọn bằng walk-forward."""

    use_ets: bool = True
    """Thành viên ETS Holt–Winters (cần statsmodels)."""

    # ── Kết hợp thành viên và hiệu chỉnh lệch ──
    combine: str = "inv_mae"
    """'mean' = trung bình đều; 'inv_mae' = trọng số nghịch đảo MAE trên `combine_window` bước gần nhất."""
    combine_window: int = 12
    combine_power: float = 2.0
    combine_min_hist: int = 6
    bias_correct: bool = True
    """Nhân dự báo nhóm với 1 + shrink·(median(thực tế/dự báo) − 1), chặn trong [1/clip, clip]."""
    bias_window: int = 12
    bias_shrink: float = 0.5
    bias_clip: float = 1.5

    # ── Phân cấp ──
    method: str = "top_down_dynamic"
    """Top-down động theo tỷ trọng EWMA."""
    ewma_span: int = 6

    # ── Cửa sổ ──
    from_period: Optional[str] = None
    """None = toàn bộ lịch sử."""
    min_train: int = 24

    # ── Khoảng dự báo ──
    interval_level: float = 0.90
    """Mức khoảng dự báo dùng chung cho mọi màn hình."""
    interval_n_back: int = 24
    """Số phần dư walk-forward gần nhất để lấy phân vị."""

    def as_record(self) -> dict:
        """Bản ghi gọn lưu kèm mỗi kết quả."""
        return asdict(self)


PRODUCTION_CONFIG = ForecastConfig()
"""Cấu hình duy nhất được phép sinh số cho màn hình và báo cáo."""
