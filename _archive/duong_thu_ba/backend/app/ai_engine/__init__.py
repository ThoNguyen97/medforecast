"""app.ai_engine — phần CÒN LẠI sau đợt tái cấu trúc 09/09/2026.

Nhánh dự báo cũ (XGBoost / Prophet / "LSTM" / MonthlyForecaster / pipeline)
đã chuyển sang _archive/ai_engine_cu/. Nhánh đó chưa từng chạy trong sản
phẩm: điểm vào duy nhất là một Celery task không nơi nào gọi, và
docker-compose không có worker nào.

Đường dự báo chính thức nằm ở app/forecasting (ensemble thống kê + dự báo
phân cấp top-down động), đánh giá bằng walk-forward trong evaluate.py.

Ở đây CHỈ còn quy đổi ca bệnh sang nhu cầu vật tư:
    ConversionModule — dùng bởi services/supply_requirement_service.py

LƯU Ý: KHÔNG thêm import cấp mô-đun nặng vào file này. Python chạy __init__
trước mọi submodule, nên mỗi import cấp cao ở đây là chi phí bắt buộc cho
mọi đường chạy. Chính vì vậy bản cũ kéo cả xgboost lẫn prophet vào bộ nhớ
dù không ai dùng.
"""
from .conversion_module import ConversionModule

__all__ = ["ConversionModule"]
