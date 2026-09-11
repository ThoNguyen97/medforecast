# RÀ SOÁT TOÀN DIỆN MÃ NGUỒN & KIẾN TRÚC — MedForecast AI

**Ngày:** 09/09/2026 · **Phạm vi:** Backend FastAPI, Data Pipeline, AI Engine, Frontend React
**Quy mô kiểm tra:** 48.764 dòng Python (192 file) + 25.502 dòng TS/TSX (176 file) + 20 file SQL (HIS PROD / STA / LOCAL)
**Phương pháp:** đọc mã trực tiếp, grep import ngược, đối chiếu schema `.sql` ↔ SQLAlchemy model ↔ TypeScript type, kiểm tra biên dịch. Mọi phát hiện đều dẫn `file:dòng` đã kiểm chứng — không có suy đoán.

---

## 1. TÓM TẮT ĐIỀU HÀNH

Hệ thống **biên dịch sạch** (`compileall` exit 0), 19/19 router được đăng ký, và **nhánh DSS mới (`app/forecasting` + `dss_*`) là một thiết kế tốt** — backtest walk-forward đúng chuẩn, tự khai báo khi dữ liệu rỗng thay vì che giấu. Đây là phần nên dùng làm chuẩn mực.

Vấn đề không nằm ở chất lượng từng dòng mã, mà ở **việc tái cấu trúc đã làm nửa chừng và dừng lại**. Kết quả là hệ thống hiện mang **hai kiến trúc song song**: một bản DSS 3 tầng đúng chuẩn (chỉ phục vụ Dashboard), và một bản "tất-cả-trong-API" cũ vẫn đang chạy và vẫn hiển thị cho người dùng. Hai bản này cho **hai câu trả lời khác nhau cho cùng một câu hỏi nghiệp vụ**.

| Tiêu chí | Điểm | Nhận định |
|---|---|---|
| Độ sạch mã | **4/10** | ~6.500 dòng code chết còn trong `app/`; 12 file test lẫn trong package sản phẩm |
| Tính nhất quán | **3/10** | 4 bản tính nhu cầu vật tư, 4 bản dự báo, 2 bản cảnh báo — chạy song song |
| Tương thích CSDL | **4/10** | 4 file SQL trỏ schema HIS không tồn tại; DSS khoá cứng SQLite; Alembic thực chất không dùng |
| Dọn phân hệ mua sắm | **3/10** | Logic đã cắt ở lõi nhưng **UI vẫn hiển thị đầy đủ**: "Đề xuất nhập kho", "Ngưỡng AT", "Lead (ngày)", "đặt hàng ngay" |
| Chuẩn DSS 3 tầng | **5/10** | Tầng đúng chuẩn tồn tại nhưng chỉ phủ 1 trong 4 màn hình chính |
| An toàn / bảo mật | **4/10** | Thiếu kiểm tra quyền trên 2 bảng tham số điều khiển toàn bộ phép tính |

**Bốn vấn đề phải xử lý trước tiên:**

1. **Số liệu người dùng nhìn thấy có thể sai** — báo cáo tồn kho lọc trên `safety_stock` đã bị vô hiệu hoá (luôn = 0) → luôn trả rỗng, không báo lỗi (`reports.py:1119-1122`).
2. **Chỉ số "độ chính xác mô hình" hiển thị trên giao diện là sai số huấn luyện, và mô hình rò rỉ mục tiêu vào đặc trưng** (`monthly_forecaster.py:79-82,122,166`).
3. **Bất kỳ tài khoản nào cũng sửa được định mức và tỷ lệ phân độ** — hai bảng quyết định toàn bộ kết quả tính nhu cầu (`admin_severity.py`, 10 endpoint dùng `get_current_user` thay vì `get_admin_user`).
4. **Cập nhật tồn kho qua `types/inventory.ts` hỏng im lặng** — không một tên trường nào khớp backend (`types/inventory.ts:26-43` vs `schemas/base.py:155-180`).

---

## 2. BẢN ĐỒ HỆ THỐNG

```
                    ┌─────────────── HIS PROD (GIAAN115_HIS, SQL Server) ───────────────┐
                    │ TT_TIEPNHAN · TT_NGOAITRU_KHAMBENH · TT_NOITRU_* · TM_ICD         │
                    │ TM_DUOC · TT_DUOC_TONKHO                                          │
                    └───────────────────────────┬───────────────────────────────────────┘
                       usp_MedForecast_DayDuLieu │ usp_..DayTieuHaoToanVien │ usp_..DayKhoCungUng
                    ┌───────────────────────────▼───────────────────────────────────────┐
                    │ STA · MEDFORECAST_DW                                              │
                    │ MF_CaBenh_VatTu · MF_CaBenh_Nhom · MF_TonKho                      │
                    │ MF_TieuHao_Tong · MF_CaBenh_PhanCap · MF_TieuHao_PhanCap           │
                    │ MF_TonKho_Lo · MF_LichSuNhap✗ · MF_VatTu_ThuocTinh✗                │
                    └──────────┬────────────────────────────────┬───────────────────────┘
          DataPipeline.run()   │                                │  dss_loader.load_all()
          (nút "Đồng bộ" gọi)  │                                │  ⚠ CHỈ CHẠY TAY qua CLI
                    ┌──────────▼──────────┐         ┌───────────▼──────────────┐
                    │ stg_* → dim_* →     │         │ fact_usage_total          │
                    │ fact_disease_case   │         │ fact_cases_by_care_level  │
                    │ mart_monthly_*      │         │ fact_usage_by_care_level  │
                    └──────────┬──────────┘         │ fact_inventory_lot        │
                               │                    └───────────┬──────────────┘
                    ┌──────────▼────────────────────────────────▼──────────────┐
                    │ SQLite LOCAL (medforecast.db)                            │
                    │ disease_cases · medical_supplies · inventory             │
                    │ + 4 VIEW ⚠ tạo THỦ CÔNG, code không tạo                  │
                    └──────┬───────────────────────────────┬───────────────────┘
                           │                               │
        ┌──────────────────▼─────────────┐   ┌─────────────▼──────────────────────┐
        │ NHÁNH MỚI (đúng 3 tầng)        │   │ NHÁNH CŨ (tất-cả-trong-API)        │
        │ topdown → dss_demand →         │   │ forecast_analysis.py (1.441 dòng)  │
        │ dss_alerts, qua dss_runner     │   │ 3 engine chạy tuần tự, ghi đè nhau │
        │ → /dashboard/*  (1 màn hình)   │   │ → /forecast/*, /alerts, /reports   │
        └────────────────────────────────┘   └────────────────────────────────────┘

✗ = nạp dữ liệu nhưng không có mã nào đọc
```

