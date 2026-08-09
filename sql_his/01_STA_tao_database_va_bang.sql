/* =============================================================================
   01 — BƯỚC 1: TẠO DATABASE VÀ BẢNG TRÊN MÁY CHỦ STAGING
   =============================================================================
   Chạy trên: máy chủ STA (staging). Cần quyền tạo database.

   VÌ SAO TẠO DATABASE RIÊNG, KHÔNG DÙNG CHUNG DB eHospital STA
   STA là môi trường test — đội khác có thể restore hoặc refresh lại DB bất cứ
   lúc nào, và khi đó bảng của MedForecast biến mất mà không ai báo. Một database
   riêng trên cùng máy chủ tránh được chuyện đó, đồng thời không lẫn với dữ liệu
   test của eHospital.

   DỮ LIỆU ĐI QUA ĐÂY LÀ SỐ ĐÃ TỔNG HỢP, KHÔNG PHẢI BẢN SAO HỒ SƠ
   Thủ tục bên PROD gộp sẵn theo (tháng × mã ICD × tỉnh × vật tư) rồi mới đẩy
   xuống. Nghĩa là không có mã bệnh nhân, không có ngày khám cụ thể, không có
   họ tên / số định danh / địa chỉ — không thể truy ngược ra một người bệnh cụ
   thể từ database này. Đây là điểm nên nêu trong báo cáo.
============================================================================= */

USE master;
GO

/* ⚙ Đổi tên database và đường dẫn file nếu cần */
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

/* ─────────────────────────────────────────────────────────────────────────
   BẢNG 1 — Ca bệnh kèm vật tư sử dụng
   Đúng 11 cột theo hợp đồng dữ liệu của MedForecast (CASE_COLUMNS), cộng
   thêm Period để lọc theo ngày cho nhanh và NgayCapNhat để biết độ tươi.

   QUY ƯỚC QUAN TRỌNG: `cases` là TỔNG SỐ CA của (tháng × mã ICD × tỉnh),
   LẶP LẠI trên mọi dòng vật tư của nhóm đó. Tầng sau lấy max() để khử phần
   lặp. Nếu đẩy xuống 1 ca mỗi dòng thì mọi tháng sẽ chỉ còn 1 ca.
   ───────────────────────────────────────────────────────────────────────── */
