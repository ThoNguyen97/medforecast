# Triển khai MedForecast (pilot bệnh viện)

Đóng gói bằng Docker: PostgreSQL + Backend (FastAPI) + Frontend (React/Nginx).

## 1. Chuẩn bị
```bash
cp .env.example .env      # rồi sửa POSTGRES_PASSWORD, SECRET_KEY (bắt buộc)
```
Sinh SECRET_KEY mạnh: `python -c "import secrets;print(secrets.token_urlsafe(48))"`

## 2. Chạy
```bash
docker compose up -d --build
```
- Frontend: http://localhost:5173
- Backend API/docs: http://localhost:8000/docs
- PostgreSQL: cổng nội bộ 5432 (không mở ra ngoài)

Khi khởi động, backend tự tạo bảng ứng dụng + bảng tầng dữ liệu (mart) trong CÙNG
một PostgreSQL (hợp nhất nguồn dữ liệu).

## 3. Đồng bộ dữ liệu
- Nút **Đồng bộ HIS** trên Dashboard gọi `POST /api/v1/sync/run` (chỉ Admin/Thủ kho).
- Hoặc chạy nền định kỳ:
  ```bash
  docker compose exec backend python -m app.data_pipeline.scheduler
  ```
  (đặt `PIPELINE_CRON`, mặc định `0 2 * * *`).

## 4. Nối HIS thật (SQL Server)

**4.1. Cấu hình `.env`**
```
PIPELINE_SOURCE=sqlserver
PIPELINE_SQLSERVER_CONN=mssql+pyodbc://user:pass@his-host:1433/HIS?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes
PIPELINE_LOOKBACK_MONTHS=3     # nạp lại 3 tháng gần nhất mỗi lần đồng bộ
```
Ảnh Docker đã cài sẵn driver **msodbcsql18** (`backend/Dockerfile`). Gói `unixodbc-dev`
không đủ — thiếu driver thật sẽ báo `Can't open lib 'ODBC Driver 18 for SQL Server'`.

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
Thêm cron trên máy chủ:
```
0 2 * * *  DATABASE_URL=postgresql+psycopg2://medforecast:PASS@localhost:5432/medforecast \
           bash /đường-dẫn/backend/scripts/backup_db.sh
```
Giữ 30 ngày gần nhất; có kiểm thử khôi phục định kỳ.

## 6. Bảo mật
- `SECRET_KEY` bắt buộc khác mặc định (app chặn khởi động production nếu còn mặc định).
- `DEBUG=False` ở production (mặc định).
- Đặt Nginx/Proxy có HTTPS phía trước khi mở ra ngoài; giới hạn đăng nhập.