**Phân bổ mã:** `app/ai_engine` 9.836 dòng (≈70% là code chết) · `app/forecasting` 1.971 dòng (đang dùng) · `api/v1/reports.py` 2.279 dòng · `api/v1/forecast_analysis.py` 1.441 dòng.

---

## 3. PHÁT HIỆN NGHIÊM TRỌNG (P0 — xử lý trong đợt tới)

### P0-1 · Chỉ số "độ chính xác mô hình" trên giao diện là sai số huấn luyện, mô hình lại rò rỉ mục tiêu
`backend/app/ai_engine/monthly_forecaster.py:79-82, 122, 166-215`

```python
# :79-82  — trung bình cả chuỗi, gồm chính hàng i
self.monthly_baselines[month] = month_data.mean()
# :122   — dùng làm đặc trưng đầu tiên cho hàng i
baseline = self.monthly_baselines.get(month, 0.0)
# :166   — dự đoán trên CHÍNH tập đã fit
final_preds = np.maximum(X_design @ coefs, 0)
```

Không có bất kỳ train/test split hay walk-forward nào trong file. MAE/RMSE/MAPE/R² tính từ `y` và `final_preds` in-sample, rồi `POST /forecast/train` (`forecast_analysis.py:412`) quảng cáo là *"độ chính xác cho từng bệnh"* và frontend hiển thị. `weather_correlations/means/stds` (`:85-95`) cũng ước lượng trên toàn bộ dữ liệu.

→ **Người dùng đang nhìn sai số huấn luyện và tưởng là sai số dự báo.** Đây là rủi ro cao nhất về mặt học thuật lẫn vận hành.
**Sửa:** gỡ `POST /forecast/train` và `/ml-analyze` (đã có `RaSoat_DeCuong_vs_ThucTe.md:79` đặt việc này); nếu giữ, phải đổi nhãn thành "sai số huấn luyện" và thay bằng walk-forward như `evaluate.py:20`.

### P0-2 · Thiếu kiểm tra quyền trên hai bảng tham số điều khiển toàn bộ phép tính
`backend/app/api/v1/admin_severity.py` — 10/10 endpoint dùng `Depends(get_current_user)`

`PUT /severity-rates/{icd_code}` (:112), `PUT /supply-norms` (:344), `PUT /supply-norms/bulk` (:432), `DELETE /supply-norms/{id}` (:496), `POST /severity-rates/recompute` (:599) — **không có `get_admin_user`**, dù mount cùng prefix `/api/v1/admin` với `admin_catalog.py` (file này lại dùng đúng).

`disease_supply_norms` và `severity_rates` là hai bảng quyết định mọi con số nhu cầu vật tư. Tài khoản `Inventory_Manager` sửa được.
**Sửa:** `APIRouter(dependencies=[Depends(get_admin_user)])` ở đầu file.

### P0-3 · Một endpoint 566 dòng chứa trọn cả ba tầng DSS, ba engine ghi đè nhau
`backend/app/api/v1/forecast_analysis.py:563-1129`

`POST /forecast/analyze` tự làm: truy vấn thô → heuristic baseline (`_compute_one_region`, :640-663) → gọi ML `DBForecastingService.analyze()` (:723-745) → gọi tiếp `group_ensemble_service.du_bao_nhom()` (:764-808) **ghi đè kết quả trên** → ghi DB → sinh `SupplyRequirement` → sinh Alert (:1049-1077).

Nếu ensemble ném lỗi, `except Exception` (:809) nuốt và trả về số của engine trước — **người dùng không biết mình đang xem kết quả của mô hình nào.** Kèm N+1 nặng: vòng lặp qua mọi tỉnh, mỗi tỉnh ~16 query (:670-696), rồi lặp lần hai train một ensemble cho từng tỉnh (:783-793). 20 tỉnh ≈ 320+ query và 20 lần huấn luyện trong một request HTTP.

Ba hàm này còn khai `async def` mà gọi code đồng bộ (`:407, :438, :564`) → **chặn event loop, treo toàn bộ worker**.
**Sửa:** (a) đổi 3 hàm sang `def` thường ngay — sửa một dòng, hết treo worker; (b) rút khối tính toán vào `analysis_service.py`, chọn MỘT engine.

### P0-4 · Hai bản tính nhu cầu vật tư copy-paste, ghi vào hai bảng khác nhau
`supply_recommendation_service.py:194-219` vs `supply_requirement_service.py:304-329`

