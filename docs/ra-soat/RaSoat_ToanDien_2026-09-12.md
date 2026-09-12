# Rà soát toàn diện MedForecast AI — 12/09/2026

Phạm vi: toàn bộ mã nguồn (backend, frontend, forecasting, sql_his), tài liệu, và
**file DB thật** `backend/data/medforecast.db` (69,8 MB, 35 bảng). Mỗi phát hiện
đều có `file:dòng` hoặc truy vấn đã chạy. Mức: **Nặng** = phải sửa trước bảo vệ ·
**Vừa** = nên sửa hoặc phải ghi chú trong luận văn · **Nhẹ** = dọn khi rảnh.

## 0. Kết luận ngắn

Phần lõi khoa học **đứng vững**: không có rò rỉ dữ liệu tương lai trong đường
sản xuất, giao thức walk-forward đúng như mô tả, các con số 0,500 / 0,516 /
0,377 / 0,541 tái lập đúng từ `ketqua_backtest/*.csv`. Dữ liệu trong DB sạch về
mặt toàn vẹn: 0 trùng khoá tự nhiên, 0 bản ghi mồ côi, 0 giá trị âm ở số ca.

Rủi ro thật nằm ở ba chỗ khác: **số liệu trong tài liệu không khớp DB hiện tại**,
**hai lỗi giao diện sẽ lộ ngay khi demo trên máy sạch**, và **tài liệu hướng dẫn
chạy đã chết** (README/DEPLOY còn chỉ Docker + Postgres trong khi file đã bị
chuyển vào `_archive/`). Tất cả đều sửa được trong 1–2 ngày.

---

## 1. NẶNG — phải sửa trước khi bảo vệ

### N1. `README.md` tự mâu thuẫn về RelMAE
`README.md:33` ghi 0,659; `README.md:281` ghi 0,500 — cùng một file. Số đúng là
**0,500** (`backend/ketqua_backtest/phancap.csv`, hàng TỔNG HỢP / Top-down động).
Dòng 33 là tàn dư bản sáng 11/09 trước M12.

### N2. Con số "23.429 ca" sai ở 4 chỗ, và phải chọn rõ mức đếm
Xuất hiện tại `docs/KetQua_Backtest_ChonCauHinh.md:227,338`,
`docs/ra-soat/RaSoat_DeCuong_vs_ThucTe.md:12`,
`docs/ra-soat/DanhGia_ChuyenSangNhomICD.md:4`. Số thật, đếm trực tiếp:

| Cách đếm | Tất cả kỳ | Kỳ đã chốt |
|---|---|---|
| **Mức khối** (`mart_monthly_cases_by_block`, region=TOAN_QUOC) | 23.754 | **23.653** |
| Mức mã (`fact_disease_case`) | 23.818 | 23.713 |

Khớp đúng `dataset/v1/nhom_thang.csv` và `ma_thang.csv`. **Dùng 23.653** (mức
khối, kỳ đã chốt) — xem §4 để hiểu vì sao hai mức khác nhau và vì sao mức khối
mới là "số lượt bệnh" đúng nghĩa. Phân bố: J00-J06 11.514 · J09-J18 7.754 ·
J20-J22 4.385.

### N3. Trang Phân tích & Dự báo mặc định một mã bệnh không còn tồn tại
`frontend/src/pages/Forecasting.tsx:72` — khi `localStorage` rỗng (máy sạch,
cửa sổ ẩn danh: **đúng tình huống demo lần đầu**) state khởi tạo là
`disease: 'dengue_fever'`. Danh mục hiện chỉ còn `J00-J06`, `J09-J18`, `J20-J22`
(`backend/app/utils/icd_groups.py`), nên `<select>` hiển thị nhãn hợp lệ nhưng
state thật vẫn là `dengue_fever`. Bấm "Phân tích" ngay lượt đầu là gửi mã không
có dữ liệu. Sửa: đổi mặc định thành `'J00-J06'`.

