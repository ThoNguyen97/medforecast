# G1 — Mã nguồn backend

Tám tệp đã chép sẵn vào đúng vị trí trong repo. Không tệp nào ghi đè mã cũ:
bảy tệp là **mới hoàn toàn**, và thay đổi duy nhất lên mã có sẵn (`dashboard.py`)
do một script riêng thực hiện, mặc định chỉ chạy thử.

| Tệp | Vai trò |
|---|---|
| `backend/app/services/period_service.py` | **Nguồn duy nhất** của mốc thời gian, số ca và quy mô danh mục |
| `backend/app/data_pipeline/dss_loader.py` | Nạp ba luồng DSS từ STA về local, xoá-rồi-chèn theo kỳ |
| `backend/app/data_pipeline/sql/usage_total_sta.sql` | Câu đọc `vw_MedForecast_TieuHaoTong` |
| `backend/app/data_pipeline/sql/cases_care_level_sta.sql` | Câu đọc `vw_MedForecast_CaBenhPhanCap` |
| `backend/app/data_pipeline/sql/usage_care_level_sta.sql` | Câu đọc `vw_MedForecast_TieuHaoPhanCap` |
| `backend/scripts/run_dss_load.py` | CLI chạy nạp |
| `backend/scripts/patch_g1_dashboard.py` | Sửa `dashboard.py` (mặc định chỉ thử) |
| `backend/scripts/verify_g1.py` | Nghiệm thu 6 tiêu chí |

**Đã kiểm chứng trên máy anh:** cả năm tệp Python biên dịch sạch; `period_service`
import được; `verify_g1.py` chạy ra kết quả thật; `patch_g1_dashboard.py` chạy thử
tìm đúng **5/5 mốc** cần sửa, không mục nào hỏng.

---

## 1. Thứ tự chạy

> ⚠ **Hai bước đầu là điều kiện bắt buộc, không phải tuỳ chọn.** Chưa làm thì
> hai trong ba luồng DSS sẽ không có gì để kéo, và **cổng chặn N1 không kiểm
> được**. Thủ tục `usp_MedForecast_DayDuLieu` đang chạy trên HIS là **bản cũ,
> không hề biết tới phân cấp chăm sóc** — đã kiểm: `03_PROD_store_tong_hop.sql`
> có **0** dòng nhắc tới `PHANCAPCHAMSOC`.

### Bước 0a — Bên STA: tạo hai bảng phân cấp

```sql
-- máy chủ STA, database MEDFORECAST_DW
:r Phase0_01_STA_bang_moi.sql
```

Tạo `MF_CaBenh_PhanCap`, `MF_TieuHao_PhanCap`, `MF_TonKho_Lo` và các view.
`G1_01_STA_sua_bang.sql` **không** thay được bước này — nó chỉ dựng lại
`MF_TieuHao_Tong`.

### Bước 0b — Bên PROD: cài thủ tục ca bệnh BẢN 3

```sql
-- HIS PROD, GIAAN115_HIS
:r phase0/G1_00_PROD_store_cabenh_v3.sql
```

Đây là bản thay thế **toàn bộ** `usp_MedForecast_DayDuLieu`. So với bản đang
chạy, nó thêm ba thứ và sửa ba lỗi:

| | |
|---|---|
| **Thêm** | `#CapDot` — rổ chăm sóc của mỗi đợt = `MIN(mã phân cấp)`; `#DxG` khử trùng ở mức nhóm; hai luồng `MF_CaBenh_PhanCap` và `MF_TieuHao_PhanCap` |
| **Sửa A1** | `DELETE` bên STA nay giới hạn theo nhóm bệnh — bản cũ chạy một nhóm sẽ xoá sạch hai nhóm kia |
| **Sửa A2** | `TRUNCATE MF_TonKho` → tên ba phần + `THROW` khi ảnh chụp rỗng |
| **Sửa A3** | Nhánh ngoại trú `INNER JOIN` → `LEFT JOIN` |

Bản 3 đã **gỡ sẵn khối 7f** (`#KQTT`) — không phải sửa tay như hướng dẫn trước
nữa. Tiêu hao toàn viện nay do `usp_MedForecast_DayTieuHaoToanVien` đảm nhiệm.

Chạy xem trước và **soi bảng tỷ trọng phân cấp** (bảng thứ ba trả về):

```sql
EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1, @ChiXem = 1;
```

Đây chính là **cổng chặn N1**. J09-J18 (viêm phổi) phải nặng hơn J00-J06 (viêm
hô hấp trên) rõ rệt. Nếu ba nhóm cho tỷ trọng gần như nhau thì
`PHANCAPCHAMSOC_ID` không phản ánh độ nặng, và Tầng 2 phải thiết kế lại **trước
khi** viết G3. Gửi lại bảng đó trước khi nạp thật.

