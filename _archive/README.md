# _archive — mã đã loại khỏi phạm vi sản phẩm

Đóng gói ngày 09/09/2026, trong đợt tái định hình MedForecast AI.
**Không xoá file nào** — mọi thứ ở đây vẫn tra cứu được khi viết báo cáo.

## Tiêu chí xác định mã chết
Grep tham chiếu ngược **có tính bắc cầu**: một file chỉ vào đây khi mọi nơi
gọi nó cũng nằm trong danh sách này. Đã loại trừ file `test_*` khỏi phép đếm.

## Các nhóm

- **ai_engine_cu/** — nhánh XGBoost/Prophet/LSTM. Điểm vào duy nhất là một
  Celery task không nơi nào gọi, và docker-compose không có worker nào; tức
  nhánh này **chưa từng chạy trong sản phẩm**. `ensemble_forecaster.py:89`
  cho thấy LSTM chưa bao giờ được cài đặt (`self.lstm_model = None`, dòng 280
  lấy trung bình XGBoost và Prophet rồi gán làm "dự đoán LSTM"). Kèm 8 file
  `.pkl` là artifact của nhánh này — trong đó 3 file thuộc phân hệ cũ
  (dengue_fever, seasonal_flu, respiratory_disease), không phải nhóm ICD hô hấp.
  *Dùng lại khi:* làm đối chứng XGBoost ở Tuần 4 — nhưng phải huấn luyện lại
  theo giao thức walk-forward, **không dùng lại MonthlyForecaster** (rò rỉ mục tiêu).

- **dich_vu_chet/** — service và Celery task 0 tham chiếu, cộng 4 file test
  nằm lẫn trong package sản phẩm.

- **sql_schema_cu/** — 4 file SQL truy vấn `KhamBenh`, `ChanDoan`, `BenhNhan`,
  `SuDungVatTu`, `VatTu`, `TonKho`: schema giả định thời chưa nối HIS thật.
  HIS thật dùng `TT_TIEPNHAN`, `TT_NGOAITRU_KHAMBENH`, `TM_ICD`, `TT_DUOC_TONKHO`.

- **frontend_chet/** — trang, hook và component 0 tham chiếu.
  `SupplyNormPage.tsx` còn không có `<Route>` nào trong `App.tsx`.

- **postgres/** — hệ quả quyết định giữ SQLite làm CSDL duy nhất. Để lại trong
  repo sẽ mâu thuẫn với kiến trúc đã chốt.

- **tap_nhap/** — script tạp, CSV kết quả tạm, file lạc chỗ ở gốc repo.

## Khôi phục
`git mv _archive/<nhóm>/<đường dẫn> <đường dẫn>` rồi hoàn lại 3 sửa đổi thủ
công ghi ở đầu `bo_ma_chet.sh`.

- `frontend_chet/components_dashboard/EpidemicMapCard.tsx` — thẻ bản đồ dịch tễ của Dashboard cũ; Dashboard v2 (11/09/2026) thay bằng thẻ "Trạng thái dữ liệu" vì hệ thống chỉ có một cơ sở.

- `ai_engine_cu/topdown.py` — Tầng 1 cũ của Dashboard (Ridge + lag trên tổng, chia theo tỷ trọng); chưa từng nằm trong bảng so sánh. Gỡ 11/09/2026 khi Dashboard chuyển sang ensemble M12 (`group_forecast.py`). Bảng `forecast_accuracy` nó ghi cũng không còn ai đọc.

## dinh_muc_nhap_tay/ — đóng gói 12/09/2026

**Vì sao:** hệ thống chạy HAI bộ máy tính nhu cầu song song. Tổng quan dùng
`dss_demand` (định mức THỰC NGHIỆM từ `fact_usage/cases_by_care_level`, chiều
phân loại là rổ chăm sóc NGT/NT1/NT2/NT3) và `dss_alerts` (ngưỡng
`dss.thresholds`: Đỏ ≤ 18 / Vàng ≤ 36 ngày DOI). Trang Cảnh báo thiếu hụt và
ba tab Quản trị (Tỷ lệ Nhẹ/TB/Nặng, Định mức thuốc/vật tư, Ngưỡng cảnh báo)
lại đi qua nhóm service dưới đây: định mức nhập tay `disease_supply_norms` ×
`severity_rates`, ngưỡng hard-code 3/7/14 ngày trong `alert_service.py`, và
cột "Đề xuất nhập" (mua sắm — đã ngoài phạm vi). Hai trang ra hai con số khác
nhau về cùng một mã; ba tab Quản trị bấm "Lưu" không đổi gì trên Dashboard.

Ngoài ra định mức gõ tay đo ra GIỐNG NHAU ở cả ba mức nặng (2/2/2 · 3/3/3 ·
1/1/1) — chiều độ nặng không mang thông tin — nên đường "nhập tay" trong
`dss_demand.py` (bản hai đường lưu ở `dss_demand_hai_duong.py`) cũng bỏ.

- backend/app/services/: `supply_recommendation_service`, `supply_planning_service`,
  `alert_service`, `severity_inference_service`; tasks/`severity_inference_task`
- backend/app/api/v1/: `alerts`, `supply_recommendations`, `supply_plan`, `admin_severity`
- backend/scripts/`seed_severity_rates.py`; tests/integration/`test_alerts_integration.py`
- frontend: `supplyRecommendationService`, `supplyPlanService`, `adminSeverityService`,
  `SupplyNormSection`, `SeverityRateSection`, `ThresholdsAndRatiosSection`, `SupplyPlanning.tsx`

**Thay bằng:** `/dashboard/v2/alerts` (cùng chuỗi Tầng 1→2→3 với Tổng quan),
`/dss/params` (sửa `dss.thresholds` + `dss.care_level`, có kiểm khoảng và audit),
`/dss/norms` (bảng tra định mức thực nghiệm, chỉ đọc).

**Còn lại chưa gom (đường thứ ba, việc kế tiếp):** `ai_engine/conversion_module.py`
+ `supply_requirement_service.py` + `api/v1/supply_requirements.py` — nuôi bảng
`supply_requirements` mà trang Báo cáo (loại "thiếu hụt") và bước 5 của
`/forecast/analyze` còn đọc; `conversion_ratios` đang 0 dòng nên đường này không
sinh gì mới. Gom về `/dashboard/v2/alerts` khi làm lại trang Báo cáo.

**Bảng DB giữ nguyên** (`disease_supply_norms`, `severity_rates`, `alerts`,
`supply_recommendations`, `conversion_ratios`) — model còn để `create_all` không
vỡ; muốn "ghi đè thủ công" thì làm lại như một lớp override rõ ràng trên
`/dss/norms`, không phải đường lùi ngầm.

## Kiểm toán 13/09/2026 — bốn thư mục mới

Tiêu chí như trên: không còn nơi gọi trong `backend/app`, `backend/scripts`
(các script còn dùng), `frontend/src` — xác minh bằng grep trước khi chuyển.
Model ORM tương ứng (`SupplyRequirement`, `ConversionRatio`, `Alert`…) vẫn giữ
trong `app/models` để `create_all` không vỡ trên DB cũ.

### duong_thu_ba/
"Đường thứ ba" tính nhu cầu vật tư qua bảng `supply_requirements`, song song
với `dss_demand`: `services/supply_requirement_service.py`, cả package
`ai_engine/` (`conversion_module.py`, `config.py` còn XGBoost/LSTM/Prophet và
`DISEASE_TYPES = dengue_fever…`), hai script `create_/regenerate_supply_requirements.py`,
test tích hợp tương ứng. Ba endpoint `GET /supply-requirements`, `/forecast/{id}`,
`POST /generate/{id}` đã xoá khỏi router; chỉ còn `/summary` (đi qua
`dss_dashboard.tang1_tang2`).

### dich_vu_chet/ (bổ sung)
- `api/v1/forecast_hier.py` + `hooks/useForecastHier.ts` + `services/forecastHierService.ts`:
  nhánh dự báo phân rã về từng mã (top_down_fixed / bottom_up / mint), giao diện
  không gọi. Kéo theo `HierarchicalForecastService.forecast()`, `inventory_report()`,
  `_codes_df()`, `_fixed_shares()` và `models.build_production_ensemble()` (trùng
  `group_forecast.make_ensemble`).
- `api/v1/supplies.py` + `services/medical_supply_service.py`: giao diện không gọi
  `/supplies`; POST vỡ sẵn (`supply_data.name` không có trong schema).
- `services/notification_service.py`: gửi mail cho bảng `alerts` đã archive.
- `data_pipeline/scheduler.py`: chỉ chạy pipeline ca bệnh, không nạp 4 luồng DSS
  → DB nửa vời so với nút Đồng bộ. Lịch chạy đúng là job SQL Agent + nút Đồng bộ.
- `forecasting/candidates_opt.py`: thành viên thử nghiệm (xgb/prophet) không có
  trong `ForecastConfig`.
- `services/dss_runner.py`: payload cho 6 endpoint dashboard cũ (`/overview`,
  `/summary`, `/risk-status`, `/critical-alerts`, `/case-trend`, `/care-level`)
  — cả 6 đã gỡ khỏi `dashboard.py` cùng lớp cache Redis; `care_level_payload`
  chuyển sang `dss_dashboard`.

### scripts_cu/
22 script thời CSV / định mức nhập tay / alerts theo safety_stock / Postgres
(`backup_db.sh`) / bản vá đã hợp nhất (`patch_g1_dashboard.py`,
`migrate_*.py`, `recreate_database.py`) và `verify_backend_dss.py` (gọi
`run_forecast_cycle` đã gỡ từ 11/09). Bộ script còn dùng: `khoi_tao_moi`,
`nang_cap_db`, `run_dss_load`, `kiem_tra_ket_noi_sta`, `kiem_tra_so_ca_nhom`,
`verify_g1`, `verify_his_pipeline`, `verify_ehospital_agg`, `sim_*`,
`sync_admin_diseases_catalog`, `xoa_va_nap_lai`, `clear_test_data`,
`create_admin_user`, `seed_data`.

### tests_cu/ và frontend_chet/ (bổ sung)
Test backend/frontend viết cho lược đồ cũ (`dengue_fever`, `MedicalSupply.name`,
`district_ward`, `ProcurementPlanner`, props cũ của `InventoryTable`…) — 2 file
fail ngay lúc collect, phần còn lại 53 failed / 37 errors trước khi kiểm toán.
Thay bằng `backend/tests/test_dss_core.py` (21 test lõi 3 tầng) và
`tests/integration/test_dss_api_integration.py` (9 test hợp đồng API);
frontend: `useReports/useInventory/reportsService/inventoryService` test viết lại.
Kèm 9 component/type mồ côi (`Modal`, `Table`, `MetricCard`, `InventoryFilters`,
`StockStatusBadge`, `PerformanceTable`, `ReportFilters`, `ConsumptionReport`,
`types/alerts.ts`).

### frontend_chet/components/inventory/InventoryStatusBadge.tsx (13/09, chiều muộn)
Nhãn "Bình thường / Dưới ngưỡng / Nguy cấp" tính từ `inventory.safety_stock` —
cột chỉ có giá trị ở 34/5.051 dòng, nên trang Vật tư luôn hiện "0 mục" trong
khi Cảnh báo báo 39 Đỏ. Trang đổi tên thành **Quản lý thuốc** và gắn nhãn DOI
từ `/dashboard/v2/alerts?focus=false` (cùng chuỗi với Cảnh báo); báo cáo
"Tồn kho" đổi theo. Không còn hệ nhãn thứ hai nào trong ứng dụng.
