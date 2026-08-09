/* =============================================================================
   03 — THỦ TỤC ĐỒNG BỘ PROD → STA  +  SQL AGENT JOB
   =============================================================================
   Chạy trên: STA. Cần chạy 01 và 02 trước.

   CÁCH LÀM
   • Tăng dần theo mốc thời gian, nhưng LÙI LẠI @SoNgayLuiLai ngày (mặc định 90).
     Lý do: hồ sơ bệnh án thường được chốt mã ICD trễ vài tuần. Nếu chỉ lấy phần
     mới hơn mốc cũ, phần bổ sung cho tháng trước sẽ mất vĩnh viễn.
   • Idempotent: trong cửa sổ đó thì XOÁ RỒI CHÈN LẠI. Chạy mấy lần cũng ra một
     kết quả, và bản ghi bị huỷ bên PROD cũng biến mất theo bên STA.
   • Mỗi lần chạy ghi một dòng vào stg.SyncLog. Lỗi thì rollback rồi ghi 'failed'.
   • Con số @SoNgayLuiLai = 90 khớp với PIPELINE_LOOKBACK_MONTHS = 3 bên
     MedForecast, để hai tầng nạp lại cùng một cửa sổ.

   HIỆU NĂNG
   Thủ tục dùng tên 4 phần qua synonym `src.*` (dễ đọc, tên bảng thật chỉ nằm ở
   file 01). Với cửa sổ 90 ngày thì cách này đủ nhanh. Nếu HIS rất lớn và job
   chậm, xem mục "Khi nào cần OPENQUERY" ở cuối file.
============================================================================= */

