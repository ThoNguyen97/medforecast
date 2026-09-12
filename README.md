# MedForecast AI - Hệ thống Dự báo Nhu cầu Vật tư Y tế

Hệ thống AI/ML dự báo nhu cầu vật tư y tế dựa trên dữ liệu môi trường và dịch tễ cho khu vực TP.HCM và các tỉnh lân cận.

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: SQLite 3.35+ (file-based, no server needed)
- **ORM**: SQLAlchemy 2.0
- **Authentication**: JWT (python-jose)
- **Background Tasks**: FastAPI BackgroundTasks (built-in)
- **Dự báo**: ensemble thống kê thuần numpy/pandas — SeasonalTrend +
  PoissonTrend + Harmonic-Poisson (thời tiết có độ trễ) + SARIMAX
  (statsmodels, tùy chọn). KHÔNG dùng deep learning: chuỗi chỉ 92 điểm
  tháng/mã, không đủ dữ liệu cho LSTM.

### Frontend
- **Framework**: React 18+ with TypeScript
- **Styling**: Tailwind CSS (Stitch Design System)
- **State Management**: React Query + Zustand
- **Charts**: Recharts
- **Build Tool**: Vite

### DevOps
- **Containerization**: Docker (optional for deployment)
- **Simple Deployment**: Single server with SQLite

## Features

- 🤖 **Dự báo nhu cầu**: ensemble 4 mô hình thống kê + dự báo phân cấp
  top-down động (EWMA), đánh giá bằng walk-forward mở rộng cửa sổ
  (RelMAE mức mã **0,500** — thắng seasonal-naive 50 %, cấu hình sản xuất M12,
  11/09/2026 chiều; xem `docs/KetQua_Backtest_ChonCauHinh.md` mục 0)
- 📊 **Real-time Dashboard**: Stitch design với metrics và charts
- 🚨 **Smart Alerts**: Cảnh báo thiếu hụt vật tư tự động
- 📦 **Inventory Management**: Quản lý tồn kho thời gian thực
- 📉 **Cảnh báo thiếu hụt**: 4 mức Đỏ/Vàng/Xanh/Xám theo số ngày tồn phủ
  nhu cầu (DOI) + FEFO, kèm lý do khi chưa đủ dữ liệu để kết luận
- 🔐 **Role-based Access**: 3 roles (Administrator, Pharmacist, Inventory_Manager)
- 📱 **Responsive Design**: Hoạt động trên desktop và mobile

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+

### Installation

#### 1. Clone repository
```bash
git clone <repository-url>
cd webyte
```

#### 2. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Tạo .env + bảng + tài khoản admin + nạp bộ dữ liệu dataset/v1 (một lệnh)
python scripts/khoi_tao_moi.py

# Chạy server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> `alembic` trong repo chỉ là bộ khung, **không dùng** — đừng chạy
> `alembic upgrade head`. Bảng được tạo bởi `Base.metadata.create_all` lúc khởi
> động; máy đã chạy trước đó mà mã nguồn vừa đổi bảng thì dùng
> `python -m scripts.nang_cap_db --ap-dung` (xem `RUN_LOCAL.md` mục 0.1).

Backend will be available at: http://localhost:8000
API Documentation: http://localhost:8000/docs

#### 3. Frontend Setup
```bash
cd frontend
npm install

# Run development server
npm run dev
```

Frontend will be available at: http://localhost:3000

**That's it!** No Docker, no Redis needed. Everything runs with SQLite.

## Triển khai (Docker)

**Hiện tại repo KHÔNG có `docker-compose.yml`.** Theo quyết định phạm vi đồ án
(xem `docs/DinhHinhLai_MedForecast_2026-09-09.md`, Quyết định 2), hệ chạy trên
**SQLite một tệp**, nhánh Postgres + compose đã chuyển vào `_archive/postgres/`
để tham khảo, không còn được bảo trì và không đảm bảo chạy được.

Cách chạy được kiểm thử thật:

| Tình huống | Làm gì |
|---|---|
| Máy mới vừa `git clone` | `RUN_LOCAL.md` mục 0 — `python scripts/khoi_tao_moi.py` |
| Máy đã chạy, mã nguồn vừa đổi bảng | `RUN_LOCAL.md` mục 0.1 — `python -m scripts.nang_cap_db --ap-dung` |
| Chạy hằng ngày (2 terminal) | `RUN_LOCAL.md` mục 1 và 2 |

`backend/Dockerfile` vẫn còn và build được ảnh backend đơn lẻ, nhưng chưa có
compose/hướng dẫn đi kèm nên **không phải đường chạy chính thức** của đồ án.

## Project Structure

```
webyte/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── ai_engine/      # ML models
│   │   └── core/           # Core utilities
│   ├── alembic/            # Database migrations
│   ├── tests/              # Backend tests
│   └── requirements.txt
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── hooks/          # Custom hooks
│   │   ├── services/       # API services
│   │   └── store/          # State management
│   └── package.json
├── data/                   # Data files and SQLite database
├── dataset/v1/             # Bộ huấn luyện công bố (CSV + manifest + datasheet)
├── docs/                   # Tài liệu đồ án (xem docs/README.md)
├── sql_his/                # Mã T-SQL phía bệnh viện (PROD → STA)
├── _archive/               # Mã đã gỡ khỏi phạm vi, giữ để tra cứu
├── RUN_LOCAL.md            # Chạy trên máy cá nhân
├── DEPLOY.md               # Triển khai pilot (SQLite một tệp)
└── README.md
```

## Environment Variables

