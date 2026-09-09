# PHASE 0 — Chốt chặn dữ liệu & mở rộng Stored Procedure

**Hướng dẫn thực thi.** Đọc hết mục 1 và 2 trước khi chạy bất kỳ file nào.

Bốn file kèm theo:

| File | Chạy ở đâu | Ghi dữ liệu? |
|---|---|---|
| `Phase0_01_STA_bang_moi.sql` | STA · `MEDFORECAST_DW` | Có — chỉ CREATE, không xoá gì |
| `Phase0_02_PROD_store_cabenh_v2.sql` | HIS PROD · `GIAAN115_HIS` | Tạo thủ tục; ghi xuống STA khi chạy |
| `Phase0_03_PROD_store_khocungung.sql` | HIS PROD · `GIAAN115_HIS` | Tạo thủ tục; ghi xuống STA khi chạy |
| `Phase0_04_LOCAL_masterdata_abcxyz.sql` | Máy chạy app · `medforecast.db` | **Có — sao lưu trước** |

---

## 1. Ba số đo đã đổi thiết kế so với bản kế hoạch

### 1.1 Bảng `severity_rates` gõ tay đã bị số thật bác bỏ

Đ4 đo trên 24 tháng, phân loại theo cấp nặng nhất của đợt:

| | Cấp 1 (nặng) | Cấp 2 (vừa) | Cấp 3 (nhẹ) |
|---|---|---|---|
| **Đo thật (Đ4)** | 42,2 % | 40,8 % | 17,0 % |
| **Đang nhập tay (J00-J06)** | 71,49 % | 23,51 % | 5,0 % |

Lệch gần 30 điểm phần trăm ở cấp nặng nhất. Ba hằng số này đang nhân trực tiếp
vào định mức ở Tầng 2, nên sai số đi thẳng vào lượng đề xuất nhập.

Vì vậy Phase 0 **bắt buộc** phải đẩy được bảng số ca theo phân cấp
(`MF_CaBenh_PhanCap`) — nhánh p̂(g,c) thực nghiệm không còn là tuỳ chọn.

Ba hằng số cũ **không xoá**: giữ lại trong `severity_rates` để đối chiếu và để
trình bày trong luận văn phần "vì sao chuyển sang tỷ trọng thực nghiệm".

### 1.2 Ngoại trú và nội trú cấp 3 không thể chung một rổ

Đ5, 12 tháng gần nhất, ba nhóm ICD đích:

| | Số lượt | Dòng toa/lượt | Số lượng/dòng |
|---|---|---|---|
| NT-cấp 3 | 122 | **16,89** | 3,33 |
| NGT | 2 425 | **4,72** | **18,29** |

Hai chiều ngược nhau: ngoại trú ít dòng toa hơn 3,5 lần nhưng mỗi dòng nhiều
gấp 5,5 lần — bệnh nhân ngoại trú lĩnh trọn đợt mang về, nội trú lĩnh theo
liều từng ngày.

Hai hệ quả:

1. **Năm rổ, không phải bốn**: `NGT | NT1 | NT2 | NT3 | NT0`. Quy ước
   "ngoại trú = cấp 3" bị bác bỏ bằng số.
2. **Định mức phải tính theo số lượng, không theo số dòng toa.** Bảng đầu ra
   mang cả hai cột, nhưng công thức chỉ dùng `so_luong`. Cột `so_dong_toa` ở
   đó để phát hiện nếu ai đó lỡ dùng nhầm.

### 1.3 `unit_price` đã mở khoá — nhưng ba giá không thay thế nhau

Đ1 xác nhận `TT_DUOC_CHUNGTU_SOLONHAP` có đủ `DONGIAMUA`, `DONGIATHAU`,
`DONGIAVON`. Cả ba được đẩy xuống STA, **không chọn hộ ứng dụng**:

| Cột | Ý nghĩa | Dùng cho |
|---|---|---|
| `don_gia_mua` | giá thực trả trên chứng từ nhập | **ABC theo giá trị** (mặc định) |
| `don_gia_thau` | giá trúng thầu, ràng buộc hợp đồng | bài toán hạn mức thầu (đã hoãn) |
| `don_gia_von` | giá vốn ghi sổ | đối chiếu kế toán |

