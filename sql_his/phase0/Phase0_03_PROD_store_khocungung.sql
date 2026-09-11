/* =============================================================================
   PHASE 0 — BƯỚC 3: THỦ TỤC KHO VÀ CUNG ỨNG (thủ tục MỚI, chạy độc lập)
   =============================================================================
   Chạy trên: HIS PROD. Cần Phase0_01 đã chạy bên STA.

   VÌ SAO TÁCH RA MỘT THỦ TỤC RIÊNG, KHÔNG NHÉT VÀO usp_MedForecast_DayDuLieu

   1. Khác nhịp. Ca bệnh tổng hợp lại 3 tháng gần nhất mỗi ngày. Tồn kho theo
      lô là ẢNH CHỤP — cần chụp mỗi ngày và GIỮ LẠI từng ngày. Lịch sử nhập
      thì gần như bất biến, chạy lại mỗi tuần là đủ.
   2. Khác nguồn. Bốn bảng TT_DUOC_* không dính gì tới TT_TIEPNHAN /
      TT_NOITRU_* / TM_ICD. Trộn vào một thủ tục 900 dòng chỉ làm khó đọc và
      khó tìm lỗi.
   3. Khác rủi ro. Luồng ca bệnh động tới dữ liệu bệnh nhân; luồng này không.
      Tách ra thì phần liên quan quyền riêng tư gọn lại đúng một file.

   -----------------------------------------------------------------------------
   BA ĐẦU RA

   MF_TonKho_Lo        tồn kho tách theo lô + hạn dùng   → FEFO
   MF_LichSuNhap       từng dòng nhập kho                → σ_L, tỷ lệ giao đủ
   MF_VatTu_ThuocTinh  suy ra từ hai bảng trên           → 4 cột master data

   -----------------------------------------------------------------------------
   ⚠ MỘT ĐIỀU CHƯA XÁC MINH ĐƯỢC — ĐỌC KỸ

   Đ2 xác nhận TT_DUOC_CHUNGTU_CHITIET có cột DONDATHANG_ID, nhưng CHƯA xác
   minh bảng ĐƠN ĐẶT HÀNG tên gì và ngày đặt nằm ở cột nào. Thiếu mảnh đó thì
   KHÔNG tính được thời gian giao hàng thật của nhà cung cấp.

   Thủ tục này vì vậy tính HAI cột và không trộn chúng:
       lead_noibo_ngay = NGAYNHAP − NGAYCHUNGTU     luôn có, thường nhỏ
       lead_thau_ngay  = NGAYNHAP − ngày đặt hàng   NULL cho tới khi có bảng ĐĐH

   Công thức SS cần σ của lead_thau_ngay. Nếu tới lúc triển khai vẫn NULL thì
   `lead_time_nguon` sẽ ghi 'MACDINH' và giao diện PHẢI hiển thị đúng như vậy —
   không được lặng lẽ lấy lead nội bộ thế chỗ, vì lead nội bộ có σ ≈ 0 và sẽ
   cho tồn an toàn thiếu nghiêm trọng.

   CHẠY Đ8 DƯỚI ĐÂY TRƯỚC. Nếu tìm ra bảng ĐĐH, mở khối ⚙ ở phần 3 của thủ tục.
============================================================================= */

USE GIAAN115_HIS;
GO
SET NOCOUNT ON;
GO

/* ═════════════════════════════════════════════════════════════════════════
   Đ8 — DÒ BẢNG ĐƠN ĐẶT HÀNG VÀ LOẠI CHỨNG TỪ NHẬP
   Chỉ đọc. Chạy trước, gửi lại kết quả rồi mới bật khối ⚙.
   ═════════════════════════════════════════════════════════════════════════ */

-- Đ8-A · Bảng nào chứa DONDATHANG_ID (bảng cha của khoá này chính là ĐĐH)
SELECT  c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
FROM    INFORMATION_SCHEMA.COLUMNS c
JOIN    INFORMATION_SCHEMA.TABLES  t ON t.TABLE_NAME = c.TABLE_NAME
                                    AND t.TABLE_TYPE = 'BASE TABLE'
WHERE   c.COLUMN_NAME LIKE '%DONDATHANG%'
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;

-- Đ8-B · Toàn bộ cột của bảng đơn đặt hàng (nếu tên đúng như dự đoán)
SELECT  c.TABLE_NAME, c.ORDINAL_POSITION, c.COLUMN_NAME, c.DATA_TYPE
FROM    INFORMATION_SCHEMA.COLUMNS c
WHERE   c.TABLE_NAME LIKE 'TT_DUOC_DONDATHANG%'
     OR c.TABLE_NAME LIKE '%DONHANG%'
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;

