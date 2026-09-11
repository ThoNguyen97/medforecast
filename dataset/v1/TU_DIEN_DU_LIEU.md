# Từ điển dữ liệu — bộ huấn luyện MedForecast v1.0

Nguồn gốc chung: HIS PROD của bệnh viện → thủ tục `usp_MedForecast_DayDuLieu`
đẩy sang STA `MEDFORECAST_DW` (bảng `MF_CaBenh_Nhom`, view
`vw_MedForecast_CaBenhNhom`) → pipeline app nạp vào `mart_monthly_cases_by_block`
/ `fact_disease_case`; thời tiết từ Open-Meteo (archive API) nạp vào
`mart_monthly_weather`. Bộ này xuất bằng `python -m app.forecasting.dataset`,
dùng CÙNG hàm đọc (`data_access.py`) mà mô hình và backtest dùng.

## `nhom_thang.csv` — chuỗi tháng theo khối ICD (đầu vào Tầng 1, mức nhóm)

Khoá: (`period`, `block_code`). Một dòng = một tháng của một khối.

| Cột | Kiểu | Đơn vị | Ý nghĩa | Nguồn / cách tính |
|---|---|---|---|---|
| `period` | text `YYYY-MM` | — | tháng lịch | tháng của ngày vào viện / ngày khám |
| `block_code` | text | — | khối ICD-10: `J00-J06` nhiễm khuẩn cấp đường hô hấp trên, `J09-J18` cúm và viêm phổi, `J20-J22` nhiễm khuẩn cấp đường hô hấp dưới khác | `icd_hierarchy.py` gộp mã 3 ký tự vào khối |
| `year`, `month` | int | — | tách từ `period` | — |
| `cases` | int | lượt | **số lượt khám/điều trị có chẩn đoán chính thuộc khối**, đếm DISTINCT lượt ở HIS (một lượt mang J01 và J06 chỉ đếm một lần ở mức khối) | `MF_CaBenh_Nhom.SoCa` |
| `is_covid` | bool | — | tháng thuộc giai đoạn COVID (2020-01 → 2021-12): các thành viên hồi quy loại các tháng này khỏi ước lượng | hằng số theo lịch |
| `is_complete` | 0/1 | — | 1 = kỳ đã chốt; 0 = kỳ đang mở (tháng hiện tại, số còn tăng). **Mô hình chỉ học trên kỳ đã chốt** | so `period` với tháng đồng bộ gần nhất |
| `temp` | float | °C | nhiệt độ trung bình tháng, trạm đại diện TP.HCM | Open-Meteo `temperature_2m_mean`, trung bình các ngày |
| `humidity` | float | % | độ ẩm tương đối trung bình tháng | Open-Meteo `relative_humidity_2m_mean` |
| `rainfall` | float | mm | tổng lượng mưa tháng | Open-Meteo `precipitation_sum`, cộng các ngày |
| `temp_lag1`, `temp_lag2` | float | °C | nhiệt độ của 1 và 2 tháng trước — đặc trưng mà Harmonic-Poisson (trễ 1–2) và SARIMAX (trễ 1) thực sự dùng | `shift(1)`, `shift(2)` trên chuỗi đã sắp theo tháng của từng khối |
| `humidity_lag1/2`, `rainfall_lag1/2` | float | %, mm | tương tự | — |

Trống (NaN) ở cột thời tiết: tháng chưa có dữ liệu thời tiết. Khi thiếu quá
`weather_min_months` (12) tháng, mô hình tự tắt thành viên thời tiết.

## `ma_thang.csv` — chuỗi tháng theo mã ICD 3 ký tự (mức mã)

Khoá: (`period`, `block_code`, `icd_code`).

| Cột | Ý nghĩa |
|---|---|
| `icd_code` | mã ICD-10 3 ký tự (J00…J22), là chẩn đoán chính của lượt |
| `cases` | số lượt có chẩn đoán chính = mã này trong tháng, **gộp toàn quốc** (đã cộng các tỉnh). Tổng theo mã trong một khối có thể **lớn hơn** `cases` của khối vì một lượt có thể mang hai mã trong cùng khối |
| các cột còn lại | như `nhom_thang.csv` |

## `ty_trong_co_dinh.csv`

| Cột | Ý nghĩa |
|---|---|
| `share` | tỷ trọng lịch sử của mã trong khối (Σ ca mã / Σ ca các mã của khối, toàn bộ lịch sử), tổng theo khối = 1. Chỉ dùng cho hướng đối chứng *top-down cố định*; hướng sản xuất *top-down động* tính tỷ trọng EWMA (span 6) tại mỗi bước từ chính `ma_thang.csv` |

## Không có trong bộ này (và vì sao)

- **Tồn kho, tiêu hao vật tư, định mức**: thuộc Tầng 2–3 (quy đổi nhu cầu,
  DOI), không phải đầu vào của mô hình dự báo ca; sẽ đóng gói riêng nếu cần.
- **Phân theo tỉnh**: bản phát hành gộp toàn quốc để giảm nguy cơ tái định danh
  và vì mô hình sản xuất dự báo mức toàn quốc (`region = TOAN_QUOC`).
- **Mức độ nặng, tuổi, giới**: không cần cho Tầng 1; có trong HIS nhưng không
  xuất.
