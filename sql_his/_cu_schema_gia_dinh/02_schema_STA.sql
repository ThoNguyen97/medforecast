/* =============================================================================
   02 — SCHEMA CỦA DB STA
   =============================================================================
   Chạy trên: STA.

   NGUYÊN TẮC THIẾT KẾ
   STA KHÔNG sao chép nguyên si HIS. Nó chỉ giữ đúng phần MedForecast cần:
     • Ít cột hơn  → job đồng bộ nhẹ, HIS đổi cột lạ cũng không ảnh hưởng.
     • KHÔNG chép dữ liệu định danh bệnh nhân (họ tên, CCCD, địa chỉ, số điện
       thoại, ngày sinh). Chỉ giữ tỉnh/thành — đủ để phân tích theo địa lý.
       Đây là điểm nên nêu trong báo cáo: giảm thiểu dữ liệu ngay từ thiết kế.
     • Tên cột do mình đặt và cố định → các script sau không phụ thuộc HIS.
============================================================================= */

IF SCHEMA_ID('stg') IS NULL EXEC(N'CREATE SCHEMA stg');
GO

/* --- Bệnh nhân: CHỈ tỉnh/thành ------------------------------------------- */
IF OBJECT_ID('stg.BenhNhan') IS NULL
CREATE TABLE stg.BenhNhan (
    BenhNhanId   bigint       NOT NULL PRIMARY KEY,
    Tinh         nvarchar(120) NULL
);
GO

/* --- Lượt khám ------------------------------------------------------------ */
IF OBJECT_ID('stg.KhamBenh') IS NULL
CREATE TABLE stg.KhamBenh (
    KhamBenhId   bigint       NOT NULL PRIMARY KEY,
    BenhNhanId   bigint       NULL,
    NgayKham     date         NOT NULL,
    TrangThai    varchar(40)  NULL,
    NgayCapNhat  datetime2(0) NULL      -- mốc thay đổi bên PROD, dùng cho tăng dần
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='ix_stg_KhamBenh_NgayKham')
    CREATE INDEX ix_stg_KhamBenh_NgayKham ON stg.KhamBenh(NgayKham) INCLUDE (BenhNhanId, TrangThai);
GO

/* --- Chẩn đoán ------------------------------------------------------------ */
IF OBJECT_ID('stg.ChanDoan') IS NULL
CREATE TABLE stg.ChanDoan (
    ChanDoanId   bigint       NOT NULL PRIMARY KEY,
    KhamBenhId   bigint       NOT NULL,
    MaICD        varchar(20)  NULL,
    TenICD       nvarchar(255) NULL,
    LaChinh      bit          NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='ix_stg_ChanDoan_KhamBenh')
    CREATE INDEX ix_stg_ChanDoan_KhamBenh ON stg.ChanDoan(KhamBenhId) INCLUDE (MaICD, LaChinh);
GO

/* --- Danh mục vật tư ------------------------------------------------------ */
IF OBJECT_ID('stg.VatTu') IS NULL
CREATE TABLE stg.VatTu (
    VatTuId      bigint       NOT NULL PRIMARY KEY,
    MaVatTu      varchar(60)  NULL,
    TenVatTu     nvarchar(400) NULL,
    MaThuoc      varchar(60)  NULL,
    HoatChat     nvarchar(500) NULL,
    DonVi        nvarchar(40) NULL,
    NhomVatTu    nvarchar(255) NULL,
    LoaiVatTu    nvarchar(80) NULL,
    MoTa         nvarchar(500) NULL,
    TrangThai    bit          NULL
);
GO

/* --- Vật tư dùng theo lượt khám ------------------------------------------ */
IF OBJECT_ID('stg.SuDungVatTu') IS NULL
CREATE TABLE stg.SuDungVatTu (
    SuDungId     bigint       NOT NULL PRIMARY KEY,
    KhamBenhId   bigint       NOT NULL,
    VatTuId      bigint       NULL,
    SoLuong      decimal(18,3) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='ix_stg_SuDungVatTu_KhamBenh')
    CREATE INDEX ix_stg_SuDungVatTu_KhamBenh ON stg.SuDungVatTu(KhamBenhId) INCLUDE (VatTuId, SoLuong);
GO

/* --- Tồn kho (ảnh chụp hiện tại) ----------------------------------------- */
IF OBJECT_ID('stg.TonKho') IS NULL
CREATE TABLE stg.TonKho (
    VatTuId      bigint       NOT NULL PRIMARY KEY,
    SoLuongTon   bigint       NULL,
    NgayCapNhat  datetime2(0) NULL
);
GO

/* --- Mốc đã đồng bộ ------------------------------------------------------- */
IF OBJECT_ID('stg.SyncWatermark') IS NULL
CREATE TABLE stg.SyncWatermark (
    TenBang       sysname      NOT NULL PRIMARY KEY,
    MocDaDongBo   datetime2(0) NULL,     -- giá trị NgayCapNhat/NgayKham lớn nhất đã lấy
    LanChayCuoi   datetime2(0) NULL
);
GO

/* --- Nhật ký đồng bộ ------------------------------------------------------ */
IF OBJECT_ID('stg.SyncLog') IS NULL
CREATE TABLE stg.SyncLog (
    Id            bigint IDENTITY(1,1) PRIMARY KEY,
    BatDau        datetime2(0) NOT NULL,
    KetThuc       datetime2(0) NULL,
    TuNgay        date         NULL,     -- cửa sổ đã nạp lại
    SoDongKhamBenh    bigint   NULL,
    SoDongChanDoan    bigint   NULL,
    SoDongSuDungVatTu bigint   NULL,
    SoDongVatTu       bigint   NULL,
    SoDongTonKho      bigint   NULL,
    TrangThai     varchar(20)  NULL,     -- ok | failed
    ThongDiep     nvarchar(2000) NULL
);
GO

PRINT N'Đã tạo schema STA.';
