# Kết nối HIS eHospital: PROD → STAGING → MedForecast

```
HIS PROD (eHospital, SQL Server)
    │  thủ tục dbo.usp_MedForecast_DayDuLieu — TỔNG HỢP ngay trên PROD
    │  SQL Agent job 01:00, tổng hợp lại cửa sổ 3 tháng
    ▼  đẩy qua linked server MEDFORECAST_STA
MEDFORECAST_DW (database riêng trên máy chủ STAGING)
    │  MF_CaBenh_VatTu · MF_CaBenh_Nhom · MF_TonKho
    │  MF_Watermark · MF_SyncLog · MF_MapVatTu
    │  vw_MedForecast_CaBenh · vw_MedForecast_CaBenhNhom · vw_MedForecast_TonKho
    ▼  PIPELINE_SOURCE=sqlserver, 02:00
MedForecast (FastAPI + PostgreSQL) → React
```

MedForecast **không bao giờ** kết nối vào PROD.

## Hai lựa chọn thiết kế đáng chú ý

**Tổng hợp trên PROD rồi mới đẩy, không sao chép hồ sơ.** Thủ tục gộp sẵn theo
(tháng × mã ICD × tỉnh × vật tư). Kết quả: khoảng 33.000 dòng thay vì gần 200.000
dòng toa thuốc — và quan trọng hơn, **không có mã bệnh nhân, không có ngày khám
cụ thể, không có họ tên / số định danh / địa chỉ** rời khỏi PROD. Từ database
trung chuyển không thể truy ngược ra một người bệnh cụ thể.

**Database riêng, không dùng chung DB eHospital STA.** STA là môi trường test —
đội khác restore hoặc refresh lại là mất sạch bảng mà không ai báo. Một database
riêng trên cùng máy chủ tránh được chuyện đó.

## Thứ tự chạy

| Script | Chạy ở đâu | Việc |
|---|---|---|
| `00_PROD_xac_nhan_cot.sql` | PROD (chỉ đọc) | Xác nhận 6 điểm phụ thuộc dữ liệu. **Chạy trước tiên.** |
| `01_STA_tao_database_va_bang.sql` | STAGING | Tạo `MEDFORECAST_DW` + 6 bảng + 3 view + tài khoản |
| `02_PROD_linked_server.sql` | PROD | Linked server `MEDFORECAST_STA` trỏ xuống STA |
| `03_PROD_store_tong_hop.sql` | PROD | Thủ tục `usp_MedForecast_DayDuLieu` (chuyển từ query export gốc) |
| `04_PROD_job.sql` | PROD (msdb) | SQL Agent job 01:00 |
| `05_kiem_tra.sql` | STA (mục 5 chạy ở PROD) | Đối chiếu số liệu, độ tươi, chất lượng |
| `06_danh_gia_du_lieu.sql` | STA (mục 6 chạy ở PROD) | Chuỗi có **học được** không: đứt gãy, tháng khuyết, mùa vụ, mẫu số |

Chỗ cần sửa theo môi trường thật được đánh dấu `⚙`.

## Phạm vi bệnh: ba NHÓM ICD, không phải bốn mã lẻ

Đề cương chốt phạm vi là **ba nhóm ICD-10**, dự báo ở cấp nhóm rồi mới phân bổ
xuống từng mã "để tăng độ ổn định trong bối cảnh mỗi mã riêng lẻ có số quan sát
hạn chế":

| Nhóm | Tên | Mã 3 ký tự |
|---|---|---|
| `J00-J06` | Nhiễm khuẩn cấp đường hô hấp trên | J00 J01 J02 J03 J04 J05 J06 |
| `J09-J18` | Cúm và viêm phổi | J09 J10 J11 J12 J13 J14 J15 J16 J17 J18 |
| `J20-J22` | Nhiễm khuẩn cấp đường hô hấp dưới khác | J20 J21 J22 |

Query export ban đầu chỉ lấy **J01, J02, J06, J20** — 4 mã trong tổng số 20, và
**thiếu trọn nhóm J09-J18**. Đó không phải một phạm vi có nghĩa về dịch tễ, chỉ
là bốn mã tình cờ nhiều ca nhất. Thủ tục nay lấy theo nhóm:

```sql
@NhomBenhDich NVARCHAR(400) = N'J00-J06,J09-J18,J20-J22'
```

