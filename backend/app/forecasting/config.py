"""Cấu hình SẢN XUẤT duy nhất của tầng dự báo (M1 — 11/09/2026).

Vì sao cần file này
-------------------
Trước 11/09/2026 có BỐN cấu hình mô hình cùng tồn tại:

    evaluate.py                      build_default_ensemble()        thời tiết TẮT
    dashboard  (dss_runner/topdown)  Ridge + lag, không phải ensemble
    trang Phân tích                  ensemble(use_weather=auto)      thời tiết BẬT
    trang Kế hoạch                   nhóm BẬT / mã TẮT

Con số MASE ~0,60 công bố trong báo cáo được đo ở dòng đầu — một cấu hình mà
không màn hình nào dùng. Từ nay MỌI nơi (backtest lẫn service) đọc tham số từ
PRODUCTION_CONFIG; không chỗ nào tự đặt tham số riêng. Muốn thử cấu hình khác
thì tạo một ForecastConfig khác và truyền vào — không sửa mặc định.

Ghi kèm cấu hình này vào mỗi kết quả dự báo (xem `ForecastConfig.as_record`)
để bảng số trong báo cáo luôn truy ngược được về đúng mô hình đã sinh ra nó.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class ForecastConfig:
    # ── thành viên ensemble ──────────────────────────────────────────────
    use_weather: bool = True
    """Thêm HarmonicPoisson(thời tiết) vào ensemble và cho SARIMAX dùng exog.
    Chỉ có hiệu lực khi chuỗi có đủ `weather_min_months` tháng thời tiết."""
    weather_min_months: int = 12
    """Dưới ngưỡng này chuỗi coi như chưa có thời tiết → tự tắt, không lỗi."""
    smearing: bool = False
    """Hiệu chỉnh Duan cho các mô hình khớp trên log1p (M8). TẮT: đo walk-forward
    11/09/2026 cho thấy ensemble vốn dự báo THỪA (MPE +13…+18%), bật smearing
    đẩy lệch lên +30%. Giữ tuỳ chọn để đối chứng trong báo cáo."""
    ridge_lam: float = 10.0
    """Hình phạt Ridge trên cột ĐÃ chuẩn hoá (M10). Dò walk-forward 3 nhóm
    11/09/2026: 10 thắng hoặc hoà bản cũ ở mọi ô; ≥30 giết J09-J18. Tối ưu theo
    nhóm khác nhau (≈100 / 10 / 30) — dò theo nhóm là thí nghiệm kế tiếp."""

    use_ets: bool = True
    """Thành viên ETS Holt–Winters (cần statsmodels). M12, 11/09/2026: đứng
    một mình đã RelMAE 0,55/0,40/0,58 (ba nhóm) — chỉ kém SARIMAX, tốt hơn xa
    ba thành viên numpy. Bằng chứng: ket_hop.csv."""

    # ── kết hợp thành viên & hiệu chỉnh lệch (M12) ───────────────────────
    combine: str = "inv_mae"
    """'mean' = trung bình đều (hành vi cũ); 'inv_mae' = trọng số nghịch đảo
    MAE của từng thành viên trên `combine_window` bước walk-forward gần nhất
    (Bates–Granger). Chỉ áp ở MỨC NHÓM; mức mã vẫn trung bình đều.

    Chọn 11/09/2026 bằng bench walk-forward 68 bước (ket_hop.csv): trung bình
    đều RelMAE nhóm 0,755/0,594/0,688 vì seasonal_trend và poisson_trend còn
    TỆ HƠN seasonal-naive (RelMAE > 1 ở J00-J06) mà vẫn được 1/5 phiếu.
    inv_mae power 2 + hệ số lệch: 0,516/0,377/0,541 — MPE về −0,5/−3/+4 %."""
    combine_window: int = 12
    combine_power: float = 2.0
    combine_min_hist: int = 6
    bias_correct: bool = True
    """Nhân dự báo nhóm với hệ số = 1 + shrink·(median(thực tế/dự báo) − 1)
    trên `bias_window` bước gần nhất, chặn trong [1/clip, clip]. Sửa lệch
    một chiều (J09-J18 hụt ~15 %, J20-J22 thừa ~13 %) mà trung bình đều
    không tự sửa. Ước lượng chỉ từ quá khứ → walk-forward vẫn trung thực."""
    bias_window: int = 12
    bias_shrink: float = 0.5
    bias_clip: float = 1.5

    # ── phân cấp ─────────────────────────────────────────────────────────
    method: str = "top_down_dynamic"
    """Chốt bằng backtest 09/08/2026: bottom-up nổ MASE 483,7 trên mã thưa."""
    ewma_span: int = 6

    # ── cửa sổ ───────────────────────────────────────────────────────────
    from_period: Optional[str] = None
    """None = toàn bộ lịch sử từ 2019. Phân tích độ nhạy ba cửa sổ đã cho thấy
    cắt ngắn làm mất mùa dịch cũ mà thành phần thời tiết cần."""
    min_train: int = 24

    # ── khoảng dự báo (M9) ───────────────────────────────────────────────
    interval_level: float = 0.90
    """Một mức cho MỌI màn hình. Trước đây Dashboard dùng 0,80 còn trang Kế
    hoạch dùng z=1,96 đã hiệu chuẩn tới ~90% độ phủ — giữ 0,90 để không mất
    kết quả hiệu chuẩn đó."""
    interval_n_back: int = 24
    """Số phần dư walk-forward gần nhất dùng để lấy phân vị. 12 (bản cũ) quá
    ít để ước lượng đuôi; 24 = hai chu kỳ mùa."""

    def as_record(self) -> dict:
        """Bản ghi gọn để lưu kèm mỗi kết quả dự báo / mỗi bảng backtest."""
        return asdict(self)


PRODUCTION_CONFIG = ForecastConfig()
"""Cấu hình duy nhất được phép sinh số cho màn hình và cho báo cáo."""
