/* =============================================================================
   MEDFORECAST — PHÉP ĐO Đ9 VÀ Đ10   (giai đoạn G0)
   =============================================================================
   Chạy trên : HIS PROD — GIAAN115_HIS (SQL Server / SSMS)
   Mục đích  : chốt hai tham số đang treo của hệ hỗ trợ quyết định
                 Đ9  → ngưỡng cảnh báo DOI (Đỏ / Vàng) lấy từ chu kỳ nhập THẬT
                 Đ10 → nhu cầu nền D_baseline, và tập mã thật sự do dịch hô hấp lái

   -----------------------------------------------------------------------------
   AN TOÀN
     • Toàn bộ script CHỈ ĐỌC. Không INSERT / UPDATE / DELETE / DDL trên bảng thật.
     • Chỉ tạo bảng tạm #... trong tempdb; có DROP trước và sau.
     • Không có linked server, không ghi ra ngoài.
     • Đ10 quét bảng toa thuốc 12 tháng → CHẠY NGOÀI GIỜ CAO ĐIỂM.
       Nếu chậm, hạ @SoThang xuống 6 rồi 3 — kết quả vẫn đủ để quyết định.

   CÁCH CHẠY TRONG SSMS
     1. Mở SSMS, kết nối máy chủ HIS PROD, chọn database GIAAN115_HIS.
     2. Bật "Results to Grid" (Ctrl+D) — script trả về nhiều bảng kết quả.
     3. Nếu DB chứa nhiều bệnh viện: sửa @BENHVIEN_ID ở dòng có dấu ⚙.
     4. CHẠY TỪNG KHỐI, không chạy cả file một lượt:
          - bôi đen khối "BƯỚC 0", nhấn F5, đọc kết quả;
          - rồi khối Đ9, F5;
          - rồi khối Đ10, F5.
        Chạy từng khối để nếu một bước lỗi thì biết ngay lỗi ở đâu.
     5. Xuất kết quả: chuột phải vào lưới → "Save Results As..." (CSV), hoặc
        Ctrl+Shift+F để ghi thẳng ra file.

   ĐỌC KẾT QUẢ Ở ĐÂU
     Mỗi bảng kết quả đều có phần "► ĐỌC THẾ NÀO" ngay trên câu lệnh sinh ra nó.
============================================================================= */

USE GIAAN115_HIS;
GO
SET NOCOUNT ON;
GO


/* ═════════════════════════════════════════════════════════════════════════════
   BƯỚC 0 — XÁC NHẬN CỘT TRƯỚC KHI ĐO
   -----------------------------------------------------------------------------
   ► ĐỌC THẾ NÀO
     Bảng trả về phải có ĐỦ 8 dòng, cột CoCot = 1 hết.
     Thiếu dòng nào thì DỪNG, gửi lại kết quả này — cột đó có tên khác trên
     máy chủ của bệnh viện và câu lệnh bên dưới phải sửa theo.
   ═════════════════════════════════════════════════════════════════════════════ */

SELECT  x.Bang, x.Cot,
        CASE WHEN COL_LENGTH(x.Bang, x.Cot) IS NULL THEN 0 ELSE 1 END AS CoCot
FROM (VALUES
    ('dbo.TT_DUOC_CHUNGTU_SOLONHAP','SOLONHAP_ID'),
    ('dbo.TT_DUOC_CHUNGTU_SOLONHAP','DUOC_ID'),
    ('dbo.TT_DUOC_CHUNGTU_SOLONHAP','NGAYNHAP'),
    ('dbo.TT_DUOC_CHUNGTU_SOLONHAP','DONGIAMUA'),
    ('dbo.TT_DUOC_CHUNGTU_SOLONHAP','HUY'),
    ('dbo.TT_NOITRU_TOATHUOC','KHAMBENH_ID'),
    ('dbo.TT_NGOAITRU_TOATHUOC','KHAMBENH_ID'),
    ('dbo.TM_ICD','PHANNHOM')
) AS x(Bang, Cot);
GO


