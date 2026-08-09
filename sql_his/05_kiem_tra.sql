/* =============================================================================
   05 — KIỂM TRA SAU MỖI LẦN ĐẨY
   =============================================================================
   Mục 1–4 chạy trên STA (MEDFORECAST_DW). Mục 5 chạy trên PROD để đối chiếu.
   Bắt buộc chạy đủ ở lần đầu tiên trước khi tin số liệu.
============================================================================= */

/* =============================================================================
   0 — ĐỐI CHIẾU VỚI QUERY EXPORT GỐC (chạy TRÊN PROD, TRƯỚC KHI bật job)
   -----------------------------------------------------------------------------
   Thủ tục là bản chuyển đổi từ câu query export dataset của nhóm. Trước khi
   đẩy bất cứ thứ gì xuống STA, chạy hai cái cạnh nhau và so kết quả.

   B1. Chạy thủ tục ở chế độ chỉ xem (không ghi gì xuống STA):
         EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1, @ChiXem = 1;
       Lưu kết quả ra file (SSMS: Results to File).

   B2. Chạy query export gốc với cùng khoảng thời gian, lưu ra file thứ hai.

   B3. So ba con số — phải khớp tuyệt đối:
         • số dòng
         • SUM(supply_quantity)
         • SUM(cases) tính theo từng mã bệnh (đừng cộng dồn cả 4 mã —
           một lượt khám có thể mang nhiều mã nên cộng dồn sẽ vượt số thật)

   Lệch thì DỪNG LẠI. Nguyên nhân hay gặp: khoảng ngày không giống nhau, hoặc
   @XuLyVungKhongXacDinh / @NguongOutlier đặt khác với query gốc.

   Muốn khớp TỪNG DÒNG với query export gốc thì phải chạy đúng cấu hình của nó —
   gốc loại bỏ ca không rõ tỉnh và không có ngưỡng ô nhỏ:
         EXEC dbo.usp_MedForecast_DayDuLieu
              @NapLaiToanBo = 1, @ChiXem = 1,
              @XuLyVungKhongXacDinh = 2, @NguongOToiThieu = 0;
   Nhưng ĐỪNG chạy job bằng cấu hình đó — xem mục 0b.

   -----------------------------------------------------------------------------
   0b — BẤT BIẾN: BẬT/TẮT NGƯỠNG Ô NHỎ KHÔNG ĐƯỢC LÀM ĐỔI TỔNG SỐ CA
   -----------------------------------------------------------------------------
   Ngưỡng ô nhỏ chỉ ĐỔI NHÃN vùng, không thêm không bớt ca. Nên chạy hai lần chỉ
   khác mỗi @NguongOToiThieu thì dòng 'ca đẩy đi' PHẢI y hệt nhau:

         EXEC dbo.usp_MedForecast_DayDuLieu
              @NapLaiToanBo = 1, @ChiXem = 1, @NguongOToiThieu = 0;
         EXEC dbo.usp_MedForecast_DayDuLieu
              @NapLaiToanBo = 1, @ChiXem = 1, @NguongOToiThieu = 5;

   Còn lệch nghĩa là còn một chỗ đang làm rơi ca phụ thuộc vào nhãn vùng. Đã gặp
   đúng hai lần trên dữ liệu thật:

     • INNER JOIN với #Drug làm mất nhóm không có toa thuốc (13.821 → 14.119)
       → sửa bằng @GiuNhomKhongCoThuoc (nhánh UNION ALL).
     • Bước gộp ô nhỏ chạy TRƯỚC bước lọc '(Không xác định)', nên 248 ca không rõ
       tỉnh bị đổi nhãn thành 'Tỉnh khác' rồi thoát khỏi bộ lọc (13.873 → 14.121)
       → sửa bằng cách đưa xử lý vùng không xác định lên bước 3a, TRƯỚC 3b.

   Thủ tục nay tự kiểm bất biến này và in cảnh báo nếu vi phạm:
       'CẢNH BÁO BẤT BIẾN: ...'
   Thấy dòng đó thì DỪNG, đừng đẩy.
============================================================================= */

USE MEDFORECAST_DW;
GO

/* --- 1. Lần chạy gần nhất ------------------------------------------------- */
SELECT TOP 10 Id, BatDau, KetThuc,
       DATEDIFF(SECOND, BatDau, KetThuc) AS SoGiay,
       TuNgay, SoDongCaBenh, SoDongTonKho, TongSoCa, TrangThai, ThongDiep
FROM   dbo.MF_SyncLog
ORDER BY Id DESC;