Trùng từng dòng: `mild_cases = round(cases × mild_rate/100)` → `Σ(ca × định mức)` → `× (1 + 15%)`. Hằng `DEFAULT_BUFFER_RATE = 15.0` khai hai chỗ (`:29` và `:280`, chỗ thứ hai khai *bên trong hàm*). Kết quả ghi vào `supply_recommendations` và `supply_requirements` — **hai màn hình lệch nhau khi một bên chạy lại.**

Tổng cộng có **4 nguồn tính nhu cầu song song đang chạy**: hai bản trên + `supply_planning_service` (cận trên dự báo phân cấp) + `dss_demand` (rổ chăm sóc NGT/NT1-3).
**Sửa:** giữ `supply_recommendation_service`, viết lại `supply_requirement_service.generate_requirements_for_forecast` để gọi nó; dài hạn dồn về `dss_demand`.

### P0-5 · Cập nhật tồn kho từ frontend hỏng im lặng
`frontend/src/types/inventory.ts:26-43` vs `backend/app/schemas/base.py:155-180`

| Frontend khai | Backend nhận |
|---|---|
| `quantity_on_hand` | `current_stock` |
| `safety_stock_level` | `safety_stock` |
| `reorder_point`, `storage_capacity`, `stock_status` | *(không tồn tại)* |
| — | `location`, `batch_number`, `expiry_date` |

**Không một tên trường nào trùng.** `inventoryService.ts:29-35` gửi `InventoryUpdateRequest` tới `PUT /inventory/{id}`; Pydantic bỏ qua field lạ → tất cả = None → cập nhật không có hiệu lực, HTTP 200, không báo lỗi. Mã đang chạy né type này (`pages/Inventory.tsx:124,869` dùng đúng tên backend), nên lỗi chỉ nổ khi ai đó tin vào type.

### P0-6 · Bốn file SQL trỏ vào schema HIS không tồn tại, lại là mặc định
`backend/app/data_pipeline/sql/{case_mssql,case_sqlite,inventory_mssql,inventory_sqlite}.sql`

SELECT các bảng `KhamBenh`, `ChanDoan`, `BenhNhan`, `SuDungVatTu`, `VatTu`, `TonKho` — grep toàn `sql_his/` (trừ `_cu_schema_gia_dinh`): **không bảng nào tồn tại**. Đây là schema giả định cũ; HIS thật là `TT_TIEPNHAN`, `TT_NGOAITRU_KHAMBENH`, `TM_ICD`, `TT_DUOC_TONKHO`.

Không phải file chết: `connectors.py:231-233` đặt làm **mặc định**, `:331-332` nạp sẵn lúc import, `sync_config_service.py:47-48` phơi ra UI dưới profile `"mssql"`. Chọn profile này = `Invalid object name 'KhamBenh'`.
**Sửa:** xoá 4 file, đổi mặc định sang `case_sta.sql`/`inventory_sta.sql`, bỏ profile `"mssql"`.

### P0-7 · Alembic thực chất không được dùng, có 4 cơ chế đổi schema song song
- `alembic/versions/` chỉ có `remove_district_ward.py`, `down_revision = None`.
- `main.py:24` gọi `Base.metadata.create_all()` mỗi lần khởi động → schema do `create_all` quyết định.
- Trên DB mới, `disease_cases` **không có** cột `district_ward` → `alembic upgrade head` sẽ **fail**.
- `alembic.ini:55` hardcode `sqlite:///./data/medforecast.db`; `env.py:40-44` không đọc `settings.DATABASE_URL` → **alembic không bao giờ trỏ được vào Postgres** dù `MIGRATE_POSTGRES.md` mô tả việc đó.
- `alembic/env.py:11-12` chỉ nạp `app.models`, **không thấy 12 bảng** của `data_pipeline/models.py` (Base riêng).

Bốn cơ chế song song: `create_all` · `dss_loader.py:159-216` (4 `CREATE TABLE`, **trùng DDL** với `Phase0_04:87-106`) · `sync_service.py:126-129` (`ALTER TABLE` chạy lén trong lúc đồng bộ) · `scripts/recreate_database.py` (`drop_all` — **xoá sạch dữ liệu**).

→ **Không có đường nâng cấp schema nào tái lập được.**

---

## 4. PHÁT HIỆN MỨC CAO (P1)