/* ═════════════════════════════════════════════════════════════════════════════
   Đ9 — CHU KỲ NHẬP KHO THỰC TẾ
   -----------------------------------------------------------------------------
   VÌ SAO PHẢI ĐO

   Ngưỡng cảnh báo hiện đang là 7 và 14 ngày — hai con số CHỌN TAY. Trước hội
   đồng, "vì sao 7 ngày" là câu không trả lời được nếu không có số này.

   Nguyên tắc chọn ngưỡng: một mã bị coi là NGUY CƠ khi lượng tồn không đủ dùng
   cho tới lần bổ sung kế tiếp. Đã bỏ phân hệ đặt hàng nên không đo được thời
   gian giao hàng của nhà cung cấp, nhưng CHU KỲ NHẬP THỰC TẾ (khoảng cách giữa
   hai lần nhập liên tiếp của cùng một mã) là đại lượng thay thế đo được, và nó
   chính là điều người dùng quan tâm: "hàng còn đủ tới đợt nhập sau không".

       ngưỡng ĐỎ   = trung vị chu kỳ nhập      (hết trước đợt sau → đứt hàng)
       ngưỡng VÀNG = 2 × ngưỡng đỏ             (còn một đợt đệm)

   Đây là MỘT CÂU ĐO CHẠY MỘT LẦN để chọn tham số, KHÔNG phải một tính năng.
   Không dựng bảng đồng bộ, không theo dõi nhà cung cấp.

   NGUỒN: TT_DUOC_CHUNGTU_SOLONHAP có sẵn DUOC_ID và NGAYNHAP, nên không cần
   nối sang TT_DUOC_CHUNGTU — tránh phụ thuộc vào tên khoá chưa xác minh.
   ═════════════════════════════════════════════════════════════════════════════ */

DECLARE @BENHVIEN_ID VARCHAR(8) = NULL;      -- ⚙ đặt 79428 nếu DB chứa nhiều bệnh viện
DECLARE @SoThangD9   INT = 24;        -- cửa sổ lịch sử nhập

IF OBJECT_ID('tempdb..#Nhap')   IS NOT NULL DROP TABLE #Nhap;
IF OBJECT_ID('tempdb..#Khoang') IS NOT NULL DROP TABLE #Khoang;
IF OBJECT_ID('tempdb..#TheoMa') IS NOT NULL DROP TABLE #TheoMa;

/* Một dòng cho mỗi (mã × NGÀY nhập). Hai chứng từ cùng ngày của cùng một mã
   là MỘT lần bổ sung, không phải hai — nếu đếm hai thì chu kỳ sẽ ra 0 ngày. */
SELECT DISTINCT
       ln.DUOC_ID,
       CAST(ln.NGAYNHAP AS DATE) AS Ngay
INTO   #Nhap
FROM   TT_DUOC_CHUNGTU_SOLONHAP ln
WHERE  ln.NGAYNHAP IS NOT NULL
  AND  CAST(ln.NGAYNHAP AS DATE) >= DATEADD(MONTH, -@SoThangD9, CAST(GETDATE() AS DATE))
  AND  ISNULL(CAST(ln.HUY AS NVARCHAR(10)), '0') <> '1';

/* Khoảng cách giữa hai lần nhập liên tiếp của cùng một mã. */
SELECT DUOC_ID, Ngay,
       DATEDIFF(DAY, LAG(Ngay) OVER (PARTITION BY DUOC_ID ORDER BY Ngay), Ngay) AS Khoang
INTO   #Khoang
FROM   #Nhap;

/* Trung vị chu kỳ của TỪNG mã + số lần nhập. */
SELECT DISTINCT
       k.DUOC_ID,
       COUNT(*)      OVER (PARTITION BY k.DUOC_ID)                       AS SoKhoang,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY k.Khoang)
             OVER (PARTITION BY k.DUOC_ID)                               AS ChuKyTrungVi
INTO   #TheoMa
FROM   #Khoang k
WHERE  k.Khoang IS NOT NULL AND k.Khoang > 0;


