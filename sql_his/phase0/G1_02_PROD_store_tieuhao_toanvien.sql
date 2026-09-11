/* =============================================================================
   G1 — BƯỚC 2: THỦ TỤC TIÊU HAO TOÀN VIỆN (thủ tục MỚI)
   =============================================================================
   Chạy trên: HIS PROD — GIAAN115_HIS.
   Điều kiện: đã chạy G1_01_STA_sua_bang.sql bên STA.

   -----------------------------------------------------------------------------
   VÌ SAO TÁCH RA MỘT THỦ TỤC RIÊNG THAY VÌ NHÉT VÀO usp_MedForecast_DayDuLieu

   1. KHÁC VŨ TRỤ DỮ LIỆU. Thủ tục ca bệnh chỉ động tới các lượt khám thuộc ba
      nhóm ICD hô hấp. Luồng này phải quét TOÀN BỘ lượt khám của bệnh viện —
      một tập lớn hơn nhiều bậc. Trộn hai vũ trụ vào một thủ tục làm mọi bảng
      tạm ở giữa mang hai nghĩa, và đó là cách sinh lỗi im lặng.

   2. KHÁC CỬA SỔ THỜI GIAN. Thủ tục ca bệnh nạp lại từ 2019 khi
      @NapLaiToanBo = 1. Luồng này chỉ cần 24 tháng gần nhất — nhu cầu nền của
      năm 2019 không nói gì về tháng tới. Nếu dùng chung tham số thì lần nạp
      toàn bộ sẽ quét bảy năm toa thuốc toàn viện, gần như chắc chắn treo.

   3. KHÁC NHỊP CHẠY. Ca bệnh chạy hằng ngày. Nhu cầu nền đổi rất chậm — chạy
      hằng tuần là đủ.

   Kết quả nghiệp vụ vẫn đúng như yêu cầu: MF_TieuHao_Tong được nạp KHÔNG LỌC
   ICD, làm nguồn cho D_baseline.

   -----------------------------------------------------------------------------
   QUY ƯỚC ĐẾM — giống hệt Đ10 để số liệu khớp với phép đo đã duyệt

   Một lượt khám có chẩn đoán hô hấp thì TOÀN BỘ thuốc của lượt đó được tính là
   "hô hấp". Lượt đồng mắc (vừa viêm phổi vừa bệnh khác) vì vậy làm phần hô hấp
   cao lên. Đây là cận trên có chủ ý, và phải ghi trong luận văn.

   Hệ quả cần nhớ: d_baseline = toàn viện − hô hấp là cận DƯỚI của nhu cầu nền.
   Nếu sau này đổi sang quy ước chia tỷ lệ theo số chẩn đoán, phải đo lại Đ10.
============================================================================= */

USE GIAAN115_HIS;
GO