| # | Vị trí | Vấn đề |
|---|---|---|
| P1-1 | `reports.py:407, 1119-1122, 1507-1534` | Lọc `safety_stock > 0 AND current_stock < safety_stock*0.3` trên cột nay **luôn = 0** (5.007/5.041 dòng — comment `dashboard.py:126-128` xác nhận) → **báo cáo luôn rỗng / luôn báo "safe", không báo lỗi**. `dashboard.py` đã sửa, `reports.py` bị bỏ sót |
| P1-2 | `inventory_service.py:215-220` | `get_low_stock_items` cùng lỗi → `GET /inventory/low-stock` luôn rỗng |
| P1-3 | `sync_service.py:67-79` | Nút "Đồng bộ HIS" **không gọi `dss_loader.load_all`** (chỉ có ở `scripts/run_dss_load.py:83`, CLI thủ công) → `fact_usage_total`, `fact_inventory_lot` không cập nhật, DSS chạy trên số cũ, im lặng |
| P1-4 | `G1_03_LOCAL_cau_hinh.sql:127-176`, `G1_04:93` | 4 view SQLite mà DSS phụ thuộc **không do mã nào tạo** (grep `CREATE VIEW` trong `*.py` = 0). Thiếu view → `_has()` guard trả rỗng, không báo lỗi |
| P1-5 | `dss_runner.py:54-66`, `topdown.py:101`, `ai_forecaster.py:64`, `data_access.py:3` | Mở thẳng `sqlite3`, `raise RuntimeError("topdown chỉ hỗ trợ SQLite")`, `INSERT OR REPLACE`, `sqlite_master` (`dss_demand.py:70`, `dss_alerts.py:72`, `period_service.py:89`) → **chuyển Postgres là toàn bộ `/dashboard/*` sập** |
| P1-6 | `alert_service.py:24-28` vs `dss_alerts.py` | Hai thuật toán cảnh báo chạy song song (ngưỡng 3/7/14 ngày hardcode vs DOI+FEFO) → **hai con số mâu thuẫn cho cùng một vật tư** trên Dashboard và trang Cảnh báo |
| P1-7 | `ensemble_forecaster.py:89, 163-170, 280, 359` | `self.lstm_model = None`, `lstm_pred = (xgb + prophet)/2`, và **bịa chỉ số đánh giá** cho "LSTM" = trung bình của 2 model kia rồi báo cáo như model thật. Trọng số thực là XGB 0,575 / Prophet 0,425; bảng "3 model" là hư cấu |
| P1-8 | `dss_demand.py:12-17` | `disease_supply_norms` có khoá `(icd, severity, supply)` nhưng `quantity_per_case` **giống hệt ở cả 3 mức** (18/18/18 · 30/30/30) → toàn bộ bộ máy `severity_inference_service` + `care_level_shares` **không làm đổi kết quả**. (`chan_doan_dinh_muc()` tự báo — xử lý đúng) |
| P1-9 | `ai_engine/config.py:171-196` | `DEFAULT_CONVERSION_RATIOS` chỉ có `dengue_fever`, `seasonal_flu`, `respiratory_disease` — **không có J00-J06 / J09-J18 / J20-J22** → mã bệnh mới trượt fallback, trả `None`, không sinh nhu cầu (`DanhGia_ChuyenSangNhomICD.md` đã cảnh báo) |
| P1-10 | `usage_total_sta.sql` | SELECT 4 cột chỉ có ở `G1_01_STA_sua_bang.sql:87-100`; bản `Phase0_01:335-343` cùng tên view chỉ có `so_luong` → nếu STA chạy Phase0 mà chưa chạy G1, `load_all` ghi `{"status":"failed"}` vào log rồi **chạy tiếp với bảng rỗng** |
| P1-11 | `pages/Alerts.tsx:230-245` | Gọi API **trong vòng lặp tuần tự**: 50 vật tư = 100 request, không transaction, hỏng giữa chừng để lại dữ liệu nửa vời — trong khi `POST /inventory/batch-update` (`inventory.py:364`) đã có sẵn |
| P1-12 | `pages/Alerts.tsx:63-88` + `pages/Reports.tsx:730-756` | Ngưỡng sửa tay lưu ở **`sessionStorage`**, rồi Reports đọc lại để tính `suggested_import` **cho báo cáo xuất Excel** → hai người dùng xuất ra hai kết quả khác nhau |
| P1-13 | `services/api.ts:28,64-67`, `authStore.ts:32-35` | `access_token` + `refresh_token` + object user trong `localStorage` (thêm bản thứ hai qua zustand `persist`) → XSS đọc được. `SupplyNormMatrix.tsx:68-76` còn tự `fetch()` bỏ qua interceptor |
| P1-14 | `main.py` | **Không có exception handler toàn cục**; 12 chỗ nhét `str(exc)` vào `detail` HTTP (`sync.py:33` có thể lộ chuỗi kết nối SQL Server) |
| P1-15 | `alerts.py:197-239` | `POST /alerts/{id}/fulfill` **ghi thẳng tồn kho, không kiểm quyền**; tạo Inventory mới với `safety_stock = int(shortage * 0.2)` (hằng vô căn cứ) |
| P1-16 | `disease_cases.py:234-259`, `environmental.py:175-198` | Import CSV: `get_current_user` (không phải manager), `await file.read()` đọc trọn vào RAM, **không kiểm `content_type` lẫn kích thước**. (`inventory.py:108-112` làm đúng) |
| P1-17 | `.env` gốc:10, `backend/.env:29` | `PIPELINE_SQLSERVER_CONN` là chuỗi ODBC thô, **không phải URL SQLAlchemy** → `connectors.py:252` `create_engine()` ném `ArgumentError`. `CAU_HINH_STA.md:22` ghi đúng dạng phải dùng |
| P1-18 | `sync_config_service.py:69` | Khoá mã hoá mật khẩu SQL Server dẫn từ `SECRET_KEY` → ở dev/staging dùng key mặc định thì mật khẩu HIS coi như plaintext. Cần biến riêng `SYNC_ENC_KEY` |

**Điểm tốt cần ghi nhận:** `.env`, `backend/.env`, `env_stagging.txt` đều **không được git theo dõi** (đã kiểm chứng bằng `git ls-files`); `_check_production_secret` (`config.py:30-38`) chặn `SECRET_KEY` mặc định ở production; không có credential hardcode trong mã.

---

## 5. CHUYÊN ĐỀ A — TÀN DƯ PHÂN HỆ MUA SẮM

Đây là mục trọng tâm của đợt rà soát. **Kết luận: lõi tính toán đã cắt đúng, nhưng lớp hiển thị chưa được dọn — người dùng vẫn thấy một hệ thống mua sắm.**

