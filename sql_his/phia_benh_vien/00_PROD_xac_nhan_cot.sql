/* =============================================================================
   00 — BỐN THỨ CẦN XÁC NHẬN TRÊN PROD TRƯỚC KHI CHẠY
   =============================================================================
   Chạy trên: HIS PROD, tài khoản chỉ đọc. Chỉ SELECT, không sửa gì.

   Query export gốc của nhóm đã trả lời phần lớn câu hỏi về schema. Còn đúng
   bốn điểm phụ thuộc dữ liệu thật, xác nhận rồi mới chạy script 01 → 04.
============================================================================= */

DECLARE @TuNgay  DATE = '2019-01-01';
DECLARE @DenNgay DATE = CAST(GETDATE() AS DATE);

/* --- 1. DB này có nhiều bệnh viện không? ---------------------------------
   Nếu ra nhiều hơn 1 dòng thì BẮT BUỘC truyền @BENHVIEN_ID vào thủ tục,
   nếu không sẽ gộp cả số liệu bệnh viện khác.                                */
SELECT BENHVIEN_ID, COUNT(*) AS SoLuotTiepNhan
FROM   TT_TIEPNHAN
WHERE  NGAYTIEPNHAN >= DATEADD(YEAR, -1, @DenNgay)
GROUP BY BENHVIEN_ID
ORDER BY SoLuotTiepNhan DESC;

/* --- 2. Suy ra tỉnh có hoạt động tốt không? ------------------------------
   Query gốc có ghi chú: nếu phần lớn ra '(Không xác định)' thì đổi
   xa.MADONVI thành xa.DONVIHANHCHINH_ID trong bước 2 của thủ tục.
   Chạy cả hai cách rồi so tỷ lệ tra được.                                    */
;WITH BN AS (
    SELECT DISTINCT bn.BENHNHAN_ID, bn.XAPHUONG_ID, bn.TINHTHANH_ID, bn.DIACHITHUONGTRU
    FROM   TT_BENHNHAN bn
    JOIN   TT_TIEPNHAN tn ON tn.BENHNHAN_ID = bn.BENHNHAN_ID
    WHERE  tn.NGAYTIEPNHAN >= DATEADD(YEAR, -1, @DenNgay)
      AND  ISNULL(NULLIF(LTRIM(RTRIM(bn.ACTIVE)), ''), '1') <> '0'
)
SELECT
    N'Cách A — xa.MADONVI (đang dùng)' AS CachNoi,
    COUNT(*) AS TongBenhNhan,
    SUM(CASE WHEN tinh.TENDONVI IS NOT NULL THEN 1 ELSE 0 END) AS TraDuocTinh,
    CAST(100.0 * SUM(CASE WHEN tinh.TENDONVI IS NOT NULL THEN 1 ELSE 0 END)
         / NULLIF(COUNT(*), 0) AS decimal(5,1)) AS PhanTram
FROM      BN bn
LEFT JOIN TM_DONVIHANHCHINH xa    ON xa.MADONVI              = bn.XAPHUONG_ID
LEFT JOIN TM_DONVIHANHCHINH huyen ON huyen.DONVIHANHCHINH_ID = xa.CAPTREN_ID
LEFT JOIN TM_DONVIHANHCHINH tinh  ON tinh.DONVIHANHCHINH_ID  =
          ISNULL(CASE WHEN xa.CAPDONVI = 3 THEN xa.CAPTREN_ID ELSE huyen.CAPTREN_ID END,
                 bn.TINHTHANH_ID)
UNION ALL
SELECT
    N'Cách B — xa.DONVIHANHCHINH_ID',
    COUNT(*),
    SUM(CASE WHEN tinh.TENDONVI IS NOT NULL THEN 1 ELSE 0 END),
    CAST(100.0 * SUM(CASE WHEN tinh.TENDONVI IS NOT NULL THEN 1 ELSE 0 END)
         / NULLIF(COUNT(*), 0) AS decimal(5,1))
FROM      BN bn
LEFT JOIN TM_DONVIHANHCHINH xa    ON xa.DONVIHANHCHINH_ID    = bn.XAPHUONG_ID
LEFT JOIN TM_DONVIHANHCHINH huyen ON huyen.DONVIHANHCHINH_ID = xa.CAPTREN_ID
LEFT JOIN TM_DONVIHANHCHINH tinh  ON tinh.DONVIHANHCHINH_ID  =
          ISNULL(CASE WHEN xa.CAPDONVI = 3 THEN xa.CAPTREN_ID ELSE huyen.CAPTREN_ID END,
                 bn.TINHTHANH_ID);

/* --- 3. Mã thuốc: MADUOC có đủ và không trùng không? ---------------------
   Thủ tục dùng D.MADUOC làm supply_code. Nếu MADUOC thiếu nhiều hoặc trùng
   thì cân nhắc đổi sang MADUOCBV (mã riêng của bệnh viện).                   */
