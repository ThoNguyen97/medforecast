USE MEDFORECAST_DW
GO

/* ═════════════════════════════════════════════════════════════════════════
   Dọn tàn dư phân hệ mua sắm bên STA (13/09/2026)

   MF_VatTu_ThuocTinh (lead time, MOQ, tỷ lệ giao đủ) và MF_LichSuNhap (0 dòng
   trên dump 13/09) chỉ phục vụ công thức tồn an toàn (R,S)/ROP — ngoài phạm vi
   DSS 3 tầng. Ứng dụng không đọc hai view tương ứng (dss_loader chỉ có 4 luồng:
   TieuHaoTong, CaBenhPhanCap, TieuHaoPhanCap, TonKhoLo_MoiNhat).

   Chạy SAU khi đã triển khai G2_01 trên PROD (thủ tục bản 2 không còn ghi
   vào hai bảng này). An toàn khi chạy lại.
   ═════════════════════════════════════════════════════════════════════════ */

IF OBJECT_ID('dbo.vw_MedForecast_VatTuThuocTinh', 'V') IS NOT NULL
    DROP VIEW dbo.vw_MedForecast_VatTuThuocTinh;
IF OBJECT_ID('dbo.vw_MedForecast_LichSuNhap', 'V') IS NOT NULL
    DROP VIEW dbo.vw_MedForecast_LichSuNhap;
IF OBJECT_ID('dbo.MF_VatTu_ThuocTinh', 'U') IS NOT NULL
    DROP TABLE dbo.MF_VatTu_ThuocTinh;
IF OBJECT_ID('dbo.MF_LichSuNhap', 'U') IS NOT NULL
    DROP TABLE dbo.MF_LichSuNhap;
GO

/* Kiểm: 5 bảng MF_ nghiệp vụ + Watermark/SyncLog/MapVatTu, 6 view còn lại */
SELECT name, type_desc
FROM   sys.objects
WHERE  name LIKE 'MF[_]%' OR name LIKE 'vw[_]MedForecast%'
ORDER BY type_desc, name;
GO
