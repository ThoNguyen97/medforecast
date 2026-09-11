# Nối app vào DB trung chuyển STA

Đang đọc file CSV. Để chuyển sang đọc thẳng `MEDFORECAST_DW` bên STAGING, dán
khối dưới vào cuối `backend/.env`, thay 3 chỗ ⚙, rồi **comment ba dòng cũ**
`PIPELINE_SOURCE=file` / `PIPELINE_DATA_DIR` ở phía trên.

```ini
# KHỐI CẤU HÌNH NỐI APP VÀO DB TRUNG CHUYỂN STA
# Dán vào cuối backend/.env, thay 3 chỗ ⚙, rồi XOÁ/COMMENT khối PIPELINE_* cũ.
# ⚠ Bỏ ba dòng cũ này đi (hoặc thêm dấu # ở đầu):
#   PIPELINE_SOURCE=file
#   PIPELINE_DATA_DIR=../../data
# --- Nguồn: DB trung chuyển bên STAGING. KHÔNG BAO GIỜ nối thẳng PROD --------
PIPELINE_SOURCE=sqlserver
# ⚙ 3 chỗ cần thay: TÊN_MÁY_STA, MẬT_KHẨU, và số hiệu driver (17 hay 18)
#   - Instance có tên  : @10.0.0.20\STA   (bỏ phần :1433)
#   - Instance mặc định: @10.0.0.20:1433
#   - Driver 18 mặc định bắt mã hoá → cần TrustServerCertificate=yes nếu chứng
#     chỉ là loại tự ký. Driver 17 thì không cần.
PIPELINE_SQLSERVER_CONN=mssql+pyodbc://medforecast_app:⚙MẬT_KHẨU@⚙10.0.0.20\STA/MEDFORECAST_DW?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
# --- Ba câu SQL đọc từ STA ---------------------------------------------------
PIPELINE_CASE_SQL_FILE=case_sta.sql
PIPELINE_INVENTORY_SQL_FILE=inventory_sta.sql
# ⚠ DÒNG QUAN TRỌNG NHẤT. Thiếu nó thì app vẫn chạy, vẫn ra số, nhưng số ca mức
# NHÓM bị cộng dồn từ các mã con — đếm trùng lượt khám mang nhiều mã cùng nhóm.
# Đo trên dữ liệu thật: lệch 181 ca. Log sẽ in WARNING nếu thiếu.
PIPELINE_CASE_GROUP_SQL_FILE=case_group_sta.sql
# --- Cửa sổ nạp lại: phải KHỚP @SoThangLuiLai của thủ tục bên PROD -----------
PIPELINE_LOOKBACK_MONTHS=3
# --- Lịch chạy: SO LE với job PROD (job 01:00 → app 02:00) ------------------
# Trùng giờ thì app đọc dữ liệu cũ một ngày.
PIPELINE_CRON=0 2 * * *
# --- Kho dữ liệu của app -----------------------------------------------------
# ⚙ Khi triển khai thật thì đổi sang Postgres:
# PIPELINE_DB_URL=postgresql+psycopg2://user:pass@localhost:5432/medforecast
PIPELINE_DB_URL=sqlite:///./data/medforecast_dw.db
# --- TM_ICD.xlsx: KHÔNG còn cần khi nguồn là STA -----------------------------
# Cột disease_group đã đi kèm dữ liệu (thủ tục PROD lấy từ TM_ICD.PHANNHOM).
# Giữ dòng dưới cũng được, nó chỉ là phương án dự phòng khi quay về nguồn file.
PIPELINE_ICD_DIR=../../data
```

## Kiểm tra trước khi đồng bộ thật

```bash
cd backend
python scripts/kiem_tra_ket_noi_sta.py
```

Chạy 5 nhóm kiểm tra (biến môi trường, driver ODBC, kết nối, cột nhóm bệnh, độ
tươi) và in rõ hỏng ở đâu, sửa thế nào. Đồng bộ thật mất vài phút và ghi vào DB;
chạy cái này trước để hỏng thì hỏng trong 5 giây.

## Ba chỗ hay vướng

**Login `medforecast_app` chưa tồn tại.** Phần tạo login nằm ở cuối
`sql_his/01_STA_tao_database_va_bang.sql` nhưng **đang bị chú thích**. Phải bỏ
chú thích, đặt mật khẩu, rồi chạy đoạn đó trên STA:

```sql
USE master;
CREATE LOGIN medforecast_app WITH PASSWORD = N'<<mật-khẩu-mạnh>>';
GO
USE MEDFORECAST_DW;
CREATE USER medforecast_app FOR LOGIN medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_CaBenh     TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_CaBenhNhom TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TonKho     TO medforecast_app;
GRANT SELECT ON dbo.MF_SyncLog                TO medforecast_app;
GO
```

Tài khoản này **chỉ đọc, và chỉ trên ba view** — không chạm được bảng gốc. Đây là
một điểm nên nêu trong phần an toàn dữ liệu của báo cáo.

**Driver ODBC chưa cài.** `pip install pyodbc` chưa đủ — pyodbc chỉ là lớp vỏ
Python, cần driver thật của Microsoft ("ODBC Driver 18 for SQL Server"). Script
kiểm tra sẽ liệt kê driver máy đang có và đối chiếu với chuỗi kết nối.

**Instance có tên.** Nếu STA chạy dạng `MÁY\STA` thì viết `@10.0.0.20\STA` và
**bỏ** phần `:1433` — hai thứ này không đi cùng nhau được.

## Sau khi đồng bộ

```bash
python -m app.data_pipeline.run --source sqlserver --full
```

Đọc log và tìm dòng `Nguồn không cấp số ca theo nhóm`. **Thấy dòng đó là chưa
xong** — biến `PIPELINE_CASE_GROUP_SQL_FILE` chưa ăn, và số ca mức nhóm sẽ bị
cộng dồn từ các mã con (lệch 181 ca trên dữ liệu thật). Không thấy là được.
