USE MEDFORECAST_DW
GO

/* sta/05_xoa_bang_mua_sam.sql
   Chạy trên: STA, CSDL MEDFORECAST_DW.
   Mục đích: xoá MF_VatTu_ThuocTinh, MF_LichSuNhap và hai view tương ứng (chỉ phục vụ ROP, ngoài phạm vi DSS).
   Điều kiện: đã triển khai prod/04 (thủ tục không còn ghi hai bảng này). Idempotent. */

IF OBJECT_ID('dbo.vw_MedForecast_VatTuThuocTinh', 'V') IS NOT NULL
    DROP VIEW dbo.vw_MedForecast_VatTuThuocTinh;
IF OBJECT_ID('dbo.vw_MedForecast_LichSuNhap', 'V') IS NOT NULL
    DROP VIEW dbo.vw_MedForecast_LichSuNhap;
IF OBJECT_ID('dbo.MF_VatTu_ThuocTinh', 'U') IS NOT NULL
    DROP TABLE dbo.MF_VatTu_ThuocTinh;
IF OBJECT_ID('dbo.MF_LichSuNhap', 'U') IS NOT NULL
    DROP TABLE dbo.MF_LichSuNhap;
GO

/* Kiểm tra: đối tượng MF_* và vw_MedForecast* còn lại */
SELECT name, type_desc
FROM   sys.objects
WHERE  name LIKE 'MF[_]%' OR name LIKE 'vw[_]MedForecast%'
ORDER BY type_desc, name;
GO
