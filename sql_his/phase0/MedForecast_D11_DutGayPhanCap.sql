/* =============================================================================
   Đ11 — PHÂN CẤP CHĂM SÓC CÓ ĐỨT GÃY THEO THỜI GIAN KHÔNG?
   =============================================================================
   Chạy trên : HIS PROD — GIAAN115_HIS (SSMS)
   An toàn   : CHỈ ĐỌC. Bảng tạm #..., có DROP trước và sau.
   Thời gian : vài chục giây.

   -----------------------------------------------------------------------------
   VÌ SAO PHẢI ĐO THÊM

   Bảng tỷ trọng phân cấp vừa chạy (`@ChiXem = 1`) cho một dấu hiệu bất thường:

       nhóm      rổ    số ca   số tháng CÓ dữ liệu   mật độ
       J00-J06   NT1     530          85            6,2 ca/tháng
       J00-J06   NT2     350          18           19,4 ca/tháng   ← gấp 3,1×
       J09-J18   NT1   2.323          93           25,0 ca/tháng
       J09-J18   NT2     988          19           52,0 ca/tháng   ← gấp 2,1×
       J20-J22   NT1     340          76            4,5 ca/tháng
       J20-J22   NT2     215          18           11,9 ca/tháng   ← gấp 2,7×

   Cấp 2 xuất hiện ở CHƯA TỚI 1/5 SỐ THÁNG, nhưng trong những tháng đó lại
   DÀY GẤP 2-3 LẦN cấp 1. Nếu chỉ là hiếm gặp thì nó phải thưa đều, không thể
   vừa thưa theo tháng vừa dày trong tháng. Dấu hiệu này chỉ tới một khả năng:
   BỆNH VIỆN ĐỔI CÁCH GHI PHÂN CẤP TẠI MỘT THỜI ĐIỂM.

   HỆ QUẢ NẾU ĐÚNG

   Tỷ trọng p̂(g,c) tính trên toàn bộ 93 kỳ sẽ pha loãng cấp 2 và cấp 3 bằng
   khoảng 75 kỳ mà chúng vốn không được ghi. Dự báo cho tháng tới sẽ ĐÁNH GIÁ
   THẤP số ca nặng vừa — tức là đề xuất thiếu đúng nhóm thuốc đắt tiền nhất.

   Khi đó Tầng 2 phải tính p̂ trên CỬA SỔ CHẾ ĐỘ GHI NHẬN HIỆN TẠI (khoảng 18-24
   kỳ gần nhất), không phải toàn bộ lịch sử. Đây là thay đổi tham số, không phải
   sửa thiết kế — nhưng phải biết mốc đứt gãy nằm ở đâu mới đặt được cửa sổ.

   -----------------------------------------------------------------------------
   ► ĐỌC KẾT QUẢ

   Đ11-A trả về số ca theo NĂM × RỔ. Nhìn cột NT2 và NT3:

     • Bằng 0 suốt nhiều năm rồi nhảy lên từ một năm nào đó
       → ĐỨT GÃY. Lấy năm đó làm mốc, đặt cửa sổ p̂ từ đó trở đi.
     • Rải rác nhỏ đều qua các năm
       → KHÔNG đứt gãy, chỉ là hiếm. Giữ nguyên toàn bộ lịch sử, và dựa vào
         cơ chế co ngót ở G3 để định mức không nhảy vì vài ca.

   Đ11-B cho biết chính xác THÁNG đầu tiên mỗi rổ xuất hiện.
   Đ11-C kiểm tra xem đứt gãy có phải chỉ ở nhóm hô hấp hay toàn viện — nếu toàn
   viện thì đó là đổi quy trình ghi chép, nếu chỉ hô hấp thì đáng ngờ hơn nhiều.
============================================================================= */

USE GIAAN115_HIS;
GO
SET NOCOUNT ON;
GO

DECLARE @BENHVIEN_ID INT = NULL;      -- ⚙ đặt 79428 nếu DB nhiều bệnh viện

