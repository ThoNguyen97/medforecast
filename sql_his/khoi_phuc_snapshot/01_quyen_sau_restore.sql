/* ═══════════════════════════════════════════════════════════════════════════
   KHÔI PHỤC SNAPSHOT · BƯỚC 1 · QUYỀN ĐỌC CHO TÀI KHOẢN ỨNG DỤNG SAU RESTORE
   MedForecast · 23/09/2026

   TRIỆU CHỨNG (nút "Kiểm tra kết nối" sau khi RESTORE MEDFORECAST_DW):
     Đăng nhập được, nhưng "0 bảng dbo.MF_*" và mọi view báo
     The SELECT permission was denied on the object 'vw_MedForecast_...'

   NGUYÊN NHÂN
   File .bak mang theo USER medforecast_app của DATABASE (kèm SID của máy chủ
   bệnh viện). Trên máy trạm, LOGIN medforecast_app được tạo mới nên có SID
   khác → user trong DB "mồ côi" (orphaned): login đăng nhập được vào server
   nhưng không ánh xạ tới user nào có quyền trong DB. sys.tables cũng trả 0
   dòng vì metadata chỉ hiện với đối tượng mà principal có quyền.

   CÁCH SỬA (idempotent — chạy lại vô hại). Chạy trong SSMS bằng tài khoản
   sysadmin của máy trạm (Windows Authentication), ngữ cảnh MEDFORECAST_DW.
   ═══════════════════════════════════════════════════════════════════════════ */
USE MEDFORECAST_DW;
GO

/* 1. Login ở mức server (bỏ qua nếu đã có). Đổi mật khẩu cho khớp cấu hình app. */
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'medforecast_app')
    CREATE LOGIN medforecast_app WITH PASSWORD = N'<mat-khau-dat-trong-app>', CHECK_POLICY = OFF;
GO

/* 2. User trong DB: nối lại với login (sửa mồ côi) hoặc tạo mới. */
IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'medforecast_app' AND type = 'S')
    ALTER USER medforecast_app WITH LOGIN = medforecast_app;
ELSE
    CREATE USER medforecast_app FOR LOGIN medforecast_app;
GO

/* 3. Quyền: CHỈ ĐỌC toàn schema dbo (12 bảng MF_* + 7 view). Không ghi. */
ALTER ROLE db_datareader ADD MEMBER medforecast_app;
GRANT SELECT ON SCHEMA::dbo TO medforecast_app;
GO

/* 4. Kiểm tra — kỳ vọng: 12 bảng, 7+ view, 1 dòng user đã ánh xạ login. */
SELECT u.name AS db_user, l.name AS server_login,
       CASE WHEN l.sid IS NULL THEN N'MỒ CÔI' ELSE N'OK' END AS trang_thai
FROM   sys.database_principals u
LEFT JOIN sys.server_principals l ON l.sid = u.sid
WHERE  u.name = N'medforecast_app';

EXECUTE AS USER = 'medforecast_app';
SELECT (SELECT COUNT(*) FROM sys.tables WHERE name LIKE 'MF[_]%') AS so_bang_MF,
       (SELECT COUNT(*) FROM sys.views  WHERE name LIKE 'vw[_]MedForecast%') AS so_view,
       (SELECT COUNT(*) FROM dbo.vw_MedForecast_TieuHaoTong) AS dong_TieuHaoTong;
REVERT;
GO
