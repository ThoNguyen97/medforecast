# ĐÁNH GIÁ ĐỒNG NHẤT: CSDL STA ↔ THỦ TỤC PROD ↔ BACKEND

**Ngày:** 11/09/2026 · **Đầu vào:** ảnh chụp cấu trúc `MEDFORECAST_DW` trên STA (12 bảng, 10 view), hai thủ tục **đang chạy thật** trên PROD (`usp_MedForecast_DayDuLieu`, `usp_MedForecast_DayTieuHaoToanVien`), mã backend nhánh `tai-cau-truc-2026-09`.
**Cách làm:** diff văn bản thủ tục PROD với bản trong repo; bóc DDL của STA từ ba script theo thứ tự áp dụng (01_STA → Phase0_01 → G1_01) và đối chiếu tự động với (a) cột thủ tục ghi vào, (b) cột backend SELECT ra, (c) tên đối tượng trên ảnh chụp; rồi kiểm tra tay các ràng buộc ngữ nghĩa mà đối chiếu cấu trúc không thấy được.

---

## KẾT LUẬN NGẮN

**Về cấu trúc: đồng nhất — không có lệch cột nào ở cả ba tầng.** Đây là kết quả tốt hơn tôi dự đoán ở đợt rà soát 09/09.

**Về ngữ nghĩa và vận hành: còn 4 chỗ lệch, trong đó 2 chỗ khiến backend chưa thực sự "nói cùng ngôn ngữ" với thủ tục.** Không chỗ nào làm sai số liệu hôm nay; cả bốn đều thuộc loại *im lặng khi hỏng* — đúng loại lỗi mà kiến trúc DSS này đã cố tránh ở tầng khác.

| Tầng đối chiếu | Kết quả |
|---|---|
| Thủ tục PROD ↔ bản trong repo | ✅ Trùng nội dung. Chỉ khác chú thích, `ALTER` thay `CREATE OR ALTER`, và **1 kiểu tham số** |
| Kho đối tượng STA (ảnh) ↔ DDL repo | ✅ 12/12 bảng, 10/10 view — kể cả `MF_MapVatTu` |
| Cột thủ tục INSERT/UPDATE ↔ DDL | ✅ 12/12 bảng, 100% cột tồn tại; 2 cột tính sẵn đúng như thủ tục ghi chú |
| Cột backend SELECT ↔ cột view | ✅ 7/7 file SQL, 100% cột tồn tại |
| Ánh xạ mã `MF_MapVatTu` | ✅ Áp nhất quán ở cả 8 view có `supply_code` |
| Mốc `MF_Watermark` | ✅ 4 luồng đều có dòng seed |
| Cửa sổ nạp lại 3 tháng | ✅ Khớp ở cả ba nơi (`@SoThangLuiLai`, `sync_config`, `dss_loader`) |
| **Nút "Đồng bộ" nạp 4 luồng DSS** | ❌ **Chưa** — chỉ nạp qua CLI |
| **Backend đọc trạng thái PROD→STA** | ❌ **Không đọc** `MF_SyncLog` / `MF_Watermark` |
| **Hợp đồng `is_vtyt`** thủ tục yêu cầu | ❌ Tầng quyết định chưa xử lý (tiềm ẩn) |
| Thứ tự chạy script STA | ⚠ Chạy lại `Phase0_01` sau `G1_01` sẽ **lùi view** |
| Quy ước đặt tên cột | ⚠ Ba kiểu trộn lẫn; chưa có tuyên bố quy ước |

---

## 1. NHỮNG GÌ ĐÃ KHỚP — bằng chứng

### 1.1 Thủ tục PROD trùng repo
- `usp_MedForecast_DayDuLieu` (964 dòng) ↔ `sql_his/phase0/G1_00_PROD_store_cabenh_v3.sql`: 42 dòng khác, **toàn bộ là chú thích** đầu/cuối và `ALTER PROCEDURE` thay `CREATE OR ALTER`.
- `usp_MedForecast_DayTieuHaoToanVien` (273 dòng) ↔ `G1_02_PROD_store_tieuhao_toanvien.sql`: 106 dòng khác — chú thích + một khối `DECLARE` gỡ lỗi để lại + **một lệch thật**: `@BENHVIEN_ID VARCHAR(8)` trên PROD, `INT` trong repo (xem mục 2.5).