### Backend (.env)
```bash
DATABASE_URL=sqlite:///./data/medforecast.db
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

REDIS_URL=redis://localhost:6379/0

# External APIs (optional)
OPENWEATHER_API_KEY=your-api-key
HEALTH_DEPT_API_URL=https://api.health.gov.vn
HEALTH_DEPT_API_KEY=your-api-key

# Email/SMS (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-password
```

### Frontend (.env)
```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Default Credentials

After running seed script:
- **Username**: admin
- **Password**: admin123
- **Role**: Administrator

⚠️ **Important**: Change default password in production!

## API Documentation

Interactive API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

### Backend Tests
```bash
cd backend
pytest
pytest --cov=app tests/  # With coverage
```

### Frontend Tests
```bash
cd frontend
npm run test
npm run test:coverage
```

## Deployment

Triển khai: xem `DEPLOY.md`; tài liệu đồ án: `docs/README.md`.

## Mô hình dự báo

Ensemble năm mô hình thống kê, khớp lại trên toàn bộ lịch sử mỗi lần dự báo
(vài giây với chuỗi 92 điểm — không có bước huấn luyện định kỳ phải vận hành):

| Thành viên | Học gì | Thang |
|---|---|---|
| SeasonalTrend | hệ số mùa nhân + xu hướng tuyến tính giảm dần | trung bình |
| PoissonTrend | log1p(ca) ~ xu hướng + 11 biến giả tháng, Ridge λ=10 chuẩn hoá | log |
| Harmonic-Poisson | mùa sin/cos + nhiệt độ/độ ẩm/mưa **trễ 1–2 tháng** | log |
| SARIMAX (1,1,1)(1,0,0,12) | exog thời tiết chuẩn hoá; cần `statsmodels` | log |
| ETS Holt–Winters | xu hướng giảm chấn + mùa cộng 12; cần `statsmodels` | log |

Các thành viên được **kết hợp bằng trọng số nghịch đảo MAE** trên 12 bước
walk-forward gần nhất (Bates–Granger) và **hiệu chỉnh lệch hệ thống** bằng hệ
số nhân ước lượng từ quá khứ (`app/forecasting/combine.py`). Trên đó là **dự
báo phân cấp top-down động**: mô hình hoá chuỗi nhóm ICD rồi chia xuống mã theo
tỷ trọng EWMA. Mọi tham số nằm ở một chỗ: `backend/app/forecasting/config.py`
→ `PRODUCTION_CONFIG`; mọi màn hình và backtest đi qua
`group_forecast.forecast_group_next`.

**Bằng chứng** (walk-forward mở rộng cửa sổ, 68 bước/nhóm, dữ liệu HIS thật):
RelMAE mức mã **0,500** — thắng seasonal-naive 50 %; mức nhóm 0,52 / 0,38 / 0,54;
lệch hệ thống −0,5 / −3,0 / +4,1 %; khoảng dự báo 90 % phủ thật 80–87 %. Sinh lại
bằng `python -m app.forecasting.run_eval`, chi tiết và các biến thể đối chứng
trong `docs/KetQua_Backtest_ChonCauHinh.md`.

**Không dùng deep learning.** 92 quan sát tháng trên mỗi chuỗi không đủ cho
LSTM; nhánh XGBoost/Prophet/LSTM cũ chưa từng chạy trong sản phẩm và đã chuyển
vào `_archive/ai_engine_cu/`.

## Cài trên máy mới

```bash
cd backend && pip install -r requirements.txt
python scripts/khoi_tao_moi.py      # .env + bảng + tài khoản + nạp dataset/v1
uvicorn app.main:app --reload --reload-dir app
```

`.env` và `data/*.db` không nằm trong git; script trên dựng lại từ `dataset/v1`
nên phần dịch tễ và dự báo chạy được ngay. Phần vật tư cần đồng bộ HIS — xem
`RUN_LOCAL.md` mục 0.

## Bộ huấn luyện đóng gói (`dataset/v1/`)

Đúng đầu vào mà mô hình học, xuất phẳng để huấn luyện lại không cần DB:
`nhom_thang.csv` (tháng × khối: số ca, COVID, đã chốt, thời tiết + trễ 1–2 tháng),
`ma_thang.csv` (tháng × mã ICD), `ty_trong_co_dinh.csv`, `manifest.json` (sha256,
giao thức chia walk-forward), từ điển dữ liệu và datasheet.

    cd backend
    python -m app.forecasting.train   --data ../dataset/v1 --out models/v1   # walk-forward + artifact
    python -m app.forecasting.predict --model models/v1/model_v1.pkl          # dự báo từ artifact
    python -m app.forecasting.dataset --db data/medforecast.db --out ../dataset/v1   # xuất lại

`models/v1/model_v1.json` ghi cấu hình, trọng số, hệ số lệch, dự báo kỳ tới và
chỉ số backtest kèm sha256 của dataset — kết quả trùng bảng chính thức
(RelMAE mã 0,500).

## Dữ liệu

- **Phạm vi**: 3 nhóm ICD hô hấp J00-J06 / J09-J18 / J20-J22 (20 mã), 2019–2026
- **Nguồn**: HIS eHospital → STA (đã khử định danh, ngưỡng ô nhỏ k=5) → SQLite
- **Môi trường**: nhiệt độ, độ ẩm, lượng mưa theo tháng (Open-Meteo), dùng ở độ trễ
- **Tối thiểu**: 24 tháng lịch sử để ensemble hoạt động; 26 tháng cho SARIMAX


## Support

For issues and questions:
- Create an issue on GitHub
- Contact: support@medforecast.ai

## License

Proprietary - All rights reserved

## Contributors

- Development Team
- Medical Advisory Board
- Data Science Team

---

**Version**: 1.0.0  
**Last Updated**: 2026-05-15