SELECT COUNT(*)                                                        AS TongThuoc,
       COUNT(DISTINCT MADUOC)                                          AS MaDuoc_KhacNhau,
       SUM(CASE WHEN MADUOC   IS NULL OR LTRIM(RTRIM(MADUOC))   = '' THEN 1 ELSE 0 END) AS Thieu_MADUOC,
       COUNT(DISTINCT MADUOCBV)                                        AS MaDuocBV_KhacNhau,
       SUM(CASE WHEN MADUOCBV IS NULL OR LTRIM(RTRIM(MADUOCBV)) = '' THEN 1 ELSE 0 END) AS Thieu_MADUOCBV,
       SUM(CASE WHEN MA_BHYT  IS NULL OR LTRIM(RTRIM(MA_BHYT))  = '' THEN 1 ELSE 0 END) AS Thieu_MA_BHYT
FROM   TM_DUOC D
JOIN   TM_LOAIDUOC ld ON ld.LOAIDUOC_ID = D.LOAIDUOC_ID
WHERE  ld.LOAIVATTU_ID = 'T';

-- Mã bị dùng cho nhiều thuốc khác nhau (sẽ làm gộp nhầm khi tổng hợp)
SELECT TOP 20 D.MADUOC, COUNT(*) AS SoThuocTrungMa
FROM   TM_DUOC D
JOIN   TM_LOAIDUOC ld ON ld.LOAIDUOC_ID = D.LOAIDUOC_ID
WHERE  ld.LOAIVATTU_ID = 'T' AND D.MADUOC IS NOT NULL
GROUP BY D.MADUOC
HAVING COUNT(*) > 1
ORDER BY SoThuocTrungMa DESC;

/* --- 4. Đối chiếu số ca với báo cáo phòng KHTH ---------------------------
   Con số theo TỪNG MÃ BỆNH phải khớp thống kê của bệnh viện. Lệch quá 2% thì
   dừng lại. Lưu ý: KHÔNG cộng dồn 4 mã — một lượt khám có thể mang nhiều mã
   nên tổng cộng dồn luôn lớn hơn số lượt thật.                               */
;WITH Enc AS (
    SELECT 'NGT' AS Loai, tn.TIEPNHAN_ID,
           DATEFROMPARTS(YEAR(KB.NGAYKHAM), MONTH(KB.NGAYKHAM), 1) AS Thang,
           LEFT(icdc.MAICD, 3) AS Ma
    FROM   TT_TIEPNHAN tn
    JOIN   TT_NGOAITRU_KHAMBENH KB   ON KB.TIEPNHAN_ID = tn.TIEPNHAN_ID
    JOIN   TM_ICD               icdc ON icdc.ICD_ID    = KB.CHANDOANICD_ID
    WHERE  KB.NGAYKHAM >= DATEADD(MONTH, -3, @DenNgay)
      AND  LEFT(icdc.MAICD, 3) IN ('J01','J02','J06','J20')
    UNION ALL
    SELECT 'NT', tn.TIEPNHAN_ID,
           DATEFROMPARTS(YEAR(tn.NGAYTIEPNHAN), MONTH(tn.NGAYTIEPNHAN), 1),
           LEFT(ISNULL(icdc.MAICD, icdBA.MAICD), 3)
    FROM   TT_TIEPNHAN tn
    JOIN   TT_NOITRU_BENHAN   BA    ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
    JOIN   TT_NOITRU_KHAMBENH KB    ON KB.BENHAN_ID   = BA.BENHAN_ID
    LEFT JOIN TM_ICD          icdc  ON icdc.ICD_ID    = KB.ICDCHINH_ID
    LEFT JOIN TM_ICD          icdBA ON icdBA.ICD_ID   = TRY_CAST(BA.ICD_BENHCHINH AS INT)
    WHERE  tn.NGAYTIEPNHAN >= DATEADD(MONTH, -3, @DenNgay)
      AND  LEFT(ISNULL(icdc.MAICD, icdBA.MAICD), 3) IN ('J01','J02','J06','J20')
)
SELECT Thang, Ma, Loai, COUNT(DISTINCT TIEPNHAN_ID) AS SoCa
FROM   Enc
GROUP BY Thang, Ma, Loai
ORDER BY Thang DESC, Ma, Loai;

/* --- 5. TM_ICD.PHANNHOM có dùng được làm nhóm ICD không? -----------------
   Thủ tục lấy phạm vi bệnh theo NHÓM (đề cương: J00-J06, J09-J18, J20-J22)
   dựa hẳn vào cột này. Ba nhóm phải xuất hiện và mỗi mã 3 ký tự chỉ thuộc
   ĐÚNG MỘT nhóm. Câu dưới phải ra đúng 3 dòng.                              */
SELECT LTRIM(RTRIM(PHANNHOM))                     AS Nhom,
       COUNT(DISTINCT LEFT(LTRIM(RTRIM(MAICD)),3)) AS SoMa3KyTu,
       COUNT(*)                                    AS SoDongICD
