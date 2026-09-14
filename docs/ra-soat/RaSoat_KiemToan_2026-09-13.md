# Kiểm toán mã nguồn MedForecast AI — 13/09/2026

Phạm vi: toàn bộ `backend/app`, `backend/scripts`, `backend/tests`, `frontend/src`,
3 thủ tục PROD (`usp_MedForecast_Day*`), dump STA `MEDFORECAST_DW`. Đối chiếu với
5 ràng buộc đã chốt (DSS 3 tầng, không mua sắm; kỳ chốt `is_complete = 1`; Ridge +
Bates–Granger; 5 rổ chăm sóc từ 2025-04; FEFO + DOI 18/36; `/dss/params`,
không còn `_sync_alerts_with_inventory`; mẫu số `v_supply_active` / `v_supply_focus`).

Ba quyết định phạm vi chốt trong phiên (đã ghi ở `claude/trang-thai-medforecast.md`):
Norm giữ Σ tiêu hao / Σ ca (không đổi sang Median/MAD); FEFO giữ dạng clamp
`u_b = clamp(d·ngày_còn_hạn − C, 0, q_b)`; VTYT chốt **phương án A** (thuốc thuần).

Kết quả kiểm chứng: `pytest` 121 passed (máy user + container); `npm run typecheck`
0 lỗi; `vitest` 144 passed / 19 file; `vite build` OK; app khởi động sạch trên DB
rỗng (8/8 mục lược đồ ngoài ORM).

---

## 1. Lỗi trọng yếu đã sửa (Nặng)

| # | File | Lỗi | Sửa |
|---|---|---|---|
| N1 | `data_pipeline/views.py`, `G1_03`, `G1_04` | 4 view lấy 12 kỳ gần nhất **kể cả tháng 2026-09 dở dang** → `d_daily` bị kéo thấp, DOI phồng; tập trọng tâm/mẫu số gồm cả VTYT (không tồn, không định mức → Xám); tập trọng tâm còn chứa mã **đã ngừng xuất**. | Mọi view thêm `period < strftime('%Y-%m','now','localtime')` và `is_vtyt = 0`; `v_supply_focus` thêm `IN (SELECT supply_code FROM v_supply_active)`. Đo trên DB thật: tập trọng tâm 299 → **242 mã**; Đỏ/Vàng/Xanh/Xám 40/31/142/86 → **40/27/138/37**; cửa sổ phân cấp 2025-10..2026-09 → **2025-09..2026-08**; `v_supply_active` 1.302 → **1.068**; Norm hiệu dụng EF5T 1,0357 → **1,01**. |
| N2 | `services/dss_demand.py::_cua_so_ky` | Cửa sổ định mức cũng lấy kỳ dở. | Lọc `period < tháng hiện tại`. |
| N3 | `api/v1/reports.py::_build_dashboard_summary_data` | Báo cáo "Tổng quan" tính `SUM(case_count)` theo `date.today()` → xu hướng +6500 %, dự báo/thực tế so với tháng mới có vài ngày. | Neo vào `period_service` (kỳ đã chốt, mart), chuỗi 6 kỳ từ mart; trả thêm `last_closed_period`, `open_period`, `forecast_period`. |
| N4 | `api/v1/forecast_analysis.py::_cap_nhat_dong_toan_quoc` | Ghi nhận lẻ một tỉnh **ghi đè** bản Toàn quốc bằng Σ tỉnh (`tong_hop_tinh_v1`, khoảng ±15 % giả) — đúng lỗi 425/393 đã sửa ở FE nhưng backend vẫn tái sinh. | Xoá hàm và khối gọi. |
| N5 | `forecast_analysis.py::_trend_factor`, `chart_main`, `trend_current_year`, `services/actual_case_service.py` | Tháng dở dang được coi là "thực tế": hệ số xu hướng bị clamp về 0,5; độ lệch dự báo/thực tế +200…+300 % cho kỳ chưa kết thúc. | Thêm `_thang_da_chot()`; tháng dở → `None`; `so_ca_thuc_te` Toàn quốc đọc `mart_monthly_cases_by_block` (`is_complete = 1`). |
| N6 | `services/disease_case_service.py:99` | `data.district_ward` không có trong `DiseaseCaseCreate` → **POST /disease-cases luôn 500**. | Xoá dòng. |
| N7 | `api/v1/disease_cases.py:109` | Dedupe theo `disease_type` (mọi bản ghi = "respiratory") → ca thứ hai cùng tháng/khu vực của mã khác bị 409. | So `icd_code`. |
| N8 | `frontend/pages/DiseaseCaseDetail.tsx` | Nút "Xuất báo cáo" `window.open(GET /reports/export?from_month…)` — backend chỉ có POST, không mang JWT → 405/401. | `reportsService.exportReport({epidemic, start_date, end_date, location})` + `triggerDownload`. |
| N9 | `frontend/components/dashboard/TrendChart.tsx` | `trend.last_year.by_block[block]` với `last_year = {}` (DB mới) → TypeError → ErrorBoundary trắng trang. | `?.` + type `TrendSection` cho phép thiếu. |
| N10 | `api/v1/config.py`, `services/config_service.py` | `GET /config` trả `his_sync.connection` kèm `password_enc` cho mọi user; `PUT /config/dss.thresholds` bỏ qua kiểm khoảng của `/dss/params`. | Che `password_enc` (expunge trước khi sửa), chặn 3 khoá chuyên biệt ở PUT. |
| N11 | `dependencies.py`, `api/v1/auth.py`, `frontend/services/api.ts` | Refresh token dùng được như access token; FE gửi access token đã hết hạn để refresh. | `_user_tu_token(loai)`; `/refresh` chỉ nhận `type = "refresh"`; FE gửi `REFRESH_TOKEN_KEY`. |
| N12 | `services/sync_service.py::_lam_moi_bang_nghiep_vu` | Upsert vật tư: nhánh TẠO MỚI có `category`, nhánh CẬP NHẬT thì không → mọi mã đã tồn tại giữ phân loại ghi lần đầu **vĩnh viễn**. Phát hiện khi sửa `#DrugMeta` trên PROD (G2_04): đồng bộ báo ok, 7.319 dòng, nhưng 3.001 mã vẫn mang nhãn "Dịch truyền" cũ. | Tách `lam_sach()` + `cap_nhat_thuoc_tinh_vat_tu()` ra mức module, liệt kê tường minh 5 cột đồng bộ trong `COT_DONG_BO`; trả thêm `legacy_supplies_updated`. 3 test khoá. |