### N4. Nút "Thêm vật tư mới" luôn thất bại
`frontend/src/pages/Inventory.tsx:565` gửi `POST /supplies/` với
`{name, category, unit}`, nhưng `MedicalSupplyBase`
(`backend/app/schemas/base.py:116-121`) bắt buộc `supply_code`, `drug_code`,
`ten_hoat_chat`, `group_name` và **không có** trường `name` → 422. Thêm nữa
endpoint cần `get_admin_user` (`backend/app/api/v1/supplies.py:55`) nhưng nút
hiện cho mọi vai trò (`Inventory.tsx:323`) → 403 với tài khoản dược/kho.
Sửa payload đúng schema và ẩn nút nếu không phải Administrator.

### N5. `DEPLOY.md` và mục Docker của README hướng dẫn thứ không còn tồn tại
`README.md:89-164` và toàn bộ `DEPLOY.md` chỉ `docker-compose.yml` /
`docker-compose.dev.yml` + PostgreSQL; hai file đã chuyển vào `_archive/postgres/`
theo Quyết định 2 (`docs/DinhHinhLai_MedForecast_2026-09-09.md:12-17`). Người
đọc ngoài làm theo sẽ dừng ngay lệnh đầu. Sửa: viết lại theo đường SQLite thật
(`scripts/khoi_tao_moi.py` → `uvicorn app.main:app`), hoặc xoá `DEPLOY.md`.

### N6. `RaSoat_DeCuong_vs_ThucTe.md` đã lỗi thời — nói thiếu thứ đã làm
Các mục còn ❌/🟡 nhưng thực tế đã xong: panel giải thích mô hình đã đổi từ văn
mẫu sốt xuất huyết sang hô hấp (`backend/app/api/v1/forecast_analysis.py:247-289`);
định mức J18 đã có qua định mức thực nghiệm theo nhóm
(`app/services/dss_demand.py:296-334`); engine `ai_engine` cũ đã gỡ khỏi trang
Phân tích (`forecast_analysis.py:390`); Prophet đã chạy và có số
(`ketqua_backtest/doi_chung_xgb_prophet.csv`); cảnh báo đã 4 mức. Nếu hội đồng
đối chiếu tài liệu rà soát với demo sẽ nghi ngờ độ cập nhật của cả bộ tài liệu.

### N7. Cột so sánh "Top-down cố định" trong backtest có rò rỉ tương lai
`mart_icd_share_in_block` tính trên **toàn lịch sử**
(`backend/app/data_pipeline/pipeline.py:402`) rồi được lấy một lần trước vòng
walk-forward và dùng lại ở mọi bước (`app/forecasting/evaluate.py:92,173`). Tức
dự báo mã năm 2021 đã dùng tỷ trọng tính tới 2026-09.

**Đường sản xuất KHÔNG bị ảnh hưởng**: `PRODUCTION_CONFIG.method =
"top_down_dynamic"` dùng `ewma_shares(hist_g, hist_c)` chỉ từ quá khứ
(`app/forecasting/hierarchical.py:15-29`), nên 0,500 / 0,516 / 0,377 / 0,541
vẫn sạch. Nhưng các số "TD cố định" (0,659 / 0,439 / 0,542) là **lạc quan giả**.
Phải ghi chú trong `KetQua_Backtest_ChonCauHinh.md`: baseline này còn được ưu ái
bởi rò rỉ, thực tế sẽ thua top-down động nhiều hơn con số đang in.

---

## 2. VỪA — sửa nếu kịp, bắt buộc ghi chú nếu không

### V1. SARIMAX dùng thời tiết cũ hơn thiết kế một tháng
`app/forecasting/sarimax_opt.py:58-66` dịch exog bằng `shift(weather_lag)`, nên
`exog[-1]` ứng với thời tiết tháng *n-1-lag*; `predict()` (dòng 99-104) tái dùng
chính hàng đó cho bước *n* → **trễ hiệu dụng 2 tháng** thay vì 1.
`HarmonicPoissonForecaster.predict` (`models.py:298-305`) tính đúng `i-L`. Đây
**không** phải rò rỉ (dùng dữ liệu cũ là phía an toàn) nhưng là bất nhất giữa
fit và predict, trên đúng thành viên mạnh nhất (RelMAE 0,518/0,360/0,560). Nếu
không sửa thì đừng khẳng định "SARIMAX dùng thời tiết trễ 1 tháng".