-- Đ8-C · Chứng từ nào là NHẬP KHO? (phân bố loại và mục đích chứng từ)
SELECT  ct.LOAICHUNGTU,
        ct.MUCDICHCHUNGTU_CODE,
        COUNT(*)                                   AS SoChungTu,
        MIN(ct.NGAYNHAP)                           AS SomNhat,
        MAX(ct.NGAYNHAP)                           AS MuonNhat,
        SUM(CASE WHEN ct.NHACUNGCAP_ID IS NOT NULL THEN 1 ELSE 0 END) AS CoNhaCungCap
FROM    TT_DUOC_CHUNGTU ct
WHERE   ct.NGAYNHAP >= DATEADD(MONTH, -24, CAST(GETDATE() AS DATE))
GROUP BY ct.LOAICHUNGTU, ct.MUCDICHCHUNGTU_CODE
ORDER BY SoChungTu DESC;

-- Đ8-D · Cột nối giữa chứng từ và chi tiết (xác nhận tên khoá)
SELECT  c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
FROM    INFORMATION_SCHEMA.COLUMNS c
WHERE   c.TABLE_NAME IN ('TT_DUOC_CHUNGTU', 'TT_DUOC_CHUNGTU_CHITIET')
  AND   c.COLUMN_NAME LIKE '%CHUNGTU%'
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;
GO


/* ═════════════════════════════════════════════════════════════════════════
   THỦ TỤC
   ═════════════════════════════════════════════════════════════════════════ */