Nghĩa là bản trong repo **là** bản đang chạy — người phản biện mở repo đọc thủ tục sẽ đọc đúng thứ bệnh viện đang dùng.

### 1.2 Ba lớp cột khớp 100%
Bảng dưới là kết quả đối chiếu tự động sau khi bóc chú thích khỏi DDL:

| Bảng STA | Cột thủ tục ghi / cột DDL | Ghi chú |
|---|---|---|
| MF_CaBenh_VatTu | 15/15 | |
| MF_CaBenh_Nhom | 7/7 | |
| MF_CaBenh_PhanCap | 7/7 | |
| MF_TieuHao_PhanCap | 13/13 | |
| MF_TieuHao_Tong | 11/13 | 2 cột còn lại là **tính sẵn** (`d_baseline_thang`, `ty_trong_hohap`) — đúng như chú thích trong thủ tục |
| MF_TonKho | 9/9 | |
| MF_TonKho_Lo · MF_LichSuNhap · MF_VatTu_ThuocTinh | 12/12 · 19/19 · 17/17 | thủ tục `DayKhoCungUng` |
| MF_Watermark · MF_SyncLog | 2/3 · 8/9 | cột còn lại là khoá / mặc định |

Bảy file SQL của backend (`case_sta`, `case_group_sta`, `inventory_sta`, `cases_care_level_sta`, `usage_care_level_sta`, `inventory_lot_sta`, `usage_total_sta`) — mọi cột SELECT đều có trong view tương ứng. `usage_total_sta.sql` đọc đúng 12 cột của bản view G1_01, gồm hai cột tính sẵn.

### 1.3 Ánh xạ mã vật tư nhất quán
`MF_MapVatTu` (HIS → app) được áp qua `ISNULL(m.MaApp, t.supply_code)` ở **cả 8 view** có `supply_code`. Không có view nào "quên" ánh xạ — nếu có, mã của cùng một vật tư sẽ khác nhau giữa các bảng fact và ghép không được.

---

## 2. NHỮNG GÌ CHƯA ĐỒNG NHẤT

### 2.1 · [CAO] Nút "Đồng bộ" không nạp 4 luồng DSS mà thủ tục sinh ra
`sync_service.run_sync()` chỉ gọi `DataPipeline.run()` (luồng CaBenh/TonKho cũ) rồi `_lam_moi_bang_nghiep_vu()`. **Không có dòng nào gọi `dss_loader.load_all`.** Bốn luồng `usage_total`, `cases_care_level`, `usage_care_level`, `inventory_lot` — chính là đầu ra của Phase 0/G1 mà hai thủ tục đẩy xuống STA — chỉ nạp được qua `python scripts/run_dss_load.py` chạy tay.

Hệ quả: thủ tục PROD có thể chạy hằng ngày, STA có dữ liệu mới, người vận hành bấm "Đồng bộ" thành công — nhưng `fact_usage_total`, `fact_cases_by_care_level`, `fact_inventory_lot` **đứng yên**, và Dashboard DSS chạy trên số cũ mà không có dấu hiệu nào.

Đây là mục 2.7 trong kế hoạch Tuần 2 tôi đã ghi nhưng **chưa làm**. Việc sửa: thêm một khối `try/except` gọi `dss_loader.load_all(self.db, connector)` trong `run_sync`, trả `flows` vào kết quả để UI hiện trạng thái từng luồng. Khoảng 30 dòng.

### 2.2 · [CAO] Backend mù trạng thái PROD→STA
Hai thủ tục ghi rất tử tế vào `MF_SyncLog` (trạng thái `ok`/`failed`, thông điệp có số dòng, tỷ trọng, ô đã gộp) và `MF_Watermark` (`MocDaDay`, `LanChayCuoi` theo từng luồng). **Backend không đọc bất kỳ cột nào trong hai bảng này** (grep `MF_Watermark|MF_SyncLog|MocDaDay|LanChayCuoi` trong `backend/app` = 0).

