/* =============================================================================
   04 — SCRIPT TỔNG HỢP: HÀM & VIEW MEDFORECAST ĐỌC
   =============================================================================
   Chạy trên: STA. Cần chạy 02 và 03 trước (STA phải có dữ liệu).

   Đây là ĐIỂM TIẾP XÚC DUY NHẤT giữa MedForecast và hạ tầng bệnh viện.
   MedForecast chỉ gọi:
        SELECT * FROM dbo.fn_MedForecast_CaBenh(@since_date);
        SELECT * FROM dbo.vw_MedForecast_TonKho;
   Nhờ vậy khi HIS đổi cấu trúc, chỉ cần sửa file này — không đụng vào ứng dụng.

   BỐN ĐIỂM PHẢI GIỮ ĐÚNG (sai một trong bốn thì hệ thống vẫn chạy nhưng ra số
   sai và KHÔNG có lỗi nào báo ra):

   1. `cases` = COUNT(DISTINCT lượt khám) theo (tháng × mã ICD × tỉnh), LẶP LẠI
      trên mọi dòng vật tư của nhóm đó. Tầng sau lấy max() để khử phần lặp — nên
      nếu trả 1 dòng/lượt khám với `1 AS cases` thì mọi tháng chỉ còn 1 ca.

   2. Mã ICD phải GOM VỀ 3 KÝ TỰ trước khi đếm. HIS thường lưu 'J01.0', 'J01.9'.
      Nếu để nguyên, mỗi mã con thành một dòng riêng và bước max() ở tầng sau sẽ
      lấy mã con lớn nhất thay vì tổng — thiếu ca. Ví dụ J01.0 = 5, J01.1 = 3 thì
      đúng phải là 8, để nguyên sẽ ra 5.

   3. Lọc @since_date trên CỘT NGÀY, không bọc cột trong hàm định dạng.

   4. Không trả ra dữ liệu định danh bệnh nhân — STA vốn đã không chép sang.
============================================================================= */

/* --- Bảng ánh xạ tỉnh (dùng khi HIS lưu MÃ SỐ thay vì tên) ---------------- */
/* Nếu HIS đã lưu tên tỉnh thì để bảng này rỗng, hàm sẽ tự dùng giá trị gốc.  */
IF OBJECT_ID('stg.MapTinh') IS NULL
CREATE TABLE stg.MapTinh (
    GiaTriNguon  nvarchar(120) NOT NULL PRIMARY KEY,   -- ví dụ '79' hoặc 'TPHCM'
    TenTinh      nvarchar(120) NOT NULL                -- ví dụ N'Thành phố Hồ Chí Minh'
);
GO
-- Ví dụ nạp: INSERT stg.MapTinh VALUES (N'79', N'Thành phố Hồ Chí Minh');

/* --- Danh sách trạng thái lượt khám được tính là "đã chốt" ---------------- */
/* ⚙ Chỉnh theo kết quả mục 5b của script 00.                                */
IF OBJECT_ID('stg.TrangThaiHopLe') IS NULL
CREATE TABLE stg.TrangThaiHopLe (TrangThai varchar(40) NOT NULL PRIMARY KEY);
GO
IF NOT EXISTS (SELECT 1 FROM stg.TrangThaiHopLe)
    INSERT stg.TrangThaiHopLe (TrangThai) VALUES ('HOAN_TAT');   -- ⚙ đổi cho khớp
GO

