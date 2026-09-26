/* =============================================================================
   sta/03_bang_tieu_hao_tong.sql
   Chạy trên: STA, CSDL MEDFORECAST_DW.
   Mục đích: dựng bảng MF_TieuHao_Tong (tiêu hao theo tháng × vật tư, toàn viện)
   và view vw_MedForecast_TieuHaoTong. File này là nơi duy nhất định nghĩa view.
   Điều kiện: đã chạy sta/02_bang_dss_phan_cap_ton_kho_lo.sql.

   Tồn kho là của toàn viện nên mẫu số DOI phải là tiêu hao toàn viện; chỉ lấy
   phần hô hấp làm DOI bị thổi phồng và báo an toàn cho mã sắp cạn. Bảng giữ:
       so_luong_toan_vien   toàn bộ xuất kho trong tháng (mẫu số DOI)
       so_luong_hohap       phần thuộc lượt khám có chẩn đoán hô hấp
       d_baseline_thang     = toàn viện − hô hấp (nhu cầu nền D_baseline)
       ty_trong_hohap       = hô hấp / toàn viện, xác định mã do dịch tễ chi phối
============================================================================= */

USE MEDFORECAST_DW;
GO

/* Dựng lại thay vì ALTER để không giữ cột so_luong của cấu trúc do sta/02 tạo.
   Muốn giữ dữ liệu hiện có thì đổi tên bảng trước khi chạy:
       EXEC sp_rename 'dbo.MF_TieuHao_Tong', 'MF_TieuHao_Tong_cu';            */
IF OBJECT_ID('dbo.MF_TieuHao_Tong') IS NOT NULL
BEGIN
    DECLARE @n INT = (SELECT COUNT(*) FROM dbo.MF_TieuHao_Tong);
    PRINT CONCAT(N'MF_TieuHao_Tong cũ có ', @n, N' dòng — sẽ bị xoá và dựng lại.');
    DROP TABLE dbo.MF_TieuHao_Tong;
END
GO

CREATE TABLE dbo.MF_TieuHao_Tong (
    Period               date          NOT NULL,
    [month]              varchar(7)    NOT NULL,   -- 'MM/YYYY'
    supply_code          nvarchar(60)  NOT NULL,
    supply_name          nvarchar(500) NULL,
    supply_unit          nvarchar(40)  NULL,
    is_vtyt              bit           NOT NULL CONSTRAINT DF_MF_THT2_VTYT DEFAULT 0,

    /* Mẫu số DOI — toàn bộ xuất kho trong tháng, không lọc bệnh */
    so_luong_toan_vien   decimal(18,3) NOT NULL,
    /* Phần thuộc lượt khám có chẩn đoán hô hấp (quy ước: cả toa của lượt) */
    so_luong_hohap       decimal(18,3) NOT NULL CONSTRAINT DF_MF_THT2_HH DEFAULT 0,
    /* Nhu cầu nền = toàn viện − hô hấp, tính sẵn cho tầng sau. */
    d_baseline_thang     AS (so_luong_toan_vien - so_luong_hohap) PERSISTED,
    /* Tỷ trọng hô hấp, 0..100. NULL khi mẫu số = 0. */
    ty_trong_hohap       AS (CASE WHEN so_luong_toan_vien > 0
                                  THEN CAST(100.0 * so_luong_hohap / so_luong_toan_vien AS decimal(6,2))
                             END) PERSISTED,

    so_dong_toa          int           NULL,       -- chỉ để đối chiếu, không dùng tính định mức
    so_luot              int           NULL,       -- số lượt có dùng vật tư này
    NgayCapNhat          datetime2(0)  NOT NULL
        CONSTRAINT DF_MF_THT2_Ngay DEFAULT SYSDATETIME(),
    CONSTRAINT PK_MF_TieuHao_Tong PRIMARY KEY (Period, supply_code)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_MF_THT2_VatTu')
    CREATE NONCLUSTERED INDEX ix_MF_THT2_VatTu
        ON dbo.MF_TieuHao_Tong (supply_code, Period)
        INCLUDE (so_luong_toan_vien, so_luong_hohap);
GO

/* Mốc đồng bộ riêng cho luồng này — khác nhịp với luồng ca bệnh. */
IF NOT EXISTS (SELECT 1 FROM dbo.MF_Watermark WHERE TenLuong = 'TieuHaoTong')
    INSERT dbo.MF_Watermark (TenLuong, MocDaDay, LanChayCuoi)
    VALUES ('TieuHaoTong', NULL, NULL);
GO

CREATE OR ALTER VIEW dbo.vw_MedForecast_TieuHaoTong
AS
SELECT  t.Period, t.[month],
        ISNULL(m.MaApp, t.supply_code) AS supply_code,
        t.supply_name, t.supply_unit, t.is_vtyt,
        t.so_luong_toan_vien,
        t.so_luong_hohap,
        t.d_baseline_thang,
        t.ty_trong_hohap,
        t.so_dong_toa, t.so_luot
FROM    dbo.MF_TieuHao_Tong t
LEFT JOIN dbo.MF_MapVatTu m ON m.MaHIS = t.supply_code;
GO

/* Bỏ chú thích nếu đã tạo user medforecast_app
GRANT SELECT ON dbo.vw_MedForecast_TieuHaoTong TO medforecast_app;
GO
*/

SELECT name AS Bang FROM sys.tables WHERE name = 'MF_TieuHao_Tong';
SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'MF_TieuHao_Tong' ORDER BY ORDINAL_POSITION;

PRINT N'Xong sta/03: MF_TieuHao_Tong có 13 cột, d_baseline_thang và ty_trong_hohap là cột tính sẵn.';
GO
