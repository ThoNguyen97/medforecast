# Rà soát đề cương ↔ thực tế (09/08/2026)

Đối chiếu từng cam kết trong `DeCuongDoAnTotNghiep_..._20260711.docx` với trạng
thái sản phẩm sau khi nối HIS thật. Ký hiệu: ✅ đạt · 🟡 đạt một phần · ❌ chưa.

---

## 1. DỮ LIỆU — 8/10 đạt, 2 việc vận hành đang treo

| Cam kết đề cương | Trạng thái | Bằng chứng / việc còn lại |
|---|---|---|
| Ca bệnh BV tại TP.HCM, 2019–2026, tổng hợp theo tháng × ICD × địa bàn | ✅ | 92 tháng, 23.429 ca, đồng bộ tự động HIS→STA→app |
| Đã loại bỏ định danh | ✅ | Tổng hợp ngay trên PROD; ngưỡng ô nhỏ k=5; căn cứ Luật 91/2025 Điều 2 |
| Ba nhóm J00-J06 / J09-J18 / J20-J22 | ✅ | Đủ 20 mã; danh mục lấy từ TM_ICD.PHANNHOM |
| Môi trường: nhiệt độ, ẩm, mưa, AQI; độ trễ 1–2 tháng | 🟡 | 309 tháng-dòng Open-Meteo, lag đã dùng trong mô hình; **AQI chưa có trong chuỗi mô hình** (chỉ hiện ở panel giải thích — mà panel đó đang là văn mẫu) |
| Vật tư: danh mục, tồn kho, lượng dùng | ✅ | 5.017 mã, tồn 1,76 triệu đơn vị, fact_supply_usage 83.637 dòng |
| Định mức sử dụng + tồn kho an toàn | ❌ | 60 định mức chỉ phủ 4 mã cũ — **J18 (bệnh lớn nhất, 30% số ca) chưa có định mức** → chuỗi cảnh báo/đề xuất mù đúng chỗ nặng nhất |
| Cờ COVID | 🟡 | is_covid 2020–2021 có trong dữ liệu và được dùng để **loại tháng COVID** khi ước lượng mùa vụ/xu hướng (`models.py:57,106,184`). **Chưa** dùng làm biến ngoại sinh SARIMAX — `sarimax_opt.py:25-33` chỉ lấy temp/humidity/rainfall. Sửa 09/09/2026 sau khi đối chiếu mã |
| Cờ dữ liệu chưa hoàn chỉnh | ✅ | is_complete, mô hình tự loại tháng dở dang |
| Số liệu được bệnh viện xác nhận | ❌ | **Chưa gửi phòng KHTH** — mọi con số vẫn là "theo hệ thống" |
| Vệ sinh còn treo | 🟡 | 1 dòng "Không Xác Định Tỉnh" + 6 mã chưa tên — đã vá code, **chờ chạy lại store 03 trên PROD + một lần sync full** |

## 2. GIAO DIỆN — đủ màn hình đề cương hứa, 3 chỗ chưa đạt chuẩn

Luồng 5 bước của đề cương: (1) tiếp nhận HIS ✅ (2) chuẩn hoá ✅ (3) dự báo
theo nhóm ✅ (4) phân bổ về mã + quy đổi vật tư ✅ (5) tồn kho dự kiến +
cảnh báo + đề xuất nhập 🟡.

| Màn hình đề cương hứa | Trạng thái | Ghi chú |
|---|---|---|
| Dashboard tổng hợp | ✅ | Cần kiểm lại chiều nhóm (P1-5) |
| Dữ liệu bệnh | ✅ | Combobox 3 nhóm, tên tiếng Việt, lọc nhóm |
| Dữ liệu thời tiết | ✅ | |
| Phân tích & Dự báo | 🟡 | Combobox 3 nhóm ✅ nhưng **chạy engine ai_engine cũ → dự báo hụt ~40% so với thực tế T6** (65 vs ~110); **panel "Giải thích mô hình" là văn mẫu sốt xuất huyết (muỗi!)** |
| Vật tư / Tồn kho | ✅ | 5.017 mã từ HIS |
| Đề xuất nhập kho + cảnh báo | 🟡 | Có công thức truy vết ✅ nhưng cảnh báo chỉ 2 trạng thái shortage/sufficient — **đề cương hứa 4 mức Đỏ-Vàng-Xanh-Xám, kèm nguyên nhân + hành động** |
| Kế hoạch nhập kho (phân cấp) | ✅ | Chuẩn mực — engine đã kiểm chứng |
| Báo cáo + xuất | ✅ | |
| Quản trị (users, phân quyền, cấu hình, nhật ký) | ✅ | + bonus: cấu hình kết nối HIS từ UI |

**Ba việc để "đạt chuẩn":** thay engine trang Phân tích (P1-4) · viết lại panel
giải thích theo yếu tố thật trong mô hình · nâng cảnh báo lên 4 mức theo Bảng 4.

## 3. MÔ HÌNH — đúng phương pháp luận, thiếu 2 bằng chứng đối chứng