Thứ tự mặc định: `COALESCE(don_gia_mua, don_gia_thau, don_gia_von)` — ABC cần
chi phí hiện hành, không phải giá hợp đồng. Phương án dự phòng Đ7-D (ABC theo
số lượng) **huỷ**.

---

## 2. Ba lỗi trong thủ tục hiện tại — đã sửa trong bản 2

| | Lỗi | Hậu quả | Cách sửa |
|---|---|---|---|
| **A1** | `DELETE ... WHERE Period >= @TuNgay` không giới hạn theo nhóm bệnh | Chạy một nhóm để xem riêng sẽ **xoá sạch hai nhóm kia**, im lặng | Giới hạn bằng `@NhomChuan` |
| **A2** | `EXEC(N'TRUNCATE TABLE dbo.MF_TonKho') AT [MEDFORECAST_STA]` | Tên hai phần phụ thuộc database mặc định của login; và nếu ảnh chụp rỗng thì **toàn bộ tồn kho về 0**, mọi vật tư báo thiếu hàng | Tên ba phần, `DELETE` thay `TRUNCATE`, `THROW` nếu ảnh chụp rỗng, đối chiếu số dòng sau khi ghi |
| **A3** | Nhánh ngoại trú dùng `JOIN TM_ICD` (INNER) | Lượt ngoại trú có `CHANDOANICD_ID` rỗng nhưng mã đích nằm ở `DS_MAICDPHU` bị rơi — dù `WHERE` đã cho phép | `LEFT JOIN`, đối xứng với nhánh nội trú |

**A1 và A2 không có công tắc tắt** — chúng là lỗi, không phải lựa chọn thiết kế.

### Chỗ dễ sai nhất của Phase 0: đếm hai lần ở mức nhóm

Một lượt mang J01 (chính) + J06 (phụ) sinh **hai** dòng trong `#Dx`. Bảng cũ
`MF_CaBenh_VatTu` cố ý giữ cả hai — dự báo theo từng mã cần vậy.

Nhưng J01 và J06 **cùng thuộc nhóm J00-J06**. Nếu ghép thẳng `#Dx` với `#Drug`
rồi gom theo nhóm, lượng thuốc của lượt đó bị cộng hai lần, và định mức phồng
lên đúng bằng tỷ lệ đồng mắc trong nhóm — không có cách nào phát hiện từ kết quả.

Bản 2 dựng bảng `#DxG` khử trùng ở mức nhóm trước khi ghép, và tự in cảnh báo
nếu bất biến không giữ. Lượt mang mã ở **hai nhóm khác nhau** (J06 + J20) vẫn
giữ hai dòng — đó là chủ ý, thuốc của lượt đó phục vụ cả hai bệnh.

---

## 3. Thứ tự thực thi

### Bước 0 — Sao lưu và chạy Đ8

```
-- Trên máy chạy app
cp backend/data/medforecast.db backend/data/saoluu_truoc_phase0_medforecast.db
```

Chạy khối **Đ8** ở đầu file `Phase0_03` (chỉ đọc, 4 câu truy vấn). Kết quả
quyết định hai việc:

- **Đ8-A/B** — tìm bảng đơn đặt hàng. Có thì mở khối ⚙ trong thủ tục để tính
  được thời gian giao hàng **thật** của nhà cung cấp. Không có thì `σ_L` chưa
  đo được và Phase 2 phải hiện cảnh báo trên giao diện.
- **Đ8-C** — xác định loại chứng từ nào là nhập mua, để loại điều chuyển nội bộ
  và trả hàng ra khỏi mẫu tính lead time.

Gửi lại kết quả Đ8 trước khi chạy tiếp — hai quyết định trên đổi tham số của
`Phase0_03`.

### Bước 1 — Tạo bảng bên STA

```sql
-- máy chủ STA
:r Phase0_01_STA_bang_moi.sql
```

Kiểm tra cuối file phải in ra đủ **6 bảng `MF_` mới** và **7 view mới**.