## 2. Lỗi Vừa đã sửa

- `dss_loader.load_flow`: DELETE + INSERT + commit bọc `try/except` → `rollback()` (test `test_load_flow_rollback_khi_insert_vo`).
- `sync_service` bước 3 lỗi không `rollback()` → session bẩn cho `fill_actuals`/`get_status`.
- `admin_catalog._get_or_init` `add + commit` trong GET → GET không ghi; dòng chỉ persist ở `_save_list`. Gỡ `admin.safety_rate` (không service nào đọc) + `SafetyRateCard` FE.
- `inventory_service.batch_update_inventory`: gán rồi mới `continue` → commit nửa chừng; nay kiểm cả hai giá trị trước, chặn chuỗi.
- `inventory.py` DELETE còn ghi bảng `alerts` (archived) → gỡ; `_trigger_alert_check` rỗng → gỡ.
- `environmental.py` 2 chỗ `commit()` không rollback → bọc.
- `forecasting/sarimax_opt.py`: exog dự báo lấy `exog[-1]` (= w[n−2]) trong khi huấn luyện lag 1 → dùng `w[n−lag]`.
- `forecast_analysis`: `rmse = mae` bịa → `None`; Pearson tính cả điểm dự báo → chỉ năm thực tế; câu "so với 3 tháng trước" dùng `counts[3]`.
- `hierarchical_forecast_service`: `_rows` nuốt `SQLAlchemyError` → log; kỳ đích xa hơn 1 bước → `horizon_months` + `horizon_note`.
- `frontend/pages/Dashboard.tsx`: "Tốt hơn naive **%**", "độ phủ **%**", "WAPE **%**" khi giá trị null; "(mục tiêu 90)" thiếu %.
- `DssParamsSection`: nhánh "đang tải" đứng trước `error` → spinner vĩnh viễn khi GET lỗi.
- `EmpiricalNormsSection`: "Cửa sổ undefined → undefined" khi chưa có kỳ.
- `Reports.tsx`: 5 request bắn mỗi lần mở trang → `enabled` theo loại báo cáo.
- `Forecasting.tsx`: `100 − null = 100 %` khi cache thiếu MAPE → dùng `accuracy_pct`.
- `vite.config.ts`: vitest thu thập cả `e2e/*.spec.ts` (Playwright) → exclude.

