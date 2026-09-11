# G1 — Nguồn dữ liệu và mốc thời gian

## 0. Đọc trước: số đo đã đổi hai quyết định

### 0.1 Ngưỡng 18 / 36 là đúng — và tôi đã lo hơi sớm

Khi mới nhìn con số "tỷ trọng hô hấp toàn viện 7,80%", tôi tính nhẩm rằng sửa
mẫu số sẽ làm hơn 70% danh mục chuyển sang cảnh báo và dashboard thành bức tường
đỏ. **Tính lại trên dữ liệu thật thì không phải vậy** — sai số đến từ chỗ tôi đã
tính cả những mã không đối chiếu được với danh mục ứng dụng như thể chúng có tồn
bằng 0.

Kết quả đúng, trên **1.250 mã** của Đ10-D đối chiếu được với danh mục local:

| Mẫu số | DOI p25 | **p50** | p75 | p90 |
|---|---|---|---|---|
| Chỉ hô hấp *(bản cũ)* | 0 | **53,8** | 900 | 4.973 |
| Toàn viện *(bản sửa)* | 0 | **22,3** | 56,2 | 123,8 |

Phân mức với ngưỡng mới, tách riêng nhóm tồn = 0:

| | tồn = 0 | Đỏ | Vàng | Xanh |
|---|---|---|---|---|
| ngưỡng cũ 7 / 14 | 323 (25,8%) | 138 (11,0%) | 53 (4,2%) | 736 (58,9%) |
| **ngưỡng mới 18 / 36** | 323 (25,8%) | **235 (18,8%)** | **236 (18,9%)** | 456 (36,5%) |

**Băng Vàng 18,9% — vượt xa cổng chặn ≥ 3% của G4.** Ngưỡng 18/36 giữ nguyên,
chốt vào cấu hình.

Ba con số cần nhớ khi bước vào G4:

- **323 mã (25,8%) có tồn = 0.** Đây *không phải* "sắp hết". Trung vị của nhóm
  này là 6/13 tháng có xuất, 102 mã chỉ xuất ≤ 4 tháng — phần lớn là hàng đặt
  theo nhu cầu hoặc đã ngừng dùng. Chỉ 42 mã xuất ≥ 10 tháng mà tồn 0, và *đó
  mới* là đỏ thật. Việc tách `level_reason` ba nhánh ở G4 vì vậy không phải chi
  tiết phụ — nó quyết định hơn một phần tư số dòng cảnh báo.
- **235 mã đỏ mà còn hàng** — danh sách hành động thật sự, quy mô hợp lý.
- **311 mã trong Đ10-D không có trong danh mục local.** Mã mới hoặc chưa đồng
  bộ. Kiểm tra ở cổng nghiệm thu G1.

### 0.2 Ngưỡng phẳng báo muộn cho hàng luân chuyển chậm

Đ9-D cho thấy chu kỳ nhập chênh **7,5 lần** giữa các nhóm:

| Nhóm | Số mã | Chu kỳ TB |
|---|---|---|
| rất đều (≥24 lần/24 tháng) | 677 | 14,0 ngày |
| đều (12–23) | 677 | 21,4 |
| vừa (6–11) | 638 | 30,1 |
| thưa (3–5) | 593 | 50,1 |
| rất thưa (1–2) | 825 | 104,5 |

Một mã có chu kỳ nhập 30 ngày mà chỉ báo đỏ khi còn 18 ngày hàng thì **đã quá
trễ để kịp đợt nhập kế tiếp**. Trong bệnh viện, báo muộn nguy hiểm hơn báo thừa.

Cách sửa rẻ: ngưỡng đỏ theo **từng mã** = chu kỳ nhập của chính mã đó, lùi về 18
ngày khi không đo được (số lần nhập < 6). Câu lệnh xuất dữ liệu đó là **Đ9-F**,
nằm ở cuối `G1_02_PROD_store_tieuhao_toanvien.sql` (đang để trong khối chú
thích, bỏ `/*` `*/` để chạy). Vẫn là **đo một lần, xuất CSV** — không dựng bảng
đồng bộ, không theo dõi nhà cung cấp.