CREATE OR ALTER PROCEDURE dbo.usp_MedForecast_DayKhoCungUng
    @BENHVIEN_ID        VARCHAR(8)           = NULL,      -- ⚙ 79428 nếu DB nhiều BV
    @SoThangLichSu      INT           = 36,        -- cửa sổ lịch sử nhập
    @LoaiChungTuNhap    NVARCHAR(400) = NULL,      -- ⚙ điền sau khi có Đ8-C,
                                                   --   vd N'NHAP,NHAPMUA'
    @GomVTYT            BIT           = 0,
    @LeadTimeMacDinh    INT           = 14,        -- dùng khi vật tư chưa từng nhập
    @MoqMacDinh         DECIMAL(18,3) = 1,
    @ChiXem             BIT           = 0
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @BatDau DATETIME2(0) = SYSDATETIME();
    DECLARE @Hom  DATE = CAST(GETDATE() AS DATE);
    DECLARE @TuNgay DATE = DATEADD(MONTH, -@SoThangLichSu, CAST(GETDATE() AS DATE));
    DECLARE @nLo INT = 0, @nNhap INT = 0, @nThuocTinh INT = 0,
            @nLoKhongHan INT = 0, @nHetHan INT = 0;

    BEGIN TRY
        /* =====================================================================
           1) #Meta — danh mục vật tư, cùng bộ lọc với thủ tục ca bệnh
           ===================================================================== */
        IF OBJECT_ID('tempdb..#Meta') IS NOT NULL DROP TABLE #Meta;
        SELECT  D.DUOC_ID,
                D.MADUOC       AS SupplyCode,
                D.TENDUOCDAYDU AS SupplyName,
                CAST(CASE WHEN ld.LOAIVATTU_ID = 'T' THEN 0 ELSE 1 END AS BIT) AS IsVtyt
        INTO    #Meta
        FROM    TM_DUOC     D
        JOIN    TM_LOAIDUOC ld ON ld.LOAIDUOC_ID = D.LOAIDUOC_ID
        WHERE  (@GomVTYT = 1 OR ld.LOAIVATTU_ID = 'T')
          AND   D.MADUOC IS NOT NULL AND LTRIM(RTRIM(D.MADUOC)) <> ''
          AND  (@BENHVIEN_ID IS NULL OR D.BENHVIEN_ID = @BENHVIEN_ID);
        CREATE UNIQUE CLUSTERED INDEX IX_Meta ON #Meta(DUOC_ID);

        /* =====================================================================
           2) #Lo — TỒN KHO THEO LÔ
           ---------------------------------------------------------------------
           LEFT JOIN sang bảng lô, KHÔNG phải INNER JOIN. Dòng tồn có
           SOLONHAP_ID rỗng vẫn phải xuống STA với lot_id = 0 và expiry NULL,
           nếu không thì tổng tồn theo lô sẽ nhỏ hơn MF_TonKho và người dùng
           nhìn thấy "hụt hàng" không có thật.

           Lô đã huỷ (HUY = '1') bị loại — số lượng của chúng đáng ra cũng
           không còn trong TT_DUOC_TONKHO, nhưng loại ở đây cho chắc.
           ===================================================================== */
        IF OBJECT_ID('tempdb..#Lo') IS NOT NULL DROP TABLE #Lo;
        SELECT
            @Hom                                          AS NgaySnapshot,
            m.SupplyCode                                  AS supply_code,
            ISNULL(tk.SOLONHAP_ID, 0)                     AS lot_id,
            MAX(CAST(COALESCE(ln.SOLONHAP, ln.SOLOSANPHAM) AS NVARCHAR(100))) AS lot_code,
            MAX(CAST(ln.HANDUNG AS DATE))                 AS expiry_date,
            CAST(CASE WHEN MAX(CAST(ln.HANDUNG AS DATE)) IS NULL THEN 0 ELSE 1 END AS BIT) AS co_han_dung,
            CAST(SUM(CAST(tk.SOLUONG AS FLOAT)) AS DECIMAL(18,3)) AS quantity,
            COUNT(DISTINCT tk.KHODUOC_ID)                 AS so_kho,
            CAST(MAX(COALESCE(ln.DONGIAMUA, tk.DONGIAMUA)) AS DECIMAL(18,4)) AS don_gia_mua,
            CAST(MAX(ln.DONGIATHAU) AS DECIMAL(18,4))     AS don_gia_thau,
            CAST(MAX(ln.DONGIAVON)  AS DECIMAL(18,4))     AS don_gia_von
        INTO   #Lo
        FROM        TT_DUOC_TONKHO             tk
        JOIN        #Meta                      m  ON m.DUOC_ID = tk.DUOC_ID
        LEFT JOIN   TT_DUOC_CHUNGTU_SOLONHAP   ln ON ln.SOLONHAP_ID = tk.SOLONHAP_ID
                                                 AND ISNULL(ln.HUY, '0') <> '1'
        WHERE  (@BENHVIEN_ID IS NULL OR tk.BENHVIEN_ID = @BENHVIEN_ID)
        GROUP BY m.SupplyCode, ISNULL(tk.SOLONHAP_ID, 0)
        HAVING SUM(CAST(tk.SOLUONG AS FLOAT)) > 0;

        SELECT @nLo         = COUNT(*),
               @nLoKhongHan = SUM(CASE WHEN expiry_date IS NULL THEN 1 ELSE 0 END),
               @nHetHan     = SUM(CASE WHEN expiry_date IS NOT NULL
                                        AND expiry_date < @Hom THEN 1 ELSE 0 END)
        FROM   #Lo;

        PRINT CONCAT(N'Tồn theo lô: ', @nLo, N' dòng; ', @nLoKhongHan,
                     N' dòng KHÔNG có hạn dùng; ', @nHetHan, N' lô đã quá hạn còn nằm trong kho.');

        /* Đối chiếu với tổng tồn — hai con số phải bằng nhau tuyệt đối.
           Lệch nghĩa là JOIN đã làm nhân bản hoặc rơi dòng.                   */
        DECLARE @TongLo FLOAT = (SELECT ISNULL(SUM(quantity), 0) FROM #Lo);
        DECLARE @TongTK FLOAT = (
            SELECT ISNULL(SUM(CAST(tk.SOLUONG AS FLOAT)), 0)
            FROM   TT_DUOC_TONKHO tk
            JOIN   #Meta m ON m.DUOC_ID = tk.DUOC_ID
            WHERE (@BENHVIEN_ID IS NULL OR tk.BENHVIEN_ID = @BENHVIEN_ID)
              AND  CAST(tk.SOLUONG AS FLOAT) > 0);
        IF ABS(@TongLo - @TongTK) > 0.5
            PRINT CONCAT(N'CẢNH BÁO: tổng tồn theo lô (', @TongLo,
                         N') khác tổng tồn thô (', @TongTK,
                         N'). Nghi JOIN sang TT_DUOC_CHUNGTU_SOLONHAP nhân bản dòng.');

        /* =====================================================================
           3) #Nhap — LỊCH SỬ NHẬP KHO
           ---------------------------------------------------------------------
           Mã vật tư suy qua SOLONHAP_ID → TT_DUOC_CHUNGTU_SOLONHAP.DUOC_ID,
           KHÔNG giả định TT_DUOC_CHUNGTU_CHITIET có cột DUOC_ID.

           Bộ lọc chứng từ nhập: mặc định "có ngày nhập và số thực tế dương".
           Sau khi có kết quả Đ8-C thì siết lại bằng @LoaiChungTuNhap để loại
           các chứng từ điều chuyển nội bộ / trả hàng — chúng làm nhiễu σ_L.
           ===================================================================== */
        IF OBJECT_ID('tempdb..#LoaiCT') IS NOT NULL DROP TABLE #LoaiCT;
        SELECT LTRIM(RTRIM(value)) AS Ma
        INTO   #LoaiCT
        FROM   STRING_SPLIT(ISNULL(@LoaiChungTuNhap, N''), ',')
        WHERE  LTRIM(RTRIM(value)) <> '';

        IF OBJECT_ID('tempdb..#Nhap') IS NOT NULL DROP TABLE #Nhap;
        SELECT
            ct.CHUNGTU_ID                                  AS chungtu_id,
            m.SupplyCode                                   AS supply_code,
            ISNULL(ctct.SOLONHAP_ID, 0)                    AS lot_id,
            CAST(ct.NGAYCHUNGTU AS DATE)                   AS ngay_chungtu,
            CAST(ct.NGAYNHAP    AS DATE)                   AS ngay_nhap,
            CAST(NULL AS DATE)                             AS ngay_dat_hang,   -- ⚙ xem khối dưới
            DATEDIFF(DAY, CAST(ct.NGAYCHUNGTU AS DATE),
                          CAST(ct.NGAYNHAP AS DATE))       AS lead_noibo_ngay,
            CAST(NULL AS INT)                              AS lead_thau_ngay,
            ct.NHACUNGCAP_ID                               AS nhacungcap_id,
            COALESCE(ctct.GOITHAU_ID, ct.GOITHAU_ID)       AS goithau_id,
            ctct.DONDATHANG_ID                             AS dondathang_id,
            CAST(ct.LOAICHUNGTU AS NVARCHAR(50))           AS loai_chungtu,
            CAST(ct.MUCDICHCHUNGTU_CODE AS NVARCHAR(50))   AS mucdich_code,
            CAST(SUM(CAST(ctct.SOLUONGYEUCAU AS FLOAT)) AS DECIMAL(18,3)) AS so_luong_yeucau,
            CAST(SUM(CAST(ctct.SOLUONGTHUCTE AS FLOAT)) AS DECIMAL(18,3)) AS so_luong_thucte,
            CAST(MAX(CAST(ctct.DONGIATHAU AS FLOAT)) AS DECIMAL(18,4))    AS don_gia_thau,
            MAX(CAST(COALESCE(ctct.HANDUNG, ln.HANDUNG) AS DATE))         AS han_dung
        INTO   #Nhap
        FROM        TT_DUOC_CHUNGTU           ct
        JOIN        TT_DUOC_CHUNGTU_CHITIET   ctct ON ctct.CHUNGTU_ID  = ct.CHUNGTU_ID
        LEFT JOIN   TT_DUOC_CHUNGTU_SOLONHAP  ln   ON ln.SOLONHAP_ID   = ctct.SOLONHAP_ID
        JOIN        #Meta                     m    ON m.DUOC_ID        = ln.DUOC_ID
        WHERE  ct.NGAYNHAP IS NOT NULL
          AND  CAST(ct.NGAYNHAP AS DATE) >= @TuNgay
          AND  CAST(ctct.SOLUONGTHUCTE AS FLOAT) > 0
          AND  (@BENHVIEN_ID IS NULL OR ct.BENHVIEN_ID = @BENHVIEN_ID)
          AND  (NOT EXISTS (SELECT 1 FROM #LoaiCT)
                OR CAST(ct.LOAICHUNGTU AS NVARCHAR(50)) IN (SELECT Ma FROM #LoaiCT)
                OR CAST(ct.MUCDICHCHUNGTU_CODE AS NVARCHAR(50)) IN (SELECT Ma FROM #LoaiCT))
        GROUP BY ct.CHUNGTU_ID, m.SupplyCode, ISNULL(ctct.SOLONHAP_ID, 0),
                 CAST(ct.NGAYCHUNGTU AS DATE), CAST(ct.NGAYNHAP AS DATE),
                 ct.NHACUNGCAP_ID, COALESCE(ctct.GOITHAU_ID, ct.GOITHAU_ID),
                 ctct.DONDATHANG_ID, CAST(ct.LOAICHUNGTU AS NVARCHAR(50)),
                 CAST(ct.MUCDICHCHUNGTU_CODE AS NVARCHAR(50));

        /* ⚙ ==================================================================
           THỜI GIAN GIAO HÀNG THẬT — mở khối này SAU KHI có kết quả Đ8-A/Đ8-B.
           Thay <BANG_DDH> và <COT_NGAY_DAT> bằng tên thật rồi bỏ chú thích.
           SQL Server phân giải tên bảng khi CHẠY chứ không khi tạo thủ tục,
           nên khối nằm trong IF sẽ không gây lỗi biên dịch nếu bảng chưa có.

        IF OBJECT_ID('dbo.<BANG_DDH>') IS NOT NULL
        BEGIN
            UPDATE n
            SET    n.ngay_dat_hang  = CAST(dh.<COT_NGAY_DAT> AS DATE),
                   n.lead_thau_ngay = DATEDIFF(DAY, CAST(dh.<COT_NGAY_DAT> AS DATE),
                                                    n.ngay_nhap)
            FROM   #Nhap n
            JOIN   dbo.<BANG_DDH> dh ON dh.DONDATHANG_ID = n.dondathang_id;

            PRINT CONCAT(N'Đã tính lead_thau_ngay cho ', @@ROWCOUNT, N' dòng nhập.');
        END
           =================================================================== */

        /* Lead âm là dữ liệu bẩn (ngày nhập trước ngày chứng từ / ngày đặt).
           Không sửa, chỉ vô hiệu hoá để không kéo lệch trung vị và σ.         */
        UPDATE #Nhap SET lead_noibo_ngay = NULL WHERE lead_noibo_ngay < 0;
        UPDATE #Nhap SET lead_thau_ngay  = NULL WHERE lead_thau_ngay  < 0;

        UPDATE #Nhap
        SET    so_luong_yeucau = NULLIF(so_luong_yeucau, 0);

        SELECT @nNhap = COUNT(*) FROM #Nhap;
        PRINT CONCAT(N'Lịch sử nhập: ', @nNhap, N' dòng trong ', @SoThangLichSu, N' tháng.');

        /* =====================================================================
           4) #ThuocTinh — suy ra 4 cột master data
           ---------------------------------------------------------------------
           TRUNG VỊ, không phải trung bình. Phân bố thời gian giao hàng lệch
           phải: đa số về đúng hẹn, thỉnh thoảng một lần chậm rất lâu. Trung
           bình sẽ bị kéo đi và cho L̄ lớn giả tạo, còn trung vị thì không.
           Nhưng σ (độ lệch chuẩn) vẫn tính trên toàn bộ mẫu — chính cái đuôi
           dài đó là lý do phải có tồn an toàn.

           `lead_time_nguon`:
               'THAU'    có ngày đặt hàng thật  → dùng được cho công thức SS
               'NOIBO'   chỉ có lead nội bộ     → σ không đại diện, CẢNH BÁO
               'MACDINH' chưa từng nhập         → dùng @LeadTimeMacDinh
           ===================================================================== */
        IF OBJECT_ID('tempdb..#LeadTS') IS NOT NULL DROP TABLE #LeadTS;
        SELECT supply_code,
               ngay_nhap,
               COALESCE(lead_thau_ngay, lead_noibo_ngay) AS lead_ngay,
               CASE WHEN lead_thau_ngay IS NOT NULL THEN 1 ELSE 0 END AS co_lead_thau,
               so_luong_thucte,
               so_luong_yeucau,
               nhacungcap_id,
               don_gia_thau
        INTO   #LeadTS
        FROM   #Nhap;

        /* Trung vị và phân vị 90 — PERCENTILE_CONT chỉ có dạng window,
           nên phải qua một bước DISTINCT.                                     */
        IF OBJECT_ID('tempdb..#Pct') IS NOT NULL DROP TABLE #Pct;
        SELECT DISTINCT
               supply_code,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lead_ngay)
                   OVER (PARTITION BY supply_code) AS lead_trungvi,
               PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY lead_ngay)
                   OVER (PARTITION BY supply_code) AS lead_p90
        INTO   #Pct
        FROM   #LeadTS
        WHERE  lead_ngay IS NOT NULL;

        /* Chu kỳ nhập thực tế — khoảng cách giữa hai lần nhập liên tiếp.
           Đây là con số để đối chiếu với T = 30 ngày đang giả định trong mô
           hình rà soát định kỳ (R,S). Nếu trung vị chu kỳ là 45 ngày thì
           T = 30 đang lạc quan và khoảng bảo vệ T + L bị tính thiếu.          */
        IF OBJECT_ID('tempdb..#ChuKy') IS NOT NULL DROP TABLE #ChuKy;
        SELECT DISTINCT
               supply_code,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY khoang)
                   OVER (PARTITION BY supply_code) AS chu_ky_trungvi
        INTO   #ChuKy
        FROM (
            SELECT supply_code,
                   DATEDIFF(DAY,
                            LAG(ngay_nhap) OVER (PARTITION BY supply_code ORDER BY ngay_nhap),
                            ngay_nhap) AS khoang
            FROM  (SELECT DISTINCT supply_code, ngay_nhap FROM #LeadTS) d
        ) k
        WHERE khoang IS NOT NULL AND khoang > 0;

        IF OBJECT_ID('tempdb..#ThuocTinh') IS NOT NULL DROP TABLE #ThuocTinh;
        SELECT
            m.SupplyCode                                      AS supply_code,
            ISNULL(a.so_lan_nhap, 0)                          AS so_lan_nhap,
            a.so_nha_cung_cap,
            CAST(ISNULL(p.lead_trungvi, @LeadTimeMacDinh) AS INT)   AS lead_time_ngay_trungvi,
            CAST(a.lead_tb     AS DECIMAL(10,2))              AS lead_time_ngay_tb,
            CAST(a.lead_dolech AS DECIMAL(10,2))              AS lead_time_ngay_dolech,
            CAST(p.lead_p90    AS INT)                        AS lead_time_ngay_p90,
            CASE WHEN a.so_lan_co_lead_thau > 0 THEN 'THAU'
                 WHEN a.so_lan_nhap          > 0 THEN 'NOIBO'
                 ELSE 'MACDINH' END                           AS lead_time_nguon,
            CAST(ck.chu_ky_trungvi AS INT)                    AS chu_ky_nhap_trungvi,
            CAST(ISNULL(a.moq, @MoqMacDinh) AS DECIMAL(18,3)) AS moq,
            CASE WHEN a.moq IS NULL THEN 'MACDINH' ELSE 'QUANSAT' END AS moq_nguon,
            CAST(a.ty_le_giao_du AS DECIMAL(9,4))             AS ty_le_giao_du_tb,
            CAST(g.don_gia_mua  AS DECIMAL(18,4))             AS don_gia_mua,
            CAST(g.don_gia_thau AS DECIMAL(18,4))             AS don_gia_thau,
            CAST(g.don_gia_von  AS DECIMAL(18,4))             AS don_gia_von,
            a.ngay_nhap_gan_nhat
        INTO   #ThuocTinh
        FROM   (SELECT DISTINCT SupplyCode FROM #Meta) m
        LEFT JOIN (
            SELECT supply_code,
                   COUNT(*)                            AS so_lan_nhap,
                   COUNT(DISTINCT nhacungcap_id)       AS so_nha_cung_cap,
                   SUM(co_lead_thau)                   AS so_lan_co_lead_thau,
                   AVG(CAST(lead_ngay AS FLOAT))       AS lead_tb,
                   STDEV(CAST(lead_ngay AS FLOAT))     AS lead_dolech,
                   MIN(NULLIF(so_luong_thucte, 0))     AS moq,
                   AVG(CASE WHEN so_luong_yeucau > 0
                            THEN so_luong_thucte / so_luong_yeucau END) AS ty_le_giao_du,
                   MAX(ngay_nhap)                      AS ngay_nhap_gan_nhat
            FROM   #LeadTS
            GROUP BY supply_code
        ) a ON a.supply_code = m.SupplyCode
        LEFT JOIN #Pct   p  ON p.supply_code  = m.SupplyCode
        LEFT JOIN #ChuKy ck ON ck.supply_code = m.SupplyCode
        /* Giá của LẦN NHẬP GẦN NHẤT — không phải trung bình lịch sử.
           ABC theo giá trị cần chi phí hiện hành.                              */
        OUTER APPLY (
            SELECT TOP 1 l.don_gia_mua, l.don_gia_thau, l.don_gia_von
            FROM   #Lo l
            WHERE  l.supply_code = m.SupplyCode
              AND (l.don_gia_mua IS NOT NULL OR l.don_gia_thau IS NOT NULL)
            ORDER BY l.expiry_date DESC, l.lot_id DESC
        ) g;

        SELECT @nThuocTinh = COUNT(*) FROM #ThuocTinh;

        /* =====================================================================
           5) Đẩy xuống STA
           ===================================================================== */
        IF @ChiXem = 1
        BEGIN
            PRINT N'CHẾ ĐỘ CHỈ XEM — không đẩy.';

            SELECT TOP 200 * FROM #Lo   ORDER BY expiry_date, supply_code;
            SELECT TOP 200 * FROM #Nhap ORDER BY ngay_nhap DESC;

            /* Bảng quan trọng nhất để đánh giá: nguồn thời gian giao hàng */
            SELECT lead_time_nguon,
                   COUNT(*)                                    AS SoVatTu,
                   CAST(AVG(lead_time_ngay_trungvi * 1.0) AS decimal(10,1)) AS TrungViTB,
                   CAST(AVG(lead_time_ngay_dolech)        AS decimal(10,2)) AS SigmaTB,
                   CAST(AVG(chu_ky_nhap_trungvi * 1.0)    AS decimal(10,1)) AS ChuKyNhapTB
            FROM   #ThuocTinh
            GROUP BY lead_time_nguon
            ORDER BY SoVatTu DESC;

            /* Hạn dùng: bức tranh FEFO trước khi triển khai */
            SELECT CASE WHEN expiry_date IS NULL                       THEN N'0 · không có hạn dùng'
                        WHEN expiry_date <  @Hom                       THEN N'1 · đã quá hạn'
                        WHEN expiry_date <  DATEADD(MONTH, 3,  @Hom)   THEN N'2 · dưới 3 tháng'
                        WHEN expiry_date <  DATEADD(MONTH, 6,  @Hom)   THEN N'3 · 3-6 tháng'
                        WHEN expiry_date <  DATEADD(MONTH, 12, @Hom)   THEN N'4 · 6-12 tháng'
                        ELSE                                                N'5 · trên 12 tháng' END AS Khoang,
                   COUNT(*)                                            AS SoLo,
                   COUNT(DISTINCT supply_code)                         AS SoVatTu,
                   CAST(SUM(quantity) AS decimal(18,1))                AS TongSoLuong,
                   CAST(SUM(quantity * ISNULL(don_gia_mua,0)) AS decimal(18,0)) AS GiaTri
            FROM   #Lo
            GROUP BY CASE WHEN expiry_date IS NULL                     THEN N'0 · không có hạn dùng'
                          WHEN expiry_date <  @Hom                     THEN N'1 · đã quá hạn'
                          WHEN expiry_date <  DATEADD(MONTH, 3,  @Hom) THEN N'2 · dưới 3 tháng'
                          WHEN expiry_date <  DATEADD(MONTH, 6,  @Hom) THEN N'3 · 3-6 tháng'
                          WHEN expiry_date <  DATEADD(MONTH, 12, @Hom) THEN N'4 · 6-12 tháng'
                          ELSE                                              N'5 · trên 12 tháng' END
            ORDER BY Khoang;

            RETURN;
        END

        IF @nLo = 0
            THROW 50011, N'Không lấy được dòng tồn kho theo lô nào — DỪNG, không đụng vào STA.', 1;

        /* Tồn theo lô: xoá đúng ảnh chụp của HÔM NAY rồi chèn lại (chạy lại
           trong ngày không sinh trùng), giữ nguyên ảnh chụp các ngày trước.  */
        DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TonKho_Lo]
        WHERE  NgaySnapshot = @Hom;

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TonKho_Lo]
              (NgaySnapshot, supply_code, lot_id, lot_code, expiry_date, co_han_dung,
               quantity, so_kho, don_gia_mua, don_gia_thau, don_gia_von, NgayCapNhat)
        SELECT NgaySnapshot, supply_code, lot_id, lot_code, expiry_date, co_han_dung,
               quantity, so_kho, don_gia_mua, don_gia_thau, don_gia_von, SYSDATETIME()
        FROM   #Lo;

        /* Lịch sử nhập: xoá cửa sổ đang nạp lại rồi chèn. */
        DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_LichSuNhap]
        WHERE  ngay_nhap >= @TuNgay;

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_LichSuNhap]
              (chungtu_id, supply_code, lot_id, ngay_chungtu, ngay_nhap, ngay_dat_hang,
               lead_noibo_ngay, lead_thau_ngay, nhacungcap_id, goithau_id, dondathang_id,
               loai_chungtu, mucdich_code, so_luong_yeucau, so_luong_thucte,
               ty_le_giao_du, don_gia_thau, han_dung, NgayCapNhat)
        SELECT chungtu_id, supply_code, lot_id, ngay_chungtu, ngay_nhap, ngay_dat_hang,
               lead_noibo_ngay, lead_thau_ngay, nhacungcap_id, goithau_id, dondathang_id,
               loai_chungtu, mucdich_code, so_luong_yeucau, so_luong_thucte,
               CASE WHEN so_luong_yeucau > 0
                    THEN CAST(so_luong_thucte / so_luong_yeucau AS DECIMAL(9,4)) END,
               don_gia_thau, han_dung, SYSDATETIME()
        FROM   #Nhap;

        /* Thuộc tính vật tư: thay toàn bộ (bảng nhỏ, ~5.000 dòng). */
        EXEC (N'DELETE FROM MEDFORECAST_DW.dbo.MF_VatTu_ThuocTinh;') AT [MEDFORECAST_STA];

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_VatTu_ThuocTinh]
              (supply_code, so_lan_nhap, so_nha_cung_cap,
               lead_time_ngay_trungvi, lead_time_ngay_tb, lead_time_ngay_dolech,
               lead_time_ngay_p90, lead_time_nguon, chu_ky_nhap_trungvi,
               moq, moq_nguon, ty_le_giao_du_tb,
               don_gia_mua, don_gia_thau, don_gia_von, ngay_nhap_gan_nhat, NgayCapNhat)
        SELECT supply_code, so_lan_nhap, so_nha_cung_cap,
               lead_time_ngay_trungvi, lead_time_ngay_tb, lead_time_ngay_dolech,
               lead_time_ngay_p90, lead_time_nguon, chu_ky_nhap_trungvi,
               moq, moq_nguon, ty_le_giao_du_tb,
               don_gia_mua, don_gia_thau, don_gia_von, ngay_nhap_gan_nhat, SYSDATETIME()
        FROM   #ThuocTinh;

        UPDATE [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_Watermark]
        SET    MocDaDay = @Hom, LanChayCuoi = SYSDATETIME()
        WHERE  TenLuong = 'KhoCungUng';

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
              (BatDau, KetThuc, TuNgay, SoDongCaBenh, SoDongTonKho, TrangThai, ThongDiep)
        VALUES (@BatDau, SYSDATETIME(), @TuNgay, @nNhap, @nLo, 'ok',
                CONCAT(N'KhoCungUng: ', @nLo, N' dòng tồn theo lô (',
                       @nLoKhongHan, N' không có hạn dùng, ', @nHetHan, N' quá hạn); ',
                       @nNhap, N' dòng lịch sử nhập; ',
                       @nThuocTinh, N' dòng thuộc tính vật tư.'));

        PRINT CONCAT(N'Xong. Lô = ', @nLo, N', lịch sử nhập = ', @nNhap,
                     N', thuộc tính = ', @nThuocTinh);
    END TRY
    BEGIN CATCH
        BEGIN TRY
            INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
                  (BatDau, KetThuc, TuNgay, TrangThai, ThongDiep)
            VALUES (@BatDau, SYSDATETIME(), @TuNgay, 'failed',
                    CONCAT(N'KhoCungUng — lỗi ', ERROR_NUMBER(), N' dòng ', ERROR_LINE(),
                           N': ', ERROR_MESSAGE()));
        END TRY
        BEGIN CATCH
            PRINT N'Không ghi được nhật ký xuống STA — kiểm tra linked server.';
        END CATCH
        THROW;
    END CATCH
