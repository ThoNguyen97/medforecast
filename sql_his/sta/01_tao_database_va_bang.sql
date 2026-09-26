/* =============================================================================
   sta/01_tao_database_va_bang.sql
   Chạy trên: STA, cần quyền tạo database. Tạo CSDL MEDFORECAST_DW.
   Mục đích: tạo CSDL riêng cho MedForecast cùng các bảng lõi (ca bệnh, tồn kho,
   mốc đồng bộ, nhật ký, ánh xạ mã), các view ứng dụng đọc và hai tài khoản.
   Điều kiện: chạy đầu tiên; sau đó chạy sta/02..05 theo thứ tự.

   Dùng database riêng thay vì DB eHospital STA vì DB đó có thể bị restore/refresh
   bất kỳ lúc nào. Dữ liệu ở đây là số đã tổng hợp theo (tháng × ICD × tỉnh ×
   vật tư): không có mã bệnh nhân, ngày khám, họ tên hay địa chỉ.
============================================================================= */

USE master;
GO

/* Đổi tên database và đường dẫn file nếu cần */
IF DB_ID(N'MEDFORECAST_DW') IS NULL
BEGIN
    CREATE DATABASE MEDFORECAST_DW;
    PRINT N'Đã tạo database MEDFORECAST_DW.';
END
ELSE
    PRINT N'Database MEDFORECAST_DW đã tồn tại — bỏ qua bước tạo.';
GO

ALTER DATABASE MEDFORECAST_DW SET RECOVERY SIMPLE;   -- dữ liệu dựng lại được từ PROD
GO

USE MEDFORECAST_DW;
GO

/* ── Mục 1. MF_CaBenh_VatTu — ca bệnh kèm vật tư sử dụng ──
   Các cột theo hợp đồng dữ liệu CASE_COLUMNS, cộng Period (lọc theo tháng) và
   NgayCapNhat (độ tươi).
   Quy ước: `cases` là tổng số ca của (tháng × mã ICD × tỉnh), lặp lại trên mọi
   dòng vật tư của nhóm đó; tầng sau lấy max() để khử phần lặp.              */
