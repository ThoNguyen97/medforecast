/* =============================================================================
   PHASE 0 — BƯỚC 1: BẢNG MỚI TRÊN MÁY CHỦ STAGING
   =============================================================================
   Chạy trên: máy chủ STA, database MEDFORECAST_DW.
   Điều kiện: đã chạy xong script 01_STA_tao_database_va_bang.sql của bản trước.

   File này CHỈ THÊM, không sửa và không xoá bảng nào đang có. Chạy lại nhiều
   lần vô hại (mọi lệnh đều có IF ... IS NULL / IF NOT EXISTS).

   -----------------------------------------------------------------------------
   SÁU BẢNG MỚI VÀ LÝ DO TỒN TẠI CỦA TỪNG BẢNG

   MF_CaBenh_PhanCap    Số ca theo (tháng × nhóm bệnh × rổ chăm sóc).
                        MẪU SỐ của định mức. Không suy ra được từ bảng cũ vì
                        bảng cũ không mang phân cấp chăm sóc.
                        → thay thế bảng severity_rates gõ tay (Đ4 đo được
                          42,2/40,8/17,0 trong khi bảng tay ghi 71,49/23,51/5).

   MF_TieuHao_PhanCap   Số lượng thuốc theo (tháng × nhóm bệnh × rổ × vật tư).
                        TỬ SỐ của định mức. Định mức = số lượng / số lượt,
                        KHÔNG phải số dòng toa / số lượt — Đ5 cho thấy ngoại trú
                        có ít dòng toa hơn nhưng số lượng mỗi dòng gấp 5,5 lần.

   MF_TieuHao_Tong      Số lượng theo (tháng × vật tư), bỏ chiều bệnh.
                        Dùng cho σ_d, phân lớp ABC-XYZ và cho vật tư không gắn
                        được với nhóm bệnh nào.

   MF_TonKho_Lo         Tồn kho tách theo LÔ, kèm hạn dùng. Nền của FEFO:
                        S_usable = Σ clamp(D(e_b) − C_(b−1), 0, q_b).
                        Bảng MF_TonKho cũ chỉ có tổng, không đủ.

   MF_LichSuNhap        Lịch sử từng dòng nhập kho. Nguồn duy nhất đo được
                        σ_L (độ lệch chuẩn thời gian giao hàng) và chu kỳ nhập
                        thực tế. Không có bảng này thì SS phải dùng L cố định.

   MF_VatTu_ThuocTinh   Bốn cột master data đang RỖNG 0/5041 trong ứng dụng:
                        lead_time_days, minimum_order_quantity, unit_price
                        (storage_capacity HIS không có — xem ghi chú cuối file).

   -----------------------------------------------------------------------------
   VỀ QUYỀN RIÊNG TƯ CỦA CÁC BẢNG MỚI

   Bảng cũ MF_CaBenh_VatTu có chiều VÙNG nên phải áp ngưỡng ô nhỏ k=5
   (Luật 91/2025, Điều 2). Các bảng mới KHÔNG có chiều vùng, không có mã bệnh
   nhân, không có ngày cụ thể — hạt nhỏ nhất là (tháng × nhóm bệnh × phân cấp).
   Một ô có 1 ca ở đây chỉ nói "trong tháng X có một lượt hô hấp ở cấp chăm sóc
   Y", không kèm nơi cư trú, không kèm mã bệnh chi tiết → không tái định danh
   được. Vì vậy KHÔNG áp ngưỡng gộp lên các bảng này: gộp sẽ làm hỏng chính
   tỷ trọng p̂(g,c) mà chúng sinh ra.
   Thủ tục vẫn ĐẾM và GHI NHẬT KÝ số ô nhỏ để có bằng chứng khi bảo vệ.
============================================================================= */

USE MEDFORECAST_DW;
GO