-- ── Đ9-A · Bối cảnh ─────────────────────────────────────────────────────────
-- ► ĐỌC THẾ NÀO: SoMaCoNhap là số mã thật sự được bổ sung trong 24 tháng.
--   Nếu con số này nhỏ hơn nhiều so với 1.080 mã đang có tồn thì phần lớn kho
--   là hàng tồn cũ không luân chuyển — ghi nhận để giải thích ở Đ9-C.
SELECT  N'Đ9-A · Bối cảnh'                                   AS Muc,
        (SELECT COUNT(DISTINCT DUOC_ID) FROM #Nhap)          AS SoMaCoNhap,
        (SELECT COUNT(*)                FROM #Nhap)          AS SoLanNhap,
        (SELECT COUNT(DISTINCT DUOC_ID) FROM #TheoMa)        AS SoMaTinhDuocChuKy,
        (SELECT MIN(Ngay) FROM #Nhap)                        AS TuNgay,
        (SELECT MAX(Ngay) FROM #Nhap)                        AS DenNgay;


-- ── Đ9-B · Phân bố khoảng cách giữa hai lần nhập (gộp toàn viện) ────────────
-- ► ĐỌC THẾ NÀO: p50 là con số quan trọng nhất — chu kỳ bổ sung điển hình.
--   p25 cho biết nhóm hàng quay vòng nhanh, p90 cho biết đuôi hàng ít dùng.
SELECT DISTINCT
        N'Đ9-B · Khoảng cách giữa 2 lần nhập (ngày)' AS Muc,
        COUNT(*)                                                  OVER () AS SoQuanSat,
        CAST(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY Khoang) OVER () AS decimal(10,1)) AS p25,
        CAST(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY Khoang) OVER () AS decimal(10,1)) AS p50_TrungVi,
        CAST(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY Khoang) OVER () AS decimal(10,1)) AS p75,
        CAST(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY Khoang) OVER () AS decimal(10,1)) AS p90
FROM    #Khoang
WHERE   Khoang IS NOT NULL AND Khoang > 0;


-- ── Đ9-C · Chỉ tính các mã BỔ SUNG ĐỀU (≥ 6 lần nhập trong 24 tháng) ────────
-- ► ĐỌC THẾ NÀO: ĐÂY LÀ BẢNG DÙNG ĐỂ CHỌN NGƯỠNG.
--   Mã chỉ nhập 1-2 lần trong hai năm là hàng đặt theo yêu cầu, không có "chu
--   kỳ" theo nghĩa vận hành, và đưa vào sẽ kéo trung vị lên rất cao.
--   Lấy cột p50_TrungVi của bảng này làm doi_red_days.
SELECT DISTINCT
        N'Đ9-C · Mã bổ sung đều — CHỌN NGƯỠNG TỪ ĐÂY' AS Muc,
        COUNT(*)                                                        OVER () AS SoMa,
        CAST(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY ChuKyTrungVi) OVER () AS decimal(10,1)) AS p25,
        CAST(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ChuKyTrungVi) OVER () AS decimal(10,1)) AS p50_TrungVi,
        CAST(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY ChuKyTrungVi) OVER () AS decimal(10,1)) AS p75,
        CAST(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY ChuKyTrungVi) OVER () AS decimal(10,1)) AS p90
FROM    #TheoMa
WHERE   SoKhoang >= 6;


-- ── Đ9-D · Chu kỳ theo mức độ luân chuyển ──────────────────────────────────
-- ► ĐỌC THẾ NÀO: nếu nhóm "rất đều" có chu kỳ ngắn hơn hẳn nhóm "thưa" thì
--   một ngưỡng phẳng cho toàn bộ danh mục là chưa đủ — khi đó ghi nhận để
--   G4 dùng ngưỡng theo nhóm thay vì một con số chung.
SELECT  CASE WHEN SoKhoang >= 24 THEN N'1 · rất đều (≥24 lần)'
             WHEN SoKhoang >= 12 THEN N'2 · đều (12-23 lần)'
             WHEN SoKhoang >=  6 THEN N'3 · vừa (6-11 lần)'
             WHEN SoKhoang >=  3 THEN N'4 · thưa (3-5 lần)'
             ELSE                     N'5 · rất thưa (1-2 lần)' END      AS NhomLuanChuyen,
        COUNT(*)                                                         AS SoMa,
        CAST(AVG(ChuKyTrungVi) AS decimal(10,1))                         AS ChuKyTrungBinh,
        CAST(MIN(ChuKyTrungVi) AS decimal(10,1))                         AS NganNhat,
        CAST(MAX(ChuKyTrungVi) AS decimal(10,1))                         AS DaiNhat