### V2. Luồng gia hạn token không bao giờ chạy
`frontend/src/services/api.ts:55-64` gửi **access token đã hết hạn** lên
`/auth/refresh` chứ không gửi `refresh_token` đã lưu (biến `REFRESH_TOKEN_KEY`
chỉ được ghi và xoá, không gửi đi đâu). Vì token đã hết hạn nên refresh chắc
chắn 401 → người dùng bị đăng xuất sau đúng `ACCESS_TOKEN_EXPIRE_MINUTES`.
Ngoài ra `verify_token` (`app/core/security.py:43-48`) không đọc claim `type`
mà `login` gắn vào refresh token (`app/api/v1/auth.py:61`), nên refresh token
(hạn 7 ngày) dùng được thẳng làm Bearer cho mọi endpoint.

### V3. `disease_cases` chứa hai grain khác nhau, và FK không được enforce
`app/services/sync_service.py:254-255` xoá sạch `disease_cases` rồi nạp lại từ
`fact_disease_case` mỗi lần Đồng bộ; nhưng `app/api/v1/disease_cases.py:471-592`
cũng ghi **ca nhập tay** vào chính bảng đó, có con là `case_supply_usage`
(FK `ON DELETE CASCADE`, `app/models/case_supply_usage.py:15-23`). SQLite mặc
định không bật `PRAGMA foreign_keys` và repo không bật ở đâu (`app/database.py`,
`app/data_pipeline/db.py` đều không) → cascade không chạy, và vì SQLite tái dùng
rowid sau khi xoá sạch, `case_id` cũ có thể trúng một dòng mới mang dữ liệu bệnh
khác — **sai âm thầm**.
Hiện **chưa xảy ra**: đã kiểm tra, cả 1676 dòng `disease_cases` đều
`data_source='HIS-STA'`, 0 `case_supply_usage` mồ côi. Tối thiểu: bật
`PRAGMA foreign_keys=ON` và không cho nhập tay vào bảng này, hoặc ghi vào phần
hạn chế.

### V4. `Dashboard.tsx:357` hiện "undefined%"
`q.improvement_vs_naive_pct?.toFixed(1)` — khi backend trả `null` mà
`available === true`, giao diện in chữ `undefined%`. Bọc `?? '—'`.

### V5. `predict.py` chia mã bằng phương pháp khác sản xuất
`app/forecasting/predict.py:44-45` dùng `split_topdown(point, shares_fixed)`
(TD cố định) trong khi sản xuất dùng EWMA động. Không service nào gọi nên không
ảnh hưởng màn hình, nhưng nếu hội đồng chạy `train.py`/`predict.py` để tái lập
sẽ ra bảng mức mã khác tài liệu. Ghi chú rõ trong `dataset/v1/README.md`.

### V6. Lỗi SQL bị nuốt, không log
`app/services/hierarchical_forecast_service.py:45-51` và
`app/services/supply_planning_service.py:29-34` bắt `SQLAlchemyError` rồi trả
`[]` không ghi log. Khi SQL thật sự sai (lệch lược đồ sau nâng cấp), luồng báo
"Chưa có dữ liệu MART — hãy chạy pipeline" (dòng 113) → đi sửa nhầm hướng. Thêm
`logger.exception`.

### V7. `DATASHEET.md` còn chỗ trống và thiếu căn cứ pháp lý
`dataset/v1/DATASHEET.md:84` còn nguyên `[Họ tên tác giả]`. Mục 5 (dòng 46-58)
chỉ nói chung "ghi rõ căn cứ cho phép khi nộp" — cần ghi căn cứ cụ thể vào chính
datasheet mà hội đồng sẽ đọc.