### Bước 2 — Cài thủ tục ca bệnh bản 2, đối chiếu trước khi đẩy

```sql
-- HIS PROD
:r Phase0_02_PROD_store_cabenh_v2.sql

-- 2A · phải ra ĐÚNG con số của bản 1
EXEC dbo.usp_MedForecast_DayDuLieu
     @NapLaiToanBo = 1, @ChiXem = 1, @DayLuongPhanCap = 0;

-- 2B · xem bốn bảng mới, vẫn chưa đẩy
EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1, @ChiXem = 1;
```

**Ở 2A**, chênh duy nhất được phép so với bản 1 là **nhiều hơn** một ít lượt
ngoại trú (do sửa lỗi A3). Chênh theo hướng ngược lại → dừng, không chạy tiếp.

**Ở 2B**, hai bảng phải soi kỹ:

- *Bảng 3 · tỷ trọng phân cấp.* Đối chiếu với Đ4 (≈ 42/41/17 toàn viện). Ở mức
  từng nhóm bệnh phải thấy **J09-J18 nặng hơn J00-J06 rõ rệt** — viêm phổi nặng
  hơn viêm hô hấp trên. **Nếu ba nhóm cho tỷ trọng gần như nhau thì
  `PHANCAPCHAMSOC_ID` không phản ánh độ nặng, và toàn bộ Tầng 2 phải thiết kế
  lại trước khi đi tiếp.** Đây là cổng chặn thật, không phải thủ tục hình thức.
- *Bảng 4 · định mức thực nghiệm.* Lấy 5–10 dòng đầu hỏi khoa Dược. Một dòng
  vô lý (ví dụ 4 000 viên paracetamol mỗi ca) là dấu hiệu lệch đơn vị tính giữa
  `TM_DONVITINH` và thực tế cấp phát.

Xong hai bước trên mới nạp thật:

```sql
EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1;
```

Job hằng ngày (`04_PROD_job.sql`) **không phải sửa** — tên thủ tục và tham số
mặc định giữ nguyên.

### Bước 3 — Cài thủ tục kho & cung ứng

```sql
:r Phase0_03_PROD_store_khocungung.sql
EXEC dbo.usp_MedForecast_DayKhoCungUng @ChiXem = 1;   -- xem trước
EXEC dbo.usp_MedForecast_DayKhoCungUng;               -- nạp thật
```

Hai bảng phải đọc ở chế độ xem trước:

- *Nguồn thời gian giao hàng.* Nếu `lead_time_nguon = 'NOIBO'` chiếm đa số thì
  `σ_L` **chưa đo được thật**. Không được lấy lead nội bộ thế chỗ — nó có σ gần
  bằng 0 và sẽ cho tồn an toàn thiếu nghiêm trọng. Giao diện phải ghi rõ đang
  dùng L cấu hình.
- *Phân bố hạn dùng.* Số lô ở khoảng "không có hạn dùng" quyết định FEFO phủ
  được bao nhiêu phần kho. Dưới 50 % thì màn hình FEFO phải có nhãn phạm vi.

Lịch chạy đề nghị: tồn theo lô **mỗi ngày** (`@SoThangLichSu = 3`), lịch sử nhập
đầy đủ **mỗi chủ nhật** (`@SoThangLichSu = 36`).

### Bước 4 — Dọn dữ liệu local, phân lớp ABC-XYZ

```
cd backend
sqlite3 data/medforecast.db ".read ../Phase0_04_LOCAL_masterdata_abcxyz.sql"
```

File này **có ghi**. Bốn việc: tạo bảng nhận dữ liệu mới, dọn 49 dòng nhãn
`'Không Xác Định Tỉnh'`, phân lớp ABC-XYZ, nạp master data và **gỡ vòng lặp
`safety_stock`**.

> Lưu ý: gỡ vòng lặp ở đây chỉ đưa cột về `NULL` và lưu lại giá trị cũ. Việc
> **chặn ghi ngược** nằm ở code (`inventory.py:217`) và thuộc Phase 1. Nếu chỉ
> dọn số mà không sửa code thì vòng lặp dựng lại nguyên vẹn sau lần bấm "phân
> tích" kế tiếp.