## 3. Dead code / tàn dư mua sắm đã gỡ (xem `_archive/README.md`)

Backend: `dss_runner.py` + 6 endpoint dashboard cũ + lớp cache Redis; `forecast_hier.py` +
4 method của `HierarchicalForecastService` + `models.build_production_ensemble`;
`supplies.py` + `medical_supply_service.py`; `notification_service.py`; `scheduler.py`;
`ai_engine/` (XGBoost/LSTM/Prophet, `DISEASE_TYPES = dengue_fever…`);
`supply_requirement_service.py` + 3 endpoint `supply-requirements`; 2 báo cáo
`consumption`/`inventory-turnover` (đọc `supply_requirements` đã ngừng sinh);
`candidates_opt.py`; `app/tasks`, `app/procurement` (rỗng); `storage_capacity` khỏi
schema; `procurement_plans` khỏi 2 script; 22 script mồ côi; 7 file test lỗi thời
(53 failed / 37 errors trước kiểm toán); import thừa (pyflakes sạch).
Frontend: `useForecastHier`/`forecastHierService`; `SafetyRateCard`; nhãn "lập/duyệt
kế hoạch cung ứng" ở ma trận quyền; `reorder_point`/`storage_capacity`/
`safety_stock_level` khỏi `types/inventory.ts` (viết lại theo `InventoryResponse`);
`ROUTES.SUPPLY_*`; comment về `SupplyPlanning.tsx` không tồn tại; 9 component/type
mồ côi; `console.log` Weather; 7 test cũ.

Comment/docstring: bỏ các khối "ĐÃ GỠ ngày … KHÔNG khôi phục", nhật ký thay đổi
trong mã, boilerplate tiếng Anh; docstring các module lõi rút về: đầu vào — nghiệp
vụ — ngoại lệ — trả về.

## 4. Bảng đối soát theo file

Trạng thái: **S** sạch (đã đọc, không sửa) · **C** cần sửa → đã sửa · **X** xoá/archive.

### Backend — lõi DSS

| File | TT | Phát hiện | Hành động |
|---|---|---|---|
| `services/dss_alerts.py` | S | FEFO, nhãn, chia 0 đều chặn; docstring đúng | Giữ; phủ 6 test |
| `services/dss_demand.py` | C | N2; docstring lịch sử dài | Lọc kỳ dở; rút docstring; 2 test |
| `services/dss_dashboard.py` | C | Nhận `care_level_payload` từ dss_runner; docstring lịch sử | Gộp hàm; rút docstring |
| `services/dss_runner.py` | X | Chỉ nuôi 6 endpoint cũ | Archive |
| `services/period_service.py` | S | `stock_signal_counts` chỉ script cũ gọi | Giữ (script đã archive) |
| `data_pipeline/views.py` | C | N1 | 4 view mới; test |
| `data_pipeline/dss_loader.py` | C | Không rollback | try/except; 3 test |
| `data_pipeline/pipeline.py` | S | `is_complete` tính đúng | — |
| `forecasting/combine.py` | S | Bates–Granger đúng spec (1/MAE, `min_hist` 6, TB cho thành viên thiếu) | Import thừa; 3 test |
| `forecasting/group_forecast.py` | S | — | — |
| `forecasting/models.py` | C | `build_production_ensemble` trùng | Gỡ |
| `forecasting/sarimax_opt.py` | C | exog lệch 1 bước | Sửa |
| `forecasting/candidates_opt.py` | X | mồ côi | Archive |
| `forecasting/test_forecasting.py` | C | sai vị trí | → `tests/` |
| `forecasting/{config,hierarchical,evaluate,data_access,dataset,predict,train,run_eval,ets_opt}.py` | S | CLI/backtest, chỉ import thừa | pyflakes sạch |