/* ═════════════════════════════════════════════════════════════════════════
   1) MF_CaBenh_PhanCap — MẪU SỐ của định mức
   -------------------------------------------------------------------------
   `ro` là rổ tính định mức, đúng 5 giá trị (Đ5 buộc tách NGT khỏi NT-cấp 3):
       'NGT'  ngoại trú                    (mặc định coi như cấp 3, nhưng
                                            KHÔNG gộp — chênh 3,5 lần)
       'NT1'  nội trú, chăm sóc cấp 1 (nặng)
       'NT2'  nội trú, chăm sóc cấp 2 (vừa)
       'NT3'  nội trú, chăm sóc cấp 3 (nhẹ)
       'NT0'  nội trú, chưa gán phân cấp   (Đ3 đo: 0,02% năm 2026, 0% 2019-2025)

   `cases` = COUNT(DISTINCT lượt tiếp nhận) trong rổ đó, ở MỨC NHÓM.
   Một lượt mang J01 + J06 (cùng nhóm J00-J06) chỉ đếm MỘT lần — đây là điểm
   khác biệt với bảng MF_CaBenh_VatTu, nơi lượt đó cố ý đếm hai lần theo mã.
   ═════════════════════════════════════════════════════════════════════════ */
IF OBJECT_ID('dbo.MF_CaBenh_PhanCap') IS NULL
CREATE TABLE dbo.MF_CaBenh_PhanCap (
    Period             date          NOT NULL,
    [month]            varchar(7)    NOT NULL,   -- 'MM/YYYY'
    disease_group      varchar(20)   NOT NULL,   -- 'J00-J06' | 'J09-J18' | 'J20-J22'
    disease_group_name nvarchar(255) NULL,
    ro                 varchar(4)    NOT NULL,   -- NGT | NT1 | NT2 | NT3 | NT0
    cases              int           NOT NULL,
    NgayCapNhat        datetime2(0)  NOT NULL
        CONSTRAINT DF_MF_CBPC_Ngay DEFAULT SYSDATETIME(),
    CONSTRAINT PK_MF_CaBenh_PhanCap PRIMARY KEY (Period, disease_group, ro),
    CONSTRAINT CK_MF_CBPC_Ro CHECK (ro IN ('NGT','NT1','NT2','NT3','NT0'))
);
GO


/* ═════════════════════════════════════════════════════════════════════════
   2) MF_TieuHao_PhanCap — TỬ SỐ của định mức
   -------------------------------------------------------------------------
   Định mức Tầng 3:   Norm(vật tư i, nhóm g, rổ r) = so_luong / cases(g, r)

   `so_dong_toa` KHÔNG dùng để tính định mức. Nó ở đây để đối chiếu và để
   phát hiện lỗi đơn vị tính: Đ5 cho thấy NGT 4,72 dòng/lượt nhưng 18,29
   đơn vị/dòng, còn NT-cấp 3 là 16,89 dòng/lượt và 3,33 đơn vị/dòng. Nếu ai
   đó lỡ tính định mức theo số dòng, hai con số này sẽ tố cáo ngay.

   `is_vtyt`: 0 = thuốc (TM_LOAIDUOC.LOAIVATTU_ID = 'T'), 1 = vật tư y tế.
   Y lệnh VTYT KHÔNG mang phân cấp chăm sóc (ISYLENHVTYT = 1), nên với các
   dòng is_vtyt = 1 thì tầng sau phải GỘP các rổ NT* lại trước khi chia —
   xem hàm định mức ở Phase 3.
   ═════════════════════════════════════════════════════════════════════════ */
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
    so_luong        decimal(18,3) NOT NULL,      -- dùng cái này để tính định mức
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