### V8. `manifest.json` mô tả giao thức chia không đúng từng khối
`n_periods_closed_per_block: 91` và `test_steps_per_block: 67` là giá trị `min()`
của 3 khối. Thực tế: J00-J06 và J09-J18 có 92 kỳ đã chốt / 68 bước,
J20-J22 có 91 / 67 (khớp `ketqua_backtest/nhom.csv`). `DATASHEET.md:17` viết
đúng hơn ("91–92 tháng/khối"). Sửa manifest hoặc đổi tên trường.

### V9. AQI/PM2.5 **thực sự đã có dữ liệu** — lý do loại phải viết lại
Tài liệu nói "AQI chưa có dữ liệu". Thực tế `environmental_data` có **144 tháng
có AQI và PM2.5**, nguồn `open-meteo`, khoảng 2022-08 → 2026-09, AQI 52–154,
PM2.5 10,65–71,43. Nhưng:
- Dữ liệu là của **3 thành phố** (Hà Nội 67, TP.HCM 124, Đà Nẵng 121 dòng), còn
  bảng mô hình thật `mart_monthly_weather` chỉ có một vùng `TOAN_QUOC` với
  **3 cột** `temp, humidity, rainfall` — AQI chưa bao giờ vào đường dữ liệu của
  mô hình (`app/forecasting/models.py:213`: `WCOLS = ["temp","humidity","rainfall"]`).
- Chỉ ~50 tháng đã chốt có AQI, so với 92 tháng cho 3 biến kia — **ngắn hơn 2
  chu kỳ mùa**, không đủ cho SARIMAX mùa 12 hay Harmonic-Poisson.

Đây mới là lý do đúng để ghi vào luận văn, thay cho "chưa có dữ liệu". Nếu muốn
khép hẳn cam kết đề cương: thêm `aqi` vào `mart_monthly_weather` + `WCOLS`, chạy
`combine_effect` trên cửa sổ 2022-08→nay và báo số — kể cả khi kết quả là "không
cải thiện", đó vẫn là câu trả lời bằng số đo.

---

## 3. NHẸ — dọn khi rảnh

- `app/api/v1/forecast_analysis.py` (~dòng 950) vẫn gọi
  `AlertModule.check_and_generate_alerts()` sau mỗi lần lưu phân tích, ghi vào
  bảng `alerts` mà **không màn hình nào đọc** — hệ cảnh báo cũ song song với
  Tầng 3. Chuyển router `alerts.py` + module này vào `_archive/`.
- 6 endpoint cũ trong `app/api/v1/dashboard.py` (`/overview`, `/risk-status`,
  `/critical-alerts`, `/summary`, `/case-trend`, `/care-level`) không còn ai gọi.
- `frontend/src/types/inventory.ts` đặt tên trường sai hoàn toàn so với backend
  (`quantity_on_hand` vs `current_stock`…); không crash vì `Inventory.tsx:95`
  cast `any`, nhưng đánh lừa TypeScript.
- Hằng số chết: `ROUTES.SUPPLY_NORMS`, `ROUTES.SUPPLY_PLAN`
  (`frontend/src/utils/constants.ts:90-91`), `DEFAULT_CONVERSION_RATIOS`
  (`backend/app/ai_engine/config.py:171`).
- `fact_supply_usage` (~86k dòng) là luồng Phase-0 cũ, không service DSS nào
  đọc; `scripts/verify_g1.py:119-138` tự xác nhận nó lệch `fact_usage_total`.
  Nên nói rõ bảng nào là nguồn thật nếu bị hỏi.
- **Tồn kho âm**: mã `BZ5T2` (Metoprolol, nhóm tim mạch) = **-30** ở cả 8
  snapshot. Tầng 3 xử lý đúng (`dss_alerts.py:304` → Xám kèm lý do), không làm
  sai cảnh báo, nhưng nên báo phòng KHTH vì đây là lỗi dữ liệu phía HIS.

---

## 4. Rà soát dữ liệu trong DB — kết quả