### Backend — API

| File | TT | Phát hiện | Hành động |
|---|---|---|---|
| `api/v1/dashboard.py` | C | 6 endpoint chết + Redis + `_enrich_alert` + `Alert` import | Viết lại: 4 endpoint v2 |
| `api/v1/dss_config.py` | S | Kiểm khoảng, Đỏ < Vàng, YYYY-MM đúng | import thừa; 1 test |
| `api/v1/forecast_analysis.py` | C | N4, N5, rmse, Pearson | Sửa |
| `api/v1/forecast_hier.py` | X | FE không gọi | Archive |
| `api/v1/reports.py` | C | N3; 2 báo cáo chết; nhánh Postgres | Sửa |
| `api/v1/supply_requirements.py` | C | 3 endpoint chết | Chỉ còn `/summary` |
| `api/v1/supplies.py` | X | FE không gọi, POST vỡ | Archive |
| `api/v1/disease_cases.py` | C | N7 | Sửa |
| `api/v1/inventory.py` | C | ghi `alerts` | Sửa |
| `api/v1/config.py` | C | N10 | Sửa |
| `api/v1/auth.py`, `dependencies.py` | C | N11 | Sửa |
| `api/v1/admin_catalog.py` | C | GET ghi DB; safety-rate | Sửa |
| `api/v1/environmental.py` | C | commit không rollback | Sửa |
| `api/v1/sync.py`, `users.py`, `audit_logs.py` | S | — | — |
| `main.py` | C | router chết; comment lịch sử | Sửa |

### Backend — services / pipeline / models

| File | TT | Hành động |
|---|---|---|
| `services/disease_case_service.py` | C | N6 |
| `services/sync_service.py` | C | rollback bước 3 |
| `services/inventory_service.py` | C | batch update; gỡ `_trigger_alert_check` |
| `services/actual_case_service.py` | C | Viết lại (N5) |
| `services/hierarchical_forecast_service.py` | C | Gỡ 4 method; log lỗi SQL; horizon |
| `services/group_ensemble_service.py` | S | Bottom-up theo tỉnh, đã cắt tháng dở theo mốc chung — giữ |
| `services/config_service.py` | C | Che mật khẩu |
| `services/{supply_requirement,medical_supply,notification}_service.py` | X | Archive |
| `services/{audit_log,environmental,openmeteo_client,sync_config,user}_service.py` | S | — |
| `data_pipeline/scheduler.py` | X | Archive |
| `ai_engine/*` | X | Archive |
| `models/*` | S | Giữ nguyên để `create_all` không vỡ |
| `schemas/base.py` | C | Bỏ `storage_capacity` |
| `scripts/` | C | 14 còn dùng; 22 archive; `procurement_plans` gỡ khỏi 2 script |
| `tests/` | C | Archive 7 file cũ; thêm `test_dss_core.py` (21), `test_dss_api_integration.py` (9); sửa 2 test auth |

### SQL Server

| File | TT | Hành động |
|---|---|---|
| `usp_MedForecast_DayKhoCungUng` | C | Bản 2 `G2_01`: chỉ `#Meta` + `#Lo` → `MF_TonKho_Lo`; bất biến tổng tồn chuyển từ PRINT sang THROW; cắt `#Nhap/#LeadTS/#Pct/#ChuKy/#ThuocTinh`, `MF_LichSuNhap`, `MF_VatTu_ThuocTinh` |
| `usp_MedForecast_DayTieuHaoToanVien` | C | Bản 2 `G2_03`: gỡ khối DECLARE comment; `@GomVTYT = 1` giữ (view local lọc) |
| `usp_MedForecast_DayDuLieu` | S | `@GomVTYT = 0` khớp phương án A; bất biến số ca; không đụng |
| STA `MEDFORECAST_DW` | C | `G2_02`: drop `MF_VatTu_ThuocTinh`, `MF_LichSuNhap`, 2 view |
| `G1_03`, `G1_04` | C | Đồng bộ với `views.py` |

### Frontend

