USE GIAAN115_HIS
GO

/* ═════════════════════════════════════════════════════════════════════════
   usp_MedForecast_DayKhoCungUng — bản 2 (13/09/2026)

   Việc duy nhất còn lại: chụp TỒN KHO THEO LÔ (kèm hạn dùng) và đẩy xuống
   STA MF_TonKho_Lo cho Tầng 3 (FEFO + DOI).

   Đã cắt so với bản 1 (Phase0_03): #Nhap (lịch sử nhập), #LeadTS/#Pct/#ChuKy
   (trung vị, p90 lead time, chu kỳ nhập), #ThuocTinh (MOQ, tỷ lệ giao đủ,
   nguồn lead time) và hai bảng đích MF_LichSuNhap, MF_VatTu_ThuocTinh. Tất
   cả thuộc bài toán mua sắm (R,S)/ROP/safety stock — ngoài phạm vi DSS
   3 tầng. Dọn bảng bên STA bằng G2_02_STA_don_tan_du_mua_sam.sql.

   Cách chạy:
     EXEC dbo.usp_MedForecast_DayKhoCungUng @ChiXem = 1;   -- xem, không đẩy
     EXEC dbo.usp_MedForecast_DayKhoCungUng;               -- đẩy ảnh chụp hôm nay
   ═════════════════════════════════════════════════════════════════════════ */
