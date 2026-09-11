# ĐỊNH HÌNH LẠI MEDFORECAST AI — KIẾN TRÚC ĐÍCH & KẾ HOẠCH 6 TUẦN

**Ngày lập:** 09/09/2026 · **Mốc:** bảo vệ đồ án trong 4–6 tuần (≈ 07–21/10/2026)
**Căn cứ:** báo cáo rà soát toàn diện 09/09/2026 + 4 quyết định phạm vi đã chốt

---

## 0. BỐN QUYẾT ĐỊNH NỀN

| # | Quyết định | Hệ quả trực tiếp |
|---|---|---|
| 1 | **Ưu tiên bảo vệ đồ án** (4–6 tuần) | Việc nào không phục vụ bằng chứng khoa học, không chặn lỗi hiển thị, không ảnh hưởng buổi demo → đẩy sang sau bảo vệ |
| 2 | **Giữ SQLite, gỡ Postgres** | **Xoá cả một nhóm lỗi khỏi danh sách.** `sqlite3` trực tiếp, `sqlite_master`, `INSERT OR REPLACE`, view SQLite — **không còn là khiếm khuyết**, mà là hệ quả của một lựa chọn kiến trúc có chủ đích. Việc cần làm đổi từ "sửa mã" thành "gỡ thứ mâu thuẫn + ghi rõ lý do" |
| 3 | **Mã chết → `_archive/` ngoài `app/`** | Không mất gì, không còn ảnh hưởng đóng gói/import, vẫn tra lại được khi viết báo cáo |
| 4 | **Bỏ hẳn phân hệ mua sắm — DSS thuần** | Hệ thống trả lời "có nguy cơ thiếu hụt không, thiếu bao nhiêu", **không** trả lời "cần đặt hàng bao nhiêu, khi nào". Nhất quán với tuyên bố đã có sẵn trong `dashboardV2.ts:11-13` |

**Điều quyết định 2 thay đổi nhiều nhất:** trong báo cáo rà soát, P1-5 (phụ thuộc cứng SQLite) là một phát hiện mức CAO trải trên 9 file. Giờ nó biến mất. Đổi lại xuất hiện một việc mới, nhẹ hơn nhiều: **gỡ mọi dấu vết Postgres đang mâu thuẫn với lựa chọn này** — nếu để lại, người phản biện mở repo thấy `MIGRATE_POSTGRES.md` và `docker-compose` chạy Postgres sẽ hỏi ngay "vậy rốt cuộc hệ thống chạy trên gì".

---

## 1. KIẾN TRÚC ĐÍCH

### 1.1 · Sơ đồ

```
┌─ NGUỒN ────────────────────────────────────────────────────────────┐
│  HIS PROD (SQL Server, chỉ đọc)          Open-Meteo (API)          │
│  3 stored procedure đẩy dữ liệu ──┐                │               │
└───────────────────────────────────┼────────────────┼───────────────┘
                                    ▼                │
┌─ TẦNG 1 · DỮ LIỆU ─────────────────────────────────┼───────────────┐
│  STA (MEDFORECAST_DW) — vùng đệm, đã khử định danh │               │
│         │  connectors.py (7 câu SQL đối chiếu view)│               │
│         ▼                                          ▼               │
│  SQLite LOCAL: stg_* → dim_* → fact_* → mart_*                     │
│  Điều phối: sync_service.run_sync()  ← DUY NHẤT một cửa vào        │
│  Sản phẩm phụ: BỘ DỮ LIỆU XUẤT BẢN (CSV/Parquet + từ điển)         │
└────────────────────────────────┬───────────────────────────────────┘
                                 ▼
┌─ TẦNG 2 · MÔ HÌNH ─────────────────────────────────────────────────┐
│  app/forecasting/ — CHỈ package này, không có nhánh thứ hai        │
│    models.build_default_ensemble()                                 │
│      = SeasonalTrend + PoissonTrend + HarmonicPoisson(thời tiết)   │
│        + SARIMAX(1,1,1)(1,0,0,12) exog                             │
│    hierarchical.ewma_shares() → top-down động về mã ICD            │
│    evaluate.walk_forward_block() → bằng chứng, không phải sản phẩm │
│  Ghi ra: disease_forecasts + BẢN GHI CẤU HÌNH MÔ HÌNH ĐÃ FIT       │
└────────────────────────────────┬───────────────────────────────────┘
                                 ▼
┌─ TẦNG 3 · QUYẾT ĐỊNH ──────────────────────────────────────────────┐
│  dss_demand   — quy đổi ca → nhu cầu vật tư theo định mức          │
│  dss_alerts   — DOI + FEFO → 4 mức Đỏ/Vàng/Xanh/Xám + lý do        │
│  KHÔNG có: lượng đặt hàng, lead-time, tồn an toàn nhập tay         │
└────────────────────────────────┬───────────────────────────────────┘
                                 ▼
      dss_runner.run_forecast_cycle()  ← điều phối 3 tầng, cô lập lỗi
                                 ▼
      API mỏng (chỉ validate → gọi service → trả)  →  React
```