| File | TT | Hành động |
|---|---|---|
| `pages/Dashboard.tsx` | C | "%" trống; `as never` |
| `pages/Alerts.tsx`, `components/dashboard/AlertsTable.tsx` | C | "đang tính" → "chưa có dự báo" |
| `pages/Reports.tsx`, `hooks/useReports.ts`, `services/reportsService.ts`, `types/reports.ts` | C | Bỏ consumption/turnover; `enabled`; `ReportType` đúng backend |
| `pages/DiseaseCaseDetail.tsx` | C | N8 |
| `pages/Weather.tsx` | C | console.log/error → state lỗi hiển thị |
| `pages/Forecasting.tsx`, `services/forecastAnalysisService.ts` | C | accuracy null; 4 type chết |
| `components/dashboard/TrendChart.tsx`, `types/dashboardV2.ts` | C | N9 |
| `components/admin/{DssParamsSection,EmpiricalNormsSection,ConfigurationsSection,RolesPermissionsSection}.tsx` | C | Như mục 2 |
| `types/inventory.ts`, `services/inventoryService.ts`, `hooks/useInventory.ts` | C | Viết lại theo backend |
| `services/api.ts` | C | N11 |
| `App.tsx`, `utils/constants.ts` | C | Comment/route chết |
| 9 component/type + 2 hook/service + 8 test | X | Archive |
| `pages/{Login,Epidemiology,Inventory,Settings}.tsx`, `components/{forecasting,layout,common}/*` còn lại | S | — |

## 4b. Rà soát phạm vi VTYT — vòng 2 (13/09, chiều muộn)

Câu hỏi *"chỉ nên dự báo trên thuốc, vì thuốc đi theo chẩn đoán còn vật tư đi theo toàn viện"* được kiểm chứng bằng số liệu và **xác nhận đúng**:

| | Thuốc | VTYT |
|---|---|---|
| Tỷ trọng hô hấp trung bình | 4,39 % | 25,71 % |

Con số 25,71 % là **giả tạo**: VTYT (găng tay, bơm kim tiêm, dây truyền) tiêu thụ theo *lượt khám*, không theo chẩn đoán, nên tỷ trọng đó chỉ phản ánh tỷ lệ lượt hô hấp trên tổng lượt. Hệ quả nếu bật VTYT: **155 mã VTYT vượt ngưỡng 25 %** và lọt vào `v_supply_focus` — tập trọng tâm 242 → 397, gần 40 % là vật tư mà Ŷ_g không lái được, phá chính định nghĩa "tập mà mô hình dịch tễ lái được nhu cầu".

Ba việc phát sinh từ vòng rà soát này:

1. **Rút lại G2_03 `@GomVTYT = 0`.** Đặt 0 sẽ xoá 5.629/5.845 dòng VTYT trong `fact_usage_total` mà **không đổi một ly kết quả DOI** (3 view đã lọc `is_vtyt = 0`), đồng thời mất bằng chứng đo đạc cho quyết định loại VTYT. Giữ `@GomVTYT = 1`, để view làm việc lọc.
2. **Không đổi 91 mã Xám thành Đỏ.** Ban đầu tưởng `EFFT2` (Cefixim, tiêu hao 34.360 đơn vị) tồn 0 là "hết hàng bị giấu dưới nhãn Xám". Đo kỹ: **79/91 mã có mã khác cùng hoạt chất đang còn tồn** (Natri hydrocarbonat có 18 mã anh em còn hàng), **54/91 đã ngừng xuất** 3 kỳ gần nhất. Gốc rễ là danh mục HIS tách **595 hoạt chất thành nhiều mã** theo lô thầu/nguồn kinh phí (`Acid amin*` 74 mã, `Natri clorid` 65, `Metformin` 62). Đổi Xám → Đỏ sẽ đẻ ra 91 cảnh báo giả.
3. **Siết tập trọng tâm và gỡ nhánh VTYT** (đã làm):
   - `v_supply_focus` phải nằm trong `v_supply_active` → 304 → **242 mã**, Xám 91 → **37** (30 % → 15 % tập theo dõi). Test khoá: `test_focus_loai_ma_da_ngung_dung`.
   - Gỡ nhánh VTYT khỏi Tầng 2: `dss_demand.empirical_norms` (`usage_vtyt`, `usage_vtyt_ngt`, `vtyt_codes`, `n_vtyt_codes`, mẫu số gộp NT*), `norms_payload` (`is_vtyt`, `ca_noi_tru`, `n_vtyt_codes`), `types/dss.ts`, `EmpiricalNormsSection.tsx` (dòng "0 mã VTYT dùng mẫu số gộp nội trú" và nhãn VTYT trên từng dòng). `fact_usage_by_care_level` có 0 dòng `is_vtyt = 1` nên toàn bộ nhánh này là mã chết vĩnh viễn với phương án A; cột `is_vtyt` giữ lại trong bảng fact như dữ liệu nguồn.

