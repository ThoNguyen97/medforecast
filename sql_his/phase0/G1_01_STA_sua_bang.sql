/* =============================================================================
   G1 — BƯỚC 1: SỬA BẢNG MF_TieuHao_Tong TRÊN STAGING
   =============================================================================
   Chạy trên: máy chủ STA, database MEDFORECAST_DW.
   Điều kiện: đã chạy Phase0_01_STA_bang_moi.sql.

   VÌ SAO PHẢI DỰNG LẠI BẢNG NÀY

   Bản cũ (Phase0_01) định nghĩa MF_TieuHao_Tong là "tiêu hao theo tháng × vật
   tư TRONG PHẠM VI BỆNH ĐÍCH". Đo Đ10 cho thấy định nghĩa đó làm mẫu số của
   DOI thiếu nghiêm trọng: ba nhóm hô hấp chỉ chiếm 7,80% tổng lượng xuất toàn
   viện, và trung vị theo từng mã chỉ 3,23%.

   Hệ quả đã đo được trên chính dữ liệu của bệnh viện (1.250 mã đối chiếu được
   với danh mục ứng dụng):

       mẫu số CHỈ HÔ HẤP   →  DOI trung vị  53,8 ngày   (p75 = 900 ngày)
       mẫu số TOÀN VIỆN    →  DOI trung vị  22,3 ngày   (p75 =  56 ngày)

   Tồn kho là của TOÀN VIỆN, nên mẫu số cũng phải là toàn viện. Dùng mẫu số cũ
   thì hệ thống báo an toàn cho những mã thật ra sắp cạn.

   BẢNG MỚI GIỮ CẢ HAI CỘT
       so_luong_toan_vien   toàn bộ xuất kho trong tháng (mẫu số của DOI)
       so_luong_hohap       phần thuộc lượt khám có chẩn đoán hô hấp
       d_baseline_thang     = toàn viện − hô hấp  (nhu cầu nền, TRỪ chứ không cộng)
       ty_trong_hohap       = hô hấp / toàn viện  → chọn tập mã do dịch lái

   Giữ cả hai cột chứ không chỉ giữ hiệu số: tầng sau cần tỷ trọng để biết mã
   nào mô hình dịch tễ thật sự lái được, và để hiển thị điều đó cho người dùng.
============================================================================= */

USE MEDFORECAST_DW;
GO

/* Bảng cũ chưa từng được nạp dữ liệu thật (G1 là lần nạp đầu tiên), nên dựng
   lại sạch thay vì ALTER — tránh để lại cột so_luong với ý nghĩa đã đổi.
   Nếu bảng đã có dữ liệu và muốn giữ, đổi tên nó trước khi chạy:
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

    /* MẪU SỐ CỦA DOI — toàn bộ xuất kho trong tháng, không lọc bệnh */
    so_luong_toan_vien   decimal(18,3) NOT NULL,
    /* Phần thuộc lượt khám có chẩn đoán hô hấp (quy ước: cả toa của lượt) */
    so_luong_hohap       decimal(18,3) NOT NULL CONSTRAINT DF_MF_THT2_HH DEFAULT 0,
    /* Nhu cầu nền = toàn viện − hô hấp. Tính sẵn để tầng sau không tự trừ sai. */
    d_baseline_thang     AS (so_luong_toan_vien - so_luong_hohap) PERSISTED,
    /* Tỷ trọng hô hấp, 0..100. NULL khi mẫu số = 0. */
    ty_trong_hohap       AS (CASE WHEN so_luong_toan_vien > 0
                                  THEN CAST(100.0 * so_luong_hohap / so_luong_toan_vien AS decimal(6,2))
                             END) PERSISTED,

    so_dong_toa          int           NULL,       -- chỉ để đối chiếu, KHÔNG dùng tính định mức
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

/* ⚙ Bỏ chú thích nếu đã tạo login ứng dụng
GRANT SELECT ON dbo.vw_MedForecast_TieuHaoTong TO medforecast_app;
GO
*/

SELECT name AS Bang FROM sys.tables WHERE name = 'MF_TieuHao_Tong';
SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'MF_TieuHao_Tong' ORDER BY ORDINAL_POSITION;

PRINT N'G1 bước 1 xong. Phải thấy 13 cột, trong đó d_baseline_thang và ty_trong_hohap là cột tính sẵn.';
GO
