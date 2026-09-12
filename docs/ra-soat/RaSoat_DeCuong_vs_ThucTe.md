# Rà soát đề cương ↔ thực tế

Lập 09/08/2026 · **trạng thái cập nhật 12/09/2026** (tài liệu sống — các ô dưới
đây phản ánh mã nguồn hiện tại, không phải trạng thái hồi tháng 8).

Đối chiếu từng cam kết trong `DeCuongDoAnTotNghiep_..._20260711.docx` với trạng
thái sản phẩm sau khi nối HIS thật. Ký hiệu: ✅ đạt · 🟡 đạt một phần · ❌ chưa ·
⛔ đã bỏ khỏi phạm vi có chủ đích.

> **Đổi phạm vi đã chốt 09/09/2026** (`../DinhHinhLai_MedForecast_2026-09-09.md`):
> hệ là **DSS thuần**, dừng ở trang *Cảnh báo thiếu hụt*; module mua sắm / kế
> hoạch cung ứng bỏ khỏi phạm vi bảo vệ. Những dòng ⛔ dưới đây không phải thiếu
> sót mà là quyết định thu hẹp, phải giải thích như vậy khi bảo vệ.
> Việc còn lại tính đến 12/09: `RaSoat_ToanDien_2026-09-12.md`.

---

## 1. DỮ LIỆU — 8/10 đạt, 2 việc vận hành đang treo (12/09: 9/10)

| Cam kết đề cương | Trạng thái | Bằng chứng / việc còn lại |
|---|---|---|
| Ca bệnh BV tại TP.HCM, 2019–2026, tổng hợp theo tháng × ICD × địa bàn | ✅ | 92 tháng, **23.653 lượt** đã chốt (đếm mức khối, 12/09 — xem `../KetQua_Backtest_ChonCauHinh.md` mục 0.3), đồng bộ tự động HIS→STA→app |
| Đã loại bỏ định danh | ✅ | Tổng hợp ngay trên PROD; ngưỡng ô nhỏ k=5; căn cứ Luật 91/2025 Điều 2 |
| Ba nhóm J00-J06 / J09-J18 / J20-J22 | ✅ | Đủ 20 mã; danh mục lấy từ TM_ICD.PHANNHOM |
| Môi trường: nhiệt độ, ẩm, mưa, AQI; độ trễ 1–2 tháng | 🟡 | Nhiệt/ẩm/mưa: ✅ 124 tháng trong `mart_monthly_weather`, trễ 1–2 tháng dùng thật trong Harmonic-Poisson và SARIMAX. Panel giải thích **đã viết lại** theo yếu tố hô hấp (`forecast_analysis.py:247-289`). **AQI/PM2.5 CÓ dữ liệu** — 144 dòng trong `environmental_data`, Open-Meteo, 2022-08→2026-09 (AQI 52–154) — nhưng là số của 3 thành phố và **chưa được đưa vào `mart_monthly_weather`/`WCOLS`**, nên mô hình chưa dùng. Lý do loại phải ghi bằng số: chỉ ~50 tháng đã chốt, **ngắn hơn 2 chu kỳ mùa**, không đủ cho SARIMAX mùa 12. Muốn khép hẳn: thêm cột rồi chạy `combine_effect` và báo số |
| Vật tư: danh mục, tồn kho, lượng dùng | ✅ | 5.017 mã, tồn 1,76 triệu đơn vị, fact_supply_usage 83.637 dòng |
| Định mức sử dụng + tồn kho an toàn | ✅ | **Đã mở khoá (09/09)**: `dss_demand.chan_doan_dinh_muc` (`dss_demand.py:296-334`) tính định mức **thực nghiệm theo KHỐI** từ `fact_usage_by_care_level`, nên J18 nằm trong khối J09-J18 và không còn mù; hàm tự báo khối nào thiếu dữ liệu. `DEFAULT_CONVERSION_RATIOS` 4 mã cũ thành mã chết, chờ dọn |
| Cờ COVID | 🟡 | is_covid 2020–2021 có trong dữ liệu và được dùng để **loại tháng COVID** khi ước lượng mùa vụ/xu hướng (`models.py:57,106,184`). **Chưa** dùng làm biến ngoại sinh SARIMAX — `sarimax_opt.py:25-33` chỉ lấy temp/humidity/rainfall. Sửa 09/09/2026 sau khi đối chiếu mã |
| Cờ dữ liệu chưa hoàn chỉnh | ✅ | is_complete, mô hình tự loại tháng dở dang |
| Số liệu được bệnh viện xác nhận | ❌ | **Vẫn chưa có bằng chứng đã gửi phòng KHTH** (rà lại 12/09) — mọi con số vẫn là "theo hệ thống". Phụ thuộc người khác trả lời nên phải gửi ngay |
| Vệ sinh còn treo | 🟡 | 1 dòng "Không Xác Định Tỉnh" + 6 mã chưa tên — đã vá code, **chờ chạy lại store 03 trên PROD + một lần sync full** |