**Số sau vòng 2** (snapshot tồn lô 2026-09-11): tập trọng tâm **242 mã** — Đỏ 40 · Vàng 27 · Xanh 138 · Xám 37; `v_supply_active` 1.068; dự báo 2026-09 **393 ca**; Norm hiệu dụng EF5T (J00-J06) **1,01/ca**. pytest 125 passed. Số CHỐT sau khi chạy `G2_01` xem §4d.

## 4c. Phân loại danh mục — G2_04 (13/09, đã triển khai PROD)

Nhánh "Dịch truyền" trong `#DrugMeta` có vế `pld.TENPHANLOAIDUOC LIKE N'%dịch truyền%'` khớp một phân loại rất rộng của `TM_PHANLOAIDUOC` nên nuốt **3.001/5.051 mã**, trong đó 665 mã tim mạch, 441 mã tiêu hoá, 232 mã nội tiết. Cột này nuôi bộ lọc "Danh mục" và biểu đồ "DOI theo danh mục".

Kiểm chứng bằng cách trừ ngược từ `medical_supplies` (`group_name` = `nd.TENNHOMDUOC`, `ten_hoat_chat` = `D.TENHOATCHAT`): 138 mã do vế hoạt chất, **0 mã** do vế `TENNHOMDUOC`, **2.863 mã** chỉ có thể do `TENPHANLOAIDUOC`. Bản vá (`G2_04`) bỏ hẳn vế đó, thêm nhóm 26 DMT BHYT, và siết natri clorid/glucose theo ĐVT Chai/Túi/Lọ.

Kết quả thật sau `EXEC usp_MedForecast_DayDuLieu` + Đồng bộ HIS (cần sửa N12 trước mới vào được app):

| | Trước | Sau |
|---|---|---|
| Toàn danh mục — Dịch truyền | 3.001 | **260** |
| Toàn danh mục — Khác | 1.108 | **3.849** |
| Tập trọng tâm — Dịch truyền | 119 | **40** |
| Tập trọng tâm — Khác | 42 | **121** |

Biểu đồ DOI theo danh mục giờ nói đúng điều cần nói: **Kháng sinh** có DOI trung vị thấp nhất (41,3 ngày, 13 mã Đỏ trên 52) — hợp lý với bài toán hô hấp; trước đó "Dịch truyền" 119 mã đứng đầu bảng và che mất tín hiệu này. Cảnh báo **không đổi** (40/27/138/37) vì `category` chỉ là nhãn hiển thị.

Ghi chú mẫu số: khối C đếm **6.693** mã `TM_DUOC` loại 'T' trên PROD, còn danh mục app chỉ **5.051** (`MF_TonKho` chỉ chứa mã có dòng trong `TT_DUOC_TONKHO`). Vì thế "Dịch truyền 379" bên PROD tương ứng **260** bên app — mọi tỷ lệ phần trăm phải nói rõ mẫu số nào.

Bài học kỹ thuật: mô phỏng CASE trên SQLite cho **130** mã trong khi SQL Server cho **379** — vì `lower()` của SQLite chỉ hạ chữ ASCII, `'26. DUNG DỊCH ĐIỀU CHỈNH NƯỚC'` thành `'26. dung dỊch ĐiỀu chỈnh nƯỚc'` nên `LIKE '%dung dịch điều chỉnh nước%'` không khớp, bỏ sót trọn 238 mã nhóm 26. **Không dùng SQLite để mô phỏng LIKE tiếng Việt của SQL Server.**

