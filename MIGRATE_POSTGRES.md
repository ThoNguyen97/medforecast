# Tạo job & đồng bộ dữ liệu lên PostgreSQL

Chuyển DB trung gian từ SQLite (bản làm) sang **PostgreSQL** (bản chuẩn/bảo vệ).
Code đã DB-agnostic — chỉ đổi cấu hình, không sửa mã.

> ✅ **ĐÃ KIỂM CHỨNG THẬT (2026-07-19)** trên PostgreSQL 16: migrate đủ 17 bảng
> (8.346 dòng dữ liệu, khớp 100% số dòng), pipeline sinh mart (2.020 fact,
> 1.652 mart tháng, 121 thời tiết, 1.672 tồn kho), idempotent (chạy lại
> ingest 0 dòng, số liệu không đổi), toàn bộ API chính trả 200 (forecast-hier
> J00-J06 = 111.3 khoảng [66,156], supply-plan 5 vật tư/4 thiếu — đúng bằng
> kết quả trên SQLite), INSERT mới không đụng sequence.
>
> Trong lần kiểm chứng đã phát hiện & sửa 5 lỗi tương thích (đã vào code):
> 1. `app/database.py` — `check_same_thread` chỉ truyền khi SQLite (Postgres từ chối); thêm `pool_pre_ping`.
> 2. `app/config.py` — thêm `extra: "ignore"` (pydantic-settings mới cấm biến PIPELINE_* trong .env).
> 3. `app/models/medical_supply.py` — `ten_hoat_chat` String(200)→String(500) (có tên dài 217 ký tự, Postgres enforce độ dài, SQLite thì không).
> 4. `app/services/hierarchical_forecast_service.py` — `MAX/MIN(boolean)` không tồn tại trên Postgres → `MAX(CASE WHEN ... THEN 1 ELSE 0 END)` (trước đó lỗi bị nuốt im lặng làm `by_code` rỗng → trang Kế hoạch nhập kho trống).
> 5. `app/api/v1/reports.py` — `func.strftime` (chỉ SQLite) → helper `_month_expr` tự chọn `strftime`/`to_char` theo DB.
>
> `scripts/migrate_to_postgres.py` cũng được nâng cấp: copy đúng thứ tự khóa
> ngoại, **reset sequence** sau copy, ép boolean/NULL, tự đối chiếu số dòng.

## Bước 1 — Chạy PostgreSQL bằng Docker (nhanh nhất)
```powershell
docker run -d --name medforecast-db `
  -e POSTGRES_DB=medforecast -e POSTGRES_USER=medforecast -e POSTGRES_PASSWORD=medforecast123 `
  -p 5432:5432 -v medforecast_pgdata:/var/lib/postgresql/data postgres:16-alpine
```
Kiểm tra: `docker ps` thấy container `medforecast-db` đang chạy.

## Bước 2 — Trỏ ứng dụng sang PostgreSQL
Sửa `backend\.env` (đổi 2 dòng — cho app và pipeline cùng 1 DB = hợp nhất):
```
DATABASE_URL=postgresql+psycopg2://medforecast:medforecast123@localhost:5432/medforecast
PIPELINE_DB_URL=postgresql+psycopg2://medforecast:medforecast123@localhost:5432/medforecast
```
(psycopg2-binary đã có trong requirements.)

## Bước 3 — Khởi động backend 1 lần để tạo bảng
```powershell
cd D:\Personnal\LienThong\CDTN\webyte\webyte\backend
venv\Scripts\activate
uvicorn app.main:app --port 8000
```
Thấy log `Database tables verified / created.` và `Data-pipeline (mart) tables verified / created.`
→ Postgres đã có đủ bảng (nhưng còn TRỐNG dữ liệu). Có thể tắt (Ctrl+C) sang bước 4.

## Bước 4 — Chuyển dữ liệu cấu hình từ SQLite sang Postgres
Postgres mới chưa có: tài khoản admin, danh mục vật tư, định mức, tỷ lệ mức độ, và
**thời tiết thật (Open-Meteo)**. Chạy script chuyển (một lần):
```powershell
$env:SQLITE_PATH="./data/medforecast.db"
$env:TARGET_DB_URL="postgresql+psycopg2://medforecast:medforecast123@localhost:5432/medforecast"
python scripts\migrate_to_postgres.py
```
Script copy: users (admin), medical_supplies, severity_rates, disease_supply_norms,
inventory, environmental_data (thời tiết)... KHÔNG copy bảng mart/fact (sẽ sinh lại ở bước 5).

## Bước 5 — Đồng bộ dữ liệu ca bệnh + tồn kho + mart
Chạy lại `uvicorn`, đăng nhập, vào **Dữ liệu bệnh → nút Đồng bộ HIS**.
Hoặc bằng lệnh (không cần mở web):
```powershell
$env:PIPELINE_DB_URL="postgresql+psycopg2://medforecast:medforecast123@localhost:5432/medforecast"
python -m app.data_pipeline.run --source file --data-dir ../data --icd-dir ../data --full
```
→ Sinh mart_monthly_cases_by_block, mart_monthly_weather, mart_inventory... trong Postgres.