### 0.3 Điều chỉnh thiết kế lớn nhất: hai tập mã gần như không giao nhau

Trên **30 mã tiêu hao lớn nhất toàn viện**, trung vị tỷ trọng hô hấp chỉ **0,8%**
— và chỉ **4/30** mã đạt ≥ 25%.

Nghĩa là mã chi phối khối lượng kho và mã do dịch hô hấp lái là hai tập khác
nhau. Nếu dashboard xếp hạng theo khối lượng hoặc giá trị, nó sẽ bị lấp đầy bởi
nhóm thứ nhất, và **phần dự báo dịch tễ — đóng góp chính của đề tài — trở nên vô
hình**. Người dùng sẽ hỏi đúng câu hội đồng sẽ hỏi.

Xử lý: không bỏ nhóm kia (chúng vẫn cần cảnh báo tồn kho), nhưng tách thành hai
tập có nhãn rõ và cho lọc được. `G1_03` tạo sẵn hai view:

- `v_supply_active` — **danh mục còn hoạt động** (~1.900 mã). Là mẫu số đúng của
  mọi tỷ lệ phần trăm. Con số "độ phủ 22,9% trên 5.041 mã" tôi ghi trong hợp
  đồng dữ liệu dùng mẫu số sai — sửa lại theo view này.
- `v_supply_focus` — **tập trọng tâm**, tỷ trọng hô hấp ≥ 25% và ≥ 3 kỳ có xuất
  (≈ 547 mã theo Đ10-B). Đây là tập mà luận điểm của đề tài thật sự đúng.

---

## 1. Bốn tệp và thứ tự chạy

| # | Tệp | Chạy ở đâu | Ghi? |
|---|---|---|---|
| 1 | `G1_01_STA_sua_bang.sql` | STA · `MEDFORECAST_DW` | DDL |
| 2 | `G1_02_PROD_store_tieuhao_toanvien.sql` | HIS PROD | Tạo thủ tục |
| 3 | *(sửa tay 2 chỗ trong SP ca bệnh — mục 3 dưới)* | HIS PROD | — |
| 4 | `G1_03_LOCAL_cau_hinh.sql` | `medforecast.db` | **Có — sao lưu trước** |
| 5 | `G1_05_STA_quyen_trang_thai.sql` (11/09) | STA · `MEDFORECAST_DW` | GRANT SELECT `MF_Watermark`/`MF_SyncLog` cho `medforecast_app` — thẻ "Trạng thái dữ liệu" trên Dashboard cần |

```bash
cp backend/data/medforecast.db backend/data/saoluu_truoc_G1_medforecast.db
```

### Bước 1 — STA

Dựng lại `MF_TieuHao_Tong` với hai cột lượng (toàn viện / hô hấp) và hai cột
tính sẵn (`d_baseline_thang`, `ty_trong_hohap`). Kiểm tra cuối file phải in ra
13 cột.

### Bước 2 — PROD, thủ tục tiêu hao toàn viện

```sql
-- xem trước, đối chiếu với Đ10 đã chạy
EXEC dbo.usp_MedForecast_DayTieuHaoToanVien @SoThang = 12, @ChiXem = 1;
```

Bảng phân bố tỷ trọng phải ra gần giống Đ10-B: `≥75%` ~110 · `50-75%` ~179 ·
`25-50%` ~258 · `10-25%` ~211 · `<10%` ~1.143. **Lệch nhiều thì dừng** — bộ lọc
ICD hoặc cửa sổ thời gian đang khác.

```sql
EXEC dbo.usp_MedForecast_DayTieuHaoToanVien;      -- nạp thật, 24 tháng
```