/* --- 2. Độ tươi: dữ liệu có đang bị cũ không? ---------------------------- */
SELECT MAX(Period)                                        AS ThangMoiNhat,
       MAX(NgayCapNhat)                                   AS LanDayCuoi,
       DATEDIFF(HOUR, MAX(NgayCapNhat), SYSDATETIME())    AS SoGioTre,
       CASE WHEN DATEDIFF(HOUR, MAX(NgayCapNhat), SYSDATETIME()) > 36
            THEN N'CẢNH BÁO: dữ liệu cũ, kiểm tra job bên PROD'
            ELSE N'Bình thường' END                       AS DanhGia
FROM   dbo.MF_CaBenh_VatTu;

/* --- 2b. KHÔNG ĐƯỢC CÓ DÒNG TRÙNG ---------------------------------------
   Đây là thứ gây "data double" làm nhiễu mô hình. Cả ba câu phải ra 0.        */
SELECT COUNT(*) AS SoKhoaBiTrung FROM (
    SELECT 1 AS x FROM dbo.MF_CaBenh_VatTu
    GROUP BY Period, disease_code, region, supply_code
    HAVING COUNT(*) > 1) t;

-- Cùng một (tháng × bệnh × vùng) mà số ca ghi khác nhau giữa các dòng thuốc
-- (đúng ra phải giống hệt nhau vì `cases` chỉ lặp lại)
SELECT COUNT(*) AS SoNhomCoSoCaKhongNhatQuan FROM (
    SELECT Period, disease_code, region
    FROM   dbo.MF_CaBenh_VatTu
    GROUP BY Period, disease_code, region
    HAVING COUNT(DISTINCT cases) > 1) t;

-- Cùng một mã thuốc nhưng ghi hai đơn vị tính khác nhau
SELECT COUNT(*) AS SoMaThuocCoNhieuDonVi FROM (
    SELECT supply_code FROM dbo.MF_CaBenh_VatTu
    WHERE  supply_code IS NOT NULL
    GROUP BY supply_code HAVING COUNT(DISTINCT supply_unit) > 1) t;

/* --- 2c. NGƯỠNG Ô NHỎ — chống tái định danh ------------------------------
   Không được còn ô mang TÊN TỈNH THẬT mà số ca dưới ngưỡng. Ô trong nhóm
   'Tỉnh khác' được phép nhỏ vì tỉnh đã bị che.                                */
DECLARE @k INT = 5;   -- ⚙ khớp @NguongOToiThieu của thủ tục

;WITH g AS (
    SELECT Period, disease_code, region, MAX(cases) AS cases
    FROM   dbo.MF_CaBenh_VatTu
    GROUP BY Period, disease_code, region)
SELECT COUNT(*) AS SoOViPhamNguong
FROM   g WHERE region <> N'Tỉnh khác' AND cases < @k;      -- phải = 0

-- Xem cụ thể ô nào vi phạm (nếu có)
;WITH g AS (
    SELECT Period, disease_code, region, MAX(cases) AS cases
    FROM   dbo.MF_CaBenh_VatTu
    GROUP BY Period, disease_code, region)
SELECT TOP 30 Period, disease_code, region, cases
FROM   g WHERE region <> N'Tỉnh khác' AND cases < @k
ORDER BY cases;

-- Mức độ gộp: bao nhiêu ca nằm trong nhóm gộp
;WITH g AS (
    SELECT Period, disease_code, region, MAX(cases) AS cases
    FROM   dbo.MF_CaBenh_VatTu
    GROUP BY Period, disease_code, region)
SELECT SUM(CASE WHEN region = N'Tỉnh khác' THEN cases ELSE 0 END) AS CaTrongNhomGop,
       SUM(cases)                                                 AS TongCa,
       CAST(100.0 * SUM(CASE WHEN region = N'Tỉnh khác' THEN cases ELSE 0 END)
            / NULLIF(SUM(cases), 0) AS decimal(5,1))              AS PhanTram,
       COUNT(DISTINCT CASE WHEN region <> N'Tỉnh khác' THEN region END) AS SoTinhConNeuTen
FROM   g;

/* --- 2d. Nhóm ca không có thuốc ------------------------------------------
   Dòng supply_code NULL là nhóm (tháng × bệnh × vùng) có ca nhưng không có toa
   nào. Chúng PHẢI tồn tại — thiếu là chuỗi số ca của mô hình bị hụt.
   Nếu ra 0 mà bệnh viện thật sự có ca không kê thuốc thì kiểm tra
   @GiuNhomKhongCoThuoc có đang bị đặt = 0 không.                              */
SELECT COUNT(*)                                                  AS SoNhomKhongCoThuoc,
       SUM(cases)                                                AS SoCaTrongNhomDo,
       (SELECT COUNT(*) FROM dbo.MF_CaBenh_VatTu)                AS TongSoDong
FROM   dbo.MF_CaBenh_VatTu
WHERE  supply_code IS NULL;