### 1.2 · Bốn quy tắc tầng (dùng để xử mọi tranh cãi về sau)

1. **Tầng API không tính toán.** Không hệ số dịch tễ, không phân loại rủi ro, không vòng lặp mô hình. Vi phạm hiện tại: `forecast_analysis.py:96-110, 230-292, 294-325, 329-357`.
2. **Một chức năng, một cài đặt.** Hiện có 4 nguồn tính nhu cầu, 2 thuật toán cảnh báo, 3 bản ensemble. Kiến trúc đích: mỗi loại đúng một.
3. **Tầng dưới không biết tầng trên.** Tầng 2 không được tự sinh `SupplyRequirement`. Vi phạm: `forecast_service.py:18-35` (nằm trong nhóm sẽ đóng gói).
4. **Dữ liệu rỗng phải nói ra, không được im lặng trả 0.** Đây là quy tắc `dss_demand.chan_doan_dinh_muc()` đã làm đúng — nâng thành chuẩn chung. Vi phạm nặng nhất: `reports.py:1119-1122` lọc trên cột đã vô hiệu hoá, trả rỗng, không báo gì.

### 1.3 · Chốt kỹ thuật để ghi vào báo cáo

| Hạng mục | Chốt | Câu giải thích khi bị hỏi |
|---|---|---|
| CSDL | SQLite đơn tệp | "Dữ liệu 92 tháng, một điểm ghi duy nhất là tiến trình đồng bộ, đọc nhiều-ghi ít. SQLite đủ và bỏ được một tầng vận hành khỏi bệnh viện." |
| Huấn luyện | Fit-tại-chỗ mỗi lần dự báo | "Chuỗi 92 điểm, fit hết vài giây. Không có lịch retrain phải vận hành, không có rủi ro mô hình trôi mà không ai biết." |
| Mô hình | Ensemble thống kê 4 thành viên, không deep learning | "92 quan sát/chuỗi không đủ cho LSTM. Em chứng minh bằng bảng đối chứng thay vì gắn một mô hình chạy được nhưng vô nghĩa." |
| Phân cấp | Top-down động (EWMA) | "Bottom-up cho MASE 483,7 trên J09-J18 ở cửa sổ 2022 — có số đo trên dữ liệu thật." |
| Phạm vi | DSS thuần, không mua sắm | "Hệ thống chỉ ra nguy cơ và lượng thiếu hụt; quyết định mua sắm thuộc quy trình đấu thầu của bệnh viện, ngoài phạm vi." |

---

## 2. BÓ FILE RÁC — MANIFEST `_archive/`

Toàn bộ danh sách dưới đây **đã kiểm chứng bằng grep tham chiếu ngược, có tính bắc cầu**: một file chỉ vào danh sách khi mọi nơi gọi nó cũng nằm trong danh sách.

### 2.1 · `_archive/ai_engine_cu/` — cụm nhánh AI cũ (~4.900 dòng)

| File | Bằng chứng chết |
|---|---|
| `forecasting_pipeline.py` | 0 tham chiếu ngoài |
| `ensemble_forecaster.py` | chỉ `forecasting_pipeline` + `__init__` |
| `xgboost_forecaster.py` | chỉ `forecasting_pipeline`, `ensemble_forecaster`, `__init__` |
| `prophet_forecaster.py` | như trên |
| `model_evaluation.py` | chỉ 4 file trên + `__init__` |
| `feature_engineering.py` | chỉ 3 file trên + `__init__` |
| `forecasting_service.py` | 0 tham chiếu ngoài |
| `csv_data_processor.py` | chỉ `forecasting_service`, `supply_demand_calculator` |
| `supply_demand_calculator.py` | chỉ `forecasting_service` |
| `weather_forecast.py` | chỉ `forecasting_service` (import trễ, dòng 162) |
| `correlation_analyzer.py` | **0 tham chiếu, kể cả trong package** |
| `models/saved_models/*.pkl` | 8 file artifact của nhánh này |
| 7 file `test_*.py` trong package | thuộc cụm trên |

**Kèm theo — sửa `app/ai_engine/__init__.py`:** hiện có 6 import cấp cao, trong đó dòng 48-50 kéo `xgboost_forecaster`, `prophet_forecaster`, `ensemble_forecaster`. Python chạy `__init__.py` trước khi nạp bất kỳ submodule nào, nên **mỗi lần đường chạy sống gọi `db_forecasting_service` là kéo theo cả thư viện XGBoost và Prophet vào bộ nhớ**. Gỡ 3 dòng này là lợi ích thật, không chỉ dọn dẹp.

### 2.2 · `_archive/dich_vu_chet/`