Chạy trực tiếp trên `backend/data/medforecast.db` (11/09/2026, 35 bảng).

**Sạch:**
- Trùng khoá tự nhiên: **0** trên `mart_monthly_cases_by_block` (kỳ×khối×vùng),
  `fact_disease_case` (kỳ×mã×khối×vùng), `mart_monthly_weather` (kỳ×vùng),
  `fact_usage_total` (kỳ×mã vật tư), `fact_inventory_snapshot` (ngày×mã),
  `medical_supplies` (mã).
- Bản ghi mồ côi: **0** ở `inventory→medical_supplies`,
  `case_supply_usage→disease_cases`, `alerts→medical_supplies`,
  `disease_supply_norms→medical_supplies`.
- Số ca âm 0 · tiêu hao âm 0 · thời tiết NULL 0 · `mart_inventory` NULL 0 ·
  lô không hạn dùng 0.
- Tỷ trọng mã trong khối tổng đúng **1,000000** cho cả 3 khối.
- `is_complete = 0` chỉ ở kỳ 2026-09 — đúng, kỳ đang mở.
- 93 kỳ liên tục 2019-01 → 2026-09, không thiếu tháng.
- Biên thời tiết hợp lý: nhiệt 25,6–30,9 °C; ẩm 59,9–89,7 %; mưa 1,4–470,9 mm.
- `disease_cases` khớp tuyệt đối `fact_disease_case` (1676 dòng / 23.818 ca).
- Đồng bộ gần nhất 11/09 13:11, `status='ok'`, 7.212 dòng, `last_period='2026-09'`.

**Một khác biệt thoạt nhìn như lỗi, thực ra ĐÚNG THEO THIẾT KẾ — và là điểm
mạnh nên chủ động nêu khi bảo vệ:**

Tổng số ca mức khối (23.754) **nhỏ hơn** tổng mức mã (23.818); 13 dòng lệch, tất
cả ở 2026-06 → 2026-09. Nguyên nhân nằm trong thủ tục T-SQL: `Cases =
COUNT(DISTINCT TIEPNHAN_ID)` được đếm **riêng** ở mức mã
(`sql_his/phase0/G1_00_PROD_store_cabenh_v3.sql:344`) và ở mức khối (dòng ~510).
Một lượt có hai mã ICD khác nhau **trong cùng một khối** thì đếm 1 ở mức khối
nhưng 2 ở mức mã. Lệch chỉ xuất hiện từ 2026-06 vì chẩn đoán phụ mới bắt đầu
được ghi từ đó.

Hệ quả cần nói rõ trong luận văn:
1. "Số lượt bệnh" đúng nghĩa là con số **mức khối** (23.653 kỳ đã chốt).
2. Đây là lý do **kiến trúc top-down là đúng** và cộng dồn bottom-up từ mã lên
   khối sẽ **vượt số thật** — một lập luận kiến trúc, không phải vá tạm.

**Một rủi ro thiết kế cần biết:** `mart_monthly_cases_by_block` chứa **cả** dòng
tổng hợp `region='TOAN_QUOC'` **lẫn** dòng từng tỉnh trong cùng một bảng (tổng
mọi dòng = 47.528 ≈ 2× số thật). Mọi truy vấn của hệ đều lọc
`region='TOAN_QUOC'` — đã kiểm `hierarchical_forecast_service.py:57,63,102` và
`app/forecasting/data_access.py:19,39,88`, **không chỗ nào thiếu lọc**. Nhưng bất
kỳ câu truy vấn mới nào quên điều kiện đó sẽ đếm gấp đôi. Ngoài ra `dim_region`
(11 tỉnh) **không chứa** `'TOAN_QUOC'`, nên vùng tổng hợp không phải giá trị hợp
lệ của bảng chiều.

---

## 5. Đã kiểm tra và ĐÚNG — dùng được khi phản biện