## 4d. Chốt số — sau `G2_01` (13/09, 17:03)

`usp_MedForecast_DayKhoCungUng` bản 2 đã chạy trên PROD; `fact_inventory_lot` có ảnh chụp mới:

| | 2026-09-11 | **2026-09-13 (chốt)** |
|---|---|---|
| Dòng tồn theo lô | 2.674 | **2.644** |
| Mã có tồn | 1.062 | **1.063** |
| Tổng số lượng | 1.409.705 | **1.346.791** |
| Đỏ / Vàng / Xanh / Xám | 40 / 27 / 138 / 37 | **39 / 28 / 137 / 38** |

Dịch chuyển 1 mã mỗi nhãn là biến động tồn kho hai ngày, không phải lỗi logic: tổng tồn giảm 62.914 đơn vị (−4,5 %) trong khi mẫu số `d_daily` giữ nguyên (tiêu hao vẫn 12 kỳ đã chốt tới 2026-08), nên vài mã quanh ngưỡng 18/36 ngày đổi phía.

Các hằng số khác **không đổi**: tập trọng tâm 242, `v_supply_active` 1.068, dự báo 2026-09 = 393 ca, Norm EF5T = 1,01/ca, ngưỡng 18/36 ngày, horizon 30 ngày.

FEFO áp dụng cho **204/242** mã (có lô kèm hạn dùng); 38 mã Xám đều do `no_stock_data` — không có dòng tồn kho, không phải do thiếu hạn dùng.

DOI trung vị theo danh mục (tập trọng tâm):

| Danh mục | n | DOI trung vị | Đỏ | Vàng | Xanh | Xám |
|---|---:|---:|---:|---:|---:|---:|
| Khác | 121 | 59,9 | 16 | 15 | 73 | 17 |
| Kháng sinh | 52 | **40,3** | **15** | 5 | 22 | 10 |
| Dịch truyền | 40 | 59,2 | 3 | 6 | 25 | 6 |
| Thuốc long đờm | 10 | 42,9 | 3 | 0 | 5 | 2 |
| Thuốc giãn phế quản | 9 | 50,3 | 1 | 1 | 6 | 1 |
| Corticoid | 6 | 131,5 | 0 | 1 | 3 | 2 |
| Thuốc hạ sốt giảm đau | 2 | 40,8 | 1 | 0 | 1 | 0 |
| Kháng histamin | 2 | 66,1 | 0 | 0 | 2 | 0 |

Kháng sinh giữ vị trí nhóm căng nhất (15/52 mã Đỏ, DOI trung vị 40,3 ngày) — đúng kỳ vọng của bài toán hô hấp và là luận điểm dùng được cho phần Kết quả của báo cáo.

Top mã Đỏ cần nêu trong .docx: `BLOT1` Ciprofloxacin (DOI 0,0), `KCBT5` Kali clorid (0,3), `S2CT10` N-acetylcystein (0,4), `VI2T9` Ampicilin + Sulbactam (0,8), `NACT9` Natri clorid (4,0).

## 5. Còn lại — không làm trong đợt này (ghi để không quên)

