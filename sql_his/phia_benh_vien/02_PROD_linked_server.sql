/* =============================================================================
   02 — BƯỚC 2: TẠO LINKED SERVER TRÊN PROD TRỎ XUỐNG STAGING
   =============================================================================
   Chạy trên: HIS PROD. Cần quyền sysadmin hoặc ALTER ANY LINKED SERVER.

   CHIỀU ĐI: PROD  ──đẩy──▶  STA
   Thủ tục tổng hợp chạy trên PROD, ghi kết quả xuống STA. Linked server vì vậy
   nằm ở PROD và trỏ tới máy chủ STA (không phải ngược lại).

   Lưu ý vận hành: cách này dùng CPU và SQL Agent của máy chủ production, nên
   phải đặt lịch ngoài giờ cao điểm. Đổi lại, không cần mở chiều kết nối từ
   STA vào PROD — thường dễ được phòng CNTT chấp thuận hơn.
============================================================================= */

/* ⚙ ─────────────── CHỈNH 4 GIÁ TRỊ NÀY ───────────────
   @LinkedName : tên gợi nhớ, các script sau dùng lại đúng tên này
   @StaHost    : tên máy hoặc IP\Instance của máy chủ STAGING
   @PushUser   : tài khoản GHI ĐƯỢC trên MEDFORECAST_DW (tạo ở script 01)
   @PushPass   : mật khẩu tài khoản đó
   ───────────────────────────────────────────────────── */
DECLARE @LinkedName sysname       = N'MEDFORECAST_STA';
DECLARE @StaHost    nvarchar(200) = N'10.0.0.20\STA';
DECLARE @PushUser   sysname       = N'medforecast_push';
DECLARE @PushPass   nvarchar(200) = N'<<mat-khau>>';

/* --- 1. Tạo linked server ------------------------------------------------- */
IF EXISTS (SELECT 1 FROM sys.servers WHERE name = @LinkedName)
    EXEC sp_dropserver @server = @LinkedName, @droplogins = 'droplogins';

EXEC sp_addlinkedserver
     @server     = @LinkedName,
     @srvproduct = N'',
     @provider   = N'MSOLEDBSQL',        -- driver hiện hành (SQLNCLI11 đã ngừng hỗ trợ)
     @datasrc    = @StaHost,
     @catalog    = N'MEDFORECAST_DW';

EXEC sp_addlinkedsrvlogin
     @rmtsrvname  = @LinkedName,
     @useself     = N'False',            -- không mượn danh tính người gọi
     @rmtuser     = @PushUser,
     @rmtpassword = @PushPass;

/* --- 2. Thiết lập ---------------------------------------------------------
   rpc out = true là BẮT BUỘC: thủ tục cần chạy TRUNCATE TABLE ở đầu xa qua
   EXEC (...) AT [linked server]. Đây là khác biệt so với chiều PROD ← STA.  */
EXEC sp_serveroption @LinkedName, 'rpc',                    'true';
EXEC sp_serveroption @LinkedName, 'rpc out',                'true';
EXEC sp_serveroption @LinkedName, 'collation compatible',   'true';
EXEC sp_serveroption @LinkedName, 'use remote collation',   'true';
EXEC sp_serveroption @LinkedName, 'lazy schema validation', 'true';
EXEC sp_serveroption @LinkedName, 'query timeout',          '900';

/* --- 3. Kiểm tra ---------------------------------------------------------- */
EXEC sp_testlinkedserver @LinkedName;
GO

/* --- 4. Thử đọc và ghi một dòng ------------------------------------------ */
SELECT TOP 5 * FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_Watermark];

INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
       (BatDau, KetThuc, TrangThai, ThongDiep)
VALUES (SYSDATETIME(), SYSDATETIME(), 'ok', N'Kiểm tra linked server từ PROD');

SELECT TOP 3 * FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
ORDER BY Id DESC;
GO

/* --- 5. Nếu collation hai máy khác nhau ----------------------------------
   Chạy trên CẢ HAI máy rồi so kết quả:
       SELECT SERVERPROPERTY('Collation');
   Khác nhau thì đặt lại tuỳ chọn dưới, nếu không phép so chuỗi sẽ chậm
   hoặc báo lỗi "cannot resolve the collation conflict":
       EXEC sp_serveroption 'MEDFORECAST_STA', 'collation compatible', 'false';
============================================================================= */