| File | Bằng chứng |
|---|---|
| `app/services/forecast_service.py` | chỉ `tasks/forecast_tasks.py` gọi |
| `app/tasks/forecast_tasks.py` | 0 nơi `.delay()`/`.apply_async()`; docker-compose không có worker |
| `app/celery_app.py` | không còn task nào sau khi bỏ 2 file trên |
| `app/services/data_collector_service.py` | 403 dòng, 0 import trong `app/` |
| `app/core/exceptions.py` | 60 dòng, 0 import toàn repo |
| `app/forecasting/ai_forecaster.py` | 0 tham chiếu |
| `app/services/test_*.py`, `app/api/v1/test_*.py` | 4 file test lẫn trong package sản phẩm |

### 2.3 · `_archive/sql_schema_cu/`

`app/data_pipeline/sql/{case_mssql, case_sqlite, inventory_mssql, inventory_sqlite}.sql` — SELECT các bảng `KhamBenh`, `ChanDoan`, `BenhNhan`, `SuDungVatTu`, `VatTu`, `TonKho` **không tồn tại trong HIS thật**.

⚠ **Không được chỉ di chuyển file.** Bốn file này đang là **mặc định** của connector (`connectors.py:231-233`), nạp sẵn lúc import (`:331-332`), và phơi ra UI thành profile `"mssql"` (`sync_config_service.py:47-48`). Phải đổi mặc định sang `case_sta.sql`/`inventory_sta.sql` và bỏ profile `"mssql"` **cùng lúc**.

### 2.4 · `_archive/frontend_chet/` (~1.400 dòng)

| Nhóm | File | Bằng chứng |
|---|---|---|
| Định mức | `pages/SupplyNormPage.tsx` (0 tham chiếu, **không có `<Route>` trong `App.tsx`**), `components/SupplyNormMatrix.tsx` (chỉ trang trên gọi) |
| Cảnh báo | `hooks/useAlerts.ts` (0), `services/alertsService.ts` (chỉ hook trên), 6 component `components/alerts/*` |
| Dịch tễ | `hooks/useEpidemiology.ts` (0), 4 component `components/epidemiology/*` — trang `Epidemiology.tsx` tự dựng UI riêng |
| Khác | `types/dashboardV2.ts` (380 dòng, mô tả `/dashboard/v2` chưa từng được cài), `components/dashboard/CriticalAlertsTable.tsx`, `components/reports/ExportButton.tsx`, `components/inventory/{UpdateStockModal, AIInsightPanel}.tsx` |

⚠ **Giữ lại `dashboardV2.ts` cho đến Tuần 5.** Nó chứa bộ nhãn ngữ nghĩa 4 mức ("Nguy cơ thiếu hụt", "Cần theo dõi sát"…) và union type `GreyReason` mà `dss_alerts.py:63` đang tham chiếu tới. Trích phần dùng được ra rồi mới đóng gói phần còn lại.

### 2.5 · `_archive/postgres/` — hệ quả quyết định 2

`docker-compose.yml`, `docker-compose.dev.yml`, `MIGRATE_POSTGRES.md`, `scripts/migrate_to_postgres.py`, và mục Docker/Postgres trong `README.md`.

### 2.6 · `_archive/tap_nhap/` — rác ở gốc repo

`.DS_Store` · `commit_medforecast.sh` · `don_repo.sh` · `git_lam_lai.sh` · `G0_cat_pham_vi.py` · `env_stagging.txt` · `package.json` + `package-lock.json` ở gốc (chỉ khai một phụ thuộc `xlsx`, không liên quan build) · `backend/kq_2022.csv`, `kq_2023.csv`, `kq_toanbo.csv` · `backend/test_api_simple.sh` · `backend/seed_respiratory_diseases.py` (bản lạc chỗ, `scripts/` đã có bản riêng)

🔴 **`backend/.env.saoluu_20260908` — xử lý riêng, không đóng gói mà XOÁ.** Đây là bản sao lưu file `.env` chứa mật khẩu HIS. `.gitignore` chỉ chặn `.env`, **không chặn `.env.saoluu_*`** — một lần `git add -A` là mật khẩu bệnh viện vào lịch sử git vĩnh viễn. Thêm `.env*` vào `.gitignore` ngay hôm nay.

### 2.7 · Ba thứ trông giống rác nhưng **PHẢI GIỮ**

| File | Vì sao giữ |
|---|---|
| `app/forecasting/run_eval.py` | 0 tham chiếu từ app — nhưng **đây chính là công cụ đã sinh ra `KetQua_Backtest_ChonCauHinh.md`**. Là bằng chứng khoa học của đồ án, không phải mã chết. Chuyển vào `research/` hoặc `scripts/`, ghi rõ vai trò |
| `app/ai_engine/{monthly_forecaster, db_forecasting_service}.py` | Vẫn **sống** qua import trễ tại `forecast_analysis.py:417, 448, 723`. Chỉ chết sau khi gỡ 2 endpoint ở Tuần 1 — đóng gói ở Tuần 2, không phải bây giờ |
| `app/ai_engine/conversion_module.py` | **Sống** — `supply_requirement_service.py:13` import cấp cao |