Nghĩa là nếu job trên PROD lỗi ba ngày liền, STA giữ nguyên dữ liệu cũ, backend đồng bộ "thành công" dữ liệu cũ đó, và màn hình hiện số ba ngày trước với nhãn "đã đồng bộ hôm nay". Toàn bộ chuỗi chốt chặn công phu trong thủ tục (THROW 50001–50023, bất biến tỷ trọng, bất biến khử trùng) **không có đường lên tới giao diện**.

Việc sửa: `sync_service` đọc `MF_Watermark` (mốc dữ liệu từng luồng) và dòng `MF_SyncLog` mới nhất theo luồng, trả về trong API trạng thái đồng bộ: *"Dữ liệu STA đến kỳ 2026-08 · lần đẩy PROD cuối 11/09 03:02 · ok"*. Nếu `failed` thì hiện thông điệp lỗi của thủ tục. Một câu SQL và ~20 dòng.

### 2.3 · [TRUNG BÌNH] Hợp đồng `is_vtyt` chưa được tầng quyết định tôn trọng
Thủ tục `DayDuLieu` ghi rõ (mục D phần đầu): *"y lệnh VTYT … KHÔNG mang phân cấp chăm sóc, nên với các dòng `is_vtyt = 1` thì tầng sau PHẢI gộp NT1+NT2+NT3+NT0 lại trước khi chia định mức. Cột `is_vtyt` trong bảng đầu ra chính là để tầng sau biết mà gộp."*

`dss_loader` mang cột `is_vtyt` xuống `fact_usage_by_care_level` đúng. Nhưng `dss_demand.py` **không có bất kỳ tham chiếu nào tới `is_vtyt`** — nó chia mọi dòng theo rổ `ro` như nhau.

Hôm nay lỗi này **tiềm ẩn** vì `@GomVTYT = 0` mặc định ở `DayDuLieu` (chỉ thuốc). Nhưng `DayTieuHaoToanVien` mặc định `@GomVTYT = 1` — nên `fact_usage_total` (mẫu số DOI) **có** VTYT còn định mức theo ca **không có**. Đó là chủ ý đúng (DOI phải phủ mọi thứ trong kho). Vấn đề chỉ nổ khi ai đó bật `@GomVTYT = 1` cho `DayDuLieu` để lấy định mức VTYT: khi đó VTYT bị chia sai theo rổ mà không báo gì.

Việc sửa: trong `dss_demand`, khi gặp `is_vtyt = 1` thì gộp rổ về một, hoặc tối thiểu `chan_doan_dinh_muc()` phải cảnh báo "có dòng VTYT theo rổ — chưa xử lý". ~15 dòng, và nó đóng đúng hợp đồng mà thủ tục đã viết.

### 2.4 · [TRUNG BÌNH] Thứ tự chạy script STA có bẫy lùi phiên bản
`vw_MedForecast_TieuHaoTong` được định nghĩa ở **hai** file, cả hai đều `CREATE OR ALTER`:
- `Phase0_01_STA_bang_moi.sql`: 9 cột (`so_luong`, không có `so_luong_toan_vien`/`so_luong_hohap`/hai cột tính sẵn)
- `G1_01_STA_sua_bang.sql`: 12 cột — bản đang chạy, bản backend đọc

Bảng `MF_TieuHao_Tong` thì an toàn (`Phase0_01` có `IF NOT EXISTS`, `G1_01` `DROP` rồi tạo lại). Nhưng **view thì không**: chạy lại `Phase0_01` sau `G1_01` — ví dụ khi dựng STA mới theo hướng dẫn "chạy Phase0 rồi G1", hoặc ai đó chạy lại Phase0 "cho chắc" — sẽ lùi view về 9 cột. Khi đó `usage_total_sta.sql` lỗi cột, `dss_loader` ghi `{"status":"failed"}` vào log rồi **chạy tiếp với `fact_usage_total` cũ**. Cùng loại im lặng như 2.1.

Việc sửa: xoá định nghĩa view khỏi `Phase0_01` (để `G1_01` là chủ duy nhất), và `verify_g1.py` kiểm đủ 12 cột trước khi `load_all`.

