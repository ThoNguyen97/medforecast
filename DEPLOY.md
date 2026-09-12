# Triển khai MedForecast (pilot bệnh viện)

Một máy chủ, **SQLite một tệp** (`backend/data/medforecast.db`), backend FastAPI +
frontend React build tĩnh. Không cần PostgreSQL, không cần Redis.

> **Lưu ý:** repo KHÔNG còn `docker-compose.yml`. Nhánh Postgres + compose đã
> chuyển vào `_archive/postgres/` theo Quyết định 2
> (`docs/DinhHinhLai_MedForecast_2026-09-09.md`) và không còn được bảo trì.
> Mọi lệnh dưới đây chạy trực tiếp trên máy chủ.

## 1. Chuẩn bị
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
Trong `.env` bắt buộc đổi `SECRET_KEY` (app **chặn khởi động** ở production nếu
còn giá trị mặc định) và đặt `ENVIRONMENT=production`, `DEBUG=False`:
```bash
python -c "import secrets;print(secrets.token_urlsafe(48))"
```
Cần driver ODBC cho SQL Server nếu nối HIS (§4): `msodbcsql17` hoặc `18`.

## 2. Tạo dữ liệu ban đầu và chạy
```bash
# Tạo bảng + tài khoản admin (+ nạp dataset/v1 nếu muốn có sẵn số ca để xem)
python scripts/khoi_tao_moi.py

# Chạy (production: bỏ --reload, đặt số worker theo CPU)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```
Đổi mật khẩu `admin` ngay sau lần đăng nhập đầu tiên.

Frontend:
```bash
cd frontend && npm ci && npm run build     # ra dist/
```
Trỏ Nginx vào `frontend/dist`, proxy `/api` sang `http://127.0.0.1:8000`.

**Nâng cấp phiên bản sau này:** `git pull` rồi
`python -m scripts.nang_cap_db --ap-dung` (so lược đồ khai báo với DB thật, tự
sao lưu trước khi sửa) — xem `RUN_LOCAL.md` mục 0.1. Đừng dùng `alembic`: thư
mục đó chỉ là bộ khung, không vận hành.

## 3. Đồng bộ dữ liệu
- Nút **Đồng bộ HIS** trong giao diện gọi `POST /api/v1/sync/run` (chỉ
  Administrator / Inventory_Manager).
- Chạy nền định kỳ:
  ```bash
  cd backend && python -m app.data_pipeline.scheduler
  ```
  (đặt `PIPELINE_CRON`, mặc định `0 2 * * *`; cần `PIPELINE_SOURCE=sqlserver`
  và `PIPELINE_SQLSERVER_CONN` trong `.env`, hoặc cấu hình sẵn ở
  **Quản trị → Kết nối HIS** — cấu hình lưu trong DB thắng `.env` và đổi không
  cần khởi động lại).
- Kiểm tra tình trạng nguồn: `python scripts/kiem_tra_ket_noi_sta.py`.

## 4. Nối HIS thật (SQL Server)

**4.1. Cấu hình `.env`**
```
PIPELINE_SOURCE=sqlserver
PIPELINE_SQLSERVER_CONN=mssql+pyodbc://user:pass@his-host:1433/HIS?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes
PIPELINE_LOOKBACK_MONTHS=3     # nạp lại 3 tháng gần nhất mỗi lần đồng bộ
```
Phải cài **driver ODBC thật** trên máy chủ (`msodbcsql17` hoặc `msodbcsql18`);
gói `unixodbc-dev` không đủ — thiếu driver sẽ báo
`Can't open lib 'ODBC Driver 18 for SQL Server'`. Số phiên bản trong chuỗi kết nối
phải khớp driver đã cài. `backend/Dockerfile` (nếu dùng) đã cài sẵn msodbcsql18.

**4.2. Chỉnh câu SQL** trong `backend/app/data_pipeline/sql/` cho khớp schema HIS
(chọn file bằng `PIPELINE_CASE_SQL_FILE` / `PIPELINE_INVENTORY_SQL_FILE`).
Khuyến nghị đọc qua DB trung gian STA thay vì PROD — xem `sql_his/README.md`. Ba nguyên tắc
**bắt buộc giữ**, nếu phá vỡ thì hệ thống chạy nhưng ra số sai mà không báo lỗi:

1. `cases` = `COUNT(DISTINCT lượt khám)` theo (tháng × mã ICD × tỉnh), **lặp lại**
   trên mọi dòng vật tư. **Không** dùng `1 AS cases` — pipeline lấy `max()` để khử
   phần lặp, nên `1 AS cases` sẽ cho ra đúng 1 ca/tháng cho mọi mã bệnh.
2. Lọc theo `:since_date` trên **cột ngày**, không bọc cột trong `FORMAT()`/`CONVERT()`
   ở mệnh đề `WHERE` (mất index → quét toàn bảng HIS sản xuất).
3. Không lấy dữ liệu định danh bệnh nhân (tên/CCCD/địa chỉ) — chỉ cần tỉnh/thành.

**4.3. Tài khoản & mạng.** Dùng tài khoản **chỉ đọc (SELECT)**; tốt nhất đề nghị bệnh
viện tạo sẵn **VIEW** rồi cấp quyền trên view. Kết nối trong mạng nội bộ, chạy đồng bộ
ngoài giờ cao điểm.

**4.4. Kiểm chứng trước khi tin số liệu.** Nạp thử **1 tháng**, so tổng số ca theo tháng
với báo cáo thống kê của phòng KHTH. Lệch quá 2% là mapping sai — dừng lại, đừng chạy
tiếp toàn bộ lịch sử.

**4.5. Tự kiểm tra pipeline** (không cần HIS, dùng dữ liệu file):
```bash
cd backend && python scripts/verify_his_pipeline.py --data-dir ../data
```

## 5. Sao lưu
SQLite: chỉ cần sao chép tệp, nhưng **phải dùng lệnh backup của sqlite3** để
không bắt được bản ghi đang dở:
```
0 2 * * *  sqlite3 /đường-dẫn/backend/data/medforecast.db \
           ".backup '/sao-luu/medforecast_$(date +\%Y\%m\%d).db'"
```
Giữ 30 ngày gần nhất, nén lại, và **kiểm thử khôi phục định kỳ** — một bản sao
chưa từng mở lại không phải bản sao. Tệp DB chứa dữ liệu bệnh viện: đặt trong
thư mục chỉ chủ sở hữu đọc được, không đưa lên git, không gửi ra ngoài.

## 6. Bảo mật
- `SECRET_KEY` bắt buộc khác mặc định (app chặn khởi động production nếu còn mặc định).
- `DEBUG=False` ở production (mặc định).
- Đặt Nginx/Proxy có HTTPS phía trước khi mở ra ngoài; giới hạn đăng nhập.