IF OBJECT_ID('dbo.MF_CaBenh_VatTu') IS NULL
CREATE TABLE dbo.MF_CaBenh_VatTu (
    Period           date          NOT NULL,   -- ngày 01 của tháng, để lọc
    [month]          varchar(7)    NOT NULL,   -- 'MM/YYYY', định dạng ứng dụng đọc
    disease_code     varchar(10)   NOT NULL,   -- mã ICD 3 ký tự, vd 'J06'
    disease_name     nvarchar(255) NULL,
    disease_group    varchar(20)   NULL,       -- nhóm ICD (TM_ICD.PHANNHOM), vd 'J00-J06'
    disease_group_name nvarchar(255) NULL,
    region           nvarchar(120) NOT NULL,   -- tên tỉnh/thành
    cases            int           NOT NULL,
    supply_code      nvarchar(60)  NULL,
    supply_name      nvarchar(500) NULL,
    supply_quantity  decimal(18,3) NULL,
    supply_unit      nvarchar(40)  NULL,
    supply_category  nvarchar(200) NULL,
    note             nvarchar(100) NULL,   -- nhóm dược lý (Kháng sinh, Corticoid…)
    NgayCapNhat      datetime2(0)  NOT NULL CONSTRAINT DF_MF_CBVT_Ngay DEFAULT SYSDATETIME()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_MF_CBVT_Period')
    CREATE CLUSTERED INDEX ix_MF_CBVT_Period
        ON dbo.MF_CaBenh_VatTu (Period, disease_code, region);
GO

/* Chốt chặn chống trùng: một dòng cho mỗi (tháng × mã bệnh × vùng × mã thuốc),
   bất kể thủ tục PROD, job chạy chồng hay chèn tay. Unique index coi các NULL
   là bằng nhau nên nhóm ca không có thuốc (supply_code NULL) cũng chỉ có một dòng. */
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ux_MF_CBVT_Khoa')
    CREATE UNIQUE INDEX ux_MF_CBVT_Khoa
        ON dbo.MF_CaBenh_VatTu (Period, disease_code, region, supply_code);
GO

/* Nếu tạo index lỗi vì bảng đã có dòng trùng, liệt kê và dọn trước:

   SELECT Period, disease_code, region, supply_code, COUNT(*) AS SoDongTrung
   FROM   dbo.MF_CaBenh_VatTu
   GROUP BY Period, disease_code, region, supply_code
   HAVING COUNT(*) > 1
   ORDER BY SoDongTrung DESC;

   Cách dọn an toàn nhất là xoá sạch rồi nạp lại toàn bộ từ PROD:
   TRUNCATE TABLE dbo.MF_CaBenh_VatTu;
   rồi trên PROD: EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1;       */

/* Bổ sung cột nhóm ICD nếu bảng đã tồn tại mà chưa có */
IF COL_LENGTH('dbo.MF_CaBenh_VatTu', 'disease_group') IS NULL
    ALTER TABLE dbo.MF_CaBenh_VatTu ADD disease_group varchar(20) NULL;
GO
IF COL_LENGTH('dbo.MF_CaBenh_VatTu', 'disease_group_name') IS NULL
    ALTER TABLE dbo.MF_CaBenh_VatTu ADD disease_group_name nvarchar(255) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_MF_CBVT_Nhom')
    CREATE NONCLUSTERED INDEX ix_MF_CBVT_Nhom
        ON dbo.MF_CaBenh_VatTu (disease_group, Period);
GO

/* ── Mục 2. MF_CaBenh_Nhom — số ca theo nhóm ICD ──
   T1 dự báo ở cấp nhóm rồi phân bổ top-down xuống mã. Số ca nhóm không bằng tổng
   các mã con: lượt mang J01 (chính) + J06 (phụ) là 2 ca theo mã nhưng 1 lượt của
   nhóm J00-J06. Chỉ PROD còn TIEPNHAN_ID để đếm DISTINCT lượt ở mức nhóm, nên
   PROD tính sẵn và đẩy xuống.
   Hạt: (tháng × nhóm × vùng), thêm dòng region = 'TOAN_QUOC' đếm DISTINCT riêng
   (không cộng các tỉnh, vì gộp ô nhỏ có thể gán một lượt vào hai nhãn vùng).  */
IF OBJECT_ID('dbo.MF_CaBenh_Nhom') IS NULL
CREATE TABLE dbo.MF_CaBenh_Nhom (
    Period             date          NOT NULL,
    [month]            varchar(7)    NOT NULL,
    disease_group      varchar(20)   NOT NULL,
    disease_group_name nvarchar(255) NULL,
    region             nvarchar(120) NOT NULL,   -- tên tỉnh, hoặc 'TOAN_QUOC'
    cases              int           NOT NULL,
    NgayCapNhat        datetime2(0)  NOT NULL CONSTRAINT DF_MF_CBN_Ngay DEFAULT SYSDATETIME(),
    CONSTRAINT PK_MF_CaBenh_Nhom PRIMARY KEY (Period, disease_group, region)
);
GO

/* ── Mục 3. MF_TonKho — tồn kho hiện tại (các cột theo INV_COLUMNS) ── */
IF OBJECT_ID('dbo.MF_TonKho') IS NULL
CREATE TABLE dbo.MF_TonKho (
    supply_code    nvarchar(60)  NOT NULL,
    drug_code      varchar(60)   NULL,
    ten_hoat_chat  nvarchar(500) NULL,
    unit           nvarchar(50)  NULL,
    group_name     nvarchar(255) NULL,
    category       nvarchar(100) NULL,
    stock_quantity bigint        NULL,
    [description]  nvarchar(500) NULL,
    NgayCapNhat    datetime2(0)  NOT NULL CONSTRAINT DF_MF_TK_Ngay DEFAULT SYSDATETIME(),
    CONSTRAINT PK_MF_TonKho PRIMARY KEY (supply_code)
);
GO

/* ── Mục 4. MF_Watermark — mốc đã đẩy theo từng luồng ── */
IF OBJECT_ID('dbo.MF_Watermark') IS NULL
CREATE TABLE dbo.MF_Watermark (
    TenLuong     varchar(40)  NOT NULL PRIMARY KEY,
    MocDaDay     date         NULL,          -- tháng lớn nhất đã đẩy
    LanChayCuoi  datetime2(0) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM dbo.MF_Watermark WHERE TenLuong = 'CaBenh')
    INSERT dbo.MF_Watermark (TenLuong, MocDaDay, LanChayCuoi) VALUES ('CaBenh', NULL, NULL);
GO

/* ── Mục 5. MF_SyncLog — nhật ký mỗi lần đẩy ── */
IF OBJECT_ID('dbo.MF_SyncLog') IS NULL
CREATE TABLE dbo.MF_SyncLog (
    Id            bigint IDENTITY(1,1) PRIMARY KEY,
    BatDau        datetime2(0)  NOT NULL,
    KetThuc       datetime2(0)  NULL,
    TuNgay        date          NULL,        -- cửa sổ đã nạp lại
    SoDongCaBenh  int           NULL,
    SoDongTonKho  int           NULL,
    TongSoCa      int           NULL,        -- để đối chiếu nhanh
    TrangThai     varchar(20)   NULL,        -- ok | failed
    ThongDiep     nvarchar(2000) NULL
);
GO

/* ── Mục 6. MF_MapVatTu — ánh xạ mã vật tư HIS ↔ mã ứng dụng ──
   Để trống ban đầu; khi mã HIS khác mã ứng dụng thì thêm dòng, các view tự đổi. */
IF OBJECT_ID('dbo.MF_MapVatTu') IS NULL
CREATE TABLE dbo.MF_MapVatTu (
    MaHIS   nvarchar(60) NOT NULL PRIMARY KEY,
    MaApp   nvarchar(60) NOT NULL,
    GhiChu  nvarchar(255) NULL
);
GO

/* ── Mục 7. View — điểm tiếp xúc của ứng dụng ──
   Ứng dụng chỉ SELECT view, không đọc bảng gốc; đổi cấu trúc bảng mà giữ tên
   cột view thì ứng dụng không phải sửa.                                     */
GO
CREATE OR ALTER VIEW dbo.vw_MedForecast_CaBenh
AS
SELECT  c.Period,
        c.[month],
        c.disease_code,
        c.disease_name,
        c.disease_group,
        c.disease_group_name,
        c.region,
        c.cases,
        ISNULL(m.MaApp, c.supply_code) AS supply_code,
        c.supply_name,
        c.supply_quantity,
        c.supply_unit,
        c.supply_category,
        c.note
FROM    dbo.MF_CaBenh_VatTu c
LEFT JOIN dbo.MF_MapVatTu m ON m.MaHIS = c.supply_code;
GO

CREATE OR ALTER VIEW dbo.vw_MedForecast_CaBenhNhom
AS
SELECT  Period, [month], disease_group, disease_group_name, region, cases
FROM    dbo.MF_CaBenh_Nhom;
GO

CREATE OR ALTER VIEW dbo.vw_MedForecast_TonKho
AS
SELECT  ISNULL(m.MaApp, t.supply_code) AS supply_code,
        t.drug_code,
        t.ten_hoat_chat,
        t.unit,
        t.group_name,
        t.category,
        t.stock_quantity,
        t.[description]
FROM    dbo.MF_TonKho t
LEFT JOIN dbo.MF_MapVatTu m ON m.MaHIS = t.supply_code;
GO

/* ── Mục 8. Tài khoản ứng dụng medforecast_app — chỉ đọc view ── */
/* Bỏ chú thích và đổi mật khẩu trước khi chạy
USE master;
CREATE LOGIN medforecast_app WITH PASSWORD = N'<<dat-mat-khau-manh>>';
GO
USE MEDFORECAST_DW;
CREATE USER medforecast_app FOR LOGIN medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_CaBenh     TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_CaBenhNhom TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TonKho     TO medforecast_app;
GRANT SELECT ON dbo.MF_SyncLog            TO medforecast_app;   -- để xem độ tươi
GO
*/

/* ── Mục 9. Tài khoản medforecast_push cho linked server từ PROD — quyền ghi ── */
/* Bỏ chú thích và đổi mật khẩu trước khi chạy
USE master;
CREATE LOGIN medforecast_push WITH PASSWORD = N'<<dat-mat-khau-manh>>';
GO
USE MEDFORECAST_DW;
CREATE USER medforecast_push FOR LOGIN medforecast_push;
ALTER ROLE db_datareader ADD MEMBER medforecast_push;
ALTER ROLE db_datawriter ADD MEMBER medforecast_push;
GRANT ALTER ON SCHEMA::dbo TO medforecast_push;   -- cần cho TRUNCATE TABLE
GO
*/

PRINT N'Xong sta/01. Kiểm tra bằng: SELECT * FROM MEDFORECAST_DW.sys.tables;';