## 2. GIAO DIỆN — đủ màn hình đề cương hứa (12/09: 3 chỗ tồn đọng đã xong)

Luồng 5 bước của đề cương: (1) tiếp nhận HIS ✅ (2) chuẩn hoá ✅ (3) dự báo
theo nhóm ✅ (4) phân bổ về mã + quy đổi vật tư ✅ (5) tồn kho dự kiến +
cảnh báo ✅ — phần **đề xuất nhập** ⛔ bỏ khỏi phạm vi (DSS thuần).

| Màn hình đề cương hứa | Trạng thái | Ghi chú |
|---|---|---|
| Dashboard tổng hợp | ✅ | Cần kiểm lại chiều nhóm (P1-5) |
| Dữ liệu bệnh | ✅ | Combobox 3 nhóm, tên tiếng Việt, lọc nhóm |
| Dữ liệu thời tiết | ✅ | |
| Phân tích & Dự báo | ✅ | **Đã sửa cả hai**: `ai_engine` cũ gỡ khỏi trang, mọi màn hình đi qua `group_forecast.forecast_group_next` (`forecast_analysis.py:390` ghi "ĐÃ GỠ"); panel giải thích viết lại theo yếu tố hô hấp thật (dòng 247-289) |
| Vật tư / Tồn kho | ✅ | 5.017 mã từ HIS |
| Cảnh báo thiếu hụt (4 mức) | ✅ | `dss_alerts.py` — Đỏ ≤18 ngày / Vàng ≤36 / Xanh / **Xám kèm `ly_do_xam`** (nói rõ vì sao chưa kết luận được thay vì hiện 0). DOI = tồn dùng được / tiêu hao ngày, FEFO |
| Kế hoạch nhập kho (phân cấp) | ⛔ | Đã **ẩn khỏi menu** theo quyết định DSS thuần 09/09; mã còn trong repo (`SupplyPlanning.tsx`, `supply_plan.py`) nhưng không route, không demo |
| Báo cáo + xuất | ✅ | |
| Quản trị (users, phân quyền, cấu hình, nhật ký) | ✅ | + bonus: cấu hình kết nối HIS từ UI |

**Ba việc để "đạt chuẩn" — đã xong cả ba tính đến 12/09:** engine trang Phân tích
đã thống nhất · panel giải thích đã viết lại · cảnh báo đã 4 mức theo Bảng 4.

## 3. MÔ HÌNH — đúng phương pháp luận (12/09: đối chứng đã có số)

| Đề cương hứa | Trạng thái | Chi tiết |
|---|---|---|
| Baseline naive + seasonal-naive | ✅ | Có, và dùng làm mẫu số MASE |
| SARIMAX (mùa vụ + ngoại sinh: thời tiết, cờ COVID) | ✅ | Trong ensemble |
| Hồi quy Poisson **hoặc** NegBin | ✅ | PoissonTrend + HarmonicPoisson(thời tiết); chữ "hoặc" → Poisson là đủ cam kết |
| **Prophet** | ✅ | **Đã chạy đối chứng 11/09** trên đúng giao thức walk-forward: Prophet RelMAE 1,3–2,4 (**tệ hơn seasonal-naive**), XGBoost chỉ +1 % → loại cả hai. Số ở `../KetQua_Backtest_ChonCauHinh.md` mục 0.4 và `backend/ketqua_backtest/doi_chung_xgb_prophet.csv`. Loại **bằng số đo**, đúng yêu cầu |
| Rolling-origin / walk-forward | ✅ | walk-forward mở rộng cửa sổ, `min_train` 24, dự báo 1 bước: **68 bước** với J00-J06 và J09-J18, **67** với J20-J22 |
| Đánh giá **MAE, RMSE, sMAPE, WAPE** | ✅ | Đủ từ 11/09/2026, thêm ME/MPE (sai số có dấu) và RelMAE. Chỉ số cũ gọi là "MASE" thực ra là RelMAE — đã đổi tên |
| Dự báo phân cấp top-down + tỷ trọng | ✅ | 4 hướng, có bằng chứng chọn (bottom-up nổ MASE 483 trên mã thưa) |
| Bảng so sánh chỉ số + cơ chế chọn mô hình | ✅ | 4 hướng phân cấp × 3 cửa sổ, **cộng hàng Prophet và XGBoost** (mục 0.4) và bảng biến thể kết hợp (mục 0.2). NegBin không chạy: đề cương ghi "Poisson **hoặc** NegBin", nhánh Poisson đã thoả |
| Lưu phiên bản mô hình, tham số, chỉ số, khoảng dự báo | ✅ | Bảng **`forecast_runs`** (11/09) ghi mỗi lần fit: `config`, `weights`, `bias_factor`, `members_used/failed`, `point_raw`, khoảng, `fingerprint`; `fill_actuals()` điền số thật khi kỳ chốt → có cả **bản ghi theo dõi trong vận hành**, xem `GET /dashboard/v2/forecast/history` |
| Khoảng dự báo | ✅ | z=1,96 ở mức nhóm, lan xuống mã |