### 2.8 · Quy ước thư mục lưu trữ

```
_archive/
  README.md          ← ngày đóng gói, tiêu chí, cách khôi phục
  ai_engine_cu/
  dich_vu_chet/
  sql_schema_cu/
  frontend_chet/
  postgres/
  tap_nhap/
```

`_archive/README.md` ghi rõ từng nhóm: **vì sao xác định là chết** (bằng chứng grep) và **điều gì xảy ra nếu cần khôi phục**. Thư mục này là một phần của câu chuyện tái cấu trúc, nên viết cho người đọc chứ không phải chỗ đổ file.

---

## 3. KẾ HOẠCH 6 TUẦN

### TUẦN 1 — Chặn lỗi số liệu và gỡ bẫy bảo vệ
*Nguyên tắc: sửa mọi thứ thầy có thể bấm vào và thấy sai, hoặc hỏi và khó trả lời.*

| # | Việc | File | Vì sao gấp |
|---|---|---|---|
| 1.1 | Gỡ `POST /forecast/train` và `/ml-analyze` + 2 lời gọi frontend (`forecastAnalysisService.ts:187,194`) | `forecast_analysis.py:406-460` | Mô hình rò rỉ mục tiêu, báo sai số in-sample như độ chính xác. **Rủi ro bảo vệ số 1** |
| 1.2 | Gỡ luôn bước gọi `DBForecastingService` trong `/analyze` | `forecast_analysis.py:723-745` | Kết quả bị ensemble ghi đè ngay ở `:764` — chạy vô ích, và làm `monthly_forecaster` chết hẳn để Tuần 2 đóng gói |
| 1.3 | Gỡ điều kiện lọc theo `safety_stock` | `reports.py:407, 1119-1122, 1507-1534`; `inventory_service.py:215-220` | Cột luôn = 0 (5.007/5.041 dòng) → báo cáo **luôn rỗng, luôn báo "safe"**, không báo lỗi |
| 1.4 | `async def` → `def` | `forecast_analysis.py:407, 438, 564` | Chặn event loop, treo worker khi demo. **Sửa 3 dòng** |
| 1.5 | Thêm `get_admin_user` cho cả router | `admin_severity.py` (10 endpoint) | Bất kỳ tài khoản nào cũng sửa được định mức và tỷ lệ phân độ |
| 1.6 | Sửa README: bỏ "XGBoost + LSTM + Prophet", ghi đúng ensemble thật | `README.md:23` | Nếu thầy đọc README rồi hỏi "LSTM đâu" thì rất khó |
| 1.7 | `.gitignore` += `.env*`; xoá `backend/.env.saoluu_20260908` | — | Mật khẩu HIS |
| 1.8 | Sửa `KetQua_Backtest_ChonCauHinh.md`: bỏ câu "ensemble tự hạ trọng số mô hình tồi" | — | Sai — `models.py:238` là `np.mean` thuần. Tài liệu này có thể đưa thầy đọc |
| 1.9 | Kiểm tra hai màn hình có hiển thị hai con số nhu cầu khác nhau không; nếu có, tạm chốt một nguồn cho bản demo | `Alerts.tsx`, `Reports.tsx`, `SupplyPlanning.tsx` | Bị hỏi tại chỗ thì không có đường lùi |

### TUẦN 2 — Bó rác, gỡ Postgres, chốt hình dạng repo

| # | Việc |
|---|---|
| 2.1 | Tạo `_archive/` theo manifest mục 2, **trên một nhánh git riêng**, commit từng nhóm một để dễ lùi |
| 2.2 | Gỡ 3 dòng import chết trong `app/ai_engine/__init__.py:48-50` |
| 2.3 | Đổi mặc định connector sang `case_sta.sql`/`inventory_sta.sql`, bỏ profile `"mssql"` (`connectors.py:231-233`, `sync_config_service.py:47-48`) |
| 2.4 | Gỡ Postgres: docker-compose, `MIGRATE_POSTGRES.md`, `migrate_to_postgres.py`, mục Docker trong README |
| 2.5 | **Quyết định Alembic.** Hiện nó *nói dối*: `alembic upgrade head` trên DB mới sẽ **fail** (drop cột `district_ward` không tồn tại), và `alembic.ini:55` hardcode đường dẫn nên không bao giờ trỏ được đi đâu khác. Hai lựa chọn — (a) gỡ hẳn, ghi rõ "schema quản lý bằng `create_all` + `recreate_database.py`, phù hợp phạm vi SQLite đơn máy"; (b) giữ và sửa `remove_district_ward.py` thành kiểm tra-trước-khi-drop rồi `alembic stamp head`. **Khuyến nghị (a)** — trung thực hơn và đỡ một thứ phải giải thích |
| 2.6 | Sửa `Phase0_04:395` `SET safety_stock = NULL` → `= 0` (đang làm rollback âm thầm cả §2+§4 của script) |
| 2.7 | Gọi `dss_loader.load_all` trong `sync_service.run_sync()`, khối `try/except` riêng | 
| 2.8 | Chạy lại toàn bộ luồng đồng bộ + `verify_g1.py` để xác nhận không vỡ gì sau khi bó rác |