CREATE OR ALTER PROCEDURE stg.usp_DongBo_PROD_sang_STA
    @SoNgayLuiLai int = 90,
    @NapLaiToanBo bit = 0      -- 1 = bỏ qua mốc, nạp lại từ đầu
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @BatDau    datetime2(0) = SYSDATETIME();
    DECLARE @Moc       datetime2(0);
    DECLARE @TuNgay    date;
    DECLARE @nKB bigint = 0, @nCD bigint = 0, @nSD bigint = 0,
            @nVT bigint = 0, @nTK bigint = 0;

    BEGIN TRY
        /* --- 1. Xác định cửa sổ cần nạp lại ------------------------------- */
        SELECT @Moc = MocDaDongBo FROM stg.SyncWatermark WHERE TenBang = N'KhamBenh';

        SET @TuNgay = CASE
                        WHEN @NapLaiToanBo = 1 OR @Moc IS NULL THEN CAST('1900-01-01' AS date)
                        ELSE CAST(DATEADD(DAY, -@SoNgayLuiLai, @Moc) AS date)
                      END;

        PRINT CONCAT(N'Nạp lại từ ngày: ', CONVERT(varchar(10), @TuNgay, 120));

        BEGIN TRANSACTION;

        /* --- 2. Lượt khám trong cửa sổ ------------------------------------ */
        /* ⚙ CHỈNH tên cột cho khớp HIS thật (chỉ ở đây và ở mục 3, 4).       */
        SELECT  k.Id           AS KhamBenhId,
                k.BenhNhanId   AS BenhNhanId,
                CAST(k.NgayKham AS date)  AS NgayKham,
                k.TrangThai    AS TrangThai,
                k.NgayCapNhat  AS NgayCapNhat
        INTO    #kb
        FROM    src.KhamBenh k
        WHERE   k.NgayKham >= @TuNgay;      -- lọc trên CỘT NGÀY: dùng được index

        CREATE UNIQUE CLUSTERED INDEX ix_kb ON #kb(KhamBenhId);
        SET @nKB = (SELECT COUNT(*) FROM #kb);

        /* Tập khoá cần dọn = lượt khám cũ trong cửa sổ  +  lượt khám mới lấy về.
           Có phần "cũ" để bản ghi bị huỷ bên PROD cũng bị xoá bên STA.        */
        SELECT KhamBenhId INTO #keys
        FROM  (SELECT KhamBenhId FROM stg.KhamBenh WHERE NgayKham >= @TuNgay
               UNION
               SELECT KhamBenhId FROM #kb) u;
        CREATE UNIQUE CLUSTERED INDEX ix_keys ON #keys(KhamBenhId);

        /* --- 3. Chẩn đoán & vật tư dùng (lọc theo cùng cửa sổ ngày) -------- */
        SELECT  cd.Id         AS ChanDoanId,
                cd.KhamBenhId AS KhamBenhId,
                cd.MaICD      AS MaICD,
                cd.TenICD     AS TenICD,
                CAST(cd.LaChinh AS bit) AS LaChinh
        INTO    #cd
        FROM    src.ChanDoan cd
        JOIN    src.KhamBenh k ON k.Id = cd.KhamBenhId
        WHERE   k.NgayKham >= @TuNgay;
        SET @nCD = (SELECT COUNT(*) FROM #cd);

        SELECT  sd.Id         AS SuDungId,
                sd.KhamBenhId AS KhamBenhId,
                sd.VatTuId    AS VatTuId,
                CAST(sd.SoLuong AS decimal(18,3)) AS SoLuong
        INTO    #sd
        FROM    src.SuDungVatTu sd
        JOIN    src.KhamBenh k ON k.Id = sd.KhamBenhId
        WHERE   k.NgayKham >= @TuNgay;
        SET @nSD = (SELECT COUNT(*) FROM #sd);

        /* --- 4. Thay thế dữ liệu trong cửa sổ ------------------------------ */
        DELETE cd FROM stg.ChanDoan    cd JOIN #keys x ON x.KhamBenhId = cd.KhamBenhId;
        DELETE sd FROM stg.SuDungVatTu sd JOIN #keys x ON x.KhamBenhId = sd.KhamBenhId;
        DELETE kb FROM stg.KhamBenh    kb JOIN #keys x ON x.KhamBenhId = kb.KhamBenhId;

        INSERT stg.KhamBenh (KhamBenhId, BenhNhanId, NgayKham, TrangThai, NgayCapNhat)
        SELECT KhamBenhId, BenhNhanId, NgayKham, TrangThai, NgayCapNhat FROM #kb;

        INSERT stg.ChanDoan (ChanDoanId, KhamBenhId, MaICD, TenICD, LaChinh)
        SELECT ChanDoanId, KhamBenhId, MaICD, TenICD, LaChinh FROM #cd;

        INSERT stg.SuDungVatTu (SuDungId, KhamBenhId, VatTuId, SoLuong)
        SELECT SuDungId, KhamBenhId, VatTuId, SoLuong FROM #sd;

        /* --- 5. Bệnh nhân: CHỈ tỉnh, và chỉ những người có mặt trong dữ liệu */
        /*        KHÔNG chép họ tên / CCCD / địa chỉ / ngày sinh.              */
        MERGE stg.BenhNhan AS t
        USING (
            SELECT DISTINCT bn.Id AS BenhNhanId, bn.Tinh AS Tinh
            FROM   src.BenhNhan bn
            JOIN   #kb k ON k.BenhNhanId = bn.Id
        ) AS s ON s.BenhNhanId = t.BenhNhanId
        WHEN MATCHED AND ISNULL(t.Tinh, N'') <> ISNULL(s.Tinh, N'')
             THEN UPDATE SET t.Tinh = s.Tinh
        WHEN NOT MATCHED BY TARGET
             THEN INSERT (BenhNhanId, Tinh) VALUES (s.BenhNhanId, s.Tinh);

        /* --- 6. Danh mục vật tư & tồn kho: bảng nhỏ, làm mới toàn bộ ------- */
        MERGE stg.VatTu AS t
        USING (
            SELECT vt.Id AS VatTuId, vt.MaVatTu, vt.TenVatTu, vt.MaThuoc, vt.HoatChat,
                   vt.DonVi, vt.NhomVatTu, vt.LoaiVatTu, vt.MoTa,
                   CAST(vt.TrangThai AS bit) AS TrangThai
            FROM   src.VatTu vt
        ) AS s ON s.VatTuId = t.VatTuId
        WHEN MATCHED THEN UPDATE SET
             t.MaVatTu = s.MaVatTu, t.TenVatTu = s.TenVatTu, t.MaThuoc = s.MaThuoc,
             t.HoatChat = s.HoatChat, t.DonVi = s.DonVi, t.NhomVatTu = s.NhomVatTu,
             t.LoaiVatTu = s.LoaiVatTu, t.MoTa = s.MoTa, t.TrangThai = s.TrangThai
        WHEN NOT MATCHED BY TARGET THEN INSERT
             (VatTuId, MaVatTu, TenVatTu, MaThuoc, HoatChat, DonVi, NhomVatTu, LoaiVatTu, MoTa, TrangThai)
             VALUES (s.VatTuId, s.MaVatTu, s.TenVatTu, s.MaThuoc, s.HoatChat, s.DonVi,
                     s.NhomVatTu, s.LoaiVatTu, s.MoTa, s.TrangThai)
        WHEN NOT MATCHED BY SOURCE THEN DELETE;
        SET @nVT = (SELECT COUNT(*) FROM stg.VatTu);

        /* Tồn kho là ảnh chụp hiện tại: gộp theo vật tư rồi thay toàn bộ.     */
        TRUNCATE TABLE stg.TonKho;
        INSERT stg.TonKho (VatTuId, SoLuongTon, NgayCapNhat)
        SELECT tk.VatTuId, SUM(CAST(tk.SoLuongTon AS bigint)), MAX(tk.NgayCapNhat)
        FROM   src.TonKho tk
        GROUP BY tk.VatTuId;
        SET @nTK = @@ROWCOUNT;

        /* --- 7. Cập nhật mốc ---------------------------------------------- */
        DECLARE @MocMoi datetime2(0) =
            (SELECT MAX(x) FROM (SELECT MAX(NgayCapNhat) AS x FROM #kb
                                 UNION ALL
                                 SELECT CAST(MAX(NgayKham) AS datetime2(0)) FROM #kb) z);

        MERGE stg.SyncWatermark AS t
        USING (SELECT N'KhamBenh' AS TenBang) AS s ON s.TenBang = t.TenBang
        WHEN MATCHED THEN UPDATE SET
             t.MocDaDongBo = CASE WHEN @MocMoi > ISNULL(t.MocDaDongBo, '19000101')
                                  THEN @MocMoi ELSE t.MocDaDongBo END,
             t.LanChayCuoi = SYSDATETIME()
        WHEN NOT MATCHED THEN INSERT (TenBang, MocDaDongBo, LanChayCuoi)
             VALUES (N'KhamBenh', @MocMoi, SYSDATETIME());

        COMMIT TRANSACTION;

        INSERT stg.SyncLog (BatDau, KetThuc, TuNgay, SoDongKhamBenh, SoDongChanDoan,
                            SoDongSuDungVatTu, SoDongVatTu, SoDongTonKho, TrangThai, ThongDiep)
        VALUES (@BatDau, SYSDATETIME(), @TuNgay, @nKB, @nCD, @nSD, @nVT, @nTK, 'ok',
                CONCAT(N'Nạp lại từ ', CONVERT(varchar(10), @TuNgay, 120),
                       N'; mốc mới = ', CONVERT(varchar(19), @MocMoi, 120)));

        PRINT CONCAT(N'Xong. KhamBenh=', @nKB, N' ChanDoan=', @nCD,
                     N' SuDungVatTu=', @nSD, N' VatTu=', @nVT, N' TonKho=', @nTK);
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
        INSERT stg.SyncLog (BatDau, KetThuc, TuNgay, TrangThai, ThongDiep)
        VALUES (@BatDau, SYSDATETIME(), @TuNgay, 'failed',
                CONCAT(N'Lỗi ', ERROR_NUMBER(), N' dòng ', ERROR_LINE(), N': ', ERROR_MESSAGE()));
        THROW;
    END CATCH
END
GO

/* =============================================================================
   SQL AGENT JOB — chạy 01:00 hằng ngày
   MedForecast đặt PIPELINE_CRON = 0 2 * * * (02:00), tức chạy SAU job này 1 giờ.
   Giữ khoảng cách đó, nếu không MedForecast sẽ đọc dữ liệu cũ một ngày.
============================================================================= */
USE msdb;
GO
IF EXISTS (SELECT 1 FROM msdb.dbo.sysjobs WHERE name = N'MedForecast - Dong bo HIS PROD sang STA')
    EXEC sp_delete_job @job_name = N'MedForecast - Dong bo HIS PROD sang STA';
GO

DECLARE @StaDb sysname = N'STA';   -- ⚙ tên database STA

EXEC sp_add_job
     @job_name = N'MedForecast - Dong bo HIS PROD sang STA',
     @description = N'Nap tang dan du lieu kham benh, chan doan, vat tu, ton kho tu HIS PROD sang STA. Cua so nap lai 90 ngay.',
     @enabled = 1;

EXEC sp_add_jobstep
     @job_name   = N'MedForecast - Dong bo HIS PROD sang STA',
     @step_name  = N'Chay thu tuc dong bo',
     @subsystem  = N'TSQL',
     @database_name = @StaDb,
     @command    = N'EXEC stg.usp_DongBo_PROD_sang_STA @SoNgayLuiLai = 90;',
     @retry_attempts = 2,
     @retry_interval = 10;      -- thử lại sau 10 phút nếu PROD đang bận

EXEC sp_add_jobschedule
     @job_name    = N'MedForecast - Dong bo HIS PROD sang STA',
     @name        = N'Hang ngay 01:00',
     @freq_type   = 4,          -- hằng ngày
     @freq_interval = 1,
     @active_start_time = 010000;

EXEC sp_add_jobserver @job_name = N'MedForecast - Dong bo HIS PROD sang STA';
GO

/* =============================================================================
   KHI NÀO CẦN OPENQUERY
   -----------------------------------------------------------------------------
   Tên 4 phần đôi khi không đẩy được điều kiện lọc sang PROD — SQL Server kéo cả
   bảng về STA rồi mới lọc. Cách kiểm tra: bật "Include Actual Execution Plan",
   chạy mục 2, xem toán tử Remote Query có chứa mệnh đề WHERE hay không.

   Nếu KHÔNG có, đổi mục 2 sang dạng dưới (điều kiện chắc chắn chạy trên PROD):

       DECLARE @sql nvarchar(max) = N'
           SELECT * INTO #kb FROM OPENQUERY([HIS_PROD], ''
               SELECT Id AS KhamBenhId, BenhNhanId,
                      CAST(NgayKham AS date) AS NgayKham,
                      TrangThai, NgayCapNhat
               FROM   HISDB.dbo.KhamBenh
               WHERE  NgayKham >= ''''' + CONVERT(varchar(10), @TuNgay, 120) + N''''' '')';
       EXEC sp_executesql @sql;

   Lưu ý: OPENQUERY không dùng được synonym, nên tên bảng thật sẽ xuất hiện thêm
   một chỗ nữa — nhớ cập nhật cùng lúc với file 01.
============================================================================= */