FROM    #TheoMa
GROUP BY CASE WHEN SoKhoang >= 24 THEN N'1 · rất đều (≥24 lần)'
              WHEN SoKhoang >= 12 THEN N'2 · đều (12-23 lần)'
              WHEN SoKhoang >=  6 THEN N'3 · vừa (6-11 lần)'
              WHEN SoKhoang >=  3 THEN N'4 · thưa (3-5 lần)'
              ELSE                     N'5 · rất thưa (1-2 lần)' END
ORDER BY NhomLuanChuyen;


-- ── Đ9-E · Gợi ý ngưỡng, tính thẳng từ số vừa đo ───────────────────────────
-- ► ĐỌC THẾ NÀO: chép hai con số DeXuat_Do và DeXuat_Vang vào bảng
--   system_config (doi_red_days, doi_amber_days) ở bước G4.
--   Nếu DeXuat_Do lệch nhiều so với 7 ngày đang giả định thì đó chính là lý do
--   băng Vàng hiện chỉ bắt được 13 mã trên 5.041.
SELECT DISTINCT
        N'Đ9-E · Gợi ý ngưỡng' AS Muc,
        CAST(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ChuKyTrungVi) OVER () AS INT)     AS DeXuat_Do,
        CAST(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ChuKyTrungVi) OVER () * 2 AS INT) AS DeXuat_Vang,
        7                                                                                    AS DangGiaDinh_Do,
        14                                                                                   AS DangGiaDinh_Vang
FROM    #TheoMa
WHERE   SoKhoang >= 6;

DROP TABLE #Nhap;
DROP TABLE #Khoang;
DROP TABLE #TheoMa;
GO


/* ═════════════════════════════════════════════════════════════════════════════
   Đ10 — TỶ TRỌNG HÔ HẤP TRONG TIÊU HAO TOÀN VIỆN
   -----------------------------------------------------------------------------
   VÌ SAO PHẢI ĐO — HAI CÂU HỎI, MỘT PHÉP ĐO

   (1) NHU CẦU NỀN. Mô phỏng trên dữ liệu hiện có cho DOI trung vị 160 ngày.
       Không kho dược nào giữ ngần ấy hàng. Nguyên nhân: mẫu số chỉ tính phần
       tiêu hao gán cho ba nhóm hô hấp, trong khi tồn kho là của TOÀN VIỆN.
           D_baseline = tiêu hao toàn viện − tiêu hao hô hấp
       Phải TRỪ, không phải cộng — cộng sẽ tính phần hô hấp hai lần.

   (2) PHẠM VI ĐÚNG CỦA ĐỀ TÀI. Với một mã mà hô hấp chỉ chiếm 3% tiêu hao thì
       mô hình dịch tễ gần như không lái được nhu cầu của nó, dù DOI vẫn tính
       ra số. Biết mã nào có tỷ trọng cao chính là biết TẬP MÃ mà luận điểm của
       đề tài thật sự đúng — và đó là một kết quả nên trình bày, không phải một
       giới hạn nên giấu.

   CỔNG CHẶN: nếu SỐ MÃ có tỷ trọng ≥ 25% mà DƯỚI 100 thì phải thu hẹp tuyên bố
   của đề tài. Xem bảng Đ10-B.

   QUY ƯỚC ĐẾM: một lượt khám mang chẩn đoán hô hấp thì TOÀN BỘ thuốc của lượt
   đó được tính là "hô hấp" — đúng bằng quy ước mà stored procedure đang dùng,
   để con số đo được khớp với con số hệ thống sẽ tính. Lượt có cả bệnh hô hấp
   lẫn bệnh khác vì vậy làm tỷ trọng cao lên; đây là giới hạn có chủ ý và phải
   ghi trong luận văn.
   ═════════════════════════════════════════════════════════════════════════════ */

DECLARE @BENHVIEN_ID VARCHAR(8) = NULL;      -- ⚙ đặt 79428 nếu DB chứa nhiều bệnh viện
DECLARE @SoThang     INT = 12;        -- hạ xuống 6 hoặc 3 nếu chạy quá lâu
DECLARE @Tu  DATE = DATEADD(MONTH, -@SoThang, CAST(GETDATE() AS DATE));
DECLARE @Den DATE = CAST(GETDATE() AS DATE);