### TUẦN 3 — Dọn UI về DSS thuần, rồi đóng gói bộ dữ liệu
*Làm dọn UI trước vì mọi ảnh chụp màn hình trong báo cáo phụ thuộc vào nó.*

| # | Việc |
|---|---|
| 3.1 | **Backend đổi từ vựng tại nguồn:** `supply_recommendation_service.py:52,70,78` — "Đặt hàng ngay {n}" → "Cần chuẩn bị bổ sung {n}"; "kỳ đặt hàng kế tiếp" → "kỳ bổ sung kế tiếp" |
| 3.2 | **Frontend đổi nhãn:** tiêu đề trang `Alerts.tsx:48,264` "Đề xuất nhập kho" → "Cảnh báo nguy cơ thiếu hụt"; cột "Đề xuất nhập" → "Lượng thiếu hụt cần chuẩn bị"; bỏ cột "Lead (ngày)" (`SupplyPlanning.tsx:167`); bỏ thẻ báo cáo `procurement` (`ReportTypePicker.tsx:14`); bỏ ô `lead_time_days` khỏi form (`Inventory.tsx:762-785`); sửa `types/config.ts:76` |
| 3.3 | Thống nhất thuật ngữ: `safety_stock` đang hiển thị bằng **ba tên** ("Ngưỡng AT", "Mức an toàn", "ngưỡng an toàn") — chọn một, và viết tắt "AT" phải được giải nghĩa ít nhất một lần trên UI |
| 3.4 | Sửa nhãn menu ≠ tiêu đề trang (`Sidebar.tsx:32` "Cảnh báo tồn kho" mở ra trang "Đề xuất nhập kho"); bổ sung mục menu cho `/supply-plan` (hiện chỉ vào được bằng gõ URL) |
| 3.5 | Xoá ~350 dòng chết trong `reports.py`: `_build_procurement_data` (:1608), `_render_procurement_pdf` (:1896), `_render_procurement_excel` (:2086), nhánh không tới được (:602-608) |
| 3.6 | Xoá endpoint `POST /inventory/sync-safety-stock` — luôn trả `updated = 0` nhưng vẫn HTTP 200 báo "đã cập nhật" |
| 3.7 | **Đóng gói bộ dữ liệu:** xuất panel `(tháng × mã ICD × nhóm) + thời tiết có độ trễ + tiêu hao vật tư` ra CSV/Parquet có phiên bản. Sửa lại từ `scripts/export_cases_to_csv.py` và `gen_full_history_csv.py` |
| 3.8 | Viết **từ điển dữ liệu** (mỗi cột: ý nghĩa, đơn vị, nguồn, cách tính) + **datasheet** (phạm vi, cách khử định danh và căn cứ pháp lý, ngưỡng ô nhỏ k=5, hạn chế đã biết) |

**Nhật ký Tuần 3 · 11/09/2026 — 3.0 Dashboard Tổng quan (làm trước 3.1–3.6 vì là ảnh chụp đầu tiên của báo cáo)**

| Đã làm | Ở đâu |
|---|---|
| Hai endpoint mới `GET /dashboard/v2` (nhanh) và `GET /dashboard/v2/forecast` (cache SQLite `dss_forecast_cache`, khoá theo dấu vân tay chuỗi ca + thời tiết + cấu hình) | `backend/app/api/v1/dashboard.py`, `backend/app/services/dss_dashboard.py` |
| **M11 khép một nửa:** Dashboard dùng CÙNG ensemble PRODUCTION_CONFIG với trang Kế hoạch qua `HierarchicalForecastService.forecast_group()` (không chia mã), không còn `topdown.py` Ridge riêng cho thẻ dự báo. `dss_runner.run_forecast_cycle` (demand-vs-stock cũ) vẫn gọi `topdown` — gỡ khi các trang khác thôi dùng 4 endpoint cũ | `hierarchical_forecast_service.py` |
| `alert_rows` trả thêm `danh_muc` (medical_supplies.category) để vẽ DOI theo danh mục | `dss_alerts.py` |
| Chất lượng dự báo đọc từ `backend/ketqua_backtest/` (phancap.csv, nhom.csv, cau_hinh.json) — không có thư mục thì thẻ ghi "chưa có", không bịa | `dss_dashboard.backtest_quality()` |
| Trang `Dashboard.tsx` viết lại: bộ lọc (kỳ chỉ đọc · nhóm bệnh · tập vật tư · mức), 5 KPI, xu hướng 12 kỳ + dải khoảng dự báo, DOI theo danh mục với vạch 18/36, bảng cảnh báo 4 mức + "Thiếu hụt dự kiến" (= Δ_need, để trống khi chưa có dự báo), phân cấp chăm sóc, Trạng thái dữ liệu (thay bản đồ dịch tễ), Diễn giải nhanh. Bỏ "Hoạt động gần đây" theo yêu cầu | `frontend/src/pages/Dashboard.tsx`, `components/dashboard/*`, `types/dashboardV2.ts` (viết lại hợp đồng), `hooks/useDashboard.ts`, `services/dashboardService.ts` |
| `EpidemicMapCard.tsx` không còn ai dùng → `_archive/frontend_chet/components_dashboard/` | |

