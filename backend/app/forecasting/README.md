# forecasting — Dự báo phân cấp từ tầng MART

Đọc chuỗi số ca theo tháng từ MART (`mart_monthly_cases_by_block`, `mart_icd_share_in_block`)
và `fact_disease_case`, dự báo theo cơ chế **phân cấp** và **so sánh 4 hướng** bằng
kiểm định walk-forward.

## Mô hình (numpy/pandas thuần — chạy ngay, không cần cài thêm)
- `NaiveForecaster`, `SeasonalNaiveForecaster` — baseline.
- `SeasonalTrendForecaster` — mức + hệ số mùa (nhân) + xu hướng giảm dần; ước lượng trên tháng không COVID.
- `PoissonTrendForecaster` — hồi quy log-tuyến tính (xấp xỉ Poisson) + Ridge.
- `Ensemble` — trung bình hóa. `build_default_ensemble()` tự thêm SARIMAX nếu cài `statsmodels`.

## Hòa giải phân cấp (`hierarchical.py`)
- `split_topdown` — top-down (chia theo tỷ trọng).
- `ewma_shares` — tỷ trọng ĐỘNG (EWMA) thay vì cố định.
- `reconcile_ols` — hòa giải MinT-OLS (dùng cả dự báo nhóm lẫn từng mã).

## Chạy so sánh
```bash
python -m app.forecasting.run_eval --db /path/medforecast_dw.db --min-train 24 --out ketqua.csv
```
Xuất bảng MAE/RMSE/MASE cho 4 hướng (bottom-up, top-down cố định, top-down động, MinT),
chọn phương án MASE thấp nhất. MASE < 1 nghĩa là tốt hơn seasonal-naive.

## Kết quả trên dữ liệu Gia An (min_train=24, 60 bước, MASE so seasonal-naive OUT-OF-SAMPLE)
| Hướng | MAE | RMSE | MASE |
|---|---|---|---|
| **Top-down động (EWMA)** | **20.37** | **26.57** | **0.746** |
| Top-down cố định | 21.03 | 27.36 | 0.772 |
| Hòa giải MinT-OLS | 21.94 | 28.47 | 0.810 |
| Bottom-up | 22.00 | 28.58 | 0.812 |

→ Top-down với **tỷ trọng động** cho sai số thấp nhất; mọi hướng đều MASE < 1
(tốt hơn seasonal-naive). Cắm thêm SARIMAX/Prophet và MinT có hiệp phương sai
co rút có thể cải thiện tiếp.

## Biến thời tiết (môi trường) — có độ trễ
`HarmonicPoissonForecaster(use_weather=True)` dùng nhiệt độ/độ ẩm/mưa (từ
`mart_monthly_weather`, nguồn Open-Meteo) ở **độ trễ 1–2 tháng** làm biến ngoại
sinh — không rò rỉ tương lai, đúng dịch tễ (bệnh bùng sau đợt thời tiết).

Hiệu quả thời tiết (walk-forward group-level, dữ liệu Gia An):
| Nhóm | KHÔNG thời tiết (MASE) | CÓ thời tiết (MASE) | Giảm MAE |
|---|---|---|---|
| J00-J06 | 0.780 | **0.715** | −8.4% |
| J20-J22 | 0.756 | **0.695** | −8.1% |

> **Đã làm rõ 11/09/2026.** Hai con số từng mâu thuẫn (−8% ở đây, −33% trong
> `KetQua_Backtest_ChonCauHinh.md`) đo HAI THỨ KHÁC NHAU: −33% là
> `HarmonicPoissonForecaster` ĐỨNG MỘT MÌNH, −8% gần với ensemble. Cả hai đều
> không đo cấu hình sản xuất. Từ nay `weather_effect()` so đúng ensemble sản
> xuất có/không thời tiết. Kết quả đo trên VM không có SARIMAX (chưa chính
> thức): J00-J06 −12,2% MAE, J09-J18 −6,8%, J20-J22 −8,0%. Số chính thức lấy
> từ `python -m app.forecasting.run_eval` chạy trên máy có statsmodels — xem
> `ketqua_backtest/thoitiet.csv` + `cau_hinh.json` kèm ngày chạy.
>
> Bảng cũ phía trên giữ lại như tư liệu; **không trích vào báo cáo**. `build_default_ensemble(use_weather=True)` tự thêm
mô hình này; service dùng cho dự báo TỔNG nhóm.