### A.1 · Điều đã làm đúng (giữ nguyên)

| Vị trí | Nội dung |
|---|---|
| `api/v1/inventory.py:213-223` | Vòng lặp ghi ngược `safety_stock` **đã bị cắt có chủ ý**, comment giải thích rõ vòng tự tham chiếu ×1,15 mỗi lần chạy. Không khôi phục |
| `dss_runner.py:197-228` | `"safety_stock"` giữ tên khoá JSON để bảng frontend không vỡ cột, nhưng **giá trị nay là ngưỡng DOI tính từ dự báo**. Cách xử lý đúng |
| `sync_service.py:97,184` | UPSERT giữ `safety_stock = 0` |
| `reports.py:508` | `"procurement"` đã bị gỡ khỏi `SUPPORTED_TYPES` |
| — | `reorder_point`, `min_stock`, `max_stock`, `purchase_order`, `PO`, `EOQ`, `supplier`: **grep toàn repo = 0 kết quả**. Đã sạch hoàn toàn |

### A.2 · Tàn dư còn CHẠY và ẢNH HƯỞNG SỐ LIỆU

| Mức | Vị trí | Hậu quả |
|---|---|---|
| CAO | `reports.py:407, 1119-1122, 1507-1534` | Phân loại rủi ro theo `safety_stock` → **luôn báo "safe", báo cáo luôn rỗng** |
| CAO | `inventory_service.py:215-220, 264-270, 303-333` | `low-stock` so `current_stock <= safety_stock × threshold` → luôn rỗng |
| CAO | `supply_recommendation_service.py:144,155` | Lấy `max(Inventory.safety_stock)` làm ngưỡng — song song và mâu thuẫn với DOI |
| CAO | `supply_planning_service.py:48, 110, 123` | `lead_time_days` đọc từ `medical_supplies`, **truyền ra API** `GET /supply-plan/{block}` — trường procurement duy nhất còn lộ ra ngoài |
| TB | `alerts.py:237` | `safety_stock = int(shortage * 0.2)` khi tạo Inventory mới — **ghi vào DB** |
| TB | `inventory.py:448-548, 585-689` | Import/export CSV & Excel vẫn parse và xuất `safety_stock`, `lead_time_days` |
| TB | `POST /inventory/sync-safety-stock` (`inventory.py:127-244`) | Endpoint **luôn trả `updated = 0`** nhưng vẫn HTTP 200 với thông điệp "Đã cập nhật ngưỡng an toàn cho 0 vật tư". Frontend vẫn gọi → người dùng tưởng đã cập nhật |

### A.3 · Tàn dư HIỂN THỊ TRÊN GIAO DIỆN (nghiêm trọng nhất — người dùng nhìn thấy)

Điều đáng chú ý: chính `frontend/src/types/dashboardV2.ts:11-13` **tuyên bố dự án đã bỏ phân hệ mua sắm** và liệt kê 7 trường cấm — nhưng file đó là code chết, còn UI thì vẫn hiển thị đầy đủ.

| Vị trí | Người dùng thấy |
|---|---|
| `pages/Alerts.tsx:48, 264, 268` | Tiêu đề trang **"Đề xuất nhập kho"** |
| `pages/Alerts.tsx:446-447, 485-497, 593-605` | Công thức `Đề xuất nhập = max(0, nhu cầu + ngưỡng AT − tồn kho)`, cột **"Ngưỡng AT"**, **"Đề xuất nhập"**, modal sửa ngưỡng |
| `pages/Alerts.tsx:22, 24` | Chuỗi lý do: *"— **đặt hàng ngay**"*, *"— đưa vào **kỳ đặt hàng** kế tiếp"* |
| `supply_recommendation_service.py:52, 70, 78` | Nguồn sinh hai chuỗi trên, **ở backend** |
| `ReportTypePicker.tsx:14, 44-51` | Thẻ báo cáo `procurement` = **"Đề xuất nhập kho"**, icon `ShoppingCart` |
| `pages/Reports.tsx:65-77, 161-196, 719-797` | Luồng báo cáo mua sắm + **xuất Excel** sheet "Đề xuất nhập kho" với cột `suggested_import`, `safety_stock` |
| `pages/SupplyPlanning.tsx:150, 164-176` | Bảng "Đề xuất nhập kho": cột **"Đề xuất nhập"**, **"Lead (ngày)"**, badge **"Cần nhập"** |
| `pages/Inventory.tsx:762-785` | Form nhập liệu có ô **"Ngưỡng AT"** và **`lead_time_days`** |
| `types/config.ts:76` | Nhãn `'lead-times': 'Thời gian đặt hàng'` trong trang Quản trị |

### A.4 · Bảng/cột chết trong CSDL (bẫy cho người bảo trì sau)

| Đối tượng | Khai ở | Trạng thái |
|---|---|---|
| `MF_LichSuNhap`, `MF_VatTu_ThuocTinh` + 2 view | `Phase0_01:231,280,370,384` · `Phase0_03` phần 2-3 | **0 tham chiếu Python**. σ_L / MOQ / `lead_time_nguon` / `ty_le_giao_du` nạp xong không ai đọc |
| `inventory_lots` (LOCAL) | `Phase0_04:48-64` | **Chết.** Trùng chức năng `fact_inventory_lot` **nhưng khác hẳn tên cột** (`has_expiry` vs `co_han_dung`, `warehouse_count` vs `so_kho`) — rất dễ nối nhầm module FEFO vào bảng rỗng, và `_has()` guard sẽ nuốt lỗi |
| `supply_attributes`, `supply_class` (ABC-XYZ) | `Phase0_04:66-122` | **Chết.** Toàn bộ phân lớp ABC-XYZ chưa có mã |
| `medical_supplies.minimum_order_quantity`, `storage_capacity` | `models/medical_supply.py:23,25` | Chỉ CRUD, không thuật toán nào dùng |
| `_luu_safety_stock_truoc_phase0` | `Phase0_04:380` | Chết — và có lẽ **chưa từng được tạo** (xem A.5) |