-- Dòng có mã thuốc thì bắt buộc phải có số lượng > 0
SELECT COUNT(*) AS SoDongCoThuocNhungKhongCoSoLuong
FROM   dbo.MF_CaBenh_VatTu
WHERE  supply_code IS NOT NULL
  AND  (supply_quantity IS NULL OR supply_quantity <= 0);      -- phải = 0

/* Ra khác 0 thì xem chính xác dòng nào. Nguyên nhân đã gặp: cột supply_quantity
   là decimal(18,3), lượng dùng nhỏ hơn 0,0005 (đơn vị lẻ, thuốc pha loãng) làm
   tròn thành 0.000 khi ghi xuống. Thủ tục nay loại các dòng đó ngay ở CTE Agg
   (HAVING SUM(dr.Qty) >= 0.001) nên số ca vẫn đủ — nhóm mất hết dòng thuốc sẽ
   rơi về nhánh "không có toa".                                                */
SELECT TOP 20 Period, [month], disease_code, disease_group, region, cases,
       supply_code, supply_name, supply_unit, supply_quantity
FROM   dbo.MF_CaBenh_VatTu
WHERE  supply_code IS NOT NULL
  AND  (supply_quantity IS NULL OR supply_quantity <= 0)
ORDER BY Period DESC;

/* --- 2e. PHẠM VI BỆNH — đủ ba nhóm theo đề cương chưa? -------------------
   Phải ra đúng 3 dòng: J00-J06, J09-J18, J20-J22. Thiếu nhóm nào nghĩa là
   thủ tục đang chạy với @NhomBenhDich hẹp hơn đề cương, hoặc TM_ICD.PHANNHOM
   bên PROD không có nhóm đó.                                                  */
SELECT disease_group, MAX(disease_group_name) AS TenNhom,
       COUNT(DISTINCT disease_code)           AS SoMaBenh,
       COUNT(DISTINCT Period)                 AS SoThang
FROM   dbo.MF_CaBenh_VatTu
GROUP BY disease_group
ORDER BY disease_group;

-- Không được có dòng nào thiếu nhóm — phải = 0
SELECT COUNT(*) AS SoDongKhongCoNhom
FROM   dbo.MF_CaBenh_VatTu
WHERE  disease_group IS NULL OR LTRIM(RTRIM(disease_group)) = '';

-- Một mã bệnh chỉ được thuộc đúng một nhóm — phải = 0 dòng
SELECT disease_code, COUNT(DISTINCT disease_group) AS SoNhom
FROM   dbo.MF_CaBenh_VatTu
GROUP BY disease_code
HAVING COUNT(DISTINCT disease_group) > 1;

/* --- 2f. SỐ CA MỨC NHÓM PHẢI NHỎ HƠN HOẶC BẰNG TỔNG CÁC MÃ CON -----------
   Đây là kiểm tra quan trọng nhất của bảng MF_CaBenh_Nhom. Một lượt khám mang
   J01 (chính) + J06 (phụ) — cả hai cùng nhóm J00-J06 — bị đếm hai lần nếu cộng
   dồn mã con. Vì vậy:

       cases mức nhóm  <=  tổng cases các mã con        (LUÔN ĐÚNG)

   Vi phạm nghĩa là hai bảng được sinh từ hai tập dữ liệu khác nhau — dừng lại.
   Cột ChenhLech cho biết phép cộng dồn đang thổi phồng bao nhiêu ca; đó cũng
   chính là mức sai mà mô hình sẽ học nếu không có bảng nhóm.                  */
;WITH ma AS (
    SELECT Period, disease_group, region, disease_code, MAX(cases) AS cases
    FROM   dbo.MF_CaBenh_VatTu
    GROUP BY Period, disease_group, region, disease_code
), congdon AS (
    SELECT Period, disease_group, region, SUM(cases) AS CongDonMaCon
    FROM   ma GROUP BY Period, disease_group, region
)
SELECT n.disease_group,
       SUM(n.cases)                                   AS TongCa_MucNhom,
       SUM(ISNULL(c.CongDonMaCon, 0))                 AS TongCa_NeuCongDon,
       SUM(ISNULL(c.CongDonMaCon, 0)) - SUM(n.cases)  AS ChenhLech_DemTrung,
       SUM(CASE WHEN n.cases > ISNULL(c.CongDonMaCon, 0) THEN 1 ELSE 0 END)
                                                      AS SoDongViPham   -- phải = 0
FROM   dbo.MF_CaBenh_Nhom n
LEFT JOIN congdon c ON c.Period        = n.Period
                   AND c.disease_group = n.disease_group
                   AND c.region        = n.region
WHERE  n.region <> N'TOAN_QUOC'
GROUP BY n.disease_group
ORDER BY n.disease_group;