- **Không có rò rỉ tương lai trong đường sản xuất.** Trọng số nghịch đảo MAE và
  hệ số lệch chỉ dùng sai số quá khứ (`combine.py`; `update()` được gọi **sau**
  `combine()` tại `group_forecast.py:73-95`). Chuẩn hoá thời tiết tính trên
  `hist = group_w.iloc[:t]` vì ensemble được fit lại ở **mỗi** bước
  (`group_forecast.py:78`). Tỷ trọng sản xuất dùng EWMA chỉ-quá-khứ.
- **RelMAE** chia cho MAE của seasonal-naive **ngoài mẫu, cùng bước**
  (`evaluate.py:43-59`) — không phải MASE in-sample; tài liệu đã tự sửa tên.
- **Độ phủ khoảng** tính tuần tự, khoảng của bước *t* dựng từ phần dư **trước** *t*
  (`evaluate.py:141-152`).
- **Backtest khớp sản xuất**: `PRODUCTION_CONFIG` là nguồn tham số duy nhất;
  `cau_hinh.json` khớp từng trường; cả `hierarchical_forecast_service` và
  `group_ensemble_service` đều đi qua `forecast_group_next`.
- **Số công bố tái lập được**: 0,500 / 0,516 / 0,377 / 0,541 khớp tuyệt đối
  `nhom.csv`, `phancap.csv`, `cau_hinh.json`.
- **Công thức Tầng 2/3**: DOI = `s_usable / d_daily`, FEFO, quy đổi theo phân cấp
  NGT/NT1/NT2/NT3/NT0 (NT0 không mặc định "nhẹ"), và **mọi** phép chia đều chặn
  mẫu số ≤ 0 trước khi tính (`dss_demand.py`, `dss_alerts.py:135,302-309`).
- **Kỳ đang mở** tách bạch khỏi kỳ đã chốt trong `period_service.py` — không còn
  lấy `max(recorded_at)` như bản cũ.
- **Phân quyền**: đã rà toàn bộ POST/PUT/DELETE trong `app/api/v1/` — **không có
  endpoint ghi nào thiếu** `Depends(...)`; CORS theo danh sách origin cụ thể;
  `config.py:30-38` chặn khởi động production nếu còn `SECRET_KEY` mặc định.
- **SQL injection**: mọi f-string vào `text()` chỉ nội suy tên bảng/cột do chính
  module quyết định (whitelist nội bộ); giá trị luôn qua bind param. Không tìm
  thấy chỗ nào nội suy giá trị từ request.
- **Khoá ở tầng kho**: các bảng fact/staging đều có `UniqueConstraint` hoặc PK
  tổng hợp đúng bản chất (`data_pipeline/models.py:107,124,135`,
  `dss_loader.py:162-213`) — phần thiết kế warehouse làm tốt hơn phần nghiệp vụ.
- **Index**: PK tổng hợp bắt đầu bằng `period`/`snapshot_date` khớp đúng cột lọc
  của `dss_demand.py:239,251`, cộng `ix_fucl_supply`, `ix_fut_supply`,
  `ix_fil_supply`. Không cần thêm index.
- **Ca biên**: `Ensemble.PLAUSIBLE_FACTOR = 5.0` chặn dự báo phi lý; SARIMAX/ETS
  có `MIN_OBS` 26/24 và ném lỗi rõ ràng thay vì trả số bịa; mọi `predict()` đều
  `max(0.0, ...)`.
- **`scripts/nang_cap_db.py`** là cách di trú đủ an toàn cho phạm vi đồ án: so
  cả hai `declarative_base` với SQLite thật, tự sao lưu trước khi sửa, và tự báo
  những ca không làm an toàn được (xoá cột, đổi kiểu, `NOT NULL` không DEFAULT).
  `alembic/` chỉ là bộ khung mồ côi — nên nói thẳng điều đó nếu bị hỏi.

---

## 6. Thứ tự đề nghị cho thời gian còn lại

**Ngày 1 — sửa mã (nửa ngày):** N3, N4, V4 (3 chỗ nhỏ trong frontend), V6 (thêm
log), bật `PRAGMA foreign_keys=ON` cho V3.

