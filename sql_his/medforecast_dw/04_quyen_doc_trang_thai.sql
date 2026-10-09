/* medforecast_dw/04_quyen_doc_trang_thai.sql
   Chạy trên: CSDL trung gian MEDFORECAST_DW, tài khoản có quyền GRANT.
   Mục đích: cấp SELECT MF_Watermark, MF_SyncLog cho medforecast_app (thẻ "Trạng thái dữ liệu").
   Điều kiện: đã tạo user medforecast_app (medforecast_dw/01 mục 8). Idempotent. */
USE MEDFORECAST_DW;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'medforecast_app')
BEGIN
    RAISERROR(N'Chưa có user medforecast_app trong MEDFORECAST_DW, chạy mục 8 của medforecast_dw/01_tao_database_va_bang.sql trước.', 16, 1);
    RETURN;
END
GRANT SELECT ON dbo.MF_Watermark TO medforecast_app;
GRANT SELECT ON dbo.MF_SyncLog   TO medforecast_app;
GO
-- Kiểm tra: hai dòng SELECT
SELECT o.name AS doi_tuong, p.permission_name, p.state_desc
FROM   sys.database_permissions p
JOIN   sys.objects o ON o.object_id = p.major_id
JOIN   sys.database_principals u ON u.principal_id = p.grantee_principal_id
WHERE  u.name = N'medforecast_app' AND o.name IN (N'MF_Watermark', N'MF_SyncLog');
GO