IF OBJECT_ID('tempdb..#Icd')  IS NOT NULL DROP TABLE #Icd;
IF OBJECT_ID('tempdb..#Dot')  IS NOT NULL DROP TABLE #Dot;

/* Mã ICD thuộc ba nhóm đích */
SELECT DISTINCT icd.ICD_ID,
       LTRIM(RTRIM(icd.PHANNHOM)) AS Nhom
INTO   #Icd
FROM   TM_ICD icd
WHERE  LTRIM(RTRIM(icd.PHANNHOM)) IN ('J00-J06','J09-J18','J20-J22');
CREATE UNIQUE CLUSTERED INDEX IX_Icd ON #Icd(ICD_ID);

/* Một dòng cho mỗi ĐỢT NỘI TRÚ thuộc nhóm đích, kèm rổ chăm sóc.
   Quy tắc rổ giống hệt thủ tục: cấp = MIN(mã phân cấp) trên các y lệnh của đợt
   (mã nhỏ = nặng hơn). Không có phân cấp nào → NT0.                          */
SELECT
    YEAR(tn.NGAYTIEPNHAN)                                   AS Nam,
    DATEFROMPARTS(YEAR(tn.NGAYTIEPNHAN), MONTH(tn.NGAYTIEPNHAN), 1) AS Thang,
    i.Nhom,
    tn.TIEPNHAN_ID,
    CAST('NT' + CAST(ISNULL(MIN(TRY_CAST(pccs.DICTIONARY_CODE AS INT)), 0)
         AS VARCHAR(1)) AS VARCHAR(4))                      AS Ro
INTO   #Dot
FROM        TT_TIEPNHAN        tn
JOIN        TT_NOITRU_BENHAN   BA   ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
JOIN        TT_NOITRU_KHAMBENH KB   ON KB.BENHAN_ID   = BA.BENHAN_ID
JOIN        #Icd               i    ON i.ICD_ID       = KB.ICDCHINH_ID
LEFT JOIN   LST_DICTIONARY     pccs ON pccs.DICTIONARY_ID        = KB.PHANCAPCHAMSOC_ID
                                   AND pccs.DICTIONARY_TYPE_CODE = 'PhanCapChamSoc'
WHERE  tn.NGAYTIEPNHAN >= '2019-01-01'
  AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
GROUP BY YEAR(tn.NGAYTIEPNHAN),
         DATEFROMPARTS(YEAR(tn.NGAYTIEPNHAN), MONTH(tn.NGAYTIEPNHAN), 1),
         i.Nhom, tn.TIEPNHAN_ID;


-- ── Đ11-A · Số ca nội trú theo NĂM × RỔ (ba nhóm gộp lại) ────────────────────
-- ► NT2/NT3 bằng 0 nhiều năm rồi nhảy lên = ĐỨT GÃY. Ghi lại năm bắt đầu.
SELECT  Nam,
        SUM(CASE WHEN Ro = 'NT1' THEN 1 ELSE 0 END) AS NT1,
        SUM(CASE WHEN Ro = 'NT2' THEN 1 ELSE 0 END) AS NT2,
        SUM(CASE WHEN Ro = 'NT3' THEN 1 ELSE 0 END) AS NT3,
        SUM(CASE WHEN Ro = 'NT0' THEN 1 ELSE 0 END) AS NT0_ChuaGan,
        COUNT(*)                                    AS TongDotNoiTru,
        CAST(100.0 * SUM(CASE WHEN Ro IN ('NT2','NT3') THEN 1 ELSE 0 END)
             / NULLIF(COUNT(*), 0) AS decimal(5,2)) AS TyLe_Cap2va3_PhanTram
FROM    #Dot
GROUP BY Nam
ORDER BY Nam;