1. ~~Trang Vật tư phân "Nguy cấp/Dưới ngưỡng" theo `safety_stock`~~ — **đã làm 13/09 (17:30)**: trang đổi tên **Quản lý thuốc**, bảng ghép `/inventory` với `/dashboard/v2/alerts?focus=false` theo `supply_code` (Tồn · Tồn hữu dụng · Tiêu hao/ngày · DOI · Nhãn), ẩn mặc định 3.575 mã không tiêu hao 12 kỳ; báo cáo "Tồn kho" (`_build_inventory_data`) đổi sang cùng chuỗi DOI (284/222/496/474 trên 1.476 mã); `InventoryStatusBadge` → `_archive/frontend_chet/`; mọi nhãn UI/API "vật tư" → "thuốc"; `/v2/alerts` limit ≤ 2000, `counts.stock_source` mới. pytest 127 · vitest 144 · typecheck/build OK.
2. `dss_dashboard._ensure_cache/_write_cache/_log_run/fill_actuals` là ghi có chủ đích trong GET (cache dự báo + sổ theo dõi); chấp nhận, đã ghi rõ trong docstring `dashboard.py`.
3. `group_ensemble_service._chuoi_thang` group-by năm/tháng làm tháng không có dòng biến mất khỏi chuỗi (nén trục thời gian) — chỉ ảnh hưởng bảng tỉnh tham khảo; nên reindex `period_range` khi có thời gian.
4. `/forecast/analyze` chạy ensemble cho mọi tỉnh kể cả `save=false` — chậm; cân nhắc tính lười.
5. `lookback_months` ở Quản trị chưa truyền vào `SqlServerConnector` (chỉ đọc env).
6. ESLint chưa có `eslint.config.js` (v9) → `npm run lint` không chạy được; typecheck + vitest thay thế.
7. Số chính thức CHỐT (**39/28/137/38**, tập trọng tâm **242**, active 1.068, Norm EF5T **1,01**, dự báo 393 ca) cần cập nhật vào báo cáo .docx và chụp lại ảnh Tổng quan/Cảnh báo.
8. ~~`G2_04`~~ — đã triển khai PROD và đồng bộ xong (xem §4c).
9. ~~`G2_01`~~ — đã chạy trên PROD, snapshot tồn lô về `2026-09-13` (xem §4d). `G2_02` (dọn `MF_VatTu_ThuocTinh`/`MF_LichSuNhap` bên STA) vẫn **chưa chạy** — thuần dọn dẹp, không ảnh hưởng số liệu.

## 6. Checklist trước khi nộp

Chạy từ thư mục repo, trên Windows (backend cần `venv` đã cài `requirements.txt`).

```powershell
# 0. Trạng thái repo: 156 file đã staged bởi đợt kiểm toán
git status --short | Measure-Object -Line
git diff --cached --stat | Select-Object -Last 1

# 1. Backend — kiểm thử + import sạch
cd backend
.\venv\Scripts\activate
python -m pyflakes app                       # 0 dòng (trừ __init__ re-export)
python -m pytest tests -q                    # kỳ vọng: 125 passed
python -c "from app.main import app; print('app OK')"

# 2. Lược đồ + view trên DB thật (idempotent), rồi kiểm số cảnh báo mới
python -m app.data_pipeline.views            # 4 view: "đã tạo"
python scripts/verify_g1.py                  # mẫu số, tập trọng tâm, DOI
python scripts/verify_his_pipeline.py        # pipeline ca bệnh, is_complete
python scripts/kiem_tra_so_ca_nhom.py        # 23.653 lượt / 92 kỳ chốt

# 3. Frontend
cd ..\frontend
npm run typecheck                            # 0 lỗi (kể cả __tests__)
npm test                                     # 19 file / 144 test passed
npm run build

# 4. SQL Server (SSMS) — theo thứ tự
#    PROD: sql_his/phase0/G2_01_PROD_store_khocungung_v2.sql
#          sql_his/phase0/G2_03_PROD_store_tieuhao_toanvien_v2.sql   (@GomVTYT giữ = 1)
#          sql_his/phase0/G2_04_PROD_sua_danh_muc_dich_truyen.sql    (khối A đo trước)
#          EXEC dbo.usp_MedForecast_DayKhoCungUng @ChiXem = 1;  -- xem trước
#          EXEC dbo.usp_MedForecast_DayKhoCungUng;              -- đẩy
#    STA : sql_his/phase0/G2_02_STA_don_tan_du_mua_sam.sql

# 5. Demo: khởi động và soi log — không được có Traceback
cd ..\backend
uvicorn app.main:app --port 8000
#    log kỳ vọng: "Lược đồ ngoài ORM: 8/8 mục sẵn sàng"
cd ..\frontend
npm run dev
#    Quản trị → Kết nối HIS → Đồng bộ; Phân tích → Toàn quốc → Ghi nhận dự báo 3 nhóm;
#    Tổng quan phải hiện 39 Đỏ · 28 Vàng (tập trọng tâm 242 mã) và không còn "%" trống.

# 6. Commit (attribution theo quy ước phiên)
git commit -m "Kiem toan 13/09: loai ky do dang, cat tan du mua sam, don dead code, test loi DSS"
```