---

## 4. Vì sao ABC-XYZ nằm ở Phase 0 chứ không để sau

Công thức `SS = Z·√[(T+L̄)σ²_d + d̄²σ²_L]` giả định nhu cầu xấp xỉ phân phối
chuẩn. Đ6 đo được **376/1 529 vật tư (24,6 %) có CV > 1** — nhu cầu gián đoạn,
tháng có tháng không.

Với nhóm đó, `σ` tính ra là con số vô nghĩa và công thức sai cả hai chiều: thừa
với vật tư gần như không dùng, thiếu với vật tư dùng theo đợt. Không phân lớp
trước thì Phase 2 sẽ áp công thức lên toàn bộ 5 041 mã và một phần tư kết quả
là số giả vờ chính xác.

Cột `phuong_phap_ss` ghi rõ mỗi vật tư đi đường nào:

| Giá trị | Nhóm | Cách xử lý |
|---|---|---|
| `CHUAN` | X, Y (≈ 1 153 mã) | công thức tồn an toàn đầy đủ |
| `LO_CO_DINH` | Z nhưng giá trị lớn (ABC A/B) | đặt theo lô cố định, tồn tối thiểu 1 lô |
| `THEO_YEU_CAU` | Z và giá trị nhỏ | không dự trữ, đặt khi khoa phòng yêu cầu |

So sánh: hiện tại có **34** vật tư được quản lý bằng định mức gõ tay.
Sau Phase 0 là **1 153** — gấp 34 lần.

---

## 5. Nghiệm thu Phase 0 — sáu câu hỏi

Sáu truy vấn nghiệm thu nằm ở cuối `Phase0_04`. Tóm tắt tiêu chí:

| | Câu hỏi | Đạt khi |
|---|---|---|
| **N1** | Tỷ trọng phân cấp có khớp Đ4 và có phân biệt giữa các nhóm bệnh? | J09-J18 nặng hơn J00-J06 rõ rệt |
| **N2** | Định mức thực nghiệm có hợp lý? | 30 dòng đầu giải thích được bằng nghiệp vụ |
| **N3** | So với 34 định mức gõ tay? | Chênh dưới 2 lần: chấp nhận. Trên 5 lần: dừng, tìm nguyên nhân |
| **N4** | FEFO phủ bao nhiêu phần kho? | Dưới 50 % thì giao diện phải ghi rõ phạm vi |
| **N5** | σ_L đo được thật hay đang mặc định? | `lead_time_source = 'THAU'` chiếm đa số |
| **N6** | Chu kỳ nhập thật so với T = 30 ngày? | Trung vị > 40 ngày thì phải chỉnh T |

**N1 và N6 là hai cổng chặn cứng.** N1 không đạt → Tầng 2 sai nền tảng.
N6 lệch → khoảng bảo vệ `T + L` đang tính thiếu, và đó là sai số hệ thống ở
mọi vật tư, không phải sai số ngẫu nhiên.

---

## 6. Những gì Phase 0 **không** làm

Ghi ra để không ai chờ nhầm:

- **Không sửa dòng code Python/TypeScript nào.** Vòng lặp `safety_stock`,
  `Ensemble.predict()` nuốt lỗi thành viên, `_classify_risk()` nhận
  `case_trend_pct = 6500` — tất cả thuộc Phase 1.
- **Không đo được `storage_capacity`.** HIS không lưu thể tích/diện tích lưu
  trữ. Cột để `NULL`. Nếu sau này muốn có trần vận hành thì gọi đúng tên là
  "trần dự trữ" (k × nhu cầu tháng cao nhất), **không** gọi là sức chứa kho —
  chính kiểu đặt tên sai đó đã sinh ra vòng lặp `safety_stock` hiện tại.
- **Không mở rộng sang vật tư y tế.** Tham số `@GomVTYT` có sẵn nhưng mặc định
  tắt. Bật lên sẽ đổi nội dung `MF_CaBenh_VatTu`, cần đo lại từ đầu.
- **Không đụng bài toán hạn mức thầu.** Đã thống nhất hoãn.
