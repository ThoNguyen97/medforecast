/* =============================================================================
   prod/01_linked_server.sql
   Chạy trên: HIS PROD. Cần quyền sysadmin hoặc ALTER ANY LINKED SERVER.
   Mục đích: tạo linked server MEDFORECAST_STA trỏ tới CSDL MEDFORECAST_DW trên
   STA. Chiều dữ liệu PROD → STA: thủ tục tổng hợp chạy trên PROD và ghi xuống
   STA, nên không cần mở kết nối từ STA vào PROD.
   Điều kiện: đã chạy sta/01..04 và tạo login medforecast_push
   (sta/01_tao_database_va_bang.sql, mục 9).
============================================================================= */

/* Tham số cần chỉnh:
   @LinkedName : tên linked server, các script prod/ sau dùng lại đúng tên này
   @StaHost    : tên máy hoặc IP\Instance của máy chủ STA
   @PushUser   : tài khoản có quyền ghi trên MEDFORECAST_DW
   @PushPass   : mật khẩu tài khoản đó                                       */
DECLARE @LinkedName sysname       = N'MEDFORECAST_STA';
DECLARE @StaHost    nvarchar(200) = N'10.0.0.20\STA';
DECLARE @PushUser   sysname       = N'medforecast_push';
DECLARE @PushPass   nvarchar(200) = N'<<mat-khau>>';

/* ── 1. Tạo linked server ── */
IF EXISTS (SELECT 1 FROM sys.servers WHERE name = @LinkedName)
    EXEC sp_dropserver @server = @LinkedName, @droplogins = 'droplogins';

EXEC sp_addlinkedserver
     @server     = @LinkedName,
     @srvproduct = N'',
     @provider   = N'MSOLEDBSQL',        -- SQLNCLI11 đã ngừng hỗ trợ
     @datasrc    = @StaHost,
     @catalog    = N'MEDFORECAST_DW';

EXEC sp_addlinkedsrvlogin
     @rmtsrvname  = @LinkedName,
     @useself     = N'False',            -- không mượn danh tính người gọi
     @rmtuser     = @PushUser,
     @rmtpassword = @PushPass;

/* ── 2. Tuỳ chọn ──
   rpc out = true là bắt buộc: thủ tục chạy lệnh ở đầu xa qua
   EXEC (...) AT [linked server].                                            */
EXEC sp_serveroption @LinkedName, 'rpc',                    'true';
EXEC sp_serveroption @LinkedName, 'rpc out',                'true';
EXEC sp_serveroption @LinkedName, 'collation compatible',   'true';
EXEC sp_serveroption @LinkedName, 'use remote collation',   'true';
EXEC sp_serveroption @LinkedName, 'lazy schema validation', 'true';
EXEC sp_serveroption @LinkedName, 'query timeout',          '900';

/* ── 3. Kiểm tra kết nối ── */
EXEC sp_testlinkedserver @LinkedName;
GO

/* ── 4. Thử đọc và ghi một dòng ── */
SELECT TOP 5 * FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_Watermark];

INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
       (BatDau, KetThuc, TrangThai, ThongDiep)
VALUES (SYSDATETIME(), SYSDATETIME(), 'ok', N'Kiểm tra linked server từ PROD');

SELECT TOP 3 * FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
ORDER BY Id DESC;
GO

/* ── 5. Khi collation hai máy khác nhau ──
   So SERVERPROPERTY('Collation') trên cả hai máy. Nếu khác, tắt tuỳ chọn
   dưới đây để tránh lỗi "cannot resolve the collation conflict":
       EXEC sp_serveroption 'MEDFORECAST_STA', 'collation compatible', 'false';
============================================================================= */
