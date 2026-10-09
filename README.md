# MedForecast AI

Hệ hỗ trợ ra quyết định (DSS) dự trù thuốc điều trị bệnh hô hấp cấp: dự báo số ca bệnh theo tháng, quy đổi thành nhu cầu thuốc và cảnh báo ngưỡng tồn kho.

| Tầng | Chức năng |
|---|---|
| Tầng 1: Dự báo số ca | Số ca theo tháng cho 3 nhóm ICD-10 (J00-J06, J09-J18, J20-J22). Ensemble thống kê (SeasonalTrend, PoissonTrend, Harmonic-Poisson có biến thời tiết trễ, SARIMAX, ETS), kết hợp theo nghịch đảo MAE, phân bổ xuống mã ICD theo tỷ trọng EWMA (top-down động). |
| Tầng 2: Quy đổi nhu cầu | Số ca dự báo nhân định mức thực nghiệm theo 5 rổ phân cấp chăm sóc (NGT, NT1, NT2, NT3, NT0), cộng nhu cầu nền. |
| Tầng 3: Cảnh báo tồn kho | Tồn hữu dụng theo FEFO và số ngày tồn phủ nhu cầu (DOI): Đỏ khi DOI ≤ 18 ngày, Vàng khi DOI ≤ 36 ngày, Xanh khi DOI > 36 ngày, Xám khi chưa đủ dữ liệu. |

Công nghệ: FastAPI, SQLAlchemy 2, SQLite, pandas, statsmodels, React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts.

## Luồng dữ liệu

1. Tại bệnh viện, dữ liệu được tổng hợp theo tháng, khử định danh và đồng bộ tự động hằng đêm sang cơ sở dữ liệu trung gian `MEDFORECAST_DW` (SQL Server). Script triển khai nằm trong `sql_his/`.
2. Ứng dụng đọc 7 view chỉ đọc `vw_MedForecast_*` của `MEDFORECAST_DW` và nạp về Data Mart SQLite nội bộ (`backend/data/medforecast.db`) theo cơ chế xóa rồi chèn (Delete-then-Insert) trên cửa sổ kỳ nạp lại.
3. Toàn bộ tính toán của ba tầng chạy trên SQLite; ứng dụng không truy vấn trực tiếp hệ thống HIS.

## Yêu cầu

- Python 3.11 trở lên, Node.js 18 trở lên.
- Microsoft ODBC Driver 17 hoặc 18 for SQL Server (chỉ cần khi đồng bộ từ `MEDFORECAST_DW`).

## Cài đặt và khởi chạy

Backend:

```bash
cd backend
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
python scripts/khoi_tao_moi.py      # tạo .env, CSDL SQLite, tài khoản admin, nạp dataset/v1
uvicorn app.main:app --reload --reload-dir app --port 8000
```

API chạy tại http://localhost:8000, tài liệu Swagger tại http://localhost:8000/docs.

Frontend:

```bash
cd frontend
npm ci
npm run dev                         # http://localhost:3000
```

Đăng nhập bằng `admin` / `admin123` và đổi mật khẩu sau lần đăng nhập đầu.

Sau bước khởi tạo, các màn hình dịch tễ và dự báo dùng được ngay với `dataset/v1`. Dữ liệu thuốc (tồn kho, định mức, cảnh báo thiếu hụt) có sau khi đồng bộ:

1. Vào Quản trị, mục Nguồn dữ liệu (CSDL DW): nhập máy chủ, database `MEDFORECAST_DW`, tài khoản `medforecast_app`.
2. Bấm Kiểm tra kết nối, sau đó Lưu cấu hình.
3. Tại trang Dữ liệu bệnh, bấm Nạp dữ liệu DW.

## Triển khai

```bash
# backend/.env: ENVIRONMENT=production, SECRET_KEY riêng, DEBUG=False
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
cd frontend && npm ci && npm run build   # phục vụ frontend/dist bằng Nginx (frontend/nginx.conf)
```

`backend/Dockerfile` và `frontend/Dockerfile` đóng gói từng thành phần. Khi mã nguồn thay đổi lược đồ trên máy đã có dữ liệu, chạy `python -m scripts.nang_cap_db --ap-dung`.

Script T-SQL phía bệnh viện, chạy theo thứ tự tên tệp:

| Thư mục | Nơi chạy | Nội dung |
|---|---|---|
| `sql_his/medforecast_dw/` (01 đến 04) | CSDL trung gian `MEDFORECAST_DW` | Tạo CSDL, bảng `MF_*`, view `vw_MedForecast_*`, tài khoản và quyền đọc |
| `sql_his/his_nguon/` (01 đến 05) | Máy chủ CSDL HIS | Linked server, 3 thủ tục `usp_MedForecast_*`, lịch chạy hằng đêm (SQL Agent) |

## Mô hình và kết quả kiểm định

```bash
cd backend
python -m app.forecasting.train --data ../dataset/v1 --out models/v1                # walk-forward và artifact
python -m app.forecasting.predict --model models/v1/model_v1.pkl                     # dự báo từ artifact
python -m app.forecasting.run_eval --db data/medforecast.db --out ketqua_backtest   # backtest Tầng 1
python scripts/backtest_tier2.py --db data/medforecast.db --out ketqua_backtest     # backtest Tầng 2
```

- `dataset/v1/`: bộ dữ liệu huấn luyện đã khử định danh, kèm manifest (sha256), từ điển dữ liệu và datasheet.
- `backend/models/v1/model_v1.json`: cấu hình, trọng số và chỉ số backtest của artifact.
- `backend/ketqua_backtest/`: kết quả walk-forward 68 bước mỗi nhóm (RelMAE mức mã 0,500 so với seasonal-naive).

Tham số mô hình tập trung tại `backend/app/forecasting/config.py` (`PRODUCTION_CONFIG`).

## Kiểm thử

```bash
cd backend && pytest
cd frontend && npm test
```

## Cấu trúc thư mục

```
backend/
  app/
    api/v1/          REST endpoints
    services/        nghiệp vụ DSS (dss_demand, dss_alerts, dss_dashboard), đồng bộ, dự báo
    forecasting/     mô hình, ensemble, phân cấp, walk-forward, CLI train/predict
    data_pipeline/   kết nối MEDFORECAST_DW, nạp fact/mart, view SQLite
    models/ schemas/ core/ utils/
  scripts/           khởi tạo, nâng cấp lược đồ, tạo admin, backtest Tầng 2
  tests/
  models/v1/  ketqua_backtest/
frontend/
  src/               pages, components, hooks, services, store, types, utils
dataset/v1/
sql_his/
  medforecast_dw/    bảng và view của CSDL trung gian
  his_nguon/         thủ tục tổng hợp và lịch đồng bộ phía HIS
```

## Biến môi trường chính (`backend/.env`)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/medforecast.db` | CSDL ứng dụng |
| `SECRET_KEY` | (bắt buộc đặt) | Khoá ký JWT |
| `ENVIRONMENT` | `development` | Giá trị `production` chặn khởi động nếu còn SECRET_KEY mặc định |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Origin của frontend |
| `PIPELINE_SQLSERVER_CONN` | (trống) | Chuỗi kết nối `MEDFORECAST_DW` cho CLI; giao diện lưu cấu hình riêng trong CSDL |

Tệp `.env` và `backend/data/*.db` chứa thông tin kết nối và dữ liệu bệnh viện, không nằm trong mã nguồn nộp.
