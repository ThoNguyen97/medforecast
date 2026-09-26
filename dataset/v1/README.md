# Bộ huấn luyện MedForecast — v1.0

Bộ dữ liệu này là chính dữ liệu đầu vào mà mô hình dự báo (Tầng 1) dùng để học,
xuất phẳng từ CSDL ứng dụng để có thể huấn luyện lại và kiểm chứng độc lập mà
không cần truy cập HIS, SQL Server hay CSDL SQLite của ứng dụng.

| File | Nội dung | Dòng |
|---|---|---|
| `nhom_thang.csv` | tháng × khối ICD: số ca, cờ COVID, cờ đã chốt, thời tiết cùng kỳ và trễ 1–2 tháng | 278 |
| `ma_thang.csv` | tháng × khối × mã ICD: số ca (gộp toàn quốc) | 938 |
| `ty_trong_co_dinh.csv` | tỷ trọng cố định mã trong khối (cho hướng top-down cố định) | 20 |
| `dim_icd.csv` | từ điển mã ICD: tên mã, khối, tên khối (tham chiếu) | 20 |
| `manifest.json` | phiên bản, ngày xuất, khoảng thời gian, số dòng, sha256 từng file, giao thức chia dữ liệu | — |
| `TU_DIEN_DU_LIEU.md` | từ điển: mỗi cột — ý nghĩa, đơn vị, nguồn, cách tính | — |
| `DATASHEET.md` | phạm vi, cách khử định danh, ô nhỏ, hạn chế đã biết, cách trích dẫn | — |

Bản `.parquet` cùng tên có khi máy xuất có `pyarrow`; nội dung giống CSV.

## Huấn luyện lại và dự báo

```bash
cd backend
python -m app.forecasting.train   --data ../dataset/v1 --out models/v1   # ~2–3 phút, cần statsmodels
python -m app.forecasting.predict --model models/v1/model_v1.pkl          # dự báo kỳ kế tiếp từ artifact
python -m app.forecasting.dataset --db data/medforecast.db --out ../dataset/v1   # xuất lại từ DB (khi có tháng mới)
```

`train.py` chạy walk-forward mở rộng cửa sổ (24 tháng huấn luyện tối thiểu,
67–68 bước kiểm định mỗi khối, mỗi bước huấn luyện lại trên toàn bộ quá khứ
trước bước đó), rồi huấn luyện lần cuối và ghi:

- `models/v1/model_v1.json` — cấu hình, thành viên, trọng số, hệ số lệch, dự
  báo kỳ kế tiếp, chỉ số backtest, sha256 của dataset đã dùng;
- `models/v1/model_v1.pkl` — thành viên đã khớp + trạng thái kết hợp (joblib),
  cho `predict.py` dùng không cần khớp lại.

Kết quả cần trùng với kết quả backtest chính thức trong `backend/ketqua_backtest/`
(`nhom.csv`, `phancap.csv`: RelMAE mức mã 0,500; mức nhóm 0,516 / 0,377 / 0,541).
Nếu không trùng thì hoặc dataset đã được xuất từ CSDL khác, hoặc cấu hình
`PRODUCTION_CONFIG` đã thay đổi; `model_v1.json` ghi cả hai để truy ngược.

## Áp cho bệnh viện khác

Tạo ba file cùng cấu trúc cột (xem `TU_DIEN_DU_LIEU.md`) từ HIS của bệnh viện
đích; tối thiểu là `nhom_thang.csv` với `period, block_code, year, month, cases,
is_covid, is_complete`. Thời tiết là tuỳ chọn (mô hình tự tắt thành viên thời
tiết nếu thiếu). Mô hình được khớp lại mỗi khi có tháng mới (vài chục giây), nên
quy trình vận hành theo tháng là *xuất → train → predict*.