Danh mục mã lấy thẳng từ **`TM_ICD.PHANNHOM`** của HIS — cột này chính là mã
nhóm. Ba hệ quả: đổi phạm vi là đổi tham số chứ không sửa câu lệnh; tên bệnh lấy
từ `TM_ICD.TENICD` thay vì `CASE` viết cứng bốn dòng; và ứng dụng không còn phải
tra file `TM_ICD.xlsx` nữa vì nhóm đã đi kèm dữ liệu.

Mục 5 và 6 của `00_PROD_xac_nhan_cot.sql` xác nhận `PHANNHOM` dùng được và đo
xem mở rộng phạm vi thêm bao nhiêu ca cho từng mã.

## Số ca của NHÓM không phải tổng số ca các mã con

Đây là chỗ dễ sai nhất khi làm dự báo phân cấp, và sai âm thầm.

Một lượt khám có thể mang J01 (chẩn đoán chính) và J06 (chẩn đoán phụ). Lượt đó
được tính 1 ca cho J01 và 1 ca cho J06 — đúng, vì mô hình theo từng mã cần biết
"lượt khám có chẩn đoán X đã dùng bao nhiêu thuốc". Nhưng **cả hai mã đều nằm
trong nhóm J00-J06**, nên cộng lại thành 2 trong khi nhóm chỉ có 1 lượt.

Không có cách nào sửa việc này ở tầng sau: xuống tới STA thì `TIEPNHAN_ID` đã
mất, không còn gì để đếm `DISTINCT`. Vì vậy thủ tục tính sẵn ở bước **7b** trên
PROD và đẩy xuống bảng riêng:

```
MF_CaBenh_Nhom  (Period × disease_group × region) → cases
```

Dòng `region = 'TOAN_QUOC'` cũng đếm `DISTINCT` riêng, **không** phải tổng các
tỉnh — vì bước gộp ô nhỏ có thể xếp cùng một lượt vào hai nhãn vùng khác nhau ở
hai mã khác nhau.

Phía ứng dụng, `mart_monthly_cases_by_block` trước đây dựng bằng
`groupby(block).sum()` — tức là đang cộng dồn và đếm trùng. Nay pipeline ưu tiên
số do nguồn cấp:

```
PIPELINE_CASE_GROUP_SQL_FILE=case_group_sta.sql
```

Không đặt biến này thì pipeline vẫn chạy nhưng **ghi cảnh báo vào log** rằng số
ca mức nhóm đang bị thổi phồng — không sai âm thầm nữa. Kiểm chứng bằng
`backend/scripts/kiem_tra_so_ca_nhom.py`; mục **2f** của `05_kiem_tra.sql` kiểm
lại trên dữ liệu thật (`cases` mức nhóm phải luôn ≤ tổng các mã con).

## Bốn điểm sai thì hệ thống vẫn chạy nhưng ra số sai

Không có thông báo lỗi nào — đây là loại sự cố khó phát hiện nhất.

**1. Đếm số ca bằng hằng số 1.** Tầng sau lấy `max()` để khử phần lặp theo dòng
vật tư, nên đẩy 1 ca mỗi dòng sẽ làm mọi tháng chỉ còn đúng 1 ca.

**2. Không gom mã ICD về 3 ký tự.** eHospital lưu ICD dưới dạng khoá trỏ sang
`TM_ICD`, và `TM_ICD.MAICD` thường là mã con `J01.0`, `J01.9`. Để nguyên thì tầng
sau gom lại rồi lấy `max()` — ra số của mã con lớn nhất chứ không phải tổng. Đo
trên dữ liệu Gia An: J01 đúng **3.418 ca**, để nguyên mã con chỉ còn **1.886** —
thiếu 45%. Thủ tục dùng `LEFT(..., 3)` ở cả chẩn đoán chính lẫn phụ.

**3. Lọc ngày bằng hàm định dạng trong `WHERE`.** Mất index, quét toàn bảng trên
máy chủ production. Luôn so sánh thẳng trên `kb.NGAYKHAM`.

**4. Quên lọc `BENHVIEN_ID` khi DB có nhiều bệnh viện.** eHospital là hệ thống
nhiều bệnh viện. Query gốc không lọc — hợp lý nếu DB chỉ có một. Chạy mục 1 của
script 00 để biết chắc; nếu ra nhiều hơn một dòng thì truyền `@BENHVIEN_ID = 79428`
vào thủ tục và vào job.

