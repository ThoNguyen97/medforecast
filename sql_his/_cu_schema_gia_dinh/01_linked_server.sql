/* =============================================================================
   01 — LINKED SERVER TỪ STA SANG HIS PROD  +  SYNONYM ÁNH XẠ BẢNG
   =============================================================================
   Chạy trên: STA (không chạy trên PROD).
   Quyền:     sysadmin hoặc ALTER ANY LINKED SERVER trên STA.

   Ý tưởng: mọi tên bảng thật của HIS chỉ xuất hiện DUY NHẤT trong file này,
   dưới dạng SYNONYM. Các script sau (03 job, 04 tổng hợp) chỉ dùng synonym
   `src.*`, nên khi HIS đổi tên bảng chỉ phải sửa lại đúng một chỗ.
============================================================================= */

/* ⚙ ─────────────── CHỈNH 5 GIÁ TRỊ NÀY THEO MÔI TRƯỜNG THẬT ───────────────
   @LinkedName : tên gợi nhớ của linked server, dùng lại ở các script sau
   @ProdHost   : tên máy hoặc IP\Instance của HIS PROD
   @ProdDb     : tên database HIS trên PROD
   @ReadUser   : tài khoản CHỈ ĐỌC trên PROD (không dùng tài khoản sa)
   @ReadPass   : mật khẩu tài khoản đó
   ------------------------------------------------------------------------- */
DECLARE @LinkedName sysname      = N'HIS_PROD';
DECLARE @ProdHost   nvarchar(200)= N'10.0.0.10\HIS';
DECLARE @ProdDb     sysname      = N'HISDB';
DECLARE @ReadUser   sysname      = N'medforecast_ro';
DECLARE @ReadPass   nvarchar(200)= N'<<mat-khau>>';

/* --- 1. Tạo linked server ------------------------------------------------- */
IF EXISTS (SELECT 1 FROM sys.servers WHERE name = @LinkedName)
    EXEC sp_dropserver @server = @LinkedName, @droplogins = 'droplogins';

EXEC sp_addlinkedserver
     @server       = @LinkedName,
     @srvproduct   = N'',
     @provider     = N'MSOLEDBSQL',       -- driver hiện hành; SQLNCLI11 đã ngừng hỗ trợ
     @datasrc      = @ProdHost,
     @catalog      = @ProdDb;

EXEC sp_addlinkedsrvlogin
     @rmtsrvname   = @LinkedName,
     @useself      = N'False',            -- KHÔNG mượn danh tính người gọi
     @rmtuser      = @ReadUser,
     @rmtpassword  = @ReadPass;

/* --- 2. Thiết lập an toàn ------------------------------------------------- */
-- rpc/rpc out = off: chặn thực thi thủ tục trên PROD qua linked server.
EXEC sp_serveroption @LinkedName, 'rpc',              'false';
EXEC sp_serveroption @LinkedName, 'rpc out',          'false';
-- collation compatible = true khi PROD và STA cùng collation (đọc nhanh hơn nhiều).
-- Kiểm tra trước bằng: SELECT SERVERPROPERTY('Collation') trên cả hai máy.
EXEC sp_serveroption @LinkedName, 'collation compatible', 'true';
-- Đẩy phép lọc/gộp sang PROD thay vì kéo cả bảng về rồi mới lọc.
EXEC sp_serveroption @LinkedName, 'use remote collation', 'true';
EXEC sp_serveroption @LinkedName, 'lazy schema validation', 'true';
-- Thời gian chờ truy vấn (giây); 0 = theo mặc định máy chủ.
EXEC sp_serveroption @LinkedName, 'query timeout',     '600';

/* --- 3. Kiểm tra kết nối -------------------------------------------------- */
EXEC sp_testlinkedserver @LinkedName;
GO

/* --- 4. Synonym: NƠI DUY NHẤT chứa tên bảng thật của HIS ------------------ */
IF SCHEMA_ID('src') IS NULL EXEC(N'CREATE SCHEMA src');
GO

/* ⚙ Đổi phần [HISDB].[dbo].[TenBangThat] theo kết quả script 00.
   Bên trái (src.XXX) GIỮ NGUYÊN — các script sau phụ thuộc vào tên này.      */
IF OBJECT_ID('src.KhamBenh')    IS NOT NULL DROP SYNONYM src.KhamBenh;
IF OBJECT_ID('src.ChanDoan')    IS NOT NULL DROP SYNONYM src.ChanDoan;
IF OBJECT_ID('src.BenhNhan')    IS NOT NULL DROP SYNONYM src.BenhNhan;
IF OBJECT_ID('src.VatTu')       IS NOT NULL DROP SYNONYM src.VatTu;
IF OBJECT_ID('src.SuDungVatTu') IS NOT NULL DROP SYNONYM src.SuDungVatTu;
IF OBJECT_ID('src.TonKho')      IS NOT NULL DROP SYNONYM src.TonKho;
GO

CREATE SYNONYM src.KhamBenh    FOR [HIS_PROD].[HISDB].[dbo].[KhamBenh];
CREATE SYNONYM src.ChanDoan    FOR [HIS_PROD].[HISDB].[dbo].[ChanDoan];
CREATE SYNONYM src.BenhNhan    FOR [HIS_PROD].[HISDB].[dbo].[BenhNhan];
CREATE SYNONYM src.VatTu       FOR [HIS_PROD].[HISDB].[dbo].[VatTu];
CREATE SYNONYM src.SuDungVatTu FOR [HIS_PROD].[HISDB].[dbo].[SuDungVatTu];
CREATE SYNONYM src.TonKho      FOR [HIS_PROD].[HISDB].[dbo].[TonKho];
GO

/* --- 5. Thử đọc 1 dòng mỗi bảng ------------------------------------------ */
SELECT TOP 1 * FROM src.KhamBenh;
SELECT TOP 1 * FROM src.ChanDoan;
SELECT TOP 1 * FROM src.BenhNhan;
SELECT TOP 1 * FROM src.VatTu;
SELECT TOP 1 * FROM src.SuDungVatTu;
SELECT TOP 1 * FROM src.TonKho;
GO