### A.5 · Một lỗi ẩn đáng chú ý

`models/inventory.py:16` khai `safety_stock` **NOT NULL**, trong khi `Phase0_04_LOCAL_masterdata_abcxyz.sql:395` chạy `UPDATE inventory SET safety_stock = NULL;` bên trong một `BEGIN…COMMIT`.

→ Câu này ném `NOT NULL constraint failed` và **rollback toàn bộ §2+§4 của Phase0_04** (dọn nhãn vùng, nạp master data, lưu bảng backup). Bằng chứng gián tiếp: `dashboard.py:126-128` ghi nhận cột về **0** chứ không NULL — tức bước này chưa từng chạy trọn.

### A.6 · Kế hoạch dọn dứt điểm

**Quyết định cần chốt trước:** hệ thống có còn trả lời câu hỏi *"cần nhập bao nhiêu"* không? Nếu **không** (đúng phạm vi DSS thuần), làm theo thứ tự:

1. **Backend — đổi từ vựng tại nguồn:** `supply_recommendation_service.py:52,70,78` — "Đặt hàng ngay {n}" → "Cần chuẩn bị bổ sung {n}"; "kỳ đặt hàng kế tiếp" → "kỳ bổ sung kế tiếp".
2. **Thống nhất một nguồn ngưỡng duy nhất:** DOI tính từ dự báo (`dss_alerts`). Gỡ `safety_stock` khỏi mọi phép phân loại rủi ro (`inventory_service.py:215-220`, `reports.py:407,1119-1122,1507-1534`); giữ cột trong DB chỉ như giá trị ghi đè thủ công có đánh dấu.
3. **Xoá endpoint** `POST /inventory/sync-safety-stock` (hoặc trả 410 Gone rõ ràng).
4. **Xoá ~350 dòng chết** trong `reports.py`: `_build_procurement_data` (:1608), `_render_procurement_pdf` (:1896), `_render_procurement_excel` (:2086), nhánh không tới được (:602-608).
5. **Frontend — đổi nhãn:** "Đề xuất nhập" → "Lượng thiếu hụt cần chuẩn bị"; bỏ cột "Lead (ngày)" (`SupplyPlanning.tsx:167`); bỏ thẻ báo cáo `procurement` (`ReportTypePicker.tsx:14`); bỏ ô `lead_time_days` khỏi form (`Inventory.tsx:762-785`); sửa nhãn `types/config.ts:76`.
6. **CSDL:** DROP `inventory_lots`, `supply_attributes`, `supply_class`; cắt phần 2-3 của `Phase0_03`. Hoặc — nếu muốn giữ ABC-XYZ cho giai đoạn sau — viết luồng thứ 5-6 trong `dss_loader.FLOWS`. **Chọn một, không để nửa vời.**
7. **Sửa `Phase0_04:395`** thành `SET safety_stock = 0` (hoặc đổi model sang `nullable=True` rồi migrate).

---

## 6. CHUYÊN ĐỀ B — TƯƠNG THÍCH CSDL BA NGUỒN

### B.1 · Đối chiếu schema STA ↔ mã Python

**Đạt:** `case_sta.sql` ↔ `vw_MedForecast_CaBenh` · `case_group_sta.sql` ↔ `vw_MedForecast_CaBenhNhom` · `inventory_sta.sql` ↔ `vw_MedForecast_TonKho` · `cases_care_level_sta.sql` ↔ `vw_MedForecast_CaBenhPhanCap` · `usage_care_level_sta.sql` ↔ `vw_MedForecast_TieuHaoPhanCap` · `inventory_lot_sta.sql` ↔ `vw_MedForecast_TonKhoLo_MoiNhat` — **khớp đủ cột**.

**Không đạt:** 4 file `*_mssql.sql`/`*_sqlite.sql` (P0-6) · `usage_total_sta.sql` phụ thuộc phiên bản view (P1-10).

### B.2 · Lệch giữa SQLAlchemy model và schema thực tế

| Mức | Vấn đề |
|---|---|
| CAO | `Inventory.safety_stock` NOT NULL ↔ `Phase0_04:395` ghi NULL (A.5) |
| TB | **Không có UNIQUE trên `inventory.supply_id`** nhưng `sync_service.py:156` dùng `{i.supply_id: i for i in …}` — dict nuốt bản ghi trùng, `:186` chỉ cập nhật một dòng. `tests/test_inventory.py:212-213` lại tạo hai dòng cùng `supply_id` khác `location` → mô hình cho phép nhiều kho, mã đồng bộ thì không |
| TB | `ten_hoat_chat`: `String(500)` (`medical_supply.py:16`) ↔ `String(200)` (`supply_recommendation.py:28`) ↔ `String(255)` (`data_pipeline/models.py:52`) ↔ STA `nvarchar(500)`. SQLite bỏ qua độ dài nên lỗi bị giấu; Postgres/SQL Server sẽ `value too long` |
| TB | `fact_inventory_lot` (`dss_loader.py:206-210`): `so_kho` khai `VARCHAR(60)` cho cột nguồn `int`, và đưa vào PK dù nguồn cho phép NULL → Postgres từ chối |
| THẤP | `data_pipeline/models.py` dùng `Base` riêng → alembic không thấy 12 bảng |
| THẤP | Thiếu index: `disease_cases` không có `(recorded_date, disease_group)` dù `sync_service.py:132` xoá-rồi-chèn toàn bảng mỗi lần đồng bộ |