## Thủ tục đến từ đâu

`03_PROD_store_tong_hop.sql` **không phải mình tự viết** — nó là câu truy vấn
export dataset mà nhóm đã dùng và đã chạy đúng trên DB thật, giữ nguyên logic
nghiệp vụ. Phần thêm vào chỉ là cơ chế đồng bộ: tham số hoá khoảng thời gian,
nạp tăng dần theo mốc, đẩy xuống STA qua linked server, ghi nhật ký, gộp thêm
luồng tồn kho, và chế độ `@ChiXem = 1` để đối chiếu với query gốc trước khi bật job.

**Bắt buộc chạy đối chiếu trước** (mục 0 của `05_kiem_tra.sql`): chạy thủ tục ở
chế độ chỉ xem, chạy query gốc, so số dòng và `SUM(supply_quantity)`. Khớp rồi
mới đẩy.

## Một đặc điểm cần biết khi đọc số

Một lượt khám có thể mang nhiều mã trong 4 bệnh (J01 chính + J06 phụ chẳng hạn).
Khi đó lượt đó được tính vào **cả hai** mã, và lượng thuốc của lượt đó cũng được
gán cho cả hai. Vì vậy tổng `cases` và tổng `supply_quantity` **cộng dồn qua 4
bệnh sẽ lớn hơn số thực tế** của bệnh viện.

Đây là lựa chọn có chủ đích: mô hình dự báo theo từng bệnh cần biết "lượt khám có
chẩn đoán X đã dùng bao nhiêu thuốc", không phải chia phần thuốc cho các bệnh
đồng mắc. Nhưng khi đối chiếu với báo cáo tổng của phòng KHTH thì phải so theo
**từng mã bệnh**, đừng cộng dồn cả 4.

## Không bao giờ cộng dồn — bốn lớp chống trùng

Câu hỏi quan trọng nhất khi làm đồng bộ định kỳ: chạy lại có bị đếm hai lần không?
Câu trả lời là không, và có bốn lớp bảo vệ.

**Xoá rồi chèn lại, không cộng vào số cũ.** Mỗi lần chạy, thủ tục `DELETE` sạch
cửa sổ đang xử lý bên STA rồi `INSERT` kết quả vừa tính. Không có phép cộng nào
vào dữ liệu sẵn có, nên chạy lại mười lần cũng ra đúng một kết quả. Nếu job chết
giữa chừng, lần chạy sau làm lại nguyên cửa sổ — hậu quả xấu nhất là **thiếu tạm
thời**, không bao giờ là thừa.

**Gom theo đúng hạt dữ liệu.** Kết quả gom theo `(tháng × mã bệnh × vùng × mã
thuốc)`, các cột mô tả lấy `MAX()` chứ không đưa vào `GROUP BY`. Đây là chỗ duy
nhất có thể sinh dòng trùng: nếu hai bản ghi trong `TM_DUOC` cùng dùng một
`MADUOC` mà tên hoặc đơn vị ghi lệch nhau, cách gom cũ sẽ tách thành **hai dòng
cùng khoá** — và tầng sau đọc lên là đếm thuốc hai lần. Cách gom mới gộp làm một
và cộng số lượng, tổng giữ nguyên. Script `00` mục 3 cho biết `MADUOC` trong DB
của anh có bị trùng hay không.

**Kiểm tra trước và sau khi đẩy.** Thủ tục đếm khoá trùng trong kết quả trước khi
gửi đi — có trùng thì `THROW`, không đẩy. Sau khi chèn, đối chiếu số dòng bên STA
với số dòng vừa gom; lệch cũng `THROW`.

**UNIQUE index bên STA.** `ux_MF_CBVT_Khoa` trên `(Period, disease_code, region,
supply_code)`. Dù thủ tục có sai, dù job chạy chồng nhau, dù ai đó chèn tay — CSDL
vẫn từ chối dòng thứ hai cùng khoá.

Mục 2b của `05_kiem_tra.sql` kiểm tra lại ba thứ sau mỗi lần đẩy: khoá trùng, số
ca không nhất quán giữa các dòng thuốc cùng nhóm, và một mã thuốc mang hai đơn vị
tính. Cả ba phải ra 0.

Phía ứng dụng cũng không cộng dồn: tầng dữ liệu của MedForecast ghi fact theo kiểu
xoá-rồi-chèn từng tháng, và bảng staging khử trùng bằng `row_hash`.