Bốn endpoint cũ `summary / case-trend / demand-vs-stock / critical-alerts` giữ nguyên cho tới khi Reports/Alerts thôi gọi.

**Nhật ký Tuần 3 · 11/09/2026 — 3.1–3.6 xong**

| # | Đã làm |
|---|---|
| 3.1 | `supply_recommendation_service`: "Đặt hàng ngay" → "Cần chuẩn bị bổ sung ngay", "kỳ đặt hàng kế tiếp" → "kỳ bổ sung kế tiếp", "Không cần nhập" → "Không cần bổ sung". `supply_planning_service` bỏ `lead_time_days` khỏi SELECT và items (khoá `suggested_import` giữ tên, nghĩa = Δ thiếu hụt) |
| 3.2 | `Alerts.tsx` tiêu đề "Cảnh báo nguy cơ thiếu hụt", cột "Thiếu hụt cần chuẩn bị", KPI "Thiếu hụt"/"Tổng lượng cần chuẩn bị", icon giỏ hàng → PackageMinus. `SupplyPlanning.tsx` "Kế hoạch cung ứng", bỏ cột Lead. `ReportTypePicker` bỏ thẻ procurement; `Reports.tsx` bỏ query/preview/xuất Excel procurement (~110 dòng, kéo theo cả sessionStorage ngưỡng tay). `Inventory.tsx` bỏ ô Lead time, bỏ nút + modal "Cập nhật ngưỡng AT từ dự báo". `types/config.ts` bỏ mục `lead-times`; `types/inventory.ts` bỏ `lead_time_days`, `minimum_order_quantity`. Schema Pydantic `MedicalSupply*` bỏ hai trường đó (cột DB giữ, không migrate); CSV mẫu và Excel xuất kho bỏ cột lead time |
| 3.3 | Một nhãn: **"Ngưỡng an toàn"** ở Alerts, Inventory, Reports, Excel (hết "Ngưỡng AT"/"Mức an toàn" lẫn lộn); giải nghĩa một lần ở đầu trang Cảnh báo. Trạng thái `critical` đổi "Cần nhập gấp" → **"Nguy cấp"** (frontend + PDF/Excel backend) |
| 3.4 | Sidebar: "Dashboard" → "Tổng quan", "Cảnh báo tồn kho" → "Cảnh báo thiếu hụt", thêm **"Kế hoạch cung ứng"** (`/supply-plan`); tiêu đề trang Dữ liệu bệnh / Thời tiết / Vật tư / Quản trị khớp nhãn menu |
| 3.5 | `reports.py`: xoá `_build_procurement_data`, `_render_procurement_pdf`, `_render_procurement_excel` và nhánh không tới được (thay bằng HTTP 400 tường minh) — 115 dòng |
| 3.6 | Xoá `POST /inventory/sync-safety-stock` (121 dòng) và toàn bộ UI gọi nó |
| + | Sửa nhân tiện: `Weather.tsx` gọi `setDistricts` không tồn tại (ReferenceError lúc chạy); kiểu `LucideIcon` cho Sidebar; `useRunSync` nhận `boolean` — **`tsc --noEmit` mã nguồn (ngoài test) = 0 lỗi**, trước đó 56 |

Còn lại của Tuần 3: 3.7 đóng gói bộ dữ liệu, 3.8 từ điển dữ liệu + datasheet.

**Nhật ký 11/09/2026 (chiều) — M12 kéo từ Tuần 4 lên, vì "độ chính xác tốt nhất có thể" là ưu tiên**

Bench cloud (statsmodels 0.15) tái lập đúng số chính thức buổi sáng, rồi: `combine.py`
(trọng số nghịch đảo MAE cửa sổ 12, luỹ thừa 2 + hệ số lệch co rút 0,5, chặn 1,5),
`ets_opt.py` (thành viên ETS), `group_forecast.py` (một đường walk-forward cho backtest
và ba service). Kết quả: RelMAE mã **0,659 → 0,500**, nhóm 0,52/0,38/0,54, lệch về
≈0, độ phủ J09-J18 68 → 80 %. `ket_hop.csv` ghi 8 biến thể đối chứng. Trang Kế hoạch
cung ứng ẩn theo quyết định phạm vi (dừng ở Cảnh báo thiếu hụt).