IF OBJECT_ID('tempdb..#Icd')    IS NOT NULL DROP TABLE #Icd;
IF OBJECT_ID('tempdb..#Ma3')    IS NOT NULL DROP TABLE #Ma3;
IF OBJECT_ID('tempdb..#KbAll')  IS NOT NULL DROP TABLE #KbAll;
IF OBJECT_ID('tempdb..#KbHH')   IS NOT NULL DROP TABLE #KbHH;
IF OBJECT_ID('tempdb..#Toa')    IS NOT NULL DROP TABLE #Toa;
IF OBJECT_ID('tempdb..#TyTrong') IS NOT NULL DROP TABLE #TyTrong;

/* --- Danh mục ICD đích ---------------------------------------------------- */
SELECT DISTINCT icd.ICD_ID
INTO   #Icd
FROM   TM_ICD icd
WHERE  LTRIM(RTRIM(icd.PHANNHOM)) IN ('J00-J06','J09-J18','J20-J22');
CREATE UNIQUE CLUSTERED INDEX IX_Icd ON #Icd(ICD_ID);

SELECT DISTINCT LEFT(LTRIM(RTRIM(icd.MAICD)), 3) AS Ma3
INTO   #Ma3
FROM   TM_ICD icd
WHERE  LTRIM(RTRIM(icd.PHANNHOM)) IN ('J00-J06','J09-J18','J20-J22')
  AND  icd.MAICD IS NOT NULL AND LEN(LTRIM(RTRIM(icd.MAICD))) >= 3;
CREATE UNIQUE CLUSTERED INDEX IX_Ma3 ON #Ma3(Ma3);

/* --- TẤT CẢ lượt khám trong cửa sổ, kèm tháng ----------------------------- */
/*     Đây là bước nặng nhất. Nếu quá lâu, hạ @SoThang.                       */
SELECT CAST('NT' AS VARCHAR(3)) AS Loai,
       KB.KHAMBENH_ID,
       DATEFROMPARTS(YEAR(tn.NGAYTIEPNHAN), MONTH(tn.NGAYTIEPNHAN), 1) AS Thang
INTO   #KbAll
FROM   TT_TIEPNHAN        tn
JOIN   TT_NOITRU_BENHAN   BA ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
JOIN   TT_NOITRU_KHAMBENH KB ON KB.BENHAN_ID   = BA.BENHAN_ID
WHERE  tn.NGAYTIEPNHAN >= @Tu AND tn.NGAYTIEPNHAN < DATEADD(DAY,1,@Den)
  AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
UNION ALL
SELECT 'NGT', KB.KHAMBENH_ID,
       DATEFROMPARTS(YEAR(KB.NGAYKHAM), MONTH(KB.NGAYKHAM), 1)
FROM   TT_TIEPNHAN          tn
JOIN   TT_NGOAITRU_KHAMBENH KB ON KB.TIEPNHAN_ID = tn.TIEPNHAN_ID
WHERE  KB.NGAYKHAM >= @Tu AND KB.NGAYKHAM < DATEADD(DAY,1,@Den)
  AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID);
CREATE CLUSTERED INDEX IX_KbAll ON #KbAll(Loai, KHAMBENH_ID);