## Ngưỡng ô nhỏ — chống tái định danh

Tổng hợp **không tự động** đồng nghĩa với ẩn danh. Một ô (tháng × bệnh × tỉnh)
chỉ có 1 ca thì dòng đó chính là hồ sơ của đúng một người, kèm tỉnh cư trú, tháng
khám, chẩn đoán và danh sách thuốc. Đo trên dữ liệu Gia An: **55% số ô có đúng
1 ca**.

Thủ tục xử lý ở bước 3b bằng cách **gộp lên, không xoá**: tỉnh nào trong
(tháng × bệnh) có dưới `@NguongOToiThieu` ca thì dồn vào nhóm `Tỉnh khác`.

| k | ô bị gộp | tỉnh còn nêu tên | ca trong nhóm gộp | tổng số ca |
|---|---|---|---|---|
| 3 | 71% | 14/48 | 13,1% | 13.351 |
| **5** | **81%** | **5/48** | **18,3%** | **13.351** |
| 10 | 85% | 3/48 | 18,3% | 13.351 |

**Tổng số ca giữ nguyên tuyệt đối ở mọi ngưỡng** — chỉ chi tiết tỉnh ở phần đuôi
bị gộp. Riêng bệnh viện này 79% số ca đến từ TP. Hồ Chí Minh nên chiều "tỉnh" vốn
không mang nhiều thông tin ngoài vài tỉnh đầu, và mô hình lại dự báo ở mức toàn
quốc — nên `k = 5` gần như không ảnh hưởng độ chính xác.

Ô trong nhóm `Tỉnh khác` vẫn có thể nhỏ, nhưng lúc đó tỉnh đã bị che nên không
còn là dấu hiệu định danh.

Về pháp lý, đây là bước biến dữ liệu từ *"đã tổng hợp"* thành *"đã khử nhận
dạng"* theo Điều 2 Luật Bảo vệ dữ liệu cá nhân 91/2025 (hiệu lực 01/01/2026) —
dữ liệu sau khi khử nhận dạng không còn là dữ liệu cá nhân.

Đặt `@NguongOToiThieu = 0` **chỉ khi** đối chiếu thủ công với query export gốc.
Job chạy tự động phải luôn bật ngưỡng. Mục 2c của `05_kiem_tra.sql` kiểm lại:
không được còn ô mang tên tỉnh thật mà số ca dưới ngưỡng.

## Nhóm ca không có toa thuốc — vì sao tổng ca từng nhảy số

Chạy thử trên dữ liệu thật cho ra hai kết quả khó hiểu:

```
ngưỡng ô nhỏ TẮT : 35.481 dòng, tổng ca = 13.821
ngưỡng ô nhỏ k=5 : 32.785 dòng, tổng ca = 14.119   ← tăng 298 ca
```

Số dòng giảm là đúng như thiết kế. Nhưng **tổng ca tăng** thì phải có gì đó sai —
gộp vùng không được sinh thêm ca.

Nguyên nhân: query export gốc nối `#Dx` với `#Drug` bằng `INNER JOIN`, nên nhóm
(tháng × bệnh × tỉnh) nào **không có dòng thuốc nào** sẽ biến mất khỏi kết quả,
kéo theo số ca của nhóm đó cũng biến mất. Khi bật ngưỡng, những tỉnh nhỏ không
có toa được gộp vào `Tỉnh khác` — nhóm này lại có thuốc (nhờ các tỉnh nhỏ khác) —
nên số ca vốn vô hình bỗng được đếm. 298 ca đó **luôn có thật**, chỉ là trước giờ
bị rơi mất.

Hệ quả nghiêm trọng hơn con số: **chuỗi số ca mà mô hình học bị thiếu đúng phần
đó**. Bệnh nhân được chẩn đoán nhưng không được kê thuốc trong hệ thống (mua
ngoài, chỉ làm xét nghiệm, hoặc chưa nhập toa) thì coi như chưa từng khám.

Đã sửa bằng tham số `@GiuNhomKhongCoThuoc` (mặc định `1`): nhóm không có thuốc
vẫn được trả về một dòng với `supply_code = NULL`. Tầng sau tính
`fact_disease_case` từ mọi dòng nên số ca đủ, còn `fact_supply_usage` bỏ qua dòng
không có mã vật tư nên không sinh nhu cầu thuốc ảo.

