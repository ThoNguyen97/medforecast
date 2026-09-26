/* sta/02_bang_dss_phan_cap_ton_kho_lo.sql
   Chạy trên: STA, CSDL MEDFORECAST_DW.
   Mục đích: tạo bảng DSS 3 tầng (MF_CaBenh_PhanCap, MF_TieuHao_PhanCap, MF_TieuHao_Tong,
   MF_TonKho_Lo, MF_LichSuNhap, MF_VatTu_ThuocTinh) và view; không áp ngưỡng ô nhỏ vì hạt tháng × nhóm × rổ.
   Điều kiện: đã chạy sta/01. Chỉ thêm, không sửa bảng có sẵn; idempotent. */

USE MEDFORECAST_DW;
GO


/* 1) MF_CaBenh_PhanCap: mẫu số định mức; ro = NGT ngoại trú, NT1..NT3 nội trú theo cấp chăm sóc,
   NT0 chưa gán; cases = COUNT(DISTINCT lượt) ở mức nhóm */
IF OBJECT_ID('dbo.MF_CaBenh_PhanCap') IS NULL
CREATE TABLE dbo.MF_CaBenh_PhanCap (
    Period             date          NOT NULL,
    [month]            varchar(7)    NOT NULL,   -- 'MM/YYYY'
    disease_group      varchar(20)   NOT NULL,   -- 'J00-J06' | 'J09-J18' | 'J20-J22'
    disease_group_name nvarchar(255) NULL,
    ro                 varchar(4)    NOT NULL,
    cases              int           NOT NULL,
    NgayCapNhat        datetime2(0)  NOT NULL
        CONSTRAINT DF_MF_CBPC_Ngay DEFAULT SYSDATETIME(),
    CONSTRAINT PK_MF_CaBenh_PhanCap PRIMARY KEY (Period, disease_group, ro),
    CONSTRAINT CK_MF_CBPC_Ro CHECK (ro IN ('NGT','NT1','NT2','NT3','NT0'))
);
GO


/* 2) MF_TieuHao_PhanCap: tử số định mức, Norm(i, g, r) = so_luong / cases(g, r);
   y lệnh VTYT không mang phân cấp nên is_vtyt = 1 phải gộp các rổ NT* trước khi chia */
