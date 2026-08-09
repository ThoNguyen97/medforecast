# data_pipeline — Tầng dữ liệu trung gian MedForecast

Đồng bộ dữ liệu từ nguồn (HIS SQL Server hoặc file export) vào **một DB trung gian**,
làm sạch & tổng hợp sẵn để phục vụ **huấn luyện mô hình** và **báo cáo tồn kho**.

## Luồng 3 tầng

```
Nguồn (HIS SQL Server / file CSV-Excel)
        │   connectors.py  (SourceConnector: SqlServerConnector | FileConnector)
        ▼
   STAGING   stg_case_supply, stg_inventory      ← landing, khử trùng theo row_hash
        │   pipeline.py  (làm sạch + cổng kiểm tra chất lượng + cờ COVID)
        ▼
   CLEAN     dim_icd, dim_supply, dim_region,
             fact_disease_case, fact_supply_usage, fact_inventory_snapshot
        │   pipeline.py  (tổng hợp)
        ▼
   MART      mart_monthly_cases_by_block   ← huấn luyện (dự báo phân cấp B1)
             mart_icd_share_in_block       ← tỷ trọng mã trong nhóm (B2/B3)
             mart_inventory                ← báo cáo tồn kho
```

## Đặc tính kỹ thuật

- **Trừu tượng nguồn**: đổi HIS ↔ file chỉ bằng đổi connector, không sửa pipeline.
- **Hợp đồng cột được ép chặt** (`_conform`): nguồn trả thiếu/thừa/lệch thứ tự cột
  vẫn không làm vỡ tầng sau bằng `KeyError`.
- **Nạp tăng dần (incremental)** theo watermark `last_period` trong `sync_state`,
  **lùi lại `PIPELINE_LOOKBACK_MONTHS` tháng** (mặc định 3) để bắt hồ sơ được chốt
  mã ICD muộn — chuyện thường gặp ở bệnh viện.
- **Idempotent**: chạy lại không nhân đôi dữ liệu (upsert theo khóa tự nhiên).
- **Cổng kiểm tra chất lượng**: chuẩn hóa mã ICD (`j01`→`J01`), loại dòng lỗi và đếm lại.
- **Cờ COVID** (2020–2021) + cờ tháng-trọn-vẹn (`is_complete` được **tính lại mỗi lần
  chạy** — xem `_refresh_completeness` — thay vì đóng băng lúc nạp).
- **Phân cấp ICD** Mã→Nhóm→Chương từ `TM_ICD` (3 nhóm đích: J00-J06, J20-J22, J09-J18).
- **DB-agnostic**: SQLite khi làm đồ án, PostgreSQL khi triển khai (chỉ đổi URL).

## Chạy

### Dev (nguồn file, SQLite)
```bash
PIPELINE_DB_URL=sqlite:///./data/medforecast_dw.db \
python -m app.data_pipeline.run --source file \
    --data-dir ../data --icd-dir ../data --full
```

### Triển khai (nguồn HIS SQL Server, PostgreSQL)
```bash
PIPELINE_DB_URL=postgresql+psycopg2://user:pass@host:5432/medforecast \
python -m app.data_pipeline.run --source sqlserver \
    --conn "mssql+pyodbc://user:pass@host:1433/HIS?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes" \
    --icd-dir ../data
```

#### Ba nguyên tắc BẮT BUỘC khi chỉnh SQL cho HIS

Chỉnh `DEFAULT_CASE_SQL` / `DEFAULT_INVENTORY_SQL` trong `connectors.py` theo schema
thật. Nếu phá vỡ một trong ba điều dưới, hệ thống **vẫn chạy nhưng ra số sai và
không báo lỗi** — đây là loại lỗi khó phát hiện nhất:

1. **`cases` = `COUNT(DISTINCT lượt khám)`** theo (tháng × mã ICD × tỉnh), **lặp lại**
   trên mọi dòng vật tư của nhóm đó. Pipeline lấy `max()` để khử phần lặp, nên nếu SQL
   trả `1 AS cases` cho từng lượt khám thì mọi tháng chỉ còn **đúng 1 ca**.
2. **Lọc `:since_date` trên cột ngày**, không bọc cột trong `FORMAT()`/`CONVERT()` ở
   `WHERE` — mất index, quét toàn bảng HIS sản xuất.
3. **Không lấy dữ liệu định danh bệnh nhân** (tên/CCCD/địa chỉ); chỉ cần tỉnh/thành.

Giữ đúng tên cột đầu ra (`CASE_COLUMNS` / `INV_COLUMNS`) là pipeline phía sau chạy
nguyên vẹn. Cột thiếu sẽ được `_conform` bù NULL kèm cảnh báo trong log.

#### Biến môi trường tinh chỉnh
| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `PIPELINE_LOOKBACK_MONTHS` | 3 | Số tháng nạp lại mỗi lần đồng bộ (bắt dữ liệu về muộn) |
| `PIPELINE_SQL_CHUNKSIZE` | 50000 | Số dòng mỗi lô khi đọc từ HIS |
| `PIPELINE_SQL_TIMEOUT` | 60 | Thời gian chờ tối đa một truy vấn (giây) |

### Lịch định kỳ (near-realtime)
```bash
PIPELINE_SOURCE=sqlserver PIPELINE_SQLSERVER_CONN="mssql+pyodbc://..." \
PIPELINE_CRON="0 2 * * *" python -m app.data_pipeline.scheduler
```

## Phụ thuộc thêm
```
pandas, openpyxl, sqlalchemy            # đã có
psycopg2-binary                          # Postgres (triển khai)
pyodbc                                   # SQL Server (triển khai)
apscheduler                              # lịch định kỳ
```

## Kết quả kiểm chứng (dữ liệu Gia An, 06/2019–05/2026)
- 33.640 dòng nguồn → 2.020 dòng `fact_disease_case` (đã khử trùng số ca lặp theo vật tư).
- Tỷ trọng nhóm J00-J06: J01 37,1% · J06 34,4% · J02 28,5% (dùng cho dự báo phân cấp).
- Cờ COVID gắn đúng cho 2020–2021. Chạy lại 3 lần không nhân đôi (idempotent).

## Tự kiểm tra
```bash
cd backend && python scripts/verify_his_pipeline.py --data-dir ../data
```
Script chạy 26 kiểm tra: không hồi quy số liệu, watermark lookback, `is_complete`
tự sửa, hợp đồng cột, đường đọc SQL Server (mô phỏng bằng SQLite), và **kiểm tra
ngược** để chứng minh SQL kiểu `1 AS cases` sẽ cho ra 1 ca/tháng.