IF OBJECT_ID('dbo.MF_CaBenh_VatTu') IS NULL
CREATE TABLE dbo.MF_CaBenh_VatTu (
    Period           date          NOT NULL,   -- ngày 01 của tháng, để lọc
    [month]          varchar(7)    NOT NULL,   -- 'MM/YYYY' — đúng định dạng app đọc
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

/* CHỐT CHẶN CHỐNG TRÙNG — quan trọng nhất trong file này.
   Một dòng cho mỗi (tháng × mã bệnh × vùng × mã thuốc). Dù thủ tục bên PROD có
   sai, dù job chạy chồng nhau, dù ai đó chèn tay — CSDL vẫn không thể chứa hai
   dòng cùng khoá. Không có dòng trùng thì mô hình không bị đếm hai lần.
   SQL Server coi các giá trị NULL là bằng nhau trong unique index, nên nhóm ca
   không có thuốc nào (supply_code NULL) cũng chỉ tồn tại đúng một dòng.        */
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ux_MF_CBVT_Khoa')
    CREATE UNIQUE INDEX ux_MF_CBVT_Khoa
        ON dbo.MF_CaBenh_VatTu (Period, disease_code, region, supply_code);
GO

/* Nếu lệnh trên báo lỗi vì bảng ĐÃ có dòng trùng (từ lần chạy cũ), xem chúng ở
   đây rồi dọn trước khi tạo index:

   SELECT Period, disease_code, region, supply_code, COUNT(*) AS SoDongTrung
   FROM   dbo.MF_CaBenh_VatTu
   GROUP BY Period, disease_code, region, supply_code
   HAVING COUNT(*) > 1
   ORDER BY SoDongTrung DESC;

   Cách dọn an toàn nhất: xoá sạch rồi cho thủ tục nạp lại từ đầu —
   TRUNCATE TABLE dbo.MF_CaBenh_VatTu;
   rồi bên PROD chạy: EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1;   */

/* Nâng cấp bảng đã tồn tại từ bản trước (chưa có cột nhóm) ------------------ */
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

/* ─────────────────────────────────────────────────────────────────────────
   BẢNG 1b — Số ca theo NHÓM ICD
   ---------------------------------------------------------------------------
   VÌ SAO PHẢI CÓ BẢNG RIÊNG, KHÔNG CỘNG TỪ BẢNG 1

   Đề cương dự báo ở cấp NHÓM rồi phân bổ xuống mã. Nhưng số ca của nhóm KHÔNG
   bằng tổng số ca các mã con: một lượt khám mang J01 (chính) và J06 (phụ) được
   tính 1 ca cho J01 và 1 ca cho J06 — cộng lại là 2, trong khi nhóm J00-J06
   chỉ có 1 lượt. Cả hai mã này đều nằm trong cùng một nhóm nên phần đếm trùng
   rơi hết vào nội bộ nhóm.

   Chỉ PROD mới còn TIEPNHAN_ID để đếm DISTINCT ở mức nhóm. Xuống tới đây thì
   thông tin đó đã mất, không có cách nào tính lại. Vì vậy PROD tính sẵn và đẩy
   xuống bảng này.

   Hạt: (tháng × nhóm × vùng). Có thêm dòng region = 'TOAN_QUOC' — cũng đếm
   DISTINCT riêng, không phải tổng các tỉnh (bước gộp ô nhỏ có thể xếp cùng một
   lượt vào hai nhãn vùng khác nhau ở hai mã khác nhau).
   ───────────────────────────────────────────────────────────────────────── */
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

/* ─────────────────────────────────────────────────────────────────────────
   BẢNG 2 — Tồn kho hiện tại (đúng 8 cột theo INV_COLUMNS)
   ───────────────────────────────────────────────────────────────────────── */
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

/* ─────────────────────────────────────────────────────────────────────────
   BẢNG 3 — Mốc đã đẩy (để lần sau chỉ đẩy phần mới)
   ───────────────────────────────────────────────────────────────────────── */
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

/* ─────────────────────────────────────────────────────────────────────────
   BẢNG 4 — Nhật ký mỗi lần đẩy
   ───────────────────────────────────────────────────────────────────────── */
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

/* ─────────────────────────────────────────────────────────────────────────
   BẢNG 5 — Ánh xạ mã vật tư HIS ↔ mã trong MedForecast
   Để trống ban đầu. Khi phát hiện mã kho của HIS khác mã trong ứng dụng thì
   thêm dòng vào đây; view bên dưới sẽ tự đổi.
   ───────────────────────────────────────────────────────────────────────── */
IF OBJECT_ID('dbo.MF_MapVatTu') IS NULL
CREATE TABLE dbo.MF_MapVatTu (
    MaHIS   nvarchar(60) NOT NULL PRIMARY KEY,
    MaApp   nvarchar(60) NOT NULL,
    GhiChu  nvarchar(255) NULL
);
GO

/* ─────────────────────────────────────────────────────────────────────────
   VIEW — Điểm tiếp xúc duy nhất mà MedForecast đọc
   Ứng dụng chỉ SELECT hai view này, không đụng bảng gốc. Sau này đổi cấu
   trúc bên trong mà giữ nguyên tên cột thì ứng dụng không cần sửa.
   ───────────────────────────────────────────────────────────────────────── */
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

/* ─────────────────────────────────────────────────────────────────────────
   TÀI KHOẢN CHO ỨNG DỤNG — chỉ đọc, chỉ trên hai view
   ───────────────────────────────────────────────────────────────────────── */
/* ⚙ Bỏ chú thích và đổi mật khẩu trước khi chạy
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

/* ─────────────────────────────────────────────────────────────────────────
   TÀI KHOẢN CHO LINKED SERVER TỪ PROD ĐẨY XUỐNG — cần quyền ghi
   ───────────────────────────────────────────────────────────────────────── */
/* ⚙ Bỏ chú thích và đổi mật khẩu trước khi chạy
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

PRINT N'Bước 1 xong. Kiểm tra bằng: SELECT * FROM MEDFORECAST_DW.sys.tables;';