### 2.5 · [THẤP] Kiểu tham số `@BENHVIEN_ID` lệch giữa hai thủ tục PROD
`DayDuLieu`: `INT` · `DayTieuHaoToanVien` trên PROD: `VARCHAR(8)` · repo và `DayKhoCungUng`: `INT`. Với mặc định `NULL` thì vô hại; nếu đặt `79428` thì so sánh `INT = VARCHAR` ép kiểu ngầm — vẫn đúng nhưng không nhất quán. Chạy lại bản repo (`CREATE OR ALTER`) là hết.

### 2.6 · [THẤP] Dữ liệu thủ tục đẩy xuống nhưng backend không đọc
`vw_MedForecast_LichSuNhap`, `vw_MedForecast_VatTuThuocTinh`, `vw_MedForecast_TonKhoLo` (bản có lịch sử) — thủ tục `DayKhoCungUng` nạp đầy đủ (σ lead-time, MOQ, tỷ lệ giao đủ), backend không có luồng nào đọc. Đã ghi trong rà soát 09/09; với quyết định "DSS thuần" thì đây là dữ liệu cho giai đoạn sau, không phải lỗi — nhưng nên nói rõ trong tài liệu STA rằng ba view này "dự phòng cho ABC-XYZ", để người sau không tưởng là bị bỏ sót.

---

## 3. VỀ "CHUẨN HOÁ" — QUY ƯỚC ĐẶT TÊN

Đếm trên 129 cột của 12 bảng STA:

| Kiểu | Số cột | Ví dụ |
|---|---|---|
| PascalCase tiếng Việt | 29 | `Period`, `NgayCapNhat`, `MocDaDay`, `TenLuong`, `BatDau`, `SoDongCaBenh` |
| snake_case tiếng Anh | 60 | `supply_code`, `disease_group`, `region`, `cases`, `stock_quantity` |
| snake_case tiếng Việt | 40 | `so_luong_toan_vien`, `so_luong_hohap`, `ty_trong_hohap`, `ten_hoat_chat`, `don_gia_von` |

Ba kiểu trong một schema **không phải lỗi**, nhưng hiện không có tuyên bố quy ước nào, nên người đọc không biết đó là chủ ý hay tuỳ tiện. Nhìn kỹ thì có một logic ngầm khá hợp lý:
- Cột **vận hành** (mốc, nhật ký, thời điểm cập nhật) → PascalCase Việt
- Cột **hợp đồng với app** → snake_case

Nhưng logic đó bị phá ở chỗ cột hợp đồng lại trộn Anh (`quantity`… trong DDL cũ) và Việt (`so_luong`, `so_luong_hohap`) — cùng một khái niệm "số lượng" có hai tên tuỳ bảng.

**Khuyến nghị trước bảo vệ: KHÔNG đổi tên.** Đổi tên cột lúc này chạm vào thủ tục PROD, view, 7 file SQL backend, `dss_loader.map`, và mọi bảng fact — rủi ro lớn, lợi ích chỉ là thẩm mỹ. Thay vào đó, **viết quy ước thành một mục trong `sql_his/README.md`**: cột vận hành PascalCase-Việt; cột hợp đồng snake_case; các cột snake_case-Việt (`so_luong_*`, `ty_trong_*`, `ten_hoat_chat`) là **thuật ngữ nghiệp vụ giữ nguyên tiếng Việt có chủ ý** để khoa Dược đọc được. Nói được lý do là đủ để bảo vệ.

---

## 4. TRẠNG THÁI XỬ LÝ (cập nhật cùng ngày)

