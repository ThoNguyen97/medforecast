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

→ Thời tiết giảm ~8% sai số. `build_default_ensemble(use_weather=True)` tự thêm
mô hình này; service dùng cho dự báo TỔNG nhóm.