| Đề cương hứa | Trạng thái | Chi tiết |
|---|---|---|
| Baseline naive + seasonal-naive | ✅ | Có, và dùng làm mẫu số MASE |
| SARIMAX (mùa vụ + ngoại sinh: thời tiết, cờ COVID) | ✅ | Trong ensemble |
| Hồi quy Poisson **hoặc** NegBin | ✅ | PoissonTrend + HarmonicPoisson(thời tiết); chữ "hoặc" → Poisson là đủ cam kết |
| **Prophet** | ❌ | Đề cương hứa khẳng định ("Huấn luyện Prophet...") nhưng ensemble hiện KHÔNG có. Phải có bằng chứng: chạy đối chứng một lần rồi ghi kết quả — giữ hay loại đều được, miễn là **loại bằng số đo chứ không phải im lặng** |
| Rolling-origin / walk-forward | ✅ | walk-forward mở rộng cửa sổ, 66–67 bước |
| Đánh giá **MAE, RMSE, sMAPE, WAPE** | ✅ | Đủ từ 11/09/2026, thêm ME/MPE (sai số có dấu) và RelMAE. Chỉ số cũ gọi là "MASE" thực ra là RelMAE — đã đổi tên |
| Dự báo phân cấp top-down + tỷ trọng | ✅ | 4 hướng, có bằng chứng chọn (bottom-up nổ MASE 483 trên mã thưa) |
| Bảng so sánh chỉ số + cơ chế chọn mô hình | 🟡 | Có cho 4 hướng phân cấp × 3 cửa sổ; **chưa có hàng Prophet/NegBin** |
| Lưu phiên bản mô hình, tham số, chỉ số, khoảng dự báo | 🟡 | disease_forecasts lưu kết quả + khoảng; chưa lưu "phiên bản cấu hình mô hình" đi kèm — bổ sung nhẹ được |
| Khoảng dự báo | ✅ | z=1,96 ở mức nhóm, lan xuống mã |

**Kết quả đã đo — số chính thức 11/09/2026** (thay bản 09/08): RelMAE mức mã
0,659 (thắng seasonal-naive ~34%); mức nhóm 0,60–0,76; độ phủ khoảng 90% đo
thật 85–88% (68% ở J09-J18); thời tiết −33%/−28% MAE ở mức mô hình đơn nhưng
chỉ +2–3% ở mức ensemble, có hại nhẹ với J09-J18. Xem KetQua_Backtest_ChonCauHinh.md.

## 4. "MÔ HÌNH CẦN TRAIN GÌ KHÔNG?" — trả lời thẳng

**Không có gì phải "train trước" theo nghĩa deep learning.** Kiến trúc này
fit-tại-chỗ: mỗi lần dự báo, ensemble ước lượng lại trên toàn bộ lịch sử đến
thời điểm đó (vài giây, dữ liệu 92 điểm/chuỗi). Không có file model nặng, không
có bước huấn luyện định kỳ phải vận hành — đây là ưu điểm nên NÓI RÕ trong báo
cáo, không phải thiếu sót.

Cái mô hình cần không phải train mà là **4 thí nghiệm/bổ sung để khép cam kết**:

1. **Đối chứng Prophet + NegBin** (một lần): thêm 2 thành viên vào walk-forward,
   chạy trên chuỗi nhóm, ghi vào bảng so sánh. Dự đoán: không thắng ensemble
   hiện tại trên chuỗi 92 điểm — nhưng phải có số để nói câu đó.
2. **Thêm sMAPE + WAPE** vào evaluate.py rồi chạy lại walk-forward chính thức
   một lần trên cấu hình chốt (2019 + TD động + thời tiết) → bảng số cuối cùng
   cho chương 4, đúng bộ chỉ số đề cương hứa.
3. **Thống nhất engine (P1-4)**: trang Phân tích bỏ ai_engine cũ, gọi ensemble
   nhóm — hết cảnh hai màn hình ra hai con số.
4. **Lưu "phiên bản mô hình"**: mỗi lần dự báo ghi kèm cấu hình (thành viên
   ensemble, trọng số, cửa sổ, có thời tiết không) vào disease_forecasts —
   đóng cam kết truy vết của Nội dung 3.

## Thứ tự làm (2 tuần tới)

| # | Việc | Loại | Ước lượng |
|---|---|---|---|
| 1 | Gửi KHTH đối chiếu (mục 4 script 00) | chờ người khác — gửi NGAY | 30 phút + chờ |
| 2 | Chạy lại store 03 + sync full (dọn 2 vết dữ liệu) | vận hành | 15 phút |
| 3 | P1-4: engine trang Phân tích + viết lại giải thích | code | 1 buổi |
| 4 | Cảnh báo 4 mức Đỏ-Vàng-Xanh-Xám (Bảng 4) | code | 1 buổi |
| 5 | Định mức mức NHÓM (mở khoá J18) | code + nhập liệu | 1 buổi |
| 6 | sMAPE/WAPE + đối chứng Prophet/NegBin + lưu phiên bản | thí nghiệm | 1 buổi |
| 7 | Cập nhật đề cương/.docx theo số mới + commit toàn bộ | viết | 1 buổi |

Xong 7 mục này thì mọi dòng đề cương đều có ô ✅ hoặc một câu giải thích có số
liệu — trạng thái tốt nhất có thể mang đi bảo vệ.