Lịch chạy: **mỗi tuần**, không cần hằng ngày. Nếu chạy lâu, hạ `@SoThang` xuống
12 rồi 6 — nhu cầu nền trên 12 tháng đã đủ ổn định.

> **Vì sao là thủ tục riêng chứ không nhét vào `usp_MedForecast_DayDuLieu`:**
> khác vũ trụ dữ liệu (toàn viện so với ba nhóm ICD), khác cửa sổ thời gian (24
> tháng so với từ 2019), khác nhịp chạy (tuần so với ngày). Nhét chung thì lần
> chạy `@NapLaiToanBo = 1` sẽ quét bảy năm toa thuốc toàn viện và gần như chắc
> chắn treo. Kết quả nghiệp vụ vẫn đúng yêu cầu: `MF_TieuHao_Tong` được nạp
> **không lọc ICD**, làm nguồn cho `D_baseline`.

### Bước 3 — Gỡ khối 7f khỏi SP ca bệnh (sửa tay, 2 chỗ)

`Phase0_02_PROD_store_cabenh_v2.sql` có một khối `#KQTT` tính tiêu hao tổng
**trong phạm vi bệnh đích** — nay đã bị thủ tục mới thay thế và phải gỡ, nếu
không hai luồng sẽ ghi đè nhau lên cùng một bảng.

**Chỗ 1** — xoá cả khối, từ dòng bắt đầu bằng

```
        /* =====================================================================
           ★ 7f) #KQTT — tiêu hao theo (tháng × vật tư), bỏ chiều bệnh
```

tới hết dòng

```
        SELECT @nDongTieuHaoTong = COUNT(*) FROM #KQTT;
```

**Chỗ 2** — trong khối đẩy, xoá đoạn:

```
            IF @nNhomDich >= 3
            BEGIN
                DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TieuHao_Tong]
                WHERE  Period >= @TuNgay;
                ...
            END
            ELSE
                PRINT N'Bỏ qua MF_TieuHao_Tong: ...';
```

Giữ nguyên phần đẩy `MF_CaBenh_PhanCap` và `MF_TieuHao_PhanCap` — hai luồng đó
vẫn đúng và vẫn cần.

Biến `@nDongTieuHaoTong` còn lại trong câu `PRINT` và `INSERT ... MF_SyncLog` sẽ
luôn bằng 0; để nguyên cũng chạy được, hoặc gỡ cho sạch.

### Bước 3b — Gọt thủ tục kho

`Phase0_03_PROD_store_khocungung.sql` có ba luồng, nay chỉ còn cần **một**:

- **Giữ** `MF_TonKho_Lo` — nền của FEFO, Đ1 đã xác nhận khả thi.
- **Bỏ** `MF_LichSuNhap` và `MF_VatTu_ThuocTinh` — thuộc phân hệ mua sắm đã cắt.
- **Bỏ** toàn bộ khối Đ8 dò bảng đơn đặt hàng ở đầu tệp.

Cách nhanh: giữ phần 1 (`#Meta`) và phần 2 (`#Lo`), xoá phần 3 (`#Nhap`), phần 4
(`#ThuocTinh`) và các khối đẩy tương ứng; đổi tên thủ tục thành
`usp_MedForecast_DayTonKhoLo`.

### Bước 4 — Local

```bash
cd backend
sqlite3 data/medforecast.db ".read ../sql_his/phase0/G1_03_LOCAL_cau_hinh.sql"
```

Tạo `fact_usage_total`, ghi ngưỡng 18/36 vào `system_config` khoá
`dss.thresholds`, và dựng ba view dùng chung. Script **chạy lại được nhiều lần**
(đã kiểm chứng).

---

## 2. Phần còn lại của G1 — sửa mã, không có script

Bốn việc này phải sửa tay trong `backend/`:

1. **Nạp dữ liệu.** `data_pipeline/connectors.py` + `pipeline.py` đọc thêm
   `vw_MedForecast_TieuHaoTong` (và ba view phân cấp) từ STA vào
   `fact_usage_total` / `fact_cases_by_care_level` / `fact_usage_by_care_level`.
2. **Neo mốc thời gian.** `api/v1/dashboard.py` — mọi KPI lấy
   `max(period) WHERE is_complete = 1`, thay cho `max(DiseaseCase.recorded_at)`.
   Hiện T9/2026 là kỳ đang mở với 3 ca trong khi T8 có 341 → xu hướng 6500%, và
   `_classify_risk(6500, 17)` trả về "Cao" mỗi lần chạy.
   Vị trí: `:653` (`/summary`), `:238` (`/overview`), `:771` (`/case-trend`).
3. **Một nguồn số ca duy nhất:** `mart_monthly_cases_by_block`. Bỏ mọi truy vấn
   KPI đọc thẳng `disease_cases`.
4. **Xoá `_classify_risk`** (`dashboard.py:644`).

---

## 3. Cổng nghiệm thu G1

- [ ] `/summary` trả `last_closed_period = "2026-08"` và `open_period = "2026-09"`
- [ ] `|cases_trend_pct| < 100` trên cả 24 kỳ lịch sử
- [ ] **Tổng `fact_usage_total` lớn hơn rõ rệt tổng `fact_supply_usage`.** Bằng
      nhau nghĩa là bộ lọc ICD vẫn còn — sửa chưa xong.
- [ ] `SELECT COUNT(*) FROM v_supply_active` ra **~1.900**, không phải ~650.
      Ra ~650 nghĩa là pipeline vẫn nạp bảng tiêu hao cũ.
- [ ] `AVG(ty_trong_hohap)` trong `v_supply_daily_demand` quanh **7–10%**. Ra
      ~100% nghĩa là `so_luong_hohap` đang được nạp bằng chính
      `so_luong_toan_vien`.
- [ ] `SELECT COUNT(*) FROM v_supply_focus` ra **~547**
- [ ] Đếm số mã trong `fact_usage_total` **không có** trong `dim_supply` — đối
      chiếu với 311 mã đã phát hiện; quyết định bổ sung danh mục hay bỏ qua

---

## 4. Trạng thái G0

**Đã giao ở lượt trước, không cần làm lại.** Ba tệp đang nằm trong repo:

| Tệp | Vị trí |
|---|---|
| `G0_cat_pham_vi.py` | thư mục gốc repo |
| `G0_HuongDan.md` | `sql_his/phase0/` |
| `MedForecast_D9_D10.sql` | `sql_his/phase0/` (đã chạy xong) |

Script đã **chạy thử trên đúng bản mã hiện tại — 15/15 phép sửa khớp chính xác**,
và với `--strip-masterdata` thì thêm 4 phép nữa cũng khớp hết. Chạy:

```bash
cd D:\Personnal\LienThong\CDTN\webyte\webyte
python G0_cat_pham_vi.py                 # thử
python G0_cat_pham_vi.py --apply
```

Tóm tắt phạm vi: **xoá** `app/procurement/` · `api/v1/procurement.py` ·
`test_procurement_api.py` · `models/procurement_plan.py`. **Sửa** `main.py` ·
`models/__init__.py` · `schemas/__init__.py` · `schemas/base.py` ·
`api/v1/inventory.py` (cắt vòng ghi ngược `safety_stock`) · `api/v1/reports.py` ·
`Sidebar.tsx`.

Bốn thứ script **cố ý không làm**, lý do đầy đủ trong `G0_HuongDan.md`: không xoá
trang `SupplyPlanning.tsx` (giao diện duy nhất của dự báo phân cấp), không xoá
~550 dòng trình bày báo cáo (khung cho báo cáo DOI ở G5), không đụng
`ai_engine` (mã chết, G2 thay toàn bộ), không drop bảng `procurement_plans`.