CREATE OR ALTER PROCEDURE dbo.usp_MedForecast_DayKhoCungUng
    @BENHVIEN_ID  VARCHAR(8) = NULL,   -- điền khi DB chứa nhiều bệnh viện
    @GomVTYT      BIT        = 0,      -- 0 = chỉ thuốc (khớp DayDuLieu và 3 view local)
    @ChiXem       BIT        = 0
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @BatDau DATETIME2(0) = SYSDATETIME();
    DECLARE @Hom    DATE = CAST(GETDATE() AS DATE);
    DECLARE @nLo INT = 0, @nLoKhongHan INT = 0, @nHetHan INT = 0;

    BEGIN TRY
        /* 1) Danh mục vật tư — cùng bộ lọc với usp_MedForecast_DayDuLieu */
        IF OBJECT_ID('tempdb..#Meta') IS NOT NULL DROP TABLE #Meta;
        SELECT  D.DUOC_ID,
                D.MADUOC AS SupplyCode
        INTO    #Meta
        FROM    TM_DUOC     D
        JOIN    TM_LOAIDUOC ld ON ld.LOAIDUOC_ID = D.LOAIDUOC_ID
        WHERE  (@GomVTYT = 1 OR ld.LOAIVATTU_ID = 'T')
          AND   D.MADUOC IS NOT NULL AND LTRIM(RTRIM(D.MADUOC)) <> ''
          AND  (@BENHVIEN_ID IS NULL OR D.BENHVIEN_ID = @BENHVIEN_ID);
        CREATE UNIQUE CLUSTERED INDEX IX_Meta ON #Meta(DUOC_ID);

        /* 2) Tồn theo lô.
           LEFT JOIN sang bảng lô: dòng tồn không tra được lô vẫn phải xuống
           STA với lot_id = 0 / expiry NULL, nếu không tổng tồn theo lô nhỏ hơn
           tổng tồn thật và Tầng 3 báo "hụt hàng" giả. Lô đã huỷ (HUY = '1')
           bị loại. */
        IF OBJECT_ID('tempdb..#Lo') IS NOT NULL DROP TABLE #Lo;
        SELECT
            @Hom                                                    AS NgaySnapshot,
            m.SupplyCode                                            AS supply_code,
            ISNULL(tk.SOLONHAP_ID, 0)                               AS lot_id,
            MAX(CAST(COALESCE(ln.SOLONHAP, ln.SOLOSANPHAM) AS NVARCHAR(100))) AS lot_code,
            MAX(CAST(ln.HANDUNG AS DATE))                           AS expiry_date,
            CAST(CASE WHEN MAX(CAST(ln.HANDUNG AS DATE)) IS NULL THEN 0 ELSE 1 END AS BIT) AS co_han_dung,
            CAST(SUM(CAST(tk.SOLUONG AS FLOAT)) AS DECIMAL(18,3))   AS quantity,
            COUNT(DISTINCT tk.KHODUOC_ID)                           AS so_kho,
            CAST(MAX(COALESCE(ln.DONGIAMUA, tk.DONGIAMUA)) AS DECIMAL(18,4)) AS don_gia_mua,
            CAST(MAX(ln.DONGIATHAU) AS DECIMAL(18,4))               AS don_gia_thau,
            CAST(MAX(ln.DONGIAVON)  AS DECIMAL(18,4))               AS don_gia_von
        INTO   #Lo
        FROM        TT_DUOC_TONKHO            tk
        JOIN        #Meta                     m  ON m.DUOC_ID = tk.DUOC_ID
        LEFT JOIN   TT_DUOC_CHUNGTU_SOLONHAP  ln ON ln.SOLONHAP_ID = tk.SOLONHAP_ID
                                                AND ISNULL(ln.HUY, '0') <> '1'
        WHERE  (@BENHVIEN_ID IS NULL OR tk.BENHVIEN_ID = @BENHVIEN_ID)
        GROUP BY m.SupplyCode, ISNULL(tk.SOLONHAP_ID, 0)
        HAVING SUM(CAST(tk.SOLUONG AS FLOAT)) > 0;

        SELECT @nLo         = COUNT(*),
               @nLoKhongHan = SUM(CASE WHEN expiry_date IS NULL THEN 1 ELSE 0 END),
               @nHetHan     = SUM(CASE WHEN expiry_date < @Hom THEN 1 ELSE 0 END)
        FROM   #Lo;

        PRINT CONCAT(N'Tồn theo lô: ', @nLo, N' dòng; ', @nLoKhongHan,
                     N' không có hạn dùng; ', @nHetHan, N' đã quá hạn còn trong kho.');

        /* Bất biến: tổng tồn theo lô = tổng tồn thô (>0). Lệch là JOIN nhân bản
           hoặc rơi dòng — dừng, không đẩy số sai xuống STA. */
        DECLARE @TongLo FLOAT = (SELECT ISNULL(SUM(quantity), 0) FROM #Lo);
        DECLARE @TongTK FLOAT = (
            SELECT ISNULL(SUM(CAST(tk.SOLUONG AS FLOAT)), 0)
            FROM   TT_DUOC_TONKHO tk
            JOIN   #Meta m ON m.DUOC_ID = tk.DUOC_ID
            WHERE (@BENHVIEN_ID IS NULL OR tk.BENHVIEN_ID = @BENHVIEN_ID)
              AND  CAST(tk.SOLUONG AS FLOAT) > 0);
        IF ABS(@TongLo - @TongTK) > 0.5
            THROW 50012, N'Tổng tồn theo lô khác tổng tồn thô — JOIN sang TT_DUOC_CHUNGTU_SOLONHAP nhân bản/rơi dòng. Không đẩy.', 1;

        /* 3) Chỉ xem */
        IF @ChiXem = 1
        BEGIN
            PRINT N'CHẾ ĐỘ CHỈ XEM — không đẩy.';
            SELECT TOP 200 * FROM #Lo ORDER BY expiry_date, supply_code;

            SELECT CASE WHEN expiry_date IS NULL                     THEN N'0 · không có hạn dùng'
                        WHEN expiry_date <  @Hom                     THEN N'1 · đã quá hạn'
                        WHEN expiry_date <  DATEADD(DAY, 30, @Hom)   THEN N'2 · dưới 30 ngày (cửa sổ FEFO)'
                        WHEN expiry_date <  DATEADD(MONTH, 6, @Hom)  THEN N'3 · 1-6 tháng'
                        WHEN expiry_date <  DATEADD(MONTH, 12, @Hom) THEN N'4 · 6-12 tháng'
                        ELSE                                              N'5 · trên 12 tháng' END AS Khoang,
                   COUNT(*)                                     AS SoLo,
                   COUNT(DISTINCT supply_code)                  AS SoVatTu,
                   CAST(SUM(quantity) AS DECIMAL(18,1))         AS TongSoLuong
            FROM   #Lo
            GROUP BY CASE WHEN expiry_date IS NULL                     THEN N'0 · không có hạn dùng'
                          WHEN expiry_date <  @Hom                     THEN N'1 · đã quá hạn'
                          WHEN expiry_date <  DATEADD(DAY, 30, @Hom)   THEN N'2 · dưới 30 ngày (cửa sổ FEFO)'
                          WHEN expiry_date <  DATEADD(MONTH, 6, @Hom)  THEN N'3 · 1-6 tháng'
                          WHEN expiry_date <  DATEADD(MONTH, 12, @Hom) THEN N'4 · 6-12 tháng'
                          ELSE                                              N'5 · trên 12 tháng' END
            ORDER BY Khoang;
            RETURN;
        END

        IF @nLo = 0
            THROW 50011, N'Không lấy được dòng tồn kho theo lô nào — DỪNG, không đụng vào STA.', 1;

        /* 4) Đẩy: xoá đúng ảnh chụp HÔM NAY rồi chèn (chạy lại trong ngày không
           trùng), giữ nguyên ảnh chụp các ngày trước. */
        DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TonKho_Lo]
        WHERE  NgaySnapshot = @Hom;

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TonKho_Lo]
              (NgaySnapshot, supply_code, lot_id, lot_code, expiry_date, co_han_dung,
               quantity, so_kho, don_gia_mua, don_gia_thau, don_gia_von, NgayCapNhat)
        SELECT NgaySnapshot, supply_code, lot_id, lot_code, expiry_date, co_han_dung,
               quantity, so_kho, don_gia_mua, don_gia_thau, don_gia_von, SYSDATETIME()
        FROM   #Lo;

        DECLARE @nSau INT = (
            SELECT COUNT(*) FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TonKho_Lo]
            WHERE NgaySnapshot = @Hom);
        IF @nSau <> @nLo
            THROW 50013, N'Số dòng bên STA không khớp số dòng đã gom.', 1;

        UPDATE [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_Watermark]
        SET    MocDaDay = @Hom, LanChayCuoi = SYSDATETIME()
        WHERE  TenLuong = 'KhoCungUng';

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
              (BatDau, KetThuc, TuNgay, SoDongTonKho, TrangThai, ThongDiep)
        VALUES (@BatDau, SYSDATETIME(), @Hom, @nLo, 'ok',
                CONCAT(N'KhoCungUng: ', @nLo, N' dòng tồn theo lô (', @nLoKhongHan,
                       N' không có hạn dùng, ', @nHetHan, N' quá hạn); VTYT=', @GomVTYT));

        PRINT CONCAT(N'Xong. Lô = ', @nLo);
    END TRY
    BEGIN CATCH
        BEGIN TRY
            INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
                  (BatDau, KetThuc, TuNgay, TrangThai, ThongDiep)
            VALUES (@BatDau, SYSDATETIME(), @Hom, 'failed',
                    CONCAT(N'KhoCungUng — lỗi ', ERROR_NUMBER(), N' dòng ', ERROR_LINE(),
                           N': ', ERROR_MESSAGE()));
        END TRY
        BEGIN CATCH
            PRINT N'Không ghi được nhật ký xuống STA — kiểm tra linked server.';
        END CATCH;
        THROW;
    END CATCH
END
GO
