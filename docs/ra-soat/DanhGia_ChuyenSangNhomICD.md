# Đánh giá tổng thể: chuyển toàn hệ thống sang góc nhìn NHÓM ICD

Ngày rà soát: 09/08/2026 — sau khi toàn tuyến HIS → STA → app chạy bằng dữ
liệu thật (23.429 ca, 20 mã, 3 nhóm — số đếm tại 09/08/2026; sau các lần đồng
bộ tiếp theo, số chốt hiện nay là 23.653 ca, xem
`KetQua_Backtest_ChonCauHinh.md` mục 0.3).

## Nguyên tắc chốt (bám đề cương)

Đề cương quy định luồng 5 bước, trong đó bước 3–4: *"Dự báo số ca bệnh theo
nhóm ICD"* rồi *"Phân bổ dự báo về từng mã bệnh và quy đổi thành nhu cầu vật
tư"*. Nghĩa là:

- **Hiển thị**: NHÓM là góc nhìn mặc định ở mọi màn hình. Người dùng nghiệp vụ
  (Khoa Dược, lãnh đạo) tư duy theo "hô hấp trên / cúm-viêm phổi / hô hấp
  dưới", không theo 20 mã lẻ.
- **Dữ liệu**: mức MÃ giữ nguyên bên dưới — bước phân bổ top-down, tỷ trọng
  EWMA và bảng ánh xạ bệnh–vật tư đều cần nó. **Không xoá gì cả, chỉ đổi tầng
  trình bày và thêm chiều nhóm vào nơi còn thiếu.**
- Backtest 09/08 củng cố nguyên tắc này: chuỗi nhóm dày và ổn định (MASE
  0,51–0,65), chuỗi mã lẻ thưa và dễ vỡ (bottom-up nổ MASE 483 trên mã thưa).

## Hai lỗi nền phát hiện khi rà — phải sửa TRƯỚC mọi việc giao diện

**N1. Tên bệnh hiển thị mã thô (J20, J18...).** Nguyên nhân đã truy ra:
`pipeline._upsert_dims` ghi cứng `icd_name=""` vào `dim_icd`, trong khi cột
`disease_name` (TENICD thật từ HIS) nằm ngay trong dataframe mà không được
dùng. Cầu nối sang `disease_cases` đọc `dim_icd` → rơi về mã. Combobox hiện 4
tên + 16 mã thô là vì 4 tên đó đến từ danh mục `admin.diseases` cũ (4 bệnh),
không phải từ dữ liệu.

**N2. Bảng `disease_cases` không có cột nhóm.** Mọi màn hình cũ đọc bảng này
nên không thể lọc/gộp theo nhóm. Cần thêm cột `disease_group` (bridge tự
ALTER + điền từ `dim_icd.block_code`).

## Kiểm kê từng màn hình

| Màn hình | API đang dùng | Hiện trạng | Việc cần làm |
|---|---|---|---|
| **Quản lý dữ liệu bệnh** (Epidemiology) | `/disease-cases/` + `/stats` + `/trends` | Bảng phẳng theo mã; tên hỏng (N1); combobox lẫn 4 tên + 16 mã; không có chiều nhóm | Thêm cột + bộ lọc **Nhóm bệnh**; bảng gộp nhóm → bấm xổ ra mã; thống kê đầu trang theo nhóm |
| **Dự báo số ca** (Forecasting) | `/forecast/analyze` (ai_engine riêng, theo mã × tỉnh) | Combobox 20 mã lẻ — đúng chỗ mô hình yếu nhất (mã thưa) | Combobox chọn **NHÓM** (3 mục); phân tích trên chuỗi nhóm từ `mart_monthly_cases_by_block`; drill-down mã dùng tỷ trọng top-down đã có |
| **Dashboard** | `/reports/*`, dashboard summary | Trend/summary theo mã | Chuyển series mặc định theo nhóm; giữ mã trong tooltip/drill |
| **Reports** | `useDiseaseOptions` = `/forecast/diseases` (mã) | Bộ lọc theo mã | Bộ lọc nhóm (cùng nguồn danh mục N3) |
| **Alerts / Khuyến nghị vật tư** | supply_recommendations (định mức theo mã) | 60 định mức chỉ phủ 4 mã cũ → 16 mã mới KHÔNG sinh nhu cầu | Chuyển **định mức sang mức NHÓM** (đề cương cho phép: "ánh xạ mã/nhóm bệnh với danh mục vật tư") — 3 nhóm dễ bảo trì hơn 20 mã, và tự phủ mã mới |
| **Kế hoạch nhập kho** (SupplyPlanning) | `forecast-hier` | **Đã theo nhóm** ✓ | Không đổi — đây là mẫu chuẩn cho các trang khác |
| **Quản trị → Cấu hình bệnh** | `admin.diseases` (4 bệnh cũ) | Danh mục lỗi thời | Thành danh mục **3 nhóm** (nguồn duy nhất cho mọi combobox), mã con lấy từ `dim_icd` |

## Kế hoạch thực hiện — từng đầu mục, có kiểm chứng

**P0 — nền dữ liệu (làm trước, không có thì mọi thứ sau vô nghĩa)**
1. ✅ *(đã sửa trong đợt giao này)* `_upsert_dims` lấy tên thật từ dữ liệu;
   cầu nối điền `disease_group` vào `disease_cases` (tự ALTER cột nếu thiếu).
   Kiểm: sau một lần Đồng bộ, cột Tên bệnh ra tên tiếng Việt, cột nhóm có giá trị.
2. Danh mục `admin.diseases` → 3 nhóm; endpoint danh mục trả nhóm + mã con.

**P1 — màn hình, mỗi mục một lượt làm + kiểm**
3. Epidemiology: lọc nhóm + bảng gộp nhóm/xổ mã + thống kê nhóm.
4. Forecasting: phân tích theo nhóm (đọc mart, giữ ai_engine phần thời tiết).
5. Dashboard + Reports: series và bộ lọc theo nhóm.

**P2 — nghiệp vụ**
6. Định mức bệnh–vật tư chuyển mức nhóm + màn nhập; khuyến nghị/cảnh báo tính
   từ dự báo nhóm.
7. Đối chiếu KHTH, cập nhật đề cương + tài liệu, commit từng mục.

Mỗi mục kết thúc bằng một tiêu chí kiểm nghiệm được (số trên màn hình khớp
truy vấn tay vào mart) — đúng tinh thần "tiêu chí nghiệm thu" trong đề cương.
