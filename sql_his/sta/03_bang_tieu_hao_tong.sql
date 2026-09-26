/* sta/03_bang_tieu_hao_tong.sql
   Chạy trên: STA, CSDL MEDFORECAST_DW.
   Mục đích: dựng bảng MF_TieuHao_Tong (tiêu hao tháng × vật tư toàn viện, mẫu số DOI)
   và view vw_MedForecast_TieuHaoTong; tồn kho là toàn viện nên mẫu số DOI cũng phải toàn viện.
   Điều kiện: đã chạy sta/02. */

USE MEDFORECAST_DW;
GO

/* Dựng lại thay vì ALTER; muốn giữ dữ liệu thì sp_rename bảng trước */
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

    /* Mẫu số DOI: toàn bộ xuất kho trong tháng */
    so_luong_toan_vien   decimal(18,3) NOT NULL,
    /* Cả toa của lượt có chẩn đoán hô hấp */
    so_luong_hohap       decimal(18,3) NOT NULL CONSTRAINT DF_MF_THT2_HH DEFAULT 0,
    /* Nhu cầu nền D_baseline */
    d_baseline_thang     AS (so_luong_toan_vien - so_luong_hohap) PERSISTED,
    /* 0..100, NULL khi mẫu số = 0 */
    ty_trong_hohap       AS (CASE WHEN so_luong_toan_vien > 0
                                  THEN CAST(100.0 * so_luong_hohap / so_luong_toan_vien AS decimal(6,2))
                             END) PERSISTED,

    so_dong_toa          int           NULL,       -- chỉ để đối chiếu
    so_luot              int           NULL,
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

/* Mốc đồng bộ riêng, khác nhịp luồng ca bệnh */
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