**Kết quả đã đo — số chính thức, cấu hình M12 chiều 11/09/2026** (thay mọi bản
trước): RelMAE mức mã **0,500** (thắng seasonal-naive 50 %); mức nhóm
**0,516 / 0,377 / 0,541**; lệch có dấu MPE −0,5 / −3,0 / +4,1 % (gần như hết
lệch hệ thống); độ phủ khoảng 90 % đo thật 87 / 80 / 85 %; WAPE mức mã 28,3 %.
Cơ chế mang lại bước nhảy: **trọng số nghịch đảo MAE** thay trung bình đều +
**hiệu chỉnh lệch** + thêm **ETS**. Thời tiết −33 %/−28 % MAE ở mức mô hình đơn
nhưng chỉ +2–3 % ở mức ensemble. Xem `../KetQua_Backtest_ChonCauHinh.md` mục 0.

## 4. "MÔ HÌNH CẦN TRAIN GÌ KHÔNG?" — trả lời thẳng

**Không có gì phải "train trước" theo nghĩa deep learning.** Kiến trúc này
fit-tại-chỗ: mỗi lần dự báo, ensemble ước lượng lại trên toàn bộ lịch sử đến
thời điểm đó (vài giây, dữ liệu 92 điểm/chuỗi). Không có file model nặng, không
có bước huấn luyện định kỳ phải vận hành — đây là ưu điểm nên NÓI RÕ trong báo
cáo, không phải thiếu sót.

Cái mô hình cần không phải train mà là **4 thí nghiệm/bổ sung để khép cam kết**
— tính đến 12/09/2026 **cả 4 đã xong**:

1. ✅ **Đối chứng Prophet + XGBoost** — chạy 11/09, có số, loại cả hai
   (mục 0.4). NegBin không cần vì đề cương ghi "hoặc".
2. ✅ **sMAPE + WAPE + ME/MPE** đã có trong `evaluate.py` và đã chạy lại
   walk-forward chính thức trên cấu hình chốt M12.
3. ✅ **Thống nhất engine** — một đường duy nhất `forecast_group_next`; nhánh
   `topdown.py` và `ai_engine` cũ đã vào `_archive/`.
4. ✅ **Lưu phiên bản mô hình** — bảng `forecast_runs`, kèm điền số thật khi kỳ
   chốt.

## Thứ tự làm — bản 09/08 đã hoàn thành

| # | Việc | Trạng thái 12/09 |
|---|---|---|
| 1 | Gửi KHTH đối chiếu | ❌ **chưa có bằng chứng đã gửi — làm ngay** |
| 2 | Chạy lại store 03 + sync full | 🟡 còn treo: redeploy `G1_00` / `Phase0_03` trên PROD (VARCHAR(8)) |
| 3 | P1-4: engine trang Phân tích + viết lại giải thích | ✅ |
| 4 | Cảnh báo 4 mức Đỏ-Vàng-Xanh-Xám | ✅ |
| 5 | Định mức mức NHÓM (mở khoá J18) | ✅ |
| 6 | sMAPE/WAPE + đối chứng Prophet + lưu phiên bản | ✅ |
| 7 | Cập nhật đề cương/.docx theo số mới | 🟡 còn lại — số phải dùng là bản M12 (0,500) |

**Việc còn lại tính đến 12/09/2026** không còn nằm ở tài liệu này nữa — xem
`RaSoat_ToanDien_2026-09-12.md` (rà soát mã nguồn + DB thật, danh sách xếp theo
mức nghiêm trọng và thứ tự xử lý).