## Bước 6 — Tạo JOB đồng bộ ĐỊNH KỲ (chọn 1 trong 2)

**Cách A — APScheduler (chạy trong tiến trình Python):**
```powershell
$env:PIPELINE_SOURCE="file"          # hoặc sqlserver khi nối HIS
$env:PIPELINE_DATA_DIR="../data"
$env:PIPELINE_ICD_DIR="../data"
$env:PIPELINE_DB_URL="postgresql+psycopg2://medforecast:medforecast123@localhost:5432/medforecast"
$env:PIPELINE_CRON="0 2 * * *"       # 02:00 mỗi ngày
python -m app.data_pipeline.scheduler
```

**Cách B — Windows Task Scheduler (khuyến nghị cho máy chủ Windows):**
- Tạo Task chạy hằng ngày, Action:
  - Program: `D:\...\backend\venv\Scripts\python.exe`
  - Arguments: `-m app.data_pipeline.run --source file --data-dir ../data --icd-dir ../data`
  - Start in: `D:\Personnal\LienThong\CDTN\webyte\webyte\backend`
  - Đặt biến môi trường PIPELINE_DB_URL trong hệ thống, hoặc dùng .env (app đã load_dotenv).

## Kiểm tra đã lên Postgres đúng
```powershell
docker exec -it medforecast-db psql -U medforecast -d medforecast -c "\dt"      # liệt kê bảng
docker exec -it medforecast-db psql -U medforecast -d medforecast -c "SELECT count(*) FROM mart_monthly_cases_by_block;"
```
Có bảng mart_* với số dòng > 0 là đồng bộ thành công.

## Sao lưu
`backend\scripts\backup_db.sh` (chạy qua cron/WSL) — pg_dump giữ 30 ngày. Xem DEPLOY.md.


---

## Phương án B — Dùng PostgreSQL trên Render.com (không cần cài local)

Rất hợp cho đồ án: không cài Docker/Postgres, chỉ lấy chuỗi kết nối rồi dán vào `.env`.

### B1. Tạo Postgres trên Render
- Vào https://dashboard.render.com → **New +** → **PostgreSQL**.
- Đặt Name (vd `medforecast`), chọn Region gần (Singapore), plan **Free**.
- Bấm **Create Database**, chờ trạng thái **Available**.

### B2. Lấy & sửa chuỗi kết nối
- Trong trang DB, mục **Connections** → copy **External Database URL**. Nó có dạng:
  ```
  postgresql://USER:PASS@dpg-xxxxx.singapore-postgres.render.com/DBNAME
  ```
- SỬA lại cho đúng driver + bật SSL (Render bắt buộc SSL khi kết nối từ ngoài):
  - Thêm `+psycopg2` sau `postgresql`.
  - Thêm `?sslmode=require` ở cuối.
  ```
  postgresql+psycopg2://USER:PASS@dpg-xxxxx.singapore-postgres.render.com/DBNAME?sslmode=require
  ```

### B3. Trỏ app sang Render (backend vẫn chạy ở máy em)
Trong `backend\.env` đặt CẢ HAI dòng bằng chuỗi vừa sửa:
```
DATABASE_URL=postgresql+psycopg2://USER:PASS@dpg-xxxxx.singapore-postgres.render.com/DBNAME?sslmode=require
PIPELINE_DB_URL=postgresql+psycopg2://USER:PASS@dpg-xxxxx.singapore-postgres.render.com/DBNAME?sslmode=require
```

### B4. Còn lại giống hệt Phương án A
- Chạy backend 1 lần → tạo bảng trên Render.
- Chạy `python scripts\migrate_to_postgres.py` (đặt `TARGET_DB_URL` = chuỗi Render) → chuyển cấu hình + thời tiết.
- Bấm **Đồng bộ HIS** → sinh mart trên Render.
- Kiểm tra: dùng nút **Connect → PSQL Command** trên Render, chạy `\dt` và `SELECT count(*) FROM mart_monthly_cases_by_block;`.

### Lưu ý quan trọng
- **Bảo mật/dữ liệu thật:** Render là cloud đặt ở nước ngoài. Dùng cho **đồ án/demo với dữ liệu mẫu (Gia An)** thì OK. Nhưng khi triển khai thật với dữ liệu bệnh nhân (PII), phải đặt Postgres **on-prem trong bệnh viện** — nêu rõ điều này trong báo cáo.
- Gói Free của Render giới hạn (~1GB, có thể hết hạn sau ~90 ngày) — vẫn dư cho đồ án.
- Kết nối cloud chậm hơn local một chút, nhưng dữ liệu nhỏ nên không đáng kể.
- (Tùy chọn nâng cao) Có thể deploy CẢ backend + frontend lên Render (Web Service) để chạy online — khi cần mình hướng dẫn riêng.