-- Dòng TOAN_QUOC phải >= mọi tỉnh lẻ trong cùng (tháng × nhóm) — phải = 0 dòng
SELECT t.Period, t.disease_group, t.region, t.cases AS CaTinh, q.cases AS CaToanQuoc
FROM   dbo.MF_CaBenh_Nhom t
JOIN   dbo.MF_CaBenh_Nhom q ON q.Period = t.Period
                           AND q.disease_group = t.disease_group
                           AND q.region = N'TOAN_QUOC'
WHERE  t.region <> N'TOAN_QUOC' AND t.cases > q.cases;

/* --- 3. Bẫy lỗi "số ca luôn bằng 1" --------------------------------------
   Nếu mọi nhóm chỉ có 1 ca thì thủ tục đang đếm sai (dùng hằng số thay vì
   COUNT(DISTINCT lượt khám)).                                              */
;WITH g AS (
    SELECT Period, disease_code, region, MAX(cases) AS cases
    FROM   dbo.MF_CaBenh_VatTu GROUP BY Period, disease_code, region)
SELECT CASE WHEN MAX(cases) <= 1
            THEN N'SAI: cases luôn = 1 — xem lại COUNT(DISTINCT) trong thủ tục'
            ELSE N'Bình thường — số ca có phân bố hợp lý' END AS KetLuan,
       MIN(cases) AS ThapNhat, MAX(cases) AS CaoNhat,
       CAST(AVG(cases * 1.0) AS decimal(10,1)) AS TrungBinh,
       COUNT(*) AS SoNhom
FROM g;

/* --- 4. Số ca theo tháng và mã bệnh (để đối chiếu với phòng KHTH) --------
   So theo TỪNG MÃ BỆNH. Không cộng dồn 4 mã: một lượt khám mang cả J01 lẫn J06
   sẽ được tính vào cả hai, nên tổng cộng dồn luôn lớn hơn số lượt thật.        */
;WITH g AS (
    SELECT Period, [month], disease_code, region, MAX(cases) AS cases
    FROM   dbo.MF_CaBenh_VatTu GROUP BY Period, [month], disease_code, region)
SELECT [month], disease_code, SUM(cases) AS SoCa
FROM   g
WHERE  Period >= DATEADD(MONTH, -6, CAST(SYSDATETIME() AS date))
GROUP BY [month], disease_code, Period
ORDER BY Period DESC, SoCa DESC;

/* --- 4b. Chất lượng dữ liệu --------------------------------------------- */
-- Mã ICD sai định dạng (phải là chữ + 2 số)
SELECT DISTINCT disease_code FROM dbo.MF_CaBenh_VatTu
WHERE  disease_code NOT LIKE '[A-Z][0-9][0-9]';

-- Nhóm ca không có dòng vật tư nào (supply_code NULL)
SELECT COUNT(*) AS SoNhomKhongCoVatTu
FROM   dbo.MF_CaBenh_VatTu WHERE supply_code IS NULL;

-- Vật tư trong ca bệnh nhưng không có trong tồn kho (sẽ không tính được đề xuất nhập)
SELECT COUNT(DISTINCT c.supply_code) AS SoMaKhongCoTonKho
FROM   dbo.MF_CaBenh_VatTu c
LEFT   JOIN dbo.MF_TonKho t ON t.supply_code = c.supply_code
WHERE  c.supply_code IS NOT NULL AND t.supply_code IS NULL;

-- Tồn kho: có số khác 0 không
SELECT COUNT(*) AS SoMatHang, SUM(stock_quantity) AS TongTon,
       SUM(CASE WHEN stock_quantity > 0 THEN 1 ELSE 0 END) AS SoMatHangConHang
FROM   dbo.MF_TonKho;

/* =============================================================================
   --- 5. ĐỐI CHIẾU VỚI PROD — chạy khối này TRÊN PROD -----------------------
   Kết quả phải khớp mục 4. Lệch nghĩa là thủ tục đẩy sót hoặc lọc sai.
============================================================================= */
/*
DECLARE @BENHVIEN_ID int = 79428;
SELECT FORMAT(kb.NGAYKHAM, 'MM/yyyy')            AS [month],
       LEFT(UPPER(LTRIM(RTRIM(icd.MAICD))), 3)   AS disease_code,
       COUNT(DISTINCT kb.KHAMBENH_ID)            AS SoCa
FROM   TT_NGOAITRU_KHAMBENH kb  WITH (NOLOCK)
JOIN   TM_ICD               icd WITH (NOLOCK) ON icd.ICD_ID = kb.CHANDOANICD_ID
WHERE  kb.BENHVIEN_ID = @BENHVIEN_ID
  AND  kb.NGAYKHAM >= DATEADD(MONTH, -6, CAST(GETDATE() AS date))
  AND  icd.MAICD LIKE 'J%'
GROUP BY FORMAT(kb.NGAYKHAM, 'MM/yyyy'), LEFT(UPPER(LTRIM(RTRIM(icd.MAICD))), 3)
ORDER BY [month] DESC, SoCa DESC;
*/