IF OBJECT_ID('dbo.MF_TieuHao_PhanCap') IS NULL
CREATE TABLE dbo.MF_TieuHao_PhanCap (
    Period          date          NOT NULL,
    [month]         varchar(7)    NOT NULL,
    disease_group   varchar(20)   NOT NULL,
    ro              varchar(4)    NOT NULL,
    supply_code     nvarchar(60)  NOT NULL,
    supply_name     nvarchar(500) NULL,
    supply_unit     nvarchar(40)  NULL,
    supply_category nvarchar(200) NULL,
    note            nvarchar(100) NULL,          -- nhóm dược lý
    is_vtyt         bit           NOT NULL CONSTRAINT DF_MF_THPC_VTYT DEFAULT 0,
    so_luong        decimal(18,3) NOT NULL,
    so_dong_toa     int           NULL,          -- chỉ để đối chiếu
    NgayCapNhat     datetime2(0)  NOT NULL
        CONSTRAINT DF_MF_THPC_Ngay DEFAULT SYSDATETIME(),
    CONSTRAINT PK_MF_TieuHao_PhanCap
        PRIMARY KEY (Period, disease_group, ro, supply_code),
    CONSTRAINT CK_MF_THPC_Ro CHECK (ro IN ('NGT','NT1','NT2','NT3','NT0'))
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_MF_THPC_VatTu')
    CREATE NONCLUSTERED INDEX ix_MF_THPC_VatTu
        ON dbo.MF_TieuHao_PhanCap (supply_code, Period);
GO


/* 3) MF_TieuHao_Tong: bỏ chiều bệnh; sta/03 dựng lại với mẫu số toàn viện và định nghĩa view */
IF OBJECT_ID('dbo.MF_TieuHao_Tong') IS NULL
CREATE TABLE dbo.MF_TieuHao_Tong (
    Period      date          NOT NULL,
    [month]     varchar(7)    NOT NULL,
    supply_code nvarchar(60)  NOT NULL,
    supply_name nvarchar(500) NULL,
    supply_unit nvarchar(40)  NULL,
    is_vtyt     bit           NOT NULL CONSTRAINT DF_MF_THT_VTYT DEFAULT 0,
    so_luong    decimal(18,3) NOT NULL,
    so_dong_toa int           NULL,
    so_luot     int           NULL,
    NgayCapNhat datetime2(0)  NOT NULL
        CONSTRAINT DF_MF_THT_Ngay DEFAULT SYSDATETIME(),
    CONSTRAINT PK_MF_TieuHao_Tong PRIMARY KEY (Period, supply_code)
);
GO


/* 4) MF_TonKho_Lo: ảnh chụp tồn theo ngày và lô, nền FEFO; giữ cả dòng lot_id = 0 (không tra được lô)
   nếu không tổng tồn theo lô nhỏ hơn MF_TonKho và sinh cảnh báo thiếu hụt giả */
IF OBJECT_ID('dbo.MF_TonKho_Lo') IS NULL
CREATE TABLE dbo.MF_TonKho_Lo (
    NgaySnapshot    date          NOT NULL,
    supply_code     nvarchar(60)  NOT NULL,
    lot_id          bigint        NOT NULL,      -- SOLONHAP_ID; 0 = không rõ lô
    lot_code        nvarchar(100) NULL,          -- SOLONHAP / SOLOSANPHAM
    expiry_date     date          NULL,          -- HANDUNG
    co_han_dung     bit           NOT NULL CONSTRAINT DF_MF_TKL_CoHD DEFAULT 0,
    quantity        decimal(18,3) NOT NULL,
    so_kho          int           NULL,
    don_gia_mua     decimal(18,4) NULL,
    don_gia_thau    decimal(18,4) NULL,
    don_gia_von     decimal(18,4) NULL,
    NgayCapNhat     datetime2(0)  NOT NULL
        CONSTRAINT DF_MF_TKL_Ngay DEFAULT SYSDATETIME(),
    CONSTRAINT PK_MF_TonKho_Lo PRIMARY KEY (NgaySnapshot, supply_code, lot_id)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_MF_TKL_HanDung')
    CREATE NONCLUSTERED INDEX ix_MF_TKL_HanDung
        ON dbo.MF_TonKho_Lo (NgaySnapshot, expiry_date)
        INCLUDE (supply_code, quantity);
GO


/* 5) MF_LichSuNhap: lịch sử nhập kho, thuộc bài toán mua sắm ngoài phạm vi DSS; sta/05 xoá */
IF OBJECT_ID('dbo.MF_LichSuNhap') IS NULL
CREATE TABLE dbo.MF_LichSuNhap (
    chungtu_id        bigint        NOT NULL,
    supply_code       nvarchar(60)  NOT NULL,
    lot_id            bigint        NOT NULL,    -- SOLONHAP_ID; 0 = không rõ
    ngay_chungtu      date          NULL,
    ngay_nhap         date          NULL,
    ngay_dat_hang     date          NULL,
    lead_noibo_ngay   int           NULL,
    lead_thau_ngay    int           NULL,
    nhacungcap_id     int           NULL,
    goithau_id        int           NULL,
    dondathang_id     bigint        NULL,
    loai_chungtu      nvarchar(50)  NULL,
    mucdich_code      nvarchar(50)  NULL,
    so_luong_yeucau   decimal(18,3) NULL,
    so_luong_thucte   decimal(18,3) NULL,
    ty_le_giao_du     decimal(9,4)  NULL,
    don_gia_thau      decimal(18,4) NULL,
    han_dung          date          NULL,
    NgayCapNhat       datetime2(0)  NOT NULL
        CONSTRAINT DF_MF_LSN_Ngay DEFAULT SYSDATETIME(),
    CONSTRAINT PK_MF_LichSuNhap PRIMARY KEY (chungtu_id, supply_code, lot_id)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_MF_LSN_VatTu')
    CREATE NONCLUSTERED INDEX ix_MF_LSN_VatTu
        ON dbo.MF_LichSuNhap (supply_code, ngay_nhap);
GO


/* 6) MF_VatTu_ThuocTinh: lead time, MOQ suy từ MF_LichSuNhap, ngoài phạm vi DSS; sta/05 xoá */
IF OBJECT_ID('dbo.MF_VatTu_ThuocTinh') IS NULL
CREATE TABLE dbo.MF_VatTu_ThuocTinh (
    supply_code             nvarchar(60)  NOT NULL PRIMARY KEY,
    so_lan_nhap             int           NULL,
    so_nha_cung_cap         int           NULL,
    lead_time_ngay_trungvi  int           NULL,
    lead_time_ngay_tb       decimal(10,2) NULL,
    lead_time_ngay_dolech   decimal(10,2) NULL,   -- σ_L
    lead_time_ngay_p90      int           NULL,
    lead_time_nguon         varchar(12)   NULL,   -- 'THAU' | 'NOIBO' | 'MACDINH'
    chu_ky_nhap_trungvi     int           NULL,   -- ngày
    moq                     decimal(18,3) NULL,
    moq_nguon               varchar(12)   NULL,   -- 'QUANSAT' | 'MACDINH'
    ty_le_giao_du_tb        decimal(9,4)  NULL,
    don_gia_mua             decimal(18,4) NULL,
    don_gia_thau            decimal(18,4) NULL,
    don_gia_von             decimal(18,4) NULL,
    ngay_nhap_gan_nhat      date          NULL,
    NgayCapNhat             datetime2(0)  NOT NULL
        CONSTRAINT DF_MF_VTTT_Ngay DEFAULT SYSDATETIME()
);
GO


/* 7) Mốc đồng bộ cho các luồng mới */
IF NOT EXISTS (SELECT 1 FROM dbo.MF_Watermark WHERE TenLuong = 'PhanCap')
    INSERT dbo.MF_Watermark (TenLuong, MocDaDay, LanChayCuoi) VALUES ('PhanCap', NULL, NULL);
IF NOT EXISTS (SELECT 1 FROM dbo.MF_Watermark WHERE TenLuong = 'KhoCungUng')
    INSERT dbo.MF_Watermark (TenLuong, MocDaDay, LanChayCuoi) VALUES ('KhoCungUng', NULL, NULL);
GO


/* 8) View: đổi mã HIS sang mã ứng dụng qua MF_MapVatTu; vw_MedForecast_TieuHaoTong do sta/03 định nghĩa */
GO
CREATE OR ALTER VIEW dbo.vw_MedForecast_CaBenhPhanCap
AS
SELECT Period, [month], disease_group, disease_group_name, ro, cases
FROM   dbo.MF_CaBenh_PhanCap;
GO

CREATE OR ALTER VIEW dbo.vw_MedForecast_TieuHaoPhanCap
AS
SELECT  t.Period, t.[month], t.disease_group, t.ro,
        ISNULL(m.MaApp, t.supply_code) AS supply_code,
        t.supply_name, t.supply_unit, t.supply_category, t.note,
        t.is_vtyt, t.so_luong, t.so_dong_toa
FROM    dbo.MF_TieuHao_PhanCap t
LEFT JOIN dbo.MF_MapVatTu m ON m.MaHIS = t.supply_code;
GO

CREATE OR ALTER VIEW dbo.vw_MedForecast_TonKhoLo
AS
SELECT  t.NgaySnapshot,
        ISNULL(m.MaApp, t.supply_code) AS supply_code,
        t.lot_id, t.lot_code, t.expiry_date, t.co_han_dung,
        t.quantity, t.so_kho,
        t.don_gia_mua, t.don_gia_thau, t.don_gia_von
FROM    dbo.MF_TonKho_Lo t
LEFT JOIN dbo.MF_MapVatTu m ON m.MaHIS = t.supply_code;
GO

/* Ảnh chụp mới nhất, dùng cho FEFO/DOI */
CREATE OR ALTER VIEW dbo.vw_MedForecast_TonKhoLo_MoiNhat
AS
SELECT  t.NgaySnapshot,
        ISNULL(m.MaApp, t.supply_code) AS supply_code,
        t.lot_id, t.lot_code, t.expiry_date, t.co_han_dung,
        t.quantity, t.so_kho,
        t.don_gia_mua, t.don_gia_thau, t.don_gia_von
FROM    dbo.MF_TonKho_Lo t
LEFT JOIN dbo.MF_MapVatTu m ON m.MaHIS = t.supply_code
WHERE   t.NgaySnapshot = (SELECT MAX(NgaySnapshot) FROM dbo.MF_TonKho_Lo);
GO

CREATE OR ALTER VIEW dbo.vw_MedForecast_LichSuNhap
AS
SELECT  l.chungtu_id,
        ISNULL(m.MaApp, l.supply_code) AS supply_code,
        l.lot_id, l.ngay_chungtu, l.ngay_nhap, l.ngay_dat_hang,
        l.lead_noibo_ngay, l.lead_thau_ngay,
        l.nhacungcap_id, l.goithau_id, l.dondathang_id,
        l.loai_chungtu, l.mucdich_code,
        l.so_luong_yeucau, l.so_luong_thucte, l.ty_le_giao_du,
        l.don_gia_thau, l.han_dung
FROM    dbo.MF_LichSuNhap l
LEFT JOIN dbo.MF_MapVatTu m ON m.MaHIS = l.supply_code;
GO

CREATE OR ALTER VIEW dbo.vw_MedForecast_VatTuThuocTinh
AS
SELECT  ISNULL(m.MaApp, v.supply_code) AS supply_code,
        v.so_lan_nhap, v.so_nha_cung_cap,
        v.lead_time_ngay_trungvi, v.lead_time_ngay_tb,
        v.lead_time_ngay_dolech, v.lead_time_ngay_p90, v.lead_time_nguon,
        v.chu_ky_nhap_trungvi,
        v.moq, v.moq_nguon, v.ty_le_giao_du_tb,
        v.don_gia_mua, v.don_gia_thau, v.don_gia_von,
        v.ngay_nhap_gan_nhat
FROM    dbo.MF_VatTu_ThuocTinh v
LEFT JOIN dbo.MF_MapVatTu m ON m.MaHIS = v.supply_code;
GO


/* 9) Quyền đọc cho medforecast_app. Bỏ chú thích nếu đã tạo user (sta/01 mục 8)
GRANT SELECT ON dbo.vw_MedForecast_CaBenhPhanCap    TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TieuHaoPhanCap   TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TieuHaoTong      TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TonKhoLo         TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TonKhoLo_MoiNhat TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_LichSuNhap       TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_VatTuThuocTinh   TO medforecast_app;
GRANT SELECT ON dbo.MF_Watermark                    TO medforecast_app;
GO
*/


/* 10) Kiểm tra sau khi chạy */
SELECT  t.name AS Bang,
        CASE WHEN t.name LIKE 'MF[_]%' THEN N'bảng dữ liệu' ELSE N'' END AS Loai,
        (SELECT SUM(p.rows) FROM sys.partitions p
         WHERE p.object_id = t.object_id AND p.index_id IN (0,1)) AS SoDong
FROM    sys.tables t
WHERE   t.name LIKE 'MF[_]%'
ORDER BY t.name;

SELECT name AS View_ FROM sys.views WHERE name LIKE 'vw[_]MedForecast[_]%' ORDER BY name;

PRINT N'Xong sta/02: đã tạo các bảng MF_* DSS và view vw_MedForecast_* tương ứng.';
GO
