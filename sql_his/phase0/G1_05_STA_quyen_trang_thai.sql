/* ═════════════════════════════════════════════════════════════════════════
   G1_05 · STA · QUYỀN ĐỌC TRẠNG THÁI ĐẨY DỮ LIỆU cho tài khoản ứng dụng
   MedForecast · 11/09/2026

   VÌ SAO
   Backend đọc dbo.MF_Watermark + dbo.MF_SyncLog để hiện thẻ "Trạng thái dữ
   liệu" (PROD→STA đẩy lúc nào, thành công không). Script 01 mới cấp SELECT
   trên MF_SyncLog; MF_Watermark ra đời ở Phase0_01 và chưa cấp — app báo:
     The SELECT permission was denied on the object 'MF_Watermark'

   CHẠY TRÊN: STA, database MEDFORECAST_DW, bằng tài khoản có quyền GRANT.
   Idempotent — chạy lại không sao.
   ═════════════════════════════════════════════════════════════════════════ */
USE MEDFORECAST_DW;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'medforecast_app')
BEGIN
    RAISERROR(N'Chưa có user medforecast_app trong MEDFORECAST_DW — chạy mục 8 của 01_STA_tao_database_va_bang.sql trước.', 16, 1);
    RETURN;
END
GRANT SELECT ON dbo.MF_Watermark TO medforecast_app;
GRANT SELECT ON dbo.MF_SyncLog   TO medforecast_app;
GO
-- Kiểm tra: hai dòng, permission_name = SELECT
SELECT o.name AS doi_tuong, p.permission_name, p.state_desc
FROM   sys.database_permissions p
JOIN   sys.objects o ON o.object_id = p.major_id
JOIN   sys.database_principals u ON u.principal_id = p.grantee_principal_id
WHERE  u.name = N'medforecast_app' AND o.name IN (N'MF_Watermark', N'MF_SyncLog');
GO
