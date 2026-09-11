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
  (RelMAE mức mã 0,659 — thắng seasonal-naive ~34%, cấu hình sản xuất 11/09/2026)
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
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create database and run migrations
alembic upgrade head

# Create initial admin user
python scripts/seed_data.py

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

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

## Chạy bằng Docker (dev)

Chạy cả 3 service (Postgres + backend + frontend) bằng `docker-compose.dev.yml`.
Mọi lệnh chạy tại **thư mục gốc repo** (nơi chứa `docker-compose.dev.yml`).

### Chuẩn bị
1. Cài & mở **Docker Desktop** (đợi icon báo *Engine running*).
2. Tạo file `.env` ở gốc repo (copy từ `.env.example`) — bắt buộc có `SECRET_KEY`
   và `POSTGRES_PASSWORD`, thiếu là compose báo lỗi ngay.
   ```powershell
   Copy-Item .env.example .env
   ```

### Build & khởi động
```powershell
# Lần đầu, hoặc sau khi sửa Dockerfile / requirements.txt
docker compose -f docker-compose.dev.yml up -d --build

# Các lần sau (image đã build sẵn)
docker compose -f docker-compose.dev.yml up -d

# Chỉ build, không chạy
docker compose -f docker-compose.dev.yml build

# Build lại sạch, bỏ cache (khi build lỗi lạ)
docker compose -f docker-compose.dev.yml build --no-cache
```

### Seed dữ liệu (lần đầu — tạo user admin)
```powershell
docker compose -f docker-compose.dev.yml exec backend python scripts/seed_data.py
```

### Truy cập
- Frontend: http://localhost:5173 (đăng nhập `admin` / `admin123`)
- API docs: http://localhost:8000/docs
- Postgres: `localhost:5432` (db `medforecast`, user `medforecast`)

### Theo dõi
```powershell
docker compose -f docker-compose.dev.yml ps              # trạng thái 3 service
docker compose -f docker-compose.dev.yml logs -f         # log tất cả
docker compose -f docker-compose.dev.yml logs -f backend # log riêng backend
```

### Dừng / dọn
```powershell
docker compose -f docker-compose.dev.yml stop            # dừng, giữ container
docker compose -f docker-compose.dev.yml down            # xóa container, GIỮ data (volume pgdata)
docker compose -f docker-compose.dev.yml down -v         # xóa luôn data DB + node_modules ⚠️
docker compose -f docker-compose.dev.yml restart backend
```

### Vào trong container
```powershell
docker compose -f docker-compose.dev.yml exec backend bash
docker compose -f docker-compose.dev.yml exec db psql -U medforecast -d medforecast
```

### Khi nào cần build lại?
Compose dev đã mount `./backend` và `./frontend` vào container nên **sửa code là tự
reload** (uvicorn `--reload`, Vite HMR) — không cần build lại. Chỉ build lại khi:
- Sửa `backend/Dockerfile` hoặc `backend/requirements.txt` → `up -d --build`
- Thêm package npm mới → `restart frontend` là đủ (service này chạy `npm install` mỗi lần start)

### Lỗi thường gặp
- **`docker : The term 'docker' is not recognized`** — PATH của terminal chưa có Docker
  CLI (thường do VSCode được mở trước khi cài Docker). Nạp lại PATH cho phiên hiện tại:
  ```powershell
  $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
  ```
  Cách dứt điểm: thoát **hẳn** VSCode (File → Exit) rồi mở lại.
- **`SECRET_KEY is required`** — thiếu `.env` ở gốc, hoặc đang chạy sai thư mục.
- **`port is already allocated`** (5432 / 8000 / 5173) — đang có backend/frontend chạy
  tay (theo `RUN_LOCAL.md`) chiếm cổng → tắt tiến trình đó trước.
- **`Cannot connect to the Docker daemon`** — Docker Desktop chưa khởi động xong.

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
├── docker-compose.yml      # Production
├── docker-compose.dev.yml  # Development (Postgres + backend + frontend)
├── .env.example            # Mẫu biến môi trường cho Docker
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

See [deployment documentation](docs/deployment.md) for production deployment instructions.

## Mô hình dự báo

Ensemble bốn mô hình thống kê, khớp lại trên toàn bộ lịch sử mỗi lần dự báo
(vài giây với chuỗi 92 điểm — không có bước huấn luyện định kỳ phải vận hành):

| Thành viên | Học gì | Thang |
|---|---|---|
| SeasonalTrend | hệ số mùa nhân + xu hướng tuyến tính giảm dần | trung bình |
| PoissonTrend | log1p(ca) ~ xu hướng + 11 biến giả tháng, Ridge λ=10 chuẩn hoá | log |
| Harmonic-Poisson | mùa sin/cos + nhiệt độ/độ ẩm/mưa **trễ 1–2 tháng** | log |
| SARIMAX (1,1,1)(1,0,0,12) | exog thời tiết chuẩn hoá; tuỳ chọn, cần `statsmodels` | log |

Trên đó là **dự báo phân cấp top-down động**: mô hình hoá chuỗi nhóm ICD rồi
chia xuống mã theo tỷ trọng EWMA. Mọi tham số nằm ở một chỗ:
`backend/app/forecasting/config.py` → `PRODUCTION_CONFIG`.

**Bằng chứng** (walk-forward mở rộng cửa sổ, 68 bước/nhóm, dữ liệu HIS thật):
RelMAE mức mã 0,659 — thắng seasonal-naive ~34%; khoảng dự báo 90% phủ thật
85–88%. Sinh lại bằng `python -m app.forecasting.run_eval`, chi tiết trong
`KetQua_Backtest_ChonCauHinh.md`.

**Không dùng deep learning.** 92 quan sát tháng trên mỗi chuỗi không đủ cho
LSTM; nhánh XGBoost/Prophet/LSTM cũ chưa từng chạy trong sản phẩm và đã chuyển
vào `_archive/ai_engine_cu/`.

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