**Tuần 4 (tối 11/09):** 4a gỡ `topdown.py` → `_archive` (Tầng 1 duy nhất); 4b đối chứng
XGBoost/Prophet đo trên cùng bench (`doi_chung_xgb_prophet.csv`, KetQua mục 0.4): Prophet
tệ hơn naive, XGBoost +1 % không đáng phụ thuộc — 4.3–4.4 khép.

**3.7 xong (tối 11/09):** `dataset/v1/` (3 CSV + manifest sha256 + README + TU_DIEN_DU_LIEU + DATASHEET),
`app/forecasting/dataset.py | train.py | predict.py`, `backend/models/v1/model_v1.json`. `train.py` chạy
từ CSV tái lập đúng 0,500 / 0,516 / 0,377 / 0,541. 3.8 (từ điển + datasheet) gộp vào đây.

### TUẦN 4 — Bằng chứng huấn luyện và đối chứng mô hình
*Đây là tuần trả lời trực tiếp câu hỏi của thầy về "model train" và "tính ứng dụng".*

| # | Việc |
|---|---|
| 4.1 | Thêm **sMAPE + WAPE** vào `evaluate.py` (đề cương hứa, hiện chỉ có MAE/RMSE/MASE) |
| 4.2 | Chạy lại walk-forward chính thức một lượt trên cấu hình đã chốt (lịch sử 2019 + TD động + thời tiết bật) → bảng số cuối cùng cho chương 4, đúng bộ chỉ số đề cương |
| 4.3 | **Đối chứng Prophet + NegBin** — thêm 2 thành viên vào cùng giao thức walk-forward, ghi vào bảng so sánh. Đề cương hứa Prophet ở thể khẳng định; phải **loại bằng số đo chứ không phải im lặng** |
| 4.4 | **Đối chứng XGBoost có lưu artifact** — hồi sinh mã trong `_archive/`, huấn luyện đúng giao thức walk-forward, lưu `.pkl` có phiên bản, đặt cạnh ensemble trong bảng so sánh. ⚠ **Tuyệt đối không dùng lại `MonthlyForecaster`** (rò rỉ mục tiêu). Kết quả nào cũng dùng được: XGBoost thua ensemble thống kê trên chuỗi 92 điểm là kết quả đã biết trong tài liệu, và giờ có bằng chứng từ chính dữ liệu bệnh viện |
| 4.5 | **Lưu vết huấn luyện:** mỗi lần dự báo ghi kèm cấu hình đã fit (thành viên ensemble, hệ số, cửa sổ lịch sử, thời tiết bật/tắt, thời điểm) + chỉ số walk-forward. Bảng `disease_forecasts` **đã có sẵn** các cột `model_used`, `model_accuracy_mae/rmse/mape` (`disease_forecast.py:34-37`) — chỉ cần ghi tử tế và sửa chú thích còn ghi "xgboost, lstm, prophet" từ thời cũ. Đóng luôn cam kết "lưu phiên bản mô hình, tham số, chỉ số" đang là 🟡 |

### TUẦN 5 — Khép cam kết đề cương còn lại

| # | Việc |
|---|---|
| 5.1 | **Định mức mức NHÓM** — mở khoá J18 (30% số ca hiện không sinh được nhu cầu). Xoá `DEFAULT_CONVERSION_RATIOS` (`ai_engine/config.py:171-196`) vốn chỉ có dengue/cúm/hô hấp chung, không có mã ICD nào của đồ án |
| 5.2 | **Điền định mức khác biệt theo mức nặng**, hoặc — nếu Khoa Dược chưa kịp — hiển thị cảnh báo từ `chan_doan_dinh_muc()` ra UI và ghi vào phần hạn chế. Hiện `quantity_per_case` giống hệt ở cả ba mức (18/18/18) nên toàn bộ bộ máy suy luận độ nặng không làm đổi kết quả |
| 5.3 | Bổ sung AQI vào chuỗi mô hình (`models.py:134` hiện `WCOLS = [temp, humidity, rainfall]`) — hoặc ghi rõ lý do loại |
| 5.4 | Trích bộ nhãn 4 mức + `GreyReason` từ `dashboardV2.ts` ra chỗ dùng thật, rồi đóng gói phần còn lại |
| 5.5 | Chụp lại toàn bộ ảnh màn hình cho báo cáo (sau khi UI đã chốt ở Tuần 3) |
| 5.6 | Gửi phòng KHTH đối chiếu số liệu — **việc này chờ người khác, nên khởi động ngay từ Tuần 1**, đây chỉ là mốc thu kết quả |

### TUẦN 6 — Viết, tổng duyệt, dự phòng

