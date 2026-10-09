/* his_nguon/01_linked_server.sql
   Chạy trên: máy chủ CSDL HIS, cần sysadmin hoặc ALTER ANY LINKED SERVER.
   Mục đích: tạo linked server MEDFORECAST_DW_LINK trỏ tới MEDFORECAST_DW (chiều từ CSDL HIS sang CSDL trung gian).
   Điều kiện: đã chạy medforecast_dw/01..04 và tạo login medforecast_push (medforecast_dw/01 mục 9). */

/* Tham số cần chỉnh; các script his_nguon/ sau dùng lại đúng @LinkedName */
DECLARE @LinkedName sysname       = N'MEDFORECAST_DW_LINK';
DECLARE @DwHost    nvarchar(200) = N'<<may-chu-dw>>';
DECLARE @PushUser   sysname       = N'medforecast_push';
DECLARE @PushPass   nvarchar(200) = N'<<mat-khau>>';

/* 1. Tạo linked server */
IF EXISTS (SELECT 1 FROM sys.servers WHERE name = @LinkedName)
    EXEC sp_dropserver @server = @LinkedName, @droplogins = 'droplogins';

EXEC sp_addlinkedserver
     @server     = @LinkedName,
     @srvproduct = N'',
     @provider   = N'MSOLEDBSQL',        -- SQLNCLI11 đã ngừng hỗ trợ
     @datasrc    = @DwHost,
     @catalog    = N'MEDFORECAST_DW';

EXEC sp_addlinkedsrvlogin
     @rmtsrvname  = @LinkedName,
     @useself     = N'False',
     @rmtuser     = @PushUser,
     @rmtpassword = @PushPass;

/* 2. Tuỳ chọn; rpc out bắt buộc cho EXEC (...) AT */
EXEC sp_serveroption @LinkedName, 'rpc',                    'true';
EXEC sp_serveroption @LinkedName, 'rpc out',                'true';
EXEC sp_serveroption @LinkedName, 'collation compatible',   'true';
EXEC sp_serveroption @LinkedName, 'use remote collation',   'true';
EXEC sp_serveroption @LinkedName, 'lazy schema validation', 'true';
EXEC sp_serveroption @LinkedName, 'query timeout',          '900';

/* 3. Kiểm tra kết nối */
EXEC sp_testlinkedserver @LinkedName;
GO

/* 4. Thử đọc và ghi một dòng */
SELECT TOP 5 * FROM [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_Watermark];

INSERT INTO [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
       (BatDau, KetThuc, TrangThai, ThongDiep)
VALUES (SYSDATETIME(), SYSDATETIME(), 'ok', N'Kiểm tra linked server từ CSDL HIS');

SELECT TOP 3 * FROM [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
ORDER BY Id DESC;
GO

/* 5. Collation hai máy khác nhau: EXEC sp_serveroption 'MEDFORECAST_DW_LINK', 'collation compatible', 'false'; */
