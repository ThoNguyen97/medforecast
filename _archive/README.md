# _archive — mã đã loại khỏi phạm vi sản phẩm

Đóng gói ngày 09/09/2026, trong đợt tái định hình MedForecast AI.
**Không xoá file nào** — mọi thứ ở đây vẫn tra cứu được khi viết báo cáo.

## Tiêu chí xác định mã chết
Grep tham chiếu ngược **có tính bắc cầu**: một file chỉ vào đây khi mọi nơi
gọi nó cũng nằm trong danh sách này. Đã loại trừ file `test_*` khỏi phép đếm.

## Các nhóm

- **ai_engine_cu/** — nhánh XGBoost/Prophet/LSTM. Điểm vào duy nhất là một
  Celery task không nơi nào gọi, và docker-compose không có worker nào; tức
  nhánh này **chưa từng chạy trong sản phẩm**. `ensemble_forecaster.py:89`
  cho thấy LSTM chưa bao giờ được cài đặt (`self.lstm_model = None`, dòng 280
  lấy trung bình XGBoost và Prophet rồi gán làm "dự đoán LSTM"). Kèm 8 file
  `.pkl` là artifact của nhánh này — trong đó 3 file thuộc phân hệ cũ
  (dengue_fever, seasonal_flu, respiratory_disease), không phải nhóm ICD hô hấp.
  *Dùng lại khi:* làm đối chứng XGBoost ở Tuần 4 — nhưng phải huấn luyện lại
  theo giao thức walk-forward, **không dùng lại MonthlyForecaster** (rò rỉ mục tiêu).

- **dich_vu_chet/** — service và Celery task 0 tham chiếu, cộng 4 file test
  nằm lẫn trong package sản phẩm.

- **sql_schema_cu/** — 4 file SQL truy vấn `KhamBenh`, `ChanDoan`, `BenhNhan`,
  `SuDungVatTu`, `VatTu`, `TonKho`: schema giả định thời chưa nối HIS thật.
  HIS thật dùng `TT_TIEPNHAN`, `TT_NGOAITRU_KHAMBENH`, `TM_ICD`, `TT_DUOC_TONKHO`.

- **frontend_chet/** — trang, hook và component 0 tham chiếu.
  `SupplyNormPage.tsx` còn không có `<Route>` nào trong `App.tsx`.

- **postgres/** — hệ quả quyết định giữ SQLite làm CSDL duy nhất. Để lại trong
  repo sẽ mâu thuẫn với kiến trúc đã chốt.

- **tap_nhap/** — script tạp, CSV kết quả tạm, file lạc chỗ ở gốc repo.

## Khôi phục
`git mv _archive/<nhóm>/<đường dẫn> <đường dẫn>` rồi hoàn lại 3 sửa đổi thủ
công ghi ở đầu `bo_ma_chet.sh`.

- `frontend_chet/components_dashboard/EpidemicMapCard.tsx` — thẻ bản đồ dịch tễ của Dashboard cũ; Dashboard v2 (11/09/2026) thay bằng thẻ "Trạng thái dữ liệu" vì hệ thống chỉ có một cơ sở.

- `ai_engine_cu/topdown.py` — Tầng 1 cũ của Dashboard (Ridge + lag trên tổng, chia theo tỷ trọng); chưa từng nằm trong bảng so sánh. Gỡ 11/09/2026 khi Dashboard chuyển sang ensemble M12 (`group_forecast.py`). Bảng `forecast_accuracy` nó ghi cũng không còn ai đọc.
