# MedForecast AI

Hệ hỗ trợ quyết định (DSS) dự báo số ca bệnh hô hấp và cảnh báo thiếu hụt thuốc từ dữ liệu HIS bệnh viện.

| Tầng | Chức năng |
|---|---|
| T1 — Dự báo | Số ca theo tháng cho 3 nhóm ICD-10 (J00-J06, J09-J18, J20-J22): ensemble thống kê (SeasonalTrend, PoissonTrend, Harmonic-Poisson có biến thời tiết trễ, SARIMAX, ETS), kết hợp nghịch đảo MAE, phân bổ xuống mã ICD theo tỷ trọng EWMA (top-down). |
| T2 — Quy đổi nhu cầu | Số ca → nhu cầu thuốc qua định mức thực nghiệm theo 5 rổ chăm sóc (NGT, NT1, NT2, NT3, NT0) + tiêu hao nền D_baseline. |
| T3 — Cảnh báo | Tồn khả dụng theo FEFO, số ngày tồn phủ nhu cầu (DOI): Đỏ ≤ 18 ngày, Vàng ≤ 36 ngày. |

**Công nghệ:** FastAPI · SQLAlchemy 2 · SQLite · pandas/statsmodels · React 18 + TypeScript · Vite · Tailwind CSS · TanStack Query · Recharts.

## Kiến trúc dữ liệu

```
HIS bệnh viện (PROD, SQL Server)
   │  usp_MedForecast_* — tổng hợp theo tháng, khử định danh (k = 5)      sql_his/prod/
   ▼
MEDFORECAST_DW trên STA — 12 bảng MF_*, 7 view vw_MedForecast_*        sql_his/sta/
   │  pyodbc (tài khoản chỉ đọc medforecast_app)
   ▼
Backend FastAPI (UAT) — ETL vào SQLite backend/data/medforecast.db
   ▼
Frontend React
```

## Yêu cầu

- Python 3.11+, Node.js 18+
- Microsoft ODBC Driver 17/18 for SQL Server (chỉ cần khi đồng bộ từ MEDFORECAST_DW)

## Cài đặt và chạy

**Backend**

```bash
cd backend
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
python scripts/khoi_tao_moi.py      # tạo .env, CSDL, tài khoản admin, nạp dataset/v1
uvicorn app.main:app --reload --reload-dir app --port 8000
```

API: http://localhost:8000 · Swagger: http://localhost:8000/docs

**Frontend**

```bash
cd frontend
npm ci
npm run dev                         # http://localhost:3000, proxy /api → localhost:8000
```

Đăng nhập: `admin` / `admin123` (đổi mật khẩu sau lần đăng nhập đầu).

Sau bước khởi tạo, các màn hình dịch tễ và dự báo chạy ngay trên `dataset/v1`. Dữ liệu vật tư (tồn kho, định mức, cảnh báo thiếu hụt) có sau khi đồng bộ: **Quản trị → Nguồn dữ liệu (CSDL DW)** → nhập máy chủ STA, database `MEDFORECAST_DW`, tài khoản `medforecast_app` → **Kiểm tra kết nối** → **Lưu cấu hình**; sau đó tại trang **Dữ liệu bệnh** bấm **Nạp dữ liệu DW**.

## Triển khai

```bash
# backend/.env: ENVIRONMENT=production, SECRET_KEY riêng, DEBUG=False
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
cd frontend && npm ci && npm run build   # phục vụ frontend/dist bằng Nginx (frontend/nginx.conf)
```

`backend/Dockerfile` và `frontend/Dockerfile` đóng gói từng thành phần (ảnh backend đã có msodbcsql18).
Khi mã nguồn thay đổi lược đồ trên máy đã có dữ liệu: `python -m scripts.nang_cap_db --ap-dung`.

**Cơ sở dữ liệu phía bệnh viện** — chạy theo thứ tự tên tệp:

| Thư mục | Nơi chạy | Nội dung |
|---|---|---|
| `sql_his/sta/01…05` | STA, CSDL `MEDFORECAST_DW` | Tạo CSDL, bảng MF_*, view vw_MedForecast_*, tài khoản và quyền đọc |
| `sql_his/prod/01…05` | HIS PROD | Linked server, 3 thủ tục `usp_MedForecast_*`, SQL Agent job |

## Mô hình và bằng chứng đánh giá

```bash
cd backend
python -m app.forecasting.train --data ../dataset/v1 --out models/v1          # walk-forward + artifact
python -m app.forecasting.predict --model models/v1/model_v1.pkl               # dự báo từ artifact
python -m app.forecasting.run_eval --db data/medforecast.db --out ketqua_backtest   # backtest Tầng 1
python scripts/backtest_tier2.py --db data/medforecast.db --out ketqua_backtest     # backtest Tầng 2
```

- `dataset/v1/` — bộ dữ liệu huấn luyện đã khử định danh, kèm manifest (sha256), từ điển dữ liệu, datasheet.
- `backend/models/v1/model_v1.json` — cấu hình, trọng số, chỉ số backtest của artifact.
- `backend/ketqua_backtest/` — kết quả walk-forward 68 bước/nhóm (RelMAE mức mã 0,500 so với seasonal-naive).

Tham số mô hình tập trung tại `backend/app/forecasting/config.py` (`PRODUCTION_CONFIG`).

## Kiểm thử

```bash
cd backend && pytest                 # unit + integration
cd frontend && npm test              # Vitest (unit)
```

## Cấu trúc thư mục

```
backend/
  app/
    api/v1/          REST endpoints
    services/        nghiệp vụ DSS (dss_demand, dss_alerts, dss_dashboard), đồng bộ, dự báo
    forecasting/     mô hình, ensemble, phân cấp, walk-forward, train/predict CLI
    data_pipeline/   kết nối MEDFORECAST_DW, ETL mart/fact, view SQLite
    models/ schemas/ core/ utils/
  scripts/           khởi tạo, nâng cấp lược đồ, tạo admin, backtest Tầng 2
  tests/
  models/v1/  ketqua_backtest/
frontend/
  src/ (pages, components, hooks, services, store, types, utils)
dataset/v1/
sql_his/sta/  sql_his/prod/
```

## Biến môi trường chính (`backend/.env`)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/medforecast.db` | CSDL ứng dụng |
| `SECRET_KEY` | — | Khoá ký JWT (bắt buộc đổi ở production) |
| `ENVIRONMENT` | `development` | `production` chặn khởi động nếu còn SECRET_KEY mặc định |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Origin frontend |
| `PIPELINE_SQLSERVER_CONN` | — | Chuỗi kết nối MEDFORECAST_DW cho CLI (giao diện lưu cấu hình riêng trong CSDL) |

Tệp `.env` và `backend/data/*.db` chứa thông tin kết nối và dữ liệu bệnh viện, không đưa vào mã nguồn nộp.