END
GO


/* =============================================================================
   CÁCH DÙNG

   BƯỚC A · Xem trước, không đẩy. Đọc kỹ hai bảng cuối.
       EXEC dbo.usp_MedForecast_DayKhoCungUng @ChiXem = 1;

       Bảng "nguồn thời gian giao hàng": nếu cột lead_time_nguon = 'NOIBO'
       chiếm đa số thì σ_L chưa đo được thật, và Phase 2 phải ghi rõ trên
       giao diện là đang dùng L cố định.

       Bảng "hạn dùng": số lô ở khoảng "0 · không có hạn dùng" quyết định
       FEFO phủ được bao nhiêu phần trăm kho. Dưới 50% thì màn hình FEFO phải
       có nhãn "chỉ áp dụng cho N/M mã có dữ liệu lô".

   BƯỚC B · Nạp thật.
       EXEC dbo.usp_MedForecast_DayKhoCungUng;

   BƯỚC C · Lịch chạy (thêm vào 04_PROD_job.sql, hoặc tạo job riêng):
       • Tồn kho theo lô — MỖI NGÀY, sau job ca bệnh:
             EXEC dbo.usp_MedForecast_DayKhoCungUng @SoThangLichSu = 3;
         (cửa sổ lịch sử ngắn cho nhanh; ảnh chụp tồn vẫn đủ)
       • Lịch sử nhập đầy đủ — MỖI CHỦ NHẬT:
             EXEC dbo.usp_MedForecast_DayKhoCungUng @SoThangLichSu = 36;

   -----------------------------------------------------------------------------
   HAI CON SỐ SẼ ĐỔI THIẾT KẾ PHASE 2, CHÚ Ý KHI ĐỌC KẾT QUẢ

   1. chu_ky_nhap_trungvi so với T = 30 ngày.
      Mô hình rà soát định kỳ (R,S) đang giả định T = 30. Nếu trung vị chu kỳ
      nhập thực tế là 45 hay 60 ngày thì khoảng bảo vệ đúng phải là T + L với
      T thật, và tồn an toàn hiện tính theo T = 30 đang THIẾU.

   2. ty_le_giao_du_tb.
      Nếu trung bình dưới 0,95 thì nhà cung cấp thường xuyên giao thiếu, và
      đó là một nguồn rủi ro thứ hai bên cạnh thời gian. Khi đó lượng đặt phải
      chia cho tỷ lệ này (đặt 105 để nhận 100), chứ không phải tăng tồn an toàn.
============================================================================= */