| # | Việc | Trạng thái |
|---|---|---|
| 0 | `@BENHVIEN_ID` | ✅ Cột HIS là `varchar(8)` → sửa **repo** về `VARCHAR(8)` ở cả 8 chỗ (không phải ngược lại như đánh giá ban đầu). Cần chạy lại `G1_00` và `Phase0_03` trên PROD vì bản đang chạy của hai thủ tục đó vẫn `INT` |
| 1 | Nút Đồng bộ nạp 4 luồng DSS | ✅ `run_sync` gọi `dss_loader.load_all`, trả `dss_flows` |
| 2 | Đọc trạng thái PROD→STA | ✅ `trang_thai_sta()` đọc `MF_Watermark` + 8 dòng `MF_SyncLog` mới nhất, kèm `warning` khi lần đẩy cuối `failed`; có trong cả `run_sync` lẫn `get_status` |
| 3 | Hợp đồng `is_vtyt` | ✅ **Làm rộng hơn**: phát hiện `fact_usage_by_care_level` được nạp nhưng **không service nào đọc** — định mức vẫn lấy từ bảng nhập tay 18/18/18. Thêm `empirical_norms()` tính Norm(i,g,ro) = Σ tiêu hao / Σ ca từ hai bảng fact của thủ tục, xử lý `is_vtyt=1` đúng hợp đồng (gộp NT*), rổ mẫu nhỏ lùi về định mức gộp nhóm. `demand_by_supply` ưu tiên nguồn này, ghi `nguon_dinh_muc` |
| 4 | Bẫy thứ tự script | ✅ `Phase0_01` không còn định nghĩa view `TieuHaoTong`; `kiem_tra_ket_noi_sta` kiểm 4 cột G1; `dss_loader` báo rõ khi view lùi phiên bản |

**Kết quả đo trên `medforecast.db` thật sau việc 3** (cửa sổ 12 kỳ 2025-10 → 2026-09):
- Định mức thực nghiệm phủ 628 / 982 / 608 mã cho ba nhóm; **579 / 981 / 569 mã có định mức KHÁC NHAU theo rổ** — chiều độ nặng giờ mang thông tin thật, không còn rỗng.
- Ví dụ J09-J18, mã NACT9: NT1 48,2 · NT2 10,2 · NT3 15,5 đơn vị/ca — gradient lâm sàng đúng chiều.
- Rổ mẫu nhỏ (< 30 ca/12 kỳ) đã lùi về định mức gộp: J00-J06 NT1+NT3, J09-J18 NT3, J20-J22 NT1+NT3.
- `fact_usage_total` và `fact_inventory_lot` hiện **rỗng** trong DB — chính là hậu quả của việc 1; sẽ đầy sau lần Đồng bộ đầu tiên với mã mới.

## 4b. VIỆC NÊN LÀM NGAY — khoảng một buổi, không đụng PROD

| # | Việc | Sửa gì | Vì sao gấp |
|---|---|---|---|
| 1 | Nối `dss_loader.load_all` vào `run_sync` | `sync_service.py` +~30 dòng | Nút Đồng bộ mới thực sự nạp đầu ra của thủ tục |
| 2 | Đọc `MF_Watermark` + `MF_SyncLog` mới nhất, trả về API trạng thái | `sync_service.py` +~20 dòng, 1 câu SQL | Chốt chặn của thủ tục lên được giao diện |
| 3 | `dss_demand` xử lý `is_vtyt = 1` (gộp rổ) hoặc cảnh báo | `dss_demand.py` +~15 dòng | Đóng hợp đồng thủ tục đã viết |
| 4 | Xoá view `TieuHaoTong` khỏi `Phase0_01`; `verify_g1` kiểm 12 cột | 2 file SQL/py | Chặn bẫy lùi phiên bản |
| 5 | Chạy lại `G1_02` trên PROD để `@BENHVIEN_ID` về `INT` | 1 lệnh trên PROD | Nhất quán ba thủ tục |
| 6 | Viết quy ước đặt tên vào `sql_his/README.md` | tài liệu | Trả lời được câu "sao trộn ba kiểu" |

Việc 1–4 tôi làm được ngay trên nhánh hiện tại. Việc 5 cần bạn chạy trên PROD. Việc 6 tôi viết, bạn duyệt.

---

*Đối chiếu tự động bằng script bóc DDL + diff; các kết luận ngữ nghĩa kiểm tra tay trên mã. Không kết luận nào dựa trên suy đoán về nội dung cột thực tế trong STA — ảnh chụp chỉ cho tên đối tượng, còn cột lấy từ DDL repo (đã xác nhận trùng với thủ tục PROD đang chạy).*