**Ngày 1–2 — thống nhất số liệu và tài liệu:** N1, N2 (sửa 4 chỗ "23.429" →
23.653 kèm câu giải thích mức đếm), V8, N7 (thêm ghi chú rò rỉ vào bảng so
sánh), V5, V7.

**Ngày 2–3 — tài liệu chạy:** N5 (viết lại README mục Docker + `DEPLOY.md`),
N6 (cập nhật `RaSoat_DeCuong_vs_ThucTe.md` theo trạng thái thật).

**Tuần 5 — chọn một trong hai cho AQI (V9):** hoặc thêm `aqi` vào
`mart_monthly_weather` + `WCOLS` rồi chạy `combine_effect` trên cửa sổ 2022-08→
nay và báo số, hoặc viết lý do loại bằng số (50 tháng < 2 chu kỳ mùa; dữ liệu 3
thành phố không phải trạm đại diện). Phương án 1 khép hẳn cam kết đề cương và
tốn khoảng nửa ngày.

**Tuần 5–6 — nếu còn thời gian:** V1 (sửa exog SARIMAX rồi **chạy lại backtest**
— nhớ là đổi số trong mọi tài liệu), V2, và dọn nhóm Nhẹ vào `_archive/`.

**Việc ngoài mã nguồn, làm ngay vì phụ thuộc người khác:** gửi phòng KHTH đối
chiếu số liệu (`RaSoat_DeCuong_vs_ThucTe.md:20,90` — không có bằng chứng đã gửi);
xin căn cứ cho phép dùng dữ liệu để điền vào DATASHEET; báo KHTH mã `BZ5T2` tồn âm.

**Còn thiếu để viết chương 3–4:** ảnh chụp màn hình các trang đã chốt; sơ đồ
kiến trúc dạng hình (hiện chỉ có ASCII trong
`DinhHinhLai_MedForecast_2026-09-09.md:25-59`); một bảng kết quả walk-forward
"chốt cuối cùng" gộp cả đối chứng XGBoost/Prophet (hiện rải ở nhiều mục).

---

## 7. Năm câu phản biện khả năng cao, kèm câu trả lời

1. **"Tổng số ca là bao nhiêu — tài liệu ghi 23.429?"** → 23.653 lượt ở kỳ đã
   chốt, đếm ở mức khối; con số cũ là của bản dữ liệu trước 11/09. Mức mã ra
   23.713 vì một lượt có hai mã cùng khối được đếm hai lần ở mức mã.
2. **"Tỷ trọng cố định có dùng dữ liệu tương lai không?"** → Có, ở **cột so sánh**
   (`pipeline.py:402` + `evaluate.py:92,173`) — nên baseline đó còn được ưu ái.
   Phương pháp **được chọn** là top-down động với EWMA chỉ-quá-khứ, sạch.
3. **"Sao gọi RelMAE chứ không phải MASE?"** → MASE chuẩn hoá theo naive
   in-sample (Hyndman–Koehler 2006); ở đây mẫu số là seasonal-naive **ngoài
   mẫu** trên cùng các bước walk-forward — công bằng hơn nhưng khác định nghĩa
   gốc, nên đổi tên cho trung thực.
4. **"Thời tiết trễ có thật có ở thời điểm dự báo?"** → Harmonic-Poisson: có,
   tính `i-L` tại đúng thời điểm dự báo. SARIMAX: có lệch một bước khiến nó dùng
   thời tiết **cũ hơn** dự kiến một tháng — phía an toàn, không rò rỉ, đã ghi
   nhận là điểm cần sửa.
5. **"Vì sao không dùng LSTM / deep learning?"** → 92 tháng ≈ 7 chu kỳ mùa
   (`DATASHEET.md:69`); và đã đo XGBoost (+1 %) với Prophet (tệ hơn seasonal
   naive) trên cùng giao thức — `ketqua_backtest/doi_chung_xgb_prophet.csv`. Kết
   luận bằng số đo, không bằng lập luận.