/* ═════════════════════════════════════════════════════════════════════════
   3) MF_TieuHao_Tong — bỏ chiều bệnh
   -------------------------------------------------------------------------
   Phạm vi: vẫn chỉ các lượt thuộc ba nhóm ICD đích (thủ tục không quét toàn
   viện). Nói cho đúng: "tổng tiêu hao trong phạm vi bệnh đích", không phải
   tổng tiêu hao toàn bệnh viện. Ghi rõ ở đây để sau này không hiểu nhầm khi
   đối chiếu với báo cáo xuất kho của khoa Dược.

   Dùng cho: σ_d hằng tháng, phân lớp XYZ, ABC theo giá trị.
   ═════════════════════════════════════════════════════════════════════════ */
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
    so_luot     int           NULL,              -- số lượt có dùng vật tư này
    NgayCapNhat datetime2(0)  NOT NULL
        CONSTRAINT DF_MF_THT_Ngay DEFAULT SYSDATETIME(),
    CONSTRAINT PK_MF_TieuHao_Tong PRIMARY KEY (Period, supply_code)
);
GO


/* ═════════════════════════════════════════════════════════════════════════
   4) MF_TonKho_Lo — nền của FEFO
   -------------------------------------------------------------------------
   Nguồn (Đ1 đã xác minh):
       TT_DUOC_TONKHO.SOLONHAP_ID  →  TT_DUOC_CHUNGTU_SOLONHAP.SOLONHAP_ID
       TT_DUOC_CHUNGTU_SOLONHAP.HANDUNG  = hạn dùng của lô

   `lot_id` = SOLONHAP_ID. Giá trị 0 dành cho dòng tồn KHÔNG tra được lô
   (SOLONHAP_ID NULL). PHẢI giữ những dòng này, không được lọc bỏ: nếu bỏ,
   tổng tồn theo lô sẽ nhỏ hơn MF_TonKho và người dùng thấy "hụt hàng" giả.
   Cột `co_han_dung` cho phép giao diện nói thật: "3.104/5.041 mã có hạn dùng".

   Ba cột giá giữ nguyên cả ba, KHÔNG chọn hộ ứng dụng:
       don_gia_mua  giá thực trả trên chứng từ nhập
       don_gia_thau giá trúng thầu (ràng buộc hợp đồng)
       don_gia_von  giá vốn ghi sổ
   ABC theo giá trị nên dùng don_gia_mua của lần nhập gần nhất; hai cột kia để
   đối chiếu và cho bài toán hạn mức thầu sau này.

   Bảng có NgaySnapshot vì tồn kho là ẢNH CHỤP, không phải chuỗi giao dịch.
   Giữ nhiều ngày để vẽ được đường tồn kho và kiểm chứng lượng hết hạn thực tế.
   ═════════════════════════════════════════════════════════════════════════ */