### Bước 1 — Bên STA: cấp quyền cho tài khoản ứng dụng

Ba view mới sẽ bị từ chối nếu chưa GRANT. Chạy trên `MEDFORECAST_DW`:

```sql
GRANT SELECT ON dbo.vw_MedForecast_TieuHaoTong     TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_CaBenhPhanCap   TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TieuHaoPhanCap  TO medforecast_app;
```

### Bước 2 — Bên PROD: nạp dữ liệu lên STA

```sql
EXEC dbo.usp_MedForecast_DayTieuHaoToanVien;          -- tiêu hao toàn viện
EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1; -- ca bệnh + 2 luồng phân cấp
```

### Bước 3 — Kéo về local

```bash
cd backend
python scripts/run_dss_load.py --full     # lần đầu
python scripts/run_dss_load.py            # các lần sau, tăng dần lùi 3 kỳ
```

Script tự tạo hai bảng phân cấp nếu chưa có, nên **không cần chạy lại
`Phase0_04`**. Nó dùng chính kết nối STA đã lưu trong Quản trị → Kết nối HIS.

### Bước 4 — Sửa dashboard

```bash
python backend/scripts/patch_g1_dashboard.py            # THỬ
python backend/scripts/patch_g1_dashboard.py --apply
```

### Bước 5 — Nghiệm thu

```bash
cd backend
python scripts/verify_g1.py
# và sau khi bật server, kiểm tra thêm chính endpoint:
python scripts/verify_g1.py --api http://127.0.0.1:8000 --token <JWT>
```

> **Vì sao phải chạy cả hai lần.** Chạy không có `--api` chỉ kiểm tra **dữ liệu**.
> Ngay lúc này, khi chưa sửa dòng mã nào, T5 và T6 đã ĐẠT — vì mart vốn đã đúng;
> lỗi 6500% nằm ở chỗ `dashboard.py` đọc `disease_cases` thay vì đọc mart. Chỉ
> khi chạy với `--api`, script mới so `last_closed_period` mà endpoint trả về với
> mốc thật trong DB, tức mới kiểm tra được **mã nguồn**.

---

## 2. Ba quyết định thiết kế, và lý do

### 2.1 Không sửa `pipeline.py`, viết module riêng

`DataPipeline.run()` gói toàn bộ staging → dim → fact → mart trong **một
transaction**. Thêm ba luồng vào giữa nghĩa là một lỗi ở luồng mới sẽ rollback cả
phần ca bệnh đang chạy tốt — đúng kiểu lỗi im lặng mà chính hàm
`_build_weather_mart` đã phải viết một đoạn chú thích dài để tránh.

`dss_loader.py` có transaction riêng và được gọi **sau** pipeline chính. Hỏng thì
chỉ ba bảng mới rỗng, mọi thứ khác nguyên vẹn. Khi đã chạy ổn vài tuần thì gọi
`load_all()` ngay sau `DataPipeline.run()` trong `sync_service.py` — nhưng đặt
trong khối `try/except` **riêng**.

### 2.2 Xoá-rồi-chèn theo kỳ, không dùng `INSERT OR REPLACE`

Mỗi kỳ có trong lần kéo bị xoá sạch rồi chèn lại; các kỳ khác giữ nguyên. Chạy
lại mười lần ra đúng một kết quả.

`INSERT OR REPLACE` **không** đủ: nếu bên nguồn một dòng biến mất (toa bị huỷ sau
khi đã đồng bộ) thì REPLACE vẫn để lại dòng cũ ở local, còn xoá-theo-kỳ thì không.

### 2.3 Giữ nguyên tên trường cũ trong response

Toàn bộ khoá cũ được giữ lại — `total_cases_current`, `shortage_supplies_count`,
`overall_risk`, `total_inventory_value`… — để frontend hiện tại không vỡ. Khoá
mới được **thêm vào bên cạnh**. Dọn kiểu TypeScript và bỏ các trường không còn
nghĩa thuộc G5, làm cùng lúc với dashboard v2.

Ba trường đổi *nguồn* nhưng giữ *tên*:

| Trường | Trước | Sau |
|---|---|---|
| `total_supplies` | 5.041 mã danh mục | ~1.900 mã **còn hoạt động** |
| `high_risk_shortages` | đếm theo `safety_stock` (nay luôn = 0) | đếm theo DOI |
| `disease_outbreaks` | `disease_type` có ca trong 7 ngày (luôn = 0) | số nhóm ICD có kỳ chốt cao hơn kỳ trước |