### B.3 · Hai DB tách rời khi chạy pipeline ngoài `main.py`

`main.py:7-10` gọi `load_dotenv()` trước khi import `app.database` nên khi chạy backend, hai bên trỏ cùng file. Nhưng `python -m app.data_pipeline.run` **không** gọi `load_dotenv`, còn `CAU_HINH_STA.md:36` lại hướng dẫn đặt `PIPELINE_DB_URL=sqlite:///./data/medforecast_dw.db` → pipeline ghi `fact_*/mart_*` vào một file, app đọc file khác; `period_service.py:106` trả False và **mọi KPI neo theo kỳ im lặng trả None**.

**Sửa:** để `get_db_url()` đọc `settings.DATABASE_URL` thay vì `os.environ`, và bỏ dòng `PIPELINE_DB_URL` khác biệt trong tài liệu.

---

## 7. CHUYÊN ĐỀ C — CHUẨN DSS 3 TẦNG

### C.1 · Bản đúng chuẩn (đang tồn tại, chỉ phủ Dashboard)

| Tầng | File | Đánh giá |
|---|---|---|
| **1 · Dữ liệu/ETL** | `data_pipeline/*`, `sync_service`, `period_service` | Tách bạch tốt; thiếu mắt xích `dss_loader` trong `run_sync` (P1-3) |
| **2 · Mô hình** | `forecasting/topdown.py`, `forecasting/models.py`, `hierarchical_forecast_service`, `group_ensemble_service` | **Tốt** — walk-forward mở rộng cửa sổ, `min_train=24`, dự báo 1 bước (`topdown.py:246-259`), khớp `KetQua_Backtest_ChonCauHinh.md` (MASE ~0,60) |
| **3 · Quyết định** | `dss_demand.py`, `dss_alerts.py`, `supply_planning_service` | Đúng vị trí; chiều severity đang rỗng (P1-8) |
| **Điều phối** | `dss_runner.run_forecast_cycle()` (:72-158) | **Tốt** — gọi tuần tự 3 tầng, một tầng lỗi không chặn tầng khác |

### C.2 · Vi phạm

- **Logic Tầng 2 nằm trong file API:** `forecast_analysis.py:230-292` (`_weather_factor`), `:329-357` (`_trend_factor`), `:96-110` (`_classify_risk`), `:294-325` (`_pearson_coefficients`).
- **Logic Tầng 3 nằm trong Tầng 2:** `forecast_service.py:18-35` — hàm dự báo tự gọi sinh `SupplyRequirement`, lỗi bị nuốt bằng `logger.error`.
- **Tầng 3 phụ thuộc cứng SQLite:** `dss_alerts.py:70-73`, `dss_runner.py:54-66` (P1-5).
- **Chỉ 1/4 màn hình chính đi qua kiến trúc đúng.** `/forecast/*`, `/alerts`, `/reports` vẫn dùng nhánh cũ.

### C.3 · Trùng lặp tổng hợp

| Chức năng | Số bản | Đang chạy | Chết |
|---|---|---|---|
| Tính nhu cầu vật tư | 4 | cả 4 | — |
| Dự báo | 4 | 3 | `forecast_service` + `forecasting_pipeline` |
| Ensemble | 3 (+1 Ridge riêng) | `monthly_forecaster`, `models.Ensemble` | `ensemble_forecaster` |
| Cảnh báo | 2 | cả 2, **khác thuật toán** | — |
| Nhu cầu vật tư (frontend) | 3 service | cả 3, 3 shape khác nhau | — |
| Type dashboard | 2 | 1 type duy nhất | `dashboardV2.ts` (380 dòng) + 5/6 interface `dashboard.ts` |

---

## 8. LỘ TRÌNH KHẮC PHỤC ĐỀ XUẤT

### Đợt 1 — Chặn máu (1-2 ngày, rủi ro thấp, tác động cao)
1. `admin_severity.py`: thêm `get_admin_user` cho cả router — **P0-2**
2. `forecast_analysis.py:407,438,564`: `async def` → `def` — **P0-3(a)**, sửa 3 dòng, hết treo worker
3. `reports.py:407,1119-1122,1507-1534` + `inventory_service.py:215-220`: gỡ điều kiện `safety_stock` — **P1-1, P1-2**
4. `sync_service.py:67-79`: gọi `dss_loader.load_all` trong khối `try/except` riêng — **P1-3**
5. `main.py`: thêm exception handler toàn cục, ngừng trả `str(exc)` ra client — **P1-14**
6. `alerts.py:197`, `disease_cases.py:234`, `environmental.py:175`: bổ sung kiểm quyền + giới hạn kích thước upload — **P1-15, P1-16**

### Đợt 2 — Dọn tàn dư mua sắm (2-3 ngày)
7. Toàn bộ mục **A.6**, bước 1→7
8. Xoá `POST /forecast/train` và `/ml-analyze` + 2 lời gọi frontend (`forecastAnalysisService.ts:187,194`) — **P0-1**
9. Sửa `types/inventory.ts` theo schema backend — **P0-5**
10. `pages/Alerts.tsx:230`: đổi sang `batch-update`; bỏ `sessionStorage` khỏi luồng báo cáo — **P1-11, P1-12**