-- ── Đ11-B · Tháng đầu và tháng cuối mỗi rổ xuất hiện, theo từng nhóm ────────
-- ► Nếu LanDau của NT2/NT3 muộn hơn NT1 vài năm → mốc đứt gãy chính là đó.
SELECT  Nhom, Ro,
        MIN(Thang)                  AS LanDau,
        MAX(Thang)                  AS LanCuoi,
        COUNT(DISTINCT Thang)       AS SoThangCoDuLieu,
        COUNT(*)                    AS SoDot,
        CAST(1.0 * COUNT(*) / NULLIF(COUNT(DISTINCT Thang), 0)
             AS decimal(10,1))      AS MatDo_CaMoiThang
FROM    #Dot
GROUP BY Nhom, Ro
ORDER BY Nhom, Ro;


-- ── Đ11-C · Cùng phép đo nhưng TOÀN VIỆN, không lọc bệnh ────────────────────
-- ► Nếu toàn viện cũng đứt gãy ở cùng mốc → bệnh viện đổi quy trình ghi chép,
--   đây là sự thật của dữ liệu và chỉ cần chọn cửa sổ cho đúng.
--   Nếu toàn viện liên tục mà riêng nhóm hô hấp đứt → phải tìm nguyên nhân
--   khác trước khi tin vào tỷ trọng p̂.
SELECT  YEAR(tn.NGAYTIEPNHAN) AS Nam,
        SUM(CASE WHEN pccs.DICTIONARY_CODE = '1' THEN 1 ELSE 0 END) AS Cap1,
        SUM(CASE WHEN pccs.DICTIONARY_CODE = '2' THEN 1 ELSE 0 END) AS Cap2,
        SUM(CASE WHEN pccs.DICTIONARY_CODE = '3' THEN 1 ELSE 0 END) AS Cap3,
        SUM(CASE WHEN pccs.DICTIONARY_CODE IS NULL THEN 1 ELSE 0 END) AS ChuaGan,
        COUNT(*)                                                      AS TongYLenh
FROM        TT_TIEPNHAN        tn
JOIN        TT_NOITRU_BENHAN   BA   ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
JOIN        TT_NOITRU_KHAMBENH KB   ON KB.BENHAN_ID   = BA.BENHAN_ID
LEFT JOIN   LST_DICTIONARY     pccs ON pccs.DICTIONARY_ID        = KB.PHANCAPCHAMSOC_ID
                                   AND pccs.DICTIONARY_TYPE_CODE = 'PhanCapChamSoc'
WHERE  tn.NGAYTIEPNHAN >= '2019-01-01'
  AND  KB.ISYLENHVTYT = 0
  AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
GROUP BY YEAR(tn.NGAYTIEPNHAN)
ORDER BY Nam;


-- ── Đ11-D · Nếu CÓ đứt gãy: tỷ trọng p̂ tính trên 18 kỳ gần nhất ────────────
-- ► So con số này với bảng tỷ trọng đã chạy (tính trên 93 kỳ). Chênh lệch
--   chính là mức sai số mà Tầng 2 sẽ mắc phải nếu dùng toàn bộ lịch sử.
SELECT  Nhom, Ro,
        COUNT(*)                                                       AS SoDot,
        CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY Nhom)
             AS decimal(5,2))                                          AS TyTrongNoiTru_18Ky
FROM    #Dot
WHERE   Thang >= DATEADD(MONTH, -18, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
GROUP BY Nhom, Ro
ORDER BY Nhom, Ro;


DROP TABLE #Icd;
DROP TABLE #Dot;
GO

/* =============================================================================
   SAU KHI CHẠY — gửi lại Đ11-A, Đ11-B, Đ11-C, Đ11-D.

   Nếu đứt gãy được xác nhận, thay đổi duy nhất cần làm là thêm một tham số
   cửa sổ cho phép tính p̂ ở Tầng 2 (G3) — không phải sửa thủ tục, không phải
   nạp lại dữ liệu. Toàn bộ lịch sử vẫn giữ để dự báo SỐ CA; chỉ riêng TỶ TRỌNG
   PHÂN CẤP dùng cửa sổ ngắn.
============================================================================= */