---

## 3. `_classify_risk` — xoá hàm, giữ chức năng

Hàm cũ **không sai về quy tắc**. Nó sai vì **đầu vào**: nhận
`predicted_trend_pct = 6500` (do so kỳ đang mở với kỳ đã chốt) nên luôn trả "Cao".

Quy tắc chuyển sang `period_service.assess_overall_risk()` với hai sửa đổi:
đầu vào là xu hướng giữa hai kỳ **đã chốt**, và ngưỡng tồn kho lấy từ đếm DOI thay
vì từ `safety_stock` đã bị vô hiệu hoá.

Nó vẫn là **quy tắc do người đặt**, chưa suy ra từ dữ liệu — nên trả kèm
`overall_risk_basis` và `overall_risk_is_provisional: true` để giao diện nói rõ
căn cứ thay vì hiện một chữ "Cao" không giải thích được. G2 sẽ thay bằng so sánh
với khoảng dự báo; lúc đó "Cao" mới có nghĩa thống kê.

---

## 4. `stock_signal_counts()` — bản tạm, có chủ đích

Hàm này đếm Đỏ/Vàng/Xanh/Xám theo `DOI = tồn / nhu cầu ngày`. **Đây chưa phải
tầng cảnh báo thật.** Bản đầy đủ ở G4 khác ở ba điểm:

- tồn hữu dụng theo **FEFO** (loại lô hết hạn trong cửa sổ bảo vệ);
- tách `level_reason` ba nhánh — đặc biệt **"tồn = 0 do đã ngừng dùng"**, nhóm
  chiếm **25,8%** danh mục và *không* phải hàng sắp hết. Ở bản tạm nhóm này được
  đếm riêng vào `zero_stock`, không nhập vào Đỏ;
- ngưỡng riêng theo từng mã (chu kỳ nhập của chính mã đó — Đ9-F).

Lý do vẫn làm ở G1: phép đếm cũ dựa trên `safety_stock`, cột đã bị vô hiệu hoá ở
G0, nên nếu không thay thì mọi thẻ KPI về tồn kho sẽ hiện 0 và trông như hệ thống
hỏng.

**Mã không có mẫu số nhu cầu → `grey`, tuyệt đối không phải `green`.** Nếu để rơi
vào green thì hàng nghìn mã chưa có tiêu hao sẽ hiện màu xanh và dashboard trông
rất đẹp mà hoàn toàn vô nghĩa.

---

## 5. Nếu có bước hỏng

| Triệu chứng | Nghi ngờ đầu tiên |
|---|---|
| `run_dss_load.py` báo `Invalid object name 'vw_MedForecast_TieuHaoTong'` | Chưa chạy `G1_01_STA_sua_bang.sql`, hoặc chạy nhầm database |
| Nạp được 0 dòng, không lỗi | Thủ tục PROD chưa chạy — `EXEC usp_MedForecast_DayTieuHaoToanVien` |
| `SELECT permission was denied` | Chưa GRANT ba view (bước 1) |
| **T4 ra ~100%** | `so_luong_hohap` đang bằng `so_luong_toan_vien` → nguồn vẫn là bảng cũ |
| **T4 ra ~0%** | Bộ lọc ICD bên SP không khớp mã nào |
| **T2 ra ~650 thay vì ~1.900** | Pipeline vẫn nạp bảng tiêu hao cũ (chỉ hô hấp) |
| `patch_g1_dashboard.py` báo "không thấy mốc" | `dashboard.py` đã sửa tay — script bỏ qua chứ không đoán; sửa tay theo `NEW_*` trong chính script |

Quay lại: `git checkout -- backend/app/api/v1/dashboard.py`

---

## 6. Còn thiếu gì để đóng G1

Sáu tiêu chí trong `verify_g1.py`. Hiện tại **T5 và T6 đã ĐẠT**; T1–T4 chờ dữ
liệu được nạp.

Thêm hai điểm cần nhìn ở phần "Thông tin bổ sung" sau khi nạp xong:

- **Bảng tỷ trọng phân cấp chăm sóc** — đây là **cổng chặn N1**. J09-J18 (viêm
  phổi) phải nặng hơn J00-J06 (viêm hô hấp trên) một cách rõ rệt. Nếu ba nhóm cho
  tỷ trọng gần như nhau thì `PHANCAPCHAMSOC_ID` không phản ánh độ nặng, và **Tầng
  2 phải thiết kế lại trước khi sang G3**.
- **Số mã có tiêu hao nhưng không có trong `dim_supply`** — đo trước đó là 311.
  Quyết định bổ sung danh mục hay bỏ qua, và ghi lại lý do.