IF OBJECT_ID('dbo.MF_TonKho_Lo') IS NULL
CREATE TABLE dbo.MF_TonKho_Lo (
    NgaySnapshot    date          NOT NULL,
    supply_code     nvarchar(60)  NOT NULL,
    lot_id          bigint        NOT NULL,      -- SOLONHAP_ID; 0 = không rõ lô
    lot_code        nvarchar(100) NULL,          -- SOLONHAP / SOLOSANPHAM
    expiry_date     date          NULL,          -- HANDUNG
    co_han_dung     bit           NOT NULL CONSTRAINT DF_MF_TKL_CoHD DEFAULT 0,
    quantity        decimal(18,3) NOT NULL,
    so_kho          int           NULL,          -- số kho đang giữ lô này
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


/* ═════════════════════════════════════════════════════════════════════════
   5) MF_LichSuNhap — nguồn duy nhất đo được σ_L
   -------------------------------------------------------------------------
   Nguồn (Đ2 đã xác minh):
       TT_DUOC_CHUNGTU        NGAYCHUNGTU, NGAYNHAP, NHACUNGCAP_ID, GOITHAU_ID
       TT_DUOC_CHUNGTU_CHITIET DONDATHANG_ID, SOLONHAP_ID,
                               SOLUONGYEUCAU, SOLUONGTHUCTE, DONGIATHAU

   HAI LOẠI "THỜI GIAN GIAO HÀNG" — ĐỪNG TRỘN
     lead_noibo_ngay  = NGAYNHAP − NGAYCHUNGTU
                        độ trễ xử lý nội bộ (chứng từ → nhập kho thực).
                        LUÔN đo được. Thường nhỏ.
     lead_thau_ngay   = NGAYNHAP − ngày đặt hàng (qua DONDATHANG_ID)
                        thời gian giao hàng THẬT của nhà cung cấp.
                        Chỉ đo được khi tìm ra bảng đơn đặt hàng — xem
                        Đ8 trong file hướng dẫn. Để NULL nếu chưa có.

   Công thức SS cần σ của lead_thau_ngay. Nếu Phase 0 chỉ lấy được
   lead_noibo_ngay thì PHẢI khai báo rõ trên giao diện là "chưa đo được thời
   gian giao hàng nhà cung cấp, đang dùng L cố định theo cấu hình" — không
   được lặng lẽ thay bằng lead nội bộ, vì làm vậy sẽ cho σ_L ≈ 0 và SS thiếu.

   `ty_le_giao_du` = SOLUONGTHUCTE / SOLUONGYEUCAU. Đây là biến thứ hai của
   bài toán 2 (nhà cung cấp giao thiếu), độc lập với biến thời gian.
   ═════════════════════════════════════════════════════════════════════════ */
IF OBJECT_ID('dbo.MF_LichSuNhap') IS NULL
CREATE TABLE dbo.MF_LichSuNhap (
    chungtu_id        bigint        NOT NULL,
    supply_code       nvarchar(60)  NOT NULL,
    lot_id            bigint        NOT NULL,    -- SOLONHAP_ID; 0 = không rõ
    ngay_chungtu      date          NULL,
    ngay_nhap         date          NULL,
    ngay_dat_hang     date          NULL,        -- NULL cho tới khi tìm ra bảng ĐĐH
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


/* ═════════════════════════════════════════════════════════════════════════
   6) MF_VatTu_ThuocTinh — bốn cột master data đang rỗng
   -------------------------------------------------------------------------
   Đo được từ MF_LichSuNhap:
       lead_time_ngay_trungvi   trung vị — dùng làm L̄. KHÔNG dùng trung bình:
                                phân bố thời gian giao hàng lệch phải, một lần
                                giao chậm 90 ngày sẽ kéo trung bình đi.
       lead_time_ngay_dolech    σ_L, vào thẳng công thức SS.
       lead_time_ngay_p90       để giao diện nói "90% các lần về trong N ngày".
       moq                      MIN(so_luong_thucte > 0) — lượng đặt nhỏ nhất
                                từng thấy. Đây là ƯỚC LƯỢNG, không phải quy định
                                của nhà cung cấp; cột `moq_nguon` ghi rõ điều đó.
       don_gia_*                giá của LẦN NHẬP GẦN NHẤT.

   KHÔNG đo được từ HIS: storage_capacity (sức chứa kho). HIS không lưu thể
   tích/diện tích lưu trữ. Cột vẫn có ở đây nhưng nguồn phải là NHẬP TAY hoặc
   quy ước — xem file Phase0_04, mục "sức chứa".
   ═════════════════════════════════════════════════════════════════════════ */
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
    chu_ky_nhap_trungvi     int           NULL,   -- số ngày giữa hai lần nhập
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


/* ═════════════════════════════════════════════════════════════════════════
   7) Mốc đồng bộ cho các luồng mới
   ═════════════════════════════════════════════════════════════════════════ */
IF NOT EXISTS (SELECT 1 FROM dbo.MF_Watermark WHERE TenLuong = 'PhanCap')
    INSERT dbo.MF_Watermark (TenLuong, MocDaDay, LanChayCuoi) VALUES ('PhanCap', NULL, NULL);
IF NOT EXISTS (SELECT 1 FROM dbo.MF_Watermark WHERE TenLuong = 'KhoCungUng')
    INSERT dbo.MF_Watermark (TenLuong, MocDaDay, LanChayCuoi) VALUES ('KhoCungUng', NULL, NULL);
GO


/* ═════════════════════════════════════════════════════════════════════════
   8) VIEW — điểm tiếp xúc duy nhất của ứng dụng
   Tất cả đều đi qua MF_MapVatTu để đổi mã HIS sang mã ứng dụng, giống hệt
   hai view cũ. Ứng dụng KHÔNG được SELECT thẳng bảng gốc.
   ═════════════════════════════════════════════════════════════════════════ */
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

CREATE OR ALTER VIEW dbo.vw_MedForecast_TieuHaoTong
AS
SELECT  t.Period, t.[month],
        ISNULL(m.MaApp, t.supply_code) AS supply_code,
        t.supply_name, t.supply_unit, t.is_vtyt,
        t.so_luong, t.so_dong_toa, t.so_luot
FROM    dbo.MF_TieuHao_Tong t
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

/* Chỉ ảnh chụp MỚI NHẤT — ứng dụng dùng view này cho màn hình FEFO,
   khỏi phải tự tìm MAX(NgaySnapshot).                                     */
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


/* ═════════════════════════════════════════════════════════════════════════
   9) QUYỀN — bổ sung cho tài khoản ứng dụng và tài khoản đẩy
   ⚙ Bỏ chú thích nếu đã tạo hai login ở script 01.
   ═════════════════════════════════════════════════════════════════════════ */
/*
GRANT SELECT ON dbo.vw_MedForecast_CaBenhPhanCap    TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TieuHaoPhanCap   TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TieuHaoTong      TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TonKhoLo         TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TonKhoLo_MoiNhat TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_LichSuNhap       TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_VatTuThuocTinh   TO medforecast_app;
GO
*/


/* ═════════════════════════════════════════════════════════════════════════
   10) KIỂM TRA SAU KHI CHẠY
   ═════════════════════════════════════════════════════════════════════════ */
SELECT  t.name AS Bang,
        CASE WHEN t.name LIKE 'MF[_]%' THEN N'bảng dữ liệu' ELSE N'' END AS Loai,
        (SELECT SUM(p.rows) FROM sys.partitions p
         WHERE p.object_id = t.object_id AND p.index_id IN (0,1)) AS SoDong
FROM    sys.tables t
WHERE   t.name LIKE 'MF[_]%'
ORDER BY t.name;

SELECT name AS View_ FROM sys.views WHERE name LIKE 'vw[_]MedForecast[_]%' ORDER BY name;

PRINT N'Phase 0 — bước 1 xong. Phải thấy đủ 6 bảng MF_ mới và 7 view mới.';
GO


/* =============================================================================
   GHI CHÚ — SỨC CHỨA KHO (storage_capacity)
   -----------------------------------------------------------------------------
   HIS không có dữ liệu này và sẽ không bao giờ có: kho dược quản lý theo giá
   trị và số lượng, không theo thể tích. Ba lựa chọn, xếp theo mức trung thực:

   1. BỎ RÀNG BUỘC (khuyến nghị cho đợt này). Đặt storage_capacity = NULL và
      để hàm calculate_order_quantity() bỏ qua trần khi NULL. Trung thực, và
      không tạo ra con số bịa trong luận văn.
   2. TRẦN THEO BỘI SỐ NHU CẦU. storage_capacity = k × nhu cầu tháng cao nhất
      trong 24 tháng (k = 3 chẳng hạn). Đây là ràng buộc VẬN HÀNH ("đừng ôm quá
      3 tháng hàng"), không phải sức chứa vật lý — phải gọi đúng tên nó trên
      giao diện là "trần dự trữ", không phải "sức chứa kho".
   3. NHẬP TAY cho nhóm A (theo Đ7/ABC, khoảng vài chục mã). Chính xác nhất
      nhưng cần khoa Dược ngồi điền.

   Đừng chọn cách 2 rồi gọi nó là "sức chứa" — đó chính là loại nhầm lẫn đã
   sinh ra vòng lặp safety_stock tự tham chiếu trong bản hiện tại.
============================================================================= */