/* --- Lượt khám CÓ chẩn đoán hô hấp (chính hoặc phụ) ----------------------- */
SELECT DISTINCT Loai, KHAMBENH_ID
INTO   #KbHH
FROM (
    -- nội trú, chẩn đoán chính
    SELECT 'NT' AS Loai, KB.KHAMBENH_ID
    FROM   TT_TIEPNHAN        tn
    JOIN   TT_NOITRU_BENHAN   BA ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
    JOIN   TT_NOITRU_KHAMBENH KB ON KB.BENHAN_ID   = BA.BENHAN_ID
    WHERE  tn.NGAYTIEPNHAN >= @Tu AND tn.NGAYTIEPNHAN < DATEADD(DAY,1,@Den)
      AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
      AND (KB.ICDCHINH_ID IN (SELECT ICD_ID FROM #Icd)
        OR TRY_CAST(BA.ICD_BENHCHINH AS INT) IN (SELECT ICD_ID FROM #Icd))
    UNION
    -- nội trú, chẩn đoán phụ (tách chuỗi rồi đối chiếu mã 3 ký tự)
    SELECT 'NT', KB.KHAMBENH_ID
    FROM   TT_TIEPNHAN        tn
    JOIN   TT_NOITRU_BENHAN   BA ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
    JOIN   TT_NOITRU_KHAMBENH KB ON KB.BENHAN_ID   = BA.BENHAN_ID
    CROSS APPLY STRING_SPLIT(ISNULL(KB.DS_MAICDPHU,''), ';') s
    JOIN   #Ma3 m ON m.Ma3 = LEFT(LTRIM(RTRIM(s.value)), 3)
    WHERE  tn.NGAYTIEPNHAN >= @Tu AND tn.NGAYTIEPNHAN < DATEADD(DAY,1,@Den)
      AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
    UNION
    -- ngoại trú, chẩn đoán chính
    SELECT 'NGT', KB.KHAMBENH_ID
    FROM   TT_TIEPNHAN          tn
    JOIN   TT_NGOAITRU_KHAMBENH KB ON KB.TIEPNHAN_ID = tn.TIEPNHAN_ID
    WHERE  KB.NGAYKHAM >= @Tu AND KB.NGAYKHAM < DATEADD(DAY,1,@Den)
      AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
      AND  KB.CHANDOANICD_ID IN (SELECT ICD_ID FROM #Icd)
    UNION
    -- ngoại trú, chẩn đoán phụ
    SELECT 'NGT', KB.KHAMBENH_ID
    FROM   TT_TIEPNHAN          tn
    JOIN   TT_NGOAITRU_KHAMBENH KB ON KB.TIEPNHAN_ID = tn.TIEPNHAN_ID
    CROSS APPLY STRING_SPLIT(ISNULL(KB.DS_MAICDPHU,''), ';') s
    JOIN   #Ma3 m ON m.Ma3 = LEFT(LTRIM(RTRIM(s.value)), 3)
    WHERE  KB.NGAYKHAM >= @Tu AND KB.NGAYKHAM < DATEADD(DAY,1,@Den)
      AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
) z;
CREATE CLUSTERED INDEX IX_KbHH ON #KbHH(Loai, KHAMBENH_ID);

/* --- Tiêu hao: TOÀN VIỆN và phần thuộc lượt hô hấp ------------------------ */
SELECT  t.DUOC_ID,
        t.Thang,
        SUM(t.SoLuong)                                        AS SL_ToanVien,
        SUM(CASE WHEN t.LaHoHap = 1 THEN t.SoLuong ELSE 0 END) AS SL_HoHap
INTO    #Toa
FROM (
    SELECT tt.DUOC_ID, k.Thang,
           CAST(ISNULL(tt.SOLUONGTHUCLINH, tt.SOLUONG) AS FLOAT) AS SoLuong,
           CASE WHEN h.KHAMBENH_ID IS NULL THEN 0 ELSE 1 END      AS LaHoHap
    FROM        TT_NOITRU_TOATHUOC tt
    JOIN        #KbAll k ON k.Loai = 'NT'  AND k.KHAMBENH_ID = tt.KHAMBENH_ID
    LEFT JOIN   #KbHH  h ON h.Loai = 'NT'  AND h.KHAMBENH_ID = tt.KHAMBENH_ID
    WHERE  ISNULL(CAST(tt.HUYTOATHUOC AS NVARCHAR(10)), '0') <> '1'
      AND  ISNULL(tt.SOLUONGTHUCLINH, tt.SOLUONG) > 0
    UNION ALL
    SELECT tt.DUOC_ID, k.Thang,
           CAST(ISNULL(tt.SOLUONG, 0) AS FLOAT),
           CASE WHEN h.KHAMBENH_ID IS NULL THEN 0 ELSE 1 END
    FROM        TT_NGOAITRU_TOATHUOC tt
    JOIN        #KbAll k ON k.Loai = 'NGT' AND k.KHAMBENH_ID = tt.KHAMBENH_ID
    LEFT JOIN   #KbHH  h ON h.Loai = 'NGT' AND h.KHAMBENH_ID = tt.KHAMBENH_ID
    WHERE  ISNULL(CAST(tt.HUYTOATHUOC AS NVARCHAR(10)), '0') <> '1'
      AND  ISNULL(tt.SOLUONG, 0) > 0
) t
GROUP BY t.DUOC_ID, t.Thang;

/* --- Tỷ trọng theo từng mã ------------------------------------------------ */
SELECT  d.MADUOC                                   AS MaVatTu,
        d.TENDUOCDAYDU                             AS TenVatTu,
        COUNT(*)                                   AS SoThangCoXuat,
        CAST(SUM(x.SL_ToanVien) AS decimal(18,1))  AS SL_ToanVien_12T,
        CAST(SUM(x.SL_HoHap)    AS decimal(18,1))  AS SL_HoHap_12T,
        CAST(100.0 * SUM(x.SL_HoHap) / NULLIF(SUM(x.SL_ToanVien),0)
             AS decimal(6,2))                      AS TyTrongHoHap_PhanTram,
        CAST(SUM(x.SL_ToanVien) / NULLIF(COUNT(*),0) AS decimal(18,1)) AS TB_Thang_ToanVien,
        CAST(SUM(x.SL_HoHap)    / NULLIF(COUNT(*),0) AS decimal(18,1)) AS TB_Thang_HoHap,
        CAST((SUM(x.SL_ToanVien) - SUM(x.SL_HoHap)) / NULLIF(COUNT(*),0)
             AS decimal(18,1))                     AS D_baseline_Thang
INTO    #TyTrong
FROM    #Toa x
JOIN    TM_DUOC d ON d.DUOC_ID = x.DUOC_ID
WHERE  (@BENHVIEN_ID IS NULL OR d.BENHVIEN_ID = @BENHVIEN_ID)
GROUP BY d.MADUOC, d.TENDUOCDAYDU
HAVING  SUM(x.SL_ToanVien) > 0;


-- ── Đ10-A · Bối cảnh ────────────────────────────────────────────────────────
-- ► ĐỌC THẾ NÀO: SoMaCoTieuHao là mẫu số thật của "danh mục còn hoạt động".
--   Đo trên DB ứng dụng ra khoảng 650 mã — hai con số nên cùng bậc.
--   TyTrongChung chỉ mang tính tham khảo vì cộng lẫn viên/gói/lọ; con số đáng
--   tin là TyTrongTrungVi (tính theo từng mã rồi lấy trung vị).
SELECT DISTINCT
        N'Đ10-A · Bối cảnh' AS Muc,
        COUNT(*)                                        OVER () AS SoMaCoTieuHao,
        CAST(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY TyTrongHoHap_PhanTram)
             OVER () AS decimal(6,2))                            AS TyTrongTrungVi,
        (SELECT CAST(100.0*SUM(SL_HoHap)/NULLIF(SUM(SL_ToanVien),0) AS decimal(6,2))
         FROM #TyTrong)                                          AS TyTrongChung_ThamKhao
FROM    #TyTrong;


-- ── Đ10-B · CỔNG CHẶN — phân bố tỷ trọng theo mã ───────────────────────────
-- ► ĐỌC THẾ NÀO: cộng SoMa của hai dòng đầu (≥75% và 50-75%) và dòng 25-50%.
--   • Tổng ≥ 100 mã  → luận điểm "dịch hô hấp lái nhu cầu vật tư" đứng vững,
--                      đi tiếp G1 bình thường.
--   • Tổng <  100 mã → DỪNG. Phải thu hẹp tuyên bố của đề tài: mô hình dịch tễ
--                      chỉ lái được một tập nhỏ, và chính việc xác định tập đó
--                      trở thành kết quả cần trình bày (xem phương án B, §4
--                      của lộ trình).
SELECT  CASE WHEN TyTrongHoHap_PhanTram >= 75 THEN N'1 · ≥ 75%  — do hô hấp lái'
             WHEN TyTrongHoHap_PhanTram >= 50 THEN N'2 · 50-75% — chủ yếu hô hấp'
             WHEN TyTrongHoHap_PhanTram >= 25 THEN N'3 · 25-50% — hô hấp đáng kể'
             WHEN TyTrongHoHap_PhanTram >= 10 THEN N'4 · 10-25% — hô hấp phụ'
             ELSE                                  N'5 · < 10%  — gần như không liên quan'
        END                                                        AS NhomTyTrong,
        COUNT(*)                                                   AS SoMa,
        CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS decimal(5,1)) AS PhanTramSoMa,
        CAST(SUM(SL_ToanVien_12T) AS decimal(18,0))                AS TongSL_ToanVien
FROM    #TyTrong
GROUP BY CASE WHEN TyTrongHoHap_PhanTram >= 75 THEN N'1 · ≥ 75%  — do hô hấp lái'
              WHEN TyTrongHoHap_PhanTram >= 50 THEN N'2 · 50-75% — chủ yếu hô hấp'
              WHEN TyTrongHoHap_PhanTram >= 25 THEN N'3 · 25-50% — hô hấp đáng kể'
              WHEN TyTrongHoHap_PhanTram >= 10 THEN N'4 · 10-25% — hô hấp phụ'
              ELSE                                  N'5 · < 10%  — gần như không liên quan'
         END
ORDER BY NhomTyTrong;


-- ── Đ10-C · 40 mã tiêu hao lớn nhất, kèm tỷ trọng và nhu cầu nền ───────────
-- ► ĐỌC THẾ NÀO: đây là các mã sẽ chi phối dashboard. Nhìn cột
--   TyTrongHoHap_PhanTram: nếu phần lớn dưới 20% thì DOI của chúng chủ yếu do
--   D_baseline quyết định chứ không do dự báo dịch — và điều đó phải nói rõ
--   trên giao diện, đừng để người dùng tưởng đèn màu đến từ mô hình dịch tễ.
SELECT TOP 40
        MaVatTu, TenVatTu, SoThangCoXuat,
        SL_ToanVien_12T, SL_HoHap_12T, TyTrongHoHap_PhanTram,
        TB_Thang_ToanVien, TB_Thang_HoHap, D_baseline_Thang
FROM    #TyTrong
ORDER BY SL_ToanVien_12T DESC;


-- ── Đ10-D · Bảng nhu cầu nền đầy đủ (xuất CSV để nạp vào G3) ───────────────
-- ► ĐỌC THẾ NÀO: cột D_baseline_Thang chính là nhu cầu nền hằng tháng của mỗi
--   mã. Lưu bảng này ra CSV; G3 sẽ nạp vào để cộng vào công thức
--       D = Σg Σc Ŷ(g,c) × Norm(i,g,c) + D_baseline
--   Chỉ lấy các mã có ít nhất 3 tháng có xuất — dưới mức đó thì trung bình
--   tháng không có ý nghĩa.
SELECT  MaVatTu, TenVatTu, SoThangCoXuat,
        TB_Thang_ToanVien, TB_Thang_HoHap, D_baseline_Thang,
        TyTrongHoHap_PhanTram
FROM    #TyTrong
WHERE   SoThangCoXuat >= 3
ORDER BY MaVatTu;


DROP TABLE #Icd;
DROP TABLE #Ma3;
DROP TABLE #KbAll;
DROP TABLE #KbHH;
DROP TABLE #Toa;
DROP TABLE #TyTrong;
GO


/* =============================================================================
   SAU KHI CHẠY — GỬI LẠI NHỮNG BẢNG NÀY
     Đ9-C, Đ9-E   → để chốt doi_red_days / doi_amber_days
     Đ10-A, Đ10-B → để quyết định đi tiếp hay thu hẹp phạm vi đề tài
     Đ10-C        → để đối chiếu bằng mắt với hiểu biết của khoa Dược
     Đ10-D (CSV)  → dữ liệu đầu vào cho G3

   NẾU GẶP LỖI
     • "Invalid column name" ở bước 0 → cột có tên khác, gửi lại bảng bước 0.
     • Đ10 chạy quá lâu → hạ @SoThang xuống 6 rồi 3.
     • "Invalid object name TT_NGOAITRU_TOATHUOC" → tên bảng toa ngoại trú khác,
       gửi lại kết quả:
         SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
         WHERE TABLE_NAME LIKE '%TOATHUOC%';
============================================================================= */