/* =============================================================================
   HÀM TỔNG HỢP CA BỆNH  (inline TVF — tối ưu hoá nội tuyến, lọc đẩy xuống được)
   Trả về đúng 11 cột theo hợp đồng CASE_COLUMNS của MedForecast.
============================================================================= */
CREATE OR ALTER FUNCTION dbo.fn_MedForecast_CaBenh (@since_date date)
RETURNS TABLE
AS
RETURN
(
    WITH ca AS (            -- 1 dòng / lượt khám, mã ICD đã gom về 3 ký tự
        SELECT DISTINCT
               k.KhamBenhId                              AS encounter_id,
               k.NgayKham                                AS ngay_kham,
               LEFT(UPPER(LTRIM(RTRIM(cd.MaICD))), 3)    AS disease_code,
               cd.TenICD                                 AS disease_name,
               ISNULL(mt.TenTinh, bn.Tinh)               AS region
        FROM   stg.KhamBenh k
        JOIN   stg.ChanDoan cd ON cd.KhamBenhId = k.KhamBenhId
        JOIN   stg.BenhNhan bn ON bn.BenhNhanId = k.BenhNhanId
        LEFT JOIN stg.MapTinh mt ON mt.GiaTriNguon = bn.Tinh
        WHERE  k.NgayKham >= @since_date
          AND  k.TrangThai IN (SELECT TrangThai FROM stg.TrangThaiHopLe)
          AND  cd.LaChinh = 1                        -- chỉ chẩn đoán chính
          AND  cd.MaICD IS NOT NULL
          AND  LEFT(UPPER(LTRIM(RTRIM(cd.MaICD))), 3) LIKE '[A-Z][0-9][0-9]'
          AND  bn.Tinh IS NOT NULL
    ),
    ca_thang AS (           -- số ca theo tháng × mã ICD × tỉnh
        SELECT FORMAT(ngay_kham, 'MM/yyyy')  AS month,
               disease_code,
               MAX(disease_name)             AS disease_name,
               region,
               COUNT(DISTINCT encounter_id)  AS cases
        FROM   ca
        GROUP BY FORMAT(ngay_kham, 'MM/yyyy'), disease_code, region
    ),
    vt_thang AS (           -- lượng vật tư theo tháng × mã ICD × tỉnh × vật tư
        SELECT FORMAT(c.ngay_kham, 'MM/yyyy') AS month,
               c.disease_code,
               c.region,
               vt.MaVatTu            AS supply_code,
               MAX(vt.TenVatTu)      AS supply_name,
               SUM(sd.SoLuong)       AS supply_quantity,
               MAX(vt.DonVi)         AS supply_unit,
               MAX(vt.NhomVatTu)     AS supply_category
        FROM   ca c
        JOIN   stg.SuDungVatTu sd ON sd.KhamBenhId = c.encounter_id
        JOIN   stg.VatTu       vt ON vt.VatTuId    = sd.VatTuId
        WHERE  vt.MaVatTu IS NOT NULL
        GROUP BY FORMAT(c.ngay_kham, 'MM/yyyy'), c.disease_code, c.region, vt.MaVatTu
    )
    SELECT  ct.month,
            ct.disease_code,
            ct.disease_name,
            ct.region,
            ct.cases,                    -- lặp trên mọi dòng vật tư: đúng hợp đồng
            vt.supply_code,
            vt.supply_name,
            vt.supply_quantity,
            vt.supply_unit,
            vt.supply_category,
            CAST(NULL AS nvarchar(50))   AS note
    FROM      ca_thang ct
    LEFT JOIN vt_thang vt
           ON vt.month        = ct.month
          AND vt.disease_code = ct.disease_code
          AND vt.region       = ct.region
);
GO

/* =============================================================================
   VIEW TỒN KHO — đúng 8 cột theo hợp đồng INV_COLUMNS
============================================================================= */
CREATE OR ALTER VIEW dbo.vw_MedForecast_TonKho
AS
SELECT  vt.MaVatTu             AS supply_code,
        vt.MaThuoc             AS drug_code,
        vt.HoatChat            AS ten_hoat_chat,
        vt.DonVi               AS unit,
        vt.NhomVatTu           AS group_name,
        vt.LoaiVatTu           AS category,
        SUM(tk.SoLuongTon)     AS stock_quantity,
        MAX(vt.MoTa)           AS description
FROM    stg.TonKho tk
JOIN    stg.VatTu  vt ON vt.VatTuId = tk.VatTuId
WHERE   ISNULL(vt.TrangThai, 1) = 1
GROUP BY vt.MaVatTu, vt.MaThuoc, vt.HoatChat, vt.DonVi, vt.NhomVatTu, vt.LoaiVatTu;
GO

/* =============================================================================
   QUYỀN CHO TÀI KHOẢN MEDFORECAST
   Chỉ cấp quyền trên hàm và view — không cấp trên bảng stg.*
============================================================================= */
/* ⚙ Đổi tên login/user cho khớp
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'medforecast_app')
    CREATE USER medforecast_app FOR LOGIN medforecast_app;
GRANT SELECT ON dbo.fn_MedForecast_CaBenh TO medforecast_app;
GRANT SELECT ON dbo.vw_MedForecast_TonKho TO medforecast_app;
*/

/* --- Thử --------------------------------------------------------------- */
SELECT TOP 20 * FROM dbo.fn_MedForecast_CaBenh('2026-01-01');
SELECT TOP 20 * FROM dbo.vw_MedForecast_TonKho;