CREATE OR ALTER PROCEDURE dbo.usp_MedForecast_DayTieuHaoToanVien
    @BENHVIEN_ID   VARCHAR(8) = NULL,   -- KHỚP KIỂU CỘT tn.BENHVIEN_ID (varchar(8)); INT sẽ ép kiểu ngầm lên cột → mất index      -- ⚙ đặt 79428 nếu DB nhiều bệnh viện
    @SoThang       INT = 24,        -- cửa sổ nạp lại; hạ xuống nếu chạy quá lâu
    @NhomBenhDich  NVARCHAR(400) = N'J00-J06,J09-J18,J20-J22',
    @GomVTYT       BIT = 1,         -- 1 = lấy cả VTYT. Ở đây MẶC ĐỊNH BẬT:
                                    -- mẫu số của DOI phải phủ mọi thứ có trong kho,
                                    -- không chỉ thuốc.
    @ChiXem        BIT = 0
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @BatDau DATETIME2(0) = SYSDATETIME();
    DECLARE @Den DATE = CAST(GETDATE() AS DATE);
    DECLARE @Tu  DATE = DATEFROMPARTS(YEAR(DATEADD(MONTH, -@SoThang, CAST(GETDATE() AS DATE))),
                                      MONTH(DATEADD(MONTH, -@SoThang, CAST(GETDATE() AS DATE))), 1);
    DECLARE @nDong INT = 0, @nMa INT = 0, @nLuot INT = 0;
    DECLARE @TyTrongChung DECIMAL(6,2);

    BEGIN TRY
        PRINT CONCAT(N'Tiêu hao toàn viện từ ', CONVERT(varchar(10), @Tu, 120),
                     N' đến ', CONVERT(varchar(10), @Den, 120));

        /* ── 1) Danh mục vật tư ─────────────────────────────────────────── */
        IF OBJECT_ID('tempdb..#Meta') IS NOT NULL DROP TABLE #Meta;
        SELECT  D.DUOC_ID,
                D.MADUOC        AS SupplyCode,
                D.TENDUOCDAYDU  AS SupplyName,
                dvt.TENDONVITINH AS SupplyUnit,
                CAST(CASE WHEN ld.LOAIVATTU_ID = 'T' THEN 0 ELSE 1 END AS BIT) AS IsVtyt
        INTO    #Meta
        FROM      TM_DUOC      D
        JOIN      TM_LOAIDUOC  ld  ON ld.LOAIDUOC_ID   = D.LOAIDUOC_ID
        LEFT JOIN TM_DONVITINH dvt ON dvt.DONVITINH_ID = D.DONVITINH_ID
        WHERE  (@GomVTYT = 1 OR ld.LOAIVATTU_ID = 'T')
          AND   D.MADUOC IS NOT NULL AND LTRIM(RTRIM(D.MADUOC)) <> ''
          AND   D.TENDUOCDAYDU IS NOT NULL
          AND  (@BENHVIEN_ID IS NULL OR D.BENHVIEN_ID = @BENHVIEN_ID);
        CREATE UNIQUE CLUSTERED INDEX IX_Meta ON #Meta(DUOC_ID);

        /* ── 2) Danh mục ICD đích ───────────────────────────────────────── */
        IF OBJECT_ID('tempdb..#NhomDich') IS NOT NULL DROP TABLE #NhomDich;
        SELECT LTRIM(RTRIM(value)) AS Nhom
        INTO   #NhomDich
        FROM   STRING_SPLIT(@NhomBenhDich, ',')
        WHERE  LTRIM(RTRIM(value)) <> '';

        IF OBJECT_ID('tempdb..#Icd') IS NOT NULL DROP TABLE #Icd;
        SELECT DISTINCT icd.ICD_ID
        INTO   #Icd
        FROM   TM_ICD icd
        JOIN   #NhomDich n ON n.Nhom = LTRIM(RTRIM(icd.PHANNHOM));
        CREATE UNIQUE CLUSTERED INDEX IX_Icd ON #Icd(ICD_ID);

        IF OBJECT_ID('tempdb..#Ma3') IS NOT NULL DROP TABLE #Ma3;
        SELECT DISTINCT LEFT(LTRIM(RTRIM(icd.MAICD)), 3) AS Ma3
        INTO   #Ma3
        FROM   TM_ICD icd
        JOIN   #NhomDich n ON n.Nhom = LTRIM(RTRIM(icd.PHANNHOM))
        WHERE  icd.MAICD IS NOT NULL AND LEN(LTRIM(RTRIM(icd.MAICD))) >= 3;
        CREATE UNIQUE CLUSTERED INDEX IX_Ma3 ON #Ma3(Ma3);

        /* ── 3) TẤT CẢ lượt khám trong cửa sổ, kèm tháng ────────────────── */
        /*     Bước nặng nhất. Nếu treo, hạ @SoThang.                        */
        IF OBJECT_ID('tempdb..#KbAll') IS NOT NULL DROP TABLE #KbAll;
        SELECT CAST('NT' AS VARCHAR(3)) AS Loai,
               KB.KHAMBENH_ID,
               tn.TIEPNHAN_ID,
               DATEFROMPARTS(YEAR(tn.NGAYTIEPNHAN), MONTH(tn.NGAYTIEPNHAN), 1) AS Thang
        INTO   #KbAll
        FROM   TT_TIEPNHAN        tn
        JOIN   TT_NOITRU_BENHAN   BA ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
        JOIN   TT_NOITRU_KHAMBENH KB ON KB.BENHAN_ID   = BA.BENHAN_ID
        WHERE  tn.NGAYTIEPNHAN >= @Tu AND tn.NGAYTIEPNHAN < DATEADD(DAY,1,@Den)
          AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
        UNION ALL
        SELECT 'NGT', KB.KHAMBENH_ID, tn.TIEPNHAN_ID,
               DATEFROMPARTS(YEAR(KB.NGAYKHAM), MONTH(KB.NGAYKHAM), 1)
        FROM   TT_TIEPNHAN          tn
        JOIN   TT_NGOAITRU_KHAMBENH KB ON KB.TIEPNHAN_ID = tn.TIEPNHAN_ID
        WHERE  KB.NGAYKHAM >= @Tu AND KB.NGAYKHAM < DATEADD(DAY,1,@Den)
          AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID);
        CREATE CLUSTERED INDEX IX_KbAll ON #KbAll(Loai, KHAMBENH_ID);

        SELECT @nLuot = COUNT(DISTINCT TIEPNHAN_ID) FROM #KbAll;

        /* ── 4) Lượt khám CÓ chẩn đoán hô hấp (chính hoặc phụ) ──────────── */
        IF OBJECT_ID('tempdb..#KbHH') IS NOT NULL DROP TABLE #KbHH;
        SELECT DISTINCT Loai, KHAMBENH_ID
        INTO   #KbHH
        FROM (
            SELECT 'NT' AS Loai, KB.KHAMBENH_ID
            FROM   TT_TIEPNHAN        tn
            JOIN   TT_NOITRU_BENHAN   BA ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
            JOIN   TT_NOITRU_KHAMBENH KB ON KB.BENHAN_ID   = BA.BENHAN_ID
            WHERE  tn.NGAYTIEPNHAN >= @Tu AND tn.NGAYTIEPNHAN < DATEADD(DAY,1,@Den)
              AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
              AND (KB.ICDCHINH_ID IN (SELECT ICD_ID FROM #Icd)
                OR TRY_CAST(BA.ICD_BENHCHINH AS INT) IN (SELECT ICD_ID FROM #Icd))
            UNION
            SELECT 'NT', KB.KHAMBENH_ID
            FROM   TT_TIEPNHAN        tn
            JOIN   TT_NOITRU_BENHAN   BA ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
            JOIN   TT_NOITRU_KHAMBENH KB ON KB.BENHAN_ID   = BA.BENHAN_ID
            CROSS APPLY STRING_SPLIT(ISNULL(KB.DS_MAICDPHU,''), ';') s
            JOIN   #Ma3 m ON m.Ma3 = LEFT(LTRIM(RTRIM(s.value)), 3)
            WHERE  tn.NGAYTIEPNHAN >= @Tu AND tn.NGAYTIEPNHAN < DATEADD(DAY,1,@Den)
              AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
            UNION
            SELECT 'NGT', KB.KHAMBENH_ID
            FROM   TT_TIEPNHAN          tn
            JOIN   TT_NGOAITRU_KHAMBENH KB ON KB.TIEPNHAN_ID = tn.TIEPNHAN_ID
            WHERE  KB.NGAYKHAM >= @Tu AND KB.NGAYKHAM < DATEADD(DAY,1,@Den)
              AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
              AND  KB.CHANDOANICD_ID IN (SELECT ICD_ID FROM #Icd)
            UNION
            SELECT 'NGT', KB.KHAMBENH_ID
            FROM   TT_TIEPNHAN          tn
            JOIN   TT_NGOAITRU_KHAMBENH KB ON KB.TIEPNHAN_ID = tn.TIEPNHAN_ID
            CROSS APPLY STRING_SPLIT(ISNULL(KB.DS_MAICDPHU,''), ';') s
            JOIN   #Ma3 m ON m.Ma3 = LEFT(LTRIM(RTRIM(s.value)), 3)
            WHERE  KB.NGAYKHAM >= @Tu AND KB.NGAYKHAM < DATEADD(DAY,1,@Den)
              AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
        ) z;
        CREATE CLUSTERED INDEX IX_KbHH ON #KbHH(Loai, KHAMBENH_ID);

        /* ── 5) Gom tiêu hao: toàn viện và phần hô hấp ──────────────────── */
        IF OBJECT_ID('tempdb..#KQ') IS NOT NULL DROP TABLE #KQ;
        SELECT
            t.Thang                                AS Period,
            RIGHT('0' + CAST(MONTH(t.Thang) AS varchar(2)), 2)
                + '/' + CAST(YEAR(t.Thang) AS varchar(4)) AS [month],
            mt.SupplyCode                          AS supply_code,
            MAX(mt.SupplyName)                     AS supply_name,
            MAX(mt.SupplyUnit)                     AS supply_unit,
            MAX(CAST(mt.IsVtyt AS TINYINT))        AS is_vtyt,
            CAST(SUM(t.SoLuong) AS decimal(18,3))                                 AS so_luong_toan_vien,
            CAST(SUM(CASE WHEN t.LaHH = 1 THEN t.SoLuong ELSE 0 END) AS decimal(18,3)) AS so_luong_hohap,
            COUNT(*)                               AS so_dong_toa,
            COUNT(DISTINCT t.TIEPNHAN_ID)          AS so_luot
        INTO #KQ
        FROM (
            SELECT tt.DUOC_ID, k.Thang, k.TIEPNHAN_ID,
                   CAST(ISNULL(tt.SOLUONGTHUCLINH, tt.SOLUONG) AS FLOAT) AS SoLuong,
                   CASE WHEN h.KHAMBENH_ID IS NULL THEN 0 ELSE 1 END      AS LaHH
            FROM      TT_NOITRU_TOATHUOC tt
            JOIN      #KbAll k ON k.Loai = 'NT' AND k.KHAMBENH_ID = tt.KHAMBENH_ID
            LEFT JOIN #KbHH  h ON h.Loai = 'NT' AND h.KHAMBENH_ID = tt.KHAMBENH_ID
            WHERE  ISNULL(CAST(tt.HUYTOATHUOC AS NVARCHAR(10)), '0') <> '1'
              AND  ISNULL(tt.SOLUONGTHUCLINH, tt.SOLUONG) > 0
            UNION ALL
            SELECT tt.DUOC_ID, k.Thang, k.TIEPNHAN_ID,
                   CAST(ISNULL(tt.SOLUONG, 0) AS FLOAT),
                   CASE WHEN h.KHAMBENH_ID IS NULL THEN 0 ELSE 1 END
            FROM      TT_NGOAITRU_TOATHUOC tt
            JOIN      #KbAll k ON k.Loai = 'NGT' AND k.KHAMBENH_ID = tt.KHAMBENH_ID
            LEFT JOIN #KbHH  h ON h.Loai = 'NGT' AND h.KHAMBENH_ID = tt.KHAMBENH_ID
            WHERE  ISNULL(CAST(tt.HUYTOATHUOC AS NVARCHAR(10)), '0') <> '1'
              AND  ISNULL(tt.SOLUONG, 0) > 0
        ) t
        JOIN #Meta mt ON mt.DUOC_ID = t.DUOC_ID
        GROUP BY t.Thang, mt.SupplyCode
        HAVING SUM(t.SoLuong) >= 0.001;

        SELECT @nDong = COUNT(*), @nMa = COUNT(DISTINCT supply_code) FROM #KQ;
        SELECT @TyTrongChung = CAST(100.0 * SUM(so_luong_hohap)
                                    / NULLIF(SUM(so_luong_toan_vien),0) AS decimal(6,2))
        FROM   #KQ;

        PRINT CONCAT(N'Dòng = ', @nDong, N', mã = ', @nMa, N', lượt khám = ', @nLuot,
                     N', tỷ trọng hô hấp chung = ', @TyTrongChung, N'%');

        /* BẤT BIẾN: phần hô hấp không bao giờ được vượt tổng. Vượt nghĩa là
           JOIN sang #KbHH đã nhân bản dòng toa.                              */
        IF EXISTS (SELECT 1 FROM #KQ WHERE so_luong_hohap > so_luong_toan_vien + 0.001)
            THROW 50021, N'Có dòng mà lượng hô hấp lớn hơn lượng toàn viện — JOIN đang nhân bản. Không đẩy.', 1;

        /* Đối chiếu với Đ10: tỷ trọng chung đo được là 7,80% trên 12 tháng.
           Lệch nhiều so với con số đó thì có gì đó đã đổi — dừng lại xem. */
        IF @TyTrongChung IS NULL OR @TyTrongChung <= 0 OR @TyTrongChung > 40
            PRINT CONCAT(N'CẢNH BÁO: tỷ trọng hô hấp chung = ', @TyTrongChung,
                         N'% — lệch xa mức 7,80% đo ở Đ10. Kiểm tra bộ lọc ICD trước khi tin kết quả.');

        /* ── 6) Đẩy xuống STA hoặc chỉ xem ──────────────────────────────── */
        IF @ChiXem = 1
        BEGIN
            PRINT N'CHẾ ĐỘ CHỈ XEM — không đẩy.';

            SELECT TOP 50 supply_code, supply_name, supply_unit,
                   SUM(so_luong_toan_vien)                                   AS TongToanVien,
                   SUM(so_luong_hohap)                                       AS TongHoHap,
                   CAST(100.0*SUM(so_luong_hohap)/NULLIF(SUM(so_luong_toan_vien),0)
                        AS decimal(6,2))                                     AS TyTrong,
                   CAST(SUM(so_luong_toan_vien)/NULLIF(COUNT(*),0) AS decimal(18,1)) AS TB_Thang
            FROM   #KQ GROUP BY supply_code, supply_name, supply_unit
            ORDER BY SUM(so_luong_toan_vien) DESC;

            SELECT CASE WHEN TyTrong >= 75 THEN N'1 · ≥75%'
                        WHEN TyTrong >= 50 THEN N'2 · 50-75%'
                        WHEN TyTrong >= 25 THEN N'3 · 25-50%'
                        WHEN TyTrong >= 10 THEN N'4 · 10-25%'
                        ELSE                    N'5 · <10%' END AS NhomTyTrong,
                   COUNT(*) AS SoMa
            FROM ( SELECT supply_code,
                          100.0*SUM(so_luong_hohap)/NULLIF(SUM(so_luong_toan_vien),0) AS TyTrong
                   FROM #KQ GROUP BY supply_code ) z
            GROUP BY CASE WHEN TyTrong >= 75 THEN N'1 · ≥75%'
                          WHEN TyTrong >= 50 THEN N'2 · 50-75%'
                          WHEN TyTrong >= 25 THEN N'3 · 25-50%'
                          WHEN TyTrong >= 10 THEN N'4 · 10-25%'
                          ELSE                    N'5 · <10%' END
            ORDER BY NhomTyTrong;
            RETURN;
        END

        IF @nDong = 0
            THROW 50022, N'Không gom được dòng nào — DỪNG, không đụng vào STA.', 1;

        DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TieuHao_Tong]
        WHERE  Period >= @Tu;

        /* d_baseline_thang và ty_trong_hohap là cột TÍNH SẴN bên STA —
           không liệt kê trong INSERT.                                         */
        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TieuHao_Tong]
              (Period, [month], supply_code, supply_name, supply_unit, is_vtyt,
               so_luong_toan_vien, so_luong_hohap, so_dong_toa, so_luot, NgayCapNhat)
        SELECT Period, [month], supply_code, supply_name, supply_unit, is_vtyt,
               so_luong_toan_vien, so_luong_hohap, so_dong_toa, so_luot, SYSDATETIME()
        FROM   #KQ;

        DECLARE @nSau INT = (
            SELECT COUNT(*) FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TieuHao_Tong]
            WHERE Period >= @Tu);
        IF @nSau <> @nDong
            THROW 50023, N'Số dòng bên STA không khớp số dòng đã gom.', 1;

        UPDATE [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_Watermark]
        SET    MocDaDay = (SELECT MAX(Period) FROM #KQ), LanChayCuoi = SYSDATETIME()
        WHERE  TenLuong = 'TieuHaoTong';

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
              (BatDau, KetThuc, TuNgay, SoDongCaBenh, TrangThai, ThongDiep)
        VALUES (@BatDau, SYSDATETIME(), @Tu, @nDong, 'ok',
                CONCAT(N'TieuHaoToanVien: ', @nDong, N' dòng, ', @nMa, N' mã, ',
                       @nLuot, N' lượt khám, tỷ trọng hô hấp chung ',
                       @TyTrongChung, N'%; VTYT=', @GomVTYT));

        PRINT CONCAT(N'Xong. Đã đẩy ', @nDong, N' dòng cho ', @nMa, N' mã.');
    END TRY
    BEGIN CATCH
        BEGIN TRY
            INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
                  (BatDau, KetThuc, TuNgay, TrangThai, ThongDiep)
            VALUES (@BatDau, SYSDATETIME(), @Tu, 'failed',
                    CONCAT(N'TieuHaoToanVien — lỗi ', ERROR_NUMBER(), N' dòng ',
                           ERROR_LINE(), N': ', ERROR_MESSAGE()));
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

   BƯỚC A · Xem trước, chưa đẩy. Đối chiếu với Đ10 đã chạy.
       EXEC dbo.usp_MedForecast_DayTieuHaoToanVien @SoThang = 12, @ChiXem = 1;
   Bảng thứ hai (phân bố tỷ trọng) phải ra gần giống Đ10-B:
       ≥75%: ~110 mã · 50-75%: ~179 · 25-50%: ~258 · 10-25%: ~211 · <10%: ~1.143
   Lệch nhiều thì DỪNG — bộ lọc ICD hoặc cửa sổ thời gian đang khác.

   BƯỚC B · Nạp thật.
       EXEC dbo.usp_MedForecast_DayTieuHaoToanVien;

   BƯỚC C · Lịch chạy — MỖI TUẦN, không cần hằng ngày:
       EXEC dbo.usp_MedForecast_DayTieuHaoToanVien @SoThang = 24;

   Nếu chạy quá lâu: hạ @SoThang xuống 12 rồi 6. Nhu cầu nền tính trên 12 tháng
   đã đủ ổn định; 24 tháng chỉ để đẹp chuỗi.
============================================================================= */


/* =============================================================================
   Đ9-F — XUẤT CHU KỲ NHẬP THEO TỪNG MÃ  (chạy riêng, chỉ đọc, một lần)
   -----------------------------------------------------------------------------
   VÌ SAO CẦN THÊM PHÉP ĐO NÀY

   Đ9-D cho thấy chu kỳ nhập chênh nhau 7,5 lần giữa các nhóm luân chuyển:

       rất đều (≥24 lần)   14,0 ngày
       đều    (12-23 lần)  21,4 ngày
       vừa    (6-11 lần)   30,1 ngày
       thưa   (3-5 lần)    50,1 ngày
       rất thưa (1-2 lần) 104,5 ngày

   Ngưỡng phẳng 18 ngày vì vậy BÁO MUỘN cho nhóm "vừa" trở đi: một mã có chu kỳ
   nhập 30 ngày mà chỉ báo đỏ khi còn 18 ngày hàng thì đã quá trễ để kịp đợt
   nhập kế tiếp. Trong bệnh viện, báo muộn nguy hiểm hơn báo thừa.

   Cách sửa rẻ nhất: ngưỡng đỏ theo TỪNG MÃ = chu kỳ nhập của chính mã đó,
   lùi về 18 ngày khi không đo được. Bảng dưới xuất đúng dữ liệu đó.

   Đây vẫn là ĐO MỘT LẦN — xuất CSV, nạp vào supply_attributes ở G4, không dựng
   bảng đồng bộ và không theo dõi nhà cung cấp.
   -----------------------------------------------------------------------------
   ► ĐỌC THẾ NÀO: xuất toàn bộ ra CSV. Cột ChuKyTrungVi là ngưỡng đỏ riêng của
     mã đó; SoLanNhap < 6 thì độ tin cậy thấp, G4 sẽ dùng 18 thay thế.
============================================================================= */
/*
DECLARE @SoThangD9 INT = 24;

IF OBJECT_ID('tempdb..#N')  IS NOT NULL DROP TABLE #N;
IF OBJECT_ID('tempdb..#K')  IS NOT NULL DROP TABLE #K;

SELECT DISTINCT ln.DUOC_ID, CAST(ln.NGAYNHAP AS DATE) AS Ngay
INTO   #N
FROM   TT_DUOC_CHUNGTU_SOLONHAP ln
WHERE  ln.NGAYNHAP IS NOT NULL
  AND  CAST(ln.NGAYNHAP AS DATE) >= DATEADD(MONTH, -@SoThangD9, CAST(GETDATE() AS DATE))
  AND  ISNULL(CAST(ln.HUY AS NVARCHAR(10)), '0') <> '1';

SELECT DUOC_ID, Ngay,
       DATEDIFF(DAY, LAG(Ngay) OVER (PARTITION BY DUOC_ID ORDER BY Ngay), Ngay) AS Khoang
INTO   #K
FROM   #N;

SELECT DISTINCT
       d.MADUOC                                                          AS MaVatTu,
       d.TENDUOCDAYDU                                                    AS TenVatTu,
       COUNT(*)      OVER (PARTITION BY k.DUOC_ID)                       AS SoLanNhap,
       CAST(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY k.Khoang)
            OVER (PARTITION BY k.DUOC_ID) AS INT)                        AS ChuKyTrungVi,
       CAST(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY k.Khoang)
            OVER (PARTITION BY k.DUOC_ID) AS INT)                        AS ChuKyP90
FROM   #K k
JOIN   TM_DUOC d ON d.DUOC_ID = k.DUOC_ID
WHERE  k.Khoang IS NOT NULL AND k.Khoang > 0
ORDER BY MaVatTu;

DROP TABLE #N;
DROP TABLE #K;
*/