FROM   TM_ICD
WHERE  LTRIM(RTRIM(PHANNHOM)) IN ('J00-J06','J09-J18','J20-J22')
GROUP BY LTRIM(RTRIM(PHANNHOM))
ORDER BY Nhom;

-- Mã 3 ký tự bị gán vào hai nhóm khác nhau — phải ra 0 dòng
SELECT LEFT(LTRIM(RTRIM(MAICD)),3) AS Ma3, COUNT(DISTINCT LTRIM(RTRIM(PHANNHOM))) AS SoNhom
FROM   TM_ICD
WHERE  LTRIM(RTRIM(PHANNHOM)) IN ('J00-J06','J09-J18','J20-J22')
GROUP BY LEFT(LTRIM(RTRIM(MAICD)),3)
HAVING COUNT(DISTINCT LTRIM(RTRIM(PHANNHOM))) > 1;

/* --- 6. MỞ RỘNG TỪ 4 MÃ LÊN ĐỦ 3 NHÓM ĐƯỢC THÊM BAO NHIÊU CA? ------------
   Query export cũ chỉ lấy J01, J02, J06, J20 — thiếu J00/J03/J04/J05,
   thiếu TRỌN nhóm J09-J18 (cúm và viêm phổi), thiếu J21/J22.
   Câu này đo phần bị bỏ sót, chạy trên toàn bộ lịch sử.

   Cột SoLuot là COUNT(DISTINCT lượt tiếp nhận) — ở mức NHÓM, nên đã khử phần
   một lượt mang nhiều mã trong cùng nhóm. Đừng cộng dồn cột này qua các mã.  */
;WITH Enc2 AS (
    SELECT tn.TIEPNHAN_ID,
           DATEFROMPARTS(YEAR(KB.NGAYKHAM), MONTH(KB.NGAYKHAM), 1) AS Thang,
           LEFT(LTRIM(RTRIM(icdc.MAICD)), 3) AS Ma3,
           LTRIM(RTRIM(icdc.PHANNHOM))       AS Nhom
    FROM   TT_TIEPNHAN tn
    JOIN   TT_NGOAITRU_KHAMBENH KB   ON KB.TIEPNHAN_ID = tn.TIEPNHAN_ID
    JOIN   TM_ICD               icdc ON icdc.ICD_ID    = KB.CHANDOANICD_ID
    WHERE  KB.NGAYKHAM >= @TuNgay
      AND  LTRIM(RTRIM(icdc.PHANNHOM)) IN ('J00-J06','J09-J18','J20-J22')
    UNION ALL
    SELECT tn.TIEPNHAN_ID,
           DATEFROMPARTS(YEAR(tn.NGAYTIEPNHAN), MONTH(tn.NGAYTIEPNHAN), 1),
           LEFT(LTRIM(RTRIM(ISNULL(icdc.MAICD, icdBA.MAICD))), 3),
           LTRIM(RTRIM(ISNULL(icdc.PHANNHOM, icdBA.PHANNHOM)))
    FROM   TT_TIEPNHAN tn
    JOIN   TT_NOITRU_BENHAN   BA   ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
    JOIN   TT_NOITRU_KHAMBENH KB   ON KB.BENHAN_ID   = BA.BENHAN_ID
    LEFT JOIN TM_ICD          icdc ON icdc.ICD_ID    = KB.ICDCHINH_ID
    LEFT JOIN TM_ICD          icdBA ON icdBA.ICD_ID  = TRY_CAST(BA.ICD_BENHCHINH AS INT)
    WHERE  tn.NGAYTIEPNHAN >= @TuNgay
      AND  LTRIM(RTRIM(ISNULL(icdc.PHANNHOM, icdBA.PHANNHOM)))
           IN ('J00-J06','J09-J18','J20-J22')
)
SELECT Nhom,
       Ma3,
       CASE WHEN Ma3 IN ('J01','J02','J06','J20') THEN N'đã có'
            ELSE N'MỚI THÊM' END              AS TinhTrang,
       COUNT(DISTINCT TIEPNHAN_ID)            AS SoLuot,
       COUNT(DISTINCT Thang)                  AS SoThangCoDuLieu
FROM   Enc2
GROUP BY Nhom, Ma3
ORDER BY Nhom, SoLuot DESC;

-- Tổng theo NHÓM (đếm DISTINCT ở mức nhóm — con số mô hình thật sự học)
SELECT Nhom,
       COUNT(DISTINCT TIEPNHAN_ID)  AS SoLuot_MucNhom,
       COUNT(DISTINCT Thang)        AS SoThang,
       CAST(1.0 * COUNT(DISTINCT TIEPNHAN_ID) / NULLIF(COUNT(DISTINCT Thang), 0)
            AS decimal(10,1))       AS TrungBinhMoiThang
FROM   Enc2
GROUP BY Nhom
ORDER BY Nhom;