### Đợt 3 — Hợp nhất kiến trúc (1 tuần)
11. Rút `forecast_analysis.py` thành `analysis_service.py`, chọn MỘT engine — **P0-3(b)**
12. Hợp nhất 4 nguồn tính nhu cầu về `dss_demand` — **P0-4**
13. Hợp nhất 2 thuật toán cảnh báo về DOI+FEFO — **P1-6**
14. Xoá ~6.500 dòng code chết (phụ lục)
15. Chuyển 12 file `test_*.py` khỏi `app/`; thêm `testpaths = tests`; thêm `.dockerignore` loại `tests/`, `*.pkl`

### Đợt 4 — Nền tảng triển khai (1 tuần)
16. Sửa `alembic/env.py` đọc `settings.DATABASE_URL`; baseline `--autogenerate` gộp cả `app.models` và `data_pipeline.models`; bỏ `create_all` khỏi `main.py`; chuyển DDL của `dss_loader` thành revision — **P0-7**
17. Thay `sqlite3` trực tiếp + `sqlite_master` bằng SQLAlchemy `inspect()` — **P1-5**
18. Xoá 4 file SQL schema chết, đổi mặc định `connectors.py:231-233` — **P0-6**
19. Sửa `.env` `PIPELINE_SQLSERVER_CONN`; tách `SYNC_ENC_KEY` — **P1-17, P1-18**
20. Điền định mức khác biệt theo mức nặng; chuyển định mức lên mức NHÓM; xoá `DEFAULT_CONVERSION_RATIOS` — **P1-8, P1-9**
21. Version hoá model (bỏ `version="latest"` ghi đè); thêm sMAPE/WAPE vào `evaluate.py`

---

## 9. PHỤ LỤC — DANH SÁCH CODE CHẾT ĐỀ XUẤT XOÁ

**Backend (~5.067 dòng):** `ai_engine/{forecasting_pipeline, ensemble_forecaster, xgboost_forecaster, prophet_forecaster, forecasting_service, csv_data_processor, supply_demand_calculator, weather_forecast, correlation_analyzer}.py` · `services/forecast_service.py` · `tasks/forecast_tasks.py` · `services/data_collector_service.py` (403 dòng, 0 import trong `app/`) · `core/exceptions.py` (60 dòng, 0 import) · `data_pipeline/sql/{case,inventory}_{mssql,sqlite}.sql`

**Frontend (~1.406 dòng):** `types/dashboardV2.ts` (380) · `pages/SupplyNormPage.tsx` + `components/SupplyNormMatrix.tsx` (420 — không có `<Route>` trong `App.tsx`) · cụm cảnh báo `hooks/useAlerts.ts` + `services/alertsService.ts` + 6 component `alerts/*` (**toàn bộ router `/api/v1/alerts` không được frontend gọi**) · cụm dịch tễ `hooks/useEpidemiology.ts` + 4 component `epidemiology/*` · `components/dashboard/CriticalAlertsTable.tsx` · `components/reports/ExportButton.tsx` · `components/inventory/{UpdateStockModal, AIInsightPanel}.tsx` · 5/6 hook trong `hooks/useInventory.ts`

**Artifact nhị phân trong source tree:** `app/ai_engine/models/saved_models/*.pkl` (8 file, 4 thuộc phân hệ cũ: `dengue_fever`, `seasonal_flu`, `respiratory_disease`, `viral_infection`). `Dockerfile:23` `COPY . .` đóng gói tất cả vào image production.

**Ghi chú UX phát hiện thêm:** `Sidebar.tsx:32` ghi menu **"Cảnh báo tồn kho"** nhưng mở ra trang tiêu đề **"Đề xuất nhập kho"**; `ROUTES.SUPPLY_PLAN` có route (`App.tsx:70`) nhưng **không có mục menu** — chỉ vào được bằng gõ URL; `pages/Inventory.tsx:676-686` dựng chuỗi CSV trong trình duyệt rồi POST như file upload để tạo bản ghi kho (thiếu `POST /inventory`), không escape dấu phẩy trong tên vật tư.

---

## 10. ĐIỂM MẠNH CẦN GIỮ

- `app/forecasting/topdown.py` + `evaluate.py`: walk-forward đúng chuẩn học thuật, có bằng chứng số trong `KetQua_Backtest_ChonCauHinh.md`.
- `dss_runner.run_forecast_cycle()`: điều phối 3 tầng, cô lập lỗi từng tầng.
- `dss_demand.chan_doan_dinh_muc()`: **tự khai báo chiều dữ liệu đang rỗng thay vì che giấu** — đây là văn hoá kỹ thuật tốt, nên nhân rộng.
- `dss_alerts.get_thresholds()` (:76-86): đọc ngưỡng từ `system_config` thay vì hardcode — nên áp dụng cho 6 nhóm hằng số còn lại (hệ số thời tiết, ngưỡng rủi ro 50/25/10%, buffer 15%, `Z_SERVICE = 1.96`…).
- Các comment giải thích quyết định kỹ thuật (`inventory.py:213-223`, `base.py:170-176` về kho âm) — chất lượng cao, giúp người sau không lặp lại lỗi cũ.
- `.env` không bị git theo dõi; `_check_production_secret` chặn key mặc định ở production.

---

*Báo cáo lập bởi rà soát tự động có kiểm chứng thủ công. Mọi tham chiếu `file:dòng` đều đã xác minh trực tiếp trên mã nguồn tại thời điểm 09/09/2026.*