Kiểm chứng bằng bản dựng lại tình huống: cách cũ tổng ca nhảy 22 → 27 khi bật
ngưỡng; cách mới giữ nguyên 27 ở cả hai chế độ.

Đặt `@GiuNhomKhongCoThuoc = 0` để quay lại đúng hành vi query gốc khi cần đối chiếu.

Thủ tục giờ in ra đủ số để không phải đoán nữa:

```
Dòng = ..., tổng ca đẩy đi = ... (gốc ..., bỏ ... ca không rõ tỉnh),
nhóm không thuốc = ..., ô đã gộp = ..., tồn kho = ...
```

`tổng ca đẩy đi` phải **không đổi** khi bật/tắt ngưỡng ô nhỏ. Nếu vẫn đổi thì còn
chỗ khác đang làm mất ca — dừng lại kiểm tra.

## Ca không rõ tỉnh — và vì sao thứ tự hai bước gộp lại quan trọng

Lần chạy thử thứ hai vẫn lệch, chỉ là lệch theo kiểu khác:

```
ngưỡng ô nhỏ TẮT : 35.531 dòng, ca đẩy đi = 13.873  (gốc 14.215, bỏ 342 ca không rõ tỉnh)
ngưỡng ô nhỏ k=5 : 32.787 dòng, ca đẩy đi = 14.121  (gốc 14.215, bỏ  94 ca không rõ tỉnh)
```

Số học chỉ thẳng vào nguyên nhân: chênh lệch ca giao đi là **248**, chênh lệch ca
bị bỏ cũng đúng **248**. Không phải sinh thêm ca — mà là 248 ca đáng lẽ bị lọc thì
lại lọt qua.

Lý do: bước **gộp ô nhỏ** đang chạy **trước** bước **lọc `(Không xác định)`**. Ô
`(Không xác định)` phần lớn là ô nhỏ, nên bị đổi nhãn thành `Tỉnh khác` — và bộ
lọc phía sau tìm nhãn `(Không xác định)` thì không còn thấy gì để lọc. Bật ngưỡng
càng cao thì càng nhiều ca "trốn" được.

Sửa bằng cách **đảo thứ tự**: xử lý vùng không xác định ở bước **3a**, gộp ô nhỏ ở
bước **3b**. Quy tắc chung để không lặp lại lỗi này: **mọi phép LỌC theo nhãn phải
chạy xong trước mọi phép ĐỔI nhãn.**

Đồng thời tham số `@BoVungKhongXacDinh` (bit) đổi thành `@XuLyVungKhongXacDinh`
(tinyint) vì hai giá trị bật/tắt không đủ diễn tả ba lựa chọn thật:

| giá trị | xử lý | tổng ca | dùng khi |
|---|---|---|---|
| 0 | giữ nhãn `(Không xác định)` như một vùng riêng | đủ | muốn nhìn thấy phần dữ liệu thiếu địa chỉ |
| **1** | **gộp vào `Tỉnh khác`** *(mặc định)* | **đủ** | **job chạy hằng ngày** |
| 2 | loại bỏ hẳn | hụt 342/14.215 ≈ 2,4% | chỉ để đối chiếu từng dòng với query export gốc |

Mặc định là `1`: "không rõ tỉnh" về mặt ngữ nghĩa cũng chính là một dạng "khác",
gộp vào đó vừa giữ đủ tổng ca vừa không bịa ra địa lý. Query export gốc dùng cách
`2` — đúng cho một lần xuất file, nhưng sai cho chuỗi huấn luyện vì làm hụt ca một
cách phụ thuộc cấu hình.

Thủ tục nay tự kiểm bất biến ngay trước khi đẩy:

```
ca đẩy đi  ==  ca gốc  −  ca loại vì không rõ tỉnh
```

Sai thì in `CẢNH BÁO BẤT BIẾN` kèm cả ba con số. Thấy dòng đó thì dừng, đừng đẩy.
Mục **0b** của `05_kiem_tra.sql` là bài kiểm tra tay tương ứng.

## Đặc thù eHospital cần nhớ

- Chẩn đoán **nằm ngay trên dòng khám**, không có bảng chẩn đoán riêng:
  ngoại trú `CHANDOANICD_ID`, nội trú `ICDCHINH_ID`.
