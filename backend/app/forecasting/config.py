"""Cấu hình sản xuất duy nhất của tầng dự báo.

Backtest và service đều đọc tham số từ PRODUCTION_CONFIG để số đánh giá khớp với số
hiển thị; thử cấu hình khác bằng cách truyền một ForecastConfig khác. Cấu hình được
ghi kèm mỗi kết quả (`ForecastConfig.as_record`) để truy ngược về mô hình đã sinh ra nó.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class ForecastConfig:
    # ── Thành viên ensemble ──
    use_weather: bool = True
    """Thêm HarmonicPoisson(thời tiết) vào ensemble và cho SARIMAX dùng exog.
    Chỉ có hiệu lực khi chuỗi có đủ `weather_min_months` tháng thời tiết."""
    weather_min_months: int = 12
    """Dưới ngưỡng này chuỗi coi như chưa có thời tiết → tự tắt, không lỗi."""
    smearing: bool = False
    """Hiệu chỉnh Duan cho các mô hình khớp trên log1p. Tắt mặc định: ensemble vốn
    dự báo thừa, smearing làm lệch dương tăng thêm (xem ketqua_backtest/smearing.csv)."""
    ridge_lam: float = 10.0
    """Hình phạt Ridge trên biến đã chuẩn hoá; chọn bằng walk-forward trên ba nhóm ICD
    (giá trị ≥ 30 làm giảm mạnh độ chính xác nhóm J09-J18)."""

    use_ets: bool = True
    """Thành viên ETS Holt–Winters (cần statsmodels); chỉ kém SARIMAX khi đứng một mình
    (xem ketqua_backtest/thanhvien.csv)."""

    # ── Kết hợp thành viên và hiệu chỉnh lệch ──
    combine: str = "inv_mae"
    """'mean' = trung bình đều; 'inv_mae' = trọng số nghịch đảo MAE của từng thành viên
    trên `combine_window` bước walk-forward gần nhất (Bates–Granger). Chỉ áp ở mức nhóm;
    mức mã dùng trung bình đều. So sánh các phương án: ketqua_backtest/ket_hop.csv."""
    combine_window: int = 12
    combine_power: float = 2.0
    combine_min_hist: int = 6
    bias_correct: bool = True
    """Nhân dự báo nhóm với hệ số 1 + shrink·(median(thực tế/dự báo) − 1) trên
    `bias_window` bước gần nhất, chặn trong [1/clip, clip], để sửa lệch một chiều.
    Hệ số chỉ ước lượng từ quá khứ nên walk-forward không bị rò rỉ thông tin."""
    bias_window: int = 12
    bias_shrink: float = 0.5
    bias_clip: float = 1.5

    # ── Phân cấp ──
    method: str = "top_down_dynamic"
    """Top-down động theo tỷ trọng EWMA; bottom-up không ổn định trên các mã thưa."""
    ewma_span: int = 6

    # ── Cửa sổ ──
    from_period: Optional[str] = None
    """None = toàn bộ lịch sử từ 2019; cắt ngắn làm mất các mùa dịch mà thành phần
    thời tiết cần để ước lượng."""
    min_train: int = 24

    # ── Khoảng dự báo ──
    interval_level: float = 0.90
    """Mức khoảng dự báo dùng chung cho mọi màn hình."""
    interval_n_back: int = 24
    """Số phần dư walk-forward gần nhất dùng để lấy phân vị (24 = hai chu kỳ mùa)."""

    def as_record(self) -> dict:
        """Bản ghi gọn để lưu kèm mỗi kết quả dự báo / mỗi bảng backtest."""
        return asdict(self)


PRODUCTION_CONFIG = ForecastConfig()
"""Cấu hình duy nhất được phép sinh số cho màn hình và cho báo cáo."""