| # | Việc |
|---|---|
| 6.1 | Cập nhật đề cương `.docx` theo số mới; mọi dòng phải có ✅ hoặc một câu giải thích **có số liệu** |
| 6.2 | Viết mục "Tái cấu trúc phạm vi" trong báo cáo — kể câu chuyện gỡ phân hệ mua sắm như một quyết định thiết kế có lý do, kèm `_archive/README.md` làm phụ lục |
| 6.3 | Tổng duyệt demo: chạy thử đúng kịch bản sẽ trình bày, bấm hết các nút, xác nhận không endpoint nào trả rỗng im lặng |
| 6.4 | Dự phòng cho việc trượt tiến độ |

---

## 4. NHỮNG GÌ KHÔNG LÀM TRONG 6 TUẦN NÀY

Với mốc bảo vệ, việc loại bỏ khỏi phạm vi cũng quan trọng như việc thêm vào. Bốn nhóm dưới đây **cố ý gác lại** — nhưng nên ghi vào mục "Hướng phát triển" của báo cáo, vì tự nhận ra hạn chế là điểm cộng khi bảo vệ:

| Nhóm | Vì sao gác |
|---|---|
| **Hợp nhất 4 nguồn tính nhu cầu về `dss_demand`** | Là việc đúng nhưng chạm vào 4 service + 3 màn hình, rủi ro vỡ cao ngay trước bảo vệ. Tuần 1 chỉ làm phần tối thiểu: đảm bảo bản demo hiển thị một con số nhất quán |
| **Rút `forecast_analysis.py` (1.441 dòng) thành service** | Sau Tuần 1 nó đã bớt nguy hiểm (bỏ 2 endpoint + 1 bước thừa). Việc tái cấu trúc còn lại là nợ kỹ thuật, không phải rủi ro bảo vệ |
| **Hợp nhất 2 thuật toán cảnh báo** | `dss_alerts` đã đúng chuẩn 4 mức và frontend **không gọi** router `/api/v1/alerts`. Kiểm tra lại điều này ở Tuần 1; nếu đúng thì vấn đề tự biến mất khi đóng gói, không cần tái cấu trúc |
| **Chuẩn hoá 6 nhóm hằng số nghiệp vụ vào `system_config`** | Chỉ `dss_alerts.get_thresholds()` làm đúng. Còn lại (hệ số thời tiết, ngưỡng rủi ro 50/25/10%, buffer 15%, `Z_SERVICE=1,96`) vẫn hardcode — ghi vào hạn chế |

---

## 5. RỦI RO BUỔI BẢO VỆ VÀ CÁCH CHẶN TRƯỚC

| Nếu thầy… | Hiện tại sẽ ra sao | Chặn ở đâu |
|---|---|---|
| Bấm "Huấn luyện" ở trang Phân tích rồi hỏi "MAPE này tính thế nào" | Đó là sai số in-sample của mô hình rò rỉ mục tiêu — không có câu trả lời tốt | **1.1** |
| Mở báo cáo tồn kho | Bảng rỗng, không có dòng nào, không thông báo gì | **1.3** |
| Đọc README rồi hỏi "LSTM ở đâu" | README ghi có, mã không có, file `.pkl` trong repo lại càng khó giải thích | **1.6** + **2.1** |
| Hỏi "hệ thống chạy trên CSDL gì" | Repo có cả SQLite lẫn Postgres, tài liệu hướng dẫn cả hai | **2.4** |
| Hỏi "dataset đâu, có dùng lại được không" | Dữ liệu nằm trong SQLite, chưa có bản xuất, chưa có từ điển | **3.7–3.8** |
| Hỏi "mô hình có train không, bằng chứng đâu" | Có train thật nhưng không lưu vết nào | **4.5** |
| Hỏi "vì sao không thử XGBoost/Prophet" | Có mã nhưng chưa từng chạy, chưa có số so sánh | **4.3–4.4** |
| Mở J18 (nhóm bệnh lớn nhất) xem đề xuất vật tư | Không sinh được nhu cầu vì thiếu định mức | **5.1–5.2** |

---

## 6. VIỆC LÀM NGAY HÔM NAY (30 phút)

1. `.gitignore` += `.env*`, xoá `backend/.env.saoluu_20260908` — **mật khẩu HIS đang hở**
2. Tạo nhánh git `tai-cau-truc-2026-09` trước khi động vào bất cứ thứ gì
3. Gửi phòng KHTH yêu cầu đối chiếu số liệu — việc chờ người khác, khởi động càng sớm càng tốt
4. Sửa 3 chỗ `async def` → `def` (`forecast_analysis.py:407, 438, 564`)

---

*Tài liệu này thay thế phần "Lộ trình khắc phục" trong báo cáo rà soát 09/09/2026, đã tái sắp xếp theo 4 quyết định phạm vi và mốc bảo vệ 4–6 tuần.*