- **Ngoại trú và nội trú gộp chung**: `TT_NGOAITRU_KHAMBENH` và
  `TT_NOITRU_BENHAN` → `TT_NOITRU_KHAMBENH`. Số ca đếm theo
  `COUNT(DISTINCT TIEPNHAN_ID)` để một lượt tiếp nhận chỉ tính một lần.
- `BA.ICD_BENHCHINH` **lẫn lộn kiểu dữ liệu** (khi là ID số, khi là text chẩn
  đoán) → phải dùng `TRY_CAST(... AS INT)` mới không lỗi convert.
- `BA.ICD_BENHPHU` là **free-text** (tên bệnh + mã trong ngoặc) → không trích mã
  được. Chẩn đoán phụ chỉ lấy từ `KB.DS_MAICDPHU` (danh sách mã chuẩn, phân cách
  bằng dấu chấm phẩy).
- **Tỉnh/thành** suy từ `TT_BENHNHAN.XAPHUONG_ID` qua `TM_DONVIHANHCHINH`
  (xã → huyện → tỉnh, `CAPDONVI = 2` là tỉnh), fallback `TINHTHANH_ID`, cuối
  cùng dò tên tỉnh trong `DIACHITHUONGTRU`.
- **Chỉ lấy thuốc**: `TM_LOAIDUOC.LOAIVATTU_ID = 'T'` — tự loại vật tư y tế,
  hoá chất, suất ăn.
- Nội trú lấy **số thực lĩnh** `SOLUONGTHUCLINH`, thiếu thì mới lấy `SOLUONG`.
- `TM_ICD` đã có sẵn cột `PHANNHOM` — nhóm ICD lấy thẳng từ HIS, không cần file
  `TM_ICD.xlsx` nữa.
- Bảng giao dịch hầu hết dùng `(NOLOCK)` trong code gốc; các script ở đây làm theo.

## Lịch chạy phải so le

Job PROD→STA chạy **01:00**, MedForecast đồng bộ **02:00**
(`PIPELINE_CRON=0 2 * * *`). Trùng giờ thì ứng dụng đọc dữ liệu cũ một ngày.
Cửa sổ tổng hợp lại là 3 tháng ở cả hai bên (`@SoThangLuiLai` và
`PIPELINE_LOOKBACK_MONTHS`) — đổi một bên thì đổi cả hai.

## Nối MedForecast vào

Trong `backend/.env`:

```
PIPELINE_SOURCE=sqlserver
PIPELINE_SQLSERVER_CONN=mssql+pyodbc://medforecast_app:<mat-khau>@<sta-host>:1433/MEDFORECAST_DW?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes
PIPELINE_CASE_SQL_FILE=case_sta.sql
PIPELINE_INVENTORY_SQL_FILE=inventory_sta.sql
PIPELINE_LOOKBACK_MONTHS=3
PIPELINE_CRON=0 2 * * *
```

## Kiểm chứng

**Cách kiểm chứng đúng đắn nhất là mục 0 của `05_kiem_tra.sql`**: chạy thủ tục ở
chế độ `@ChiXem = 1` và chạy query export gốc cạnh nhau trên chính DB thật, so số
dòng và `SUM(supply_quantity)`. Cùng một máy, cùng một dữ liệu — không có cách nào
chắc chắn hơn. **Làm bước này trước khi đẩy bất cứ thứ gì xuống STA.**

Ngoài ra, ba nguyên tắc chung của tầng dữ liệu (đếm `COUNT(DISTINCT` lượt tiếp
nhận`)`, gom mã ICD về 3 ký tự, loại toa đã huỷ) đã được kiểm chứng riêng trên
bản mô phỏng bằng SQLite — `backend/scripts/sim_ehospital_prod.py` và
`verify_ehospital_agg.py`, 16 kiểm tra PASS, tổng ca và tổng lượng thuốc khớp
tuyệt đối dữ liệu Gia An. Bản mô phỏng đó dựng theo phiên bản thủ tục trước khi
chuyển sang query gốc, nên nó xác nhận **nguyên tắc**, không xác nhận từng dòng
SQL hiện tại.

**Cú pháp T-SQL chưa chạy trên SQL Server thật** — môi trường kiểm chứng chỉ có
SQLite. Chạy lần đầu ở chế độ `@ChiXem = 1`, xem có lỗi cú pháp không, rồi mới đẩy.

Bộ script cũ dựng theo schema giả định (chiều PROD ← STA) nằm ở
`_cu_schema_gia_dinh/`, giữ lại để đối chiếu, không dùng nữa.
