/* =============================================================================
   05 — KIỂM TRA SAU KHI ĐỒNG BỘ
   =============================================================================
   Chạy trên: STA, sau mỗi lần chạy job (và bắt buộc ở lần đầu tiên).
============================================================================= */

/* --- 1. Lần chạy gần nhất ------------------------------------------------ */
SELECT TOP 10 Id, BatDau, KetThuc,
       DATEDIFF(SECOND, BatDau, KetThuc) AS [GiaySoVoi],
       TuNgay, SoDongKhamBenh, SoDongChanDoan, SoDongSuDungVatTu,
       SoDongVatTu, SoDongTonKho, TrangThai, ThongDiep
FROM   stg.SyncLog
ORDER BY Id DESC;

/* --- 2. Độ tươi dữ liệu: STA có đang chậm hơn PROD không? ----------------- */
/* Cảnh báo nếu lượt khám mới nhất bên STA cũ hơn 2 ngày.                     */
SELECT  MAX(NgayKham)                        AS [NgayKhamMoiNhat_STA],
        DATEDIFF(DAY, MAX(NgayKham), CAST(SYSDATETIME() AS date)) AS [SoNgayTre],
        CASE WHEN DATEDIFF(DAY, MAX(NgayKham), CAST(SYSDATETIME() AS date)) > 2
             THEN N'⚠ DỮ LIỆU CŨ — kiểm tra job' ELSE N'OK' END AS [DanhGia]
FROM    stg.KhamBenh;

/* --- 3. Đối chiếu số ca STA vs PROD cho 3 tháng gần nhất ------------------
   Hai cột phải BẰNG NHAU. Lệch = job đồng bộ sót dữ liệu.                   */
;WITH sta AS (
    SELECT LEFT(CONVERT(varchar(10), NgayKham, 120), 7) AS Thang, COUNT(*) AS SoLuot
    FROM   stg.KhamBenh
    WHERE  NgayKham >= DATEADD(MONTH, -3, CAST(SYSDATETIME() AS date))
    GROUP BY LEFT(CONVERT(varchar(10), NgayKham, 120), 7)
), prod AS (
    SELECT LEFT(CONVERT(varchar(10), NgayKham, 120), 7) AS Thang, COUNT(*) AS SoLuot
    FROM   src.KhamBenh
    WHERE  NgayKham >= DATEADD(MONTH, -3, CAST(SYSDATETIME() AS date))
    GROUP BY LEFT(CONVERT(varchar(10), NgayKham, 120), 7)
)
SELECT ISNULL(s.Thang, p.Thang) AS Thang,
       p.SoLuot AS [PROD], s.SoLuot AS [STA],
       ISNULL(s.SoLuot, 0) - ISNULL(p.SoLuot, 0) AS [Lech]
FROM   prod p FULL JOIN sta s ON s.Thang = p.Thang
ORDER BY Thang;

/* --- 4. Kết quả hàm tổng hợp: số ca theo nhóm hô hấp ----------------------
   Con số này PHẢI khớp báo cáo thống kê của phòng KHTH.                     */
SELECT  month, disease_code, MAX(cases) AS SoCa
FROM    dbo.fn_MedForecast_CaBenh(DATEADD(MONTH, -6, CAST(SYSDATETIME() AS date)))
WHERE   disease_code LIKE 'J%'
GROUP BY month, disease_code
ORDER BY month DESC, SoCa DESC;

/* --- 5. Chất lượng dữ liệu ----------------------------------------------- */
-- 5a. Lượt khám không tra được tỉnh (sẽ bị tầng sau loại bỏ)
SELECT COUNT(*) AS [LuotKham_ThieuTinh]
FROM   stg.KhamBenh k LEFT JOIN stg.BenhNhan bn ON bn.BenhNhanId = k.BenhNhanId
WHERE  bn.Tinh IS NULL;

-- 5b. Mã ICD sai định dạng (không phải chữ + 2 số)
SELECT TOP 30 MaICD, COUNT(*) AS SoDong
FROM   stg.ChanDoan
WHERE  LEFT(UPPER(LTRIM(RTRIM(MaICD))), 3) NOT LIKE '[A-Z][0-9][0-9]'
GROUP BY MaICD ORDER BY SoDong DESC;

-- 5c. Vật tư dùng nhưng không có trong danh mục (mất tên, mất đơn vị)
SELECT COUNT(*) AS [SuDung_KhongCoTrongDanhMuc]
FROM   stg.SuDungVatTu sd LEFT JOIN stg.VatTu vt ON vt.VatTuId = sd.VatTuId
WHERE  vt.VatTuId IS NULL;

-- 5d. Giá trị tỉnh chưa được ánh xạ (chỉ có ý nghĩa khi HIS lưu mã số)
SELECT TOP 30 bn.Tinh AS [GiaTriChuaAnhXa], COUNT(*) AS SoBenhNhan
FROM   stg.BenhNhan bn LEFT JOIN stg.MapTinh mt ON mt.GiaTriNguon = bn.Tinh
WHERE  mt.GiaTriNguon IS NULL
GROUP BY bn.Tinh ORDER BY SoBenhNhan DESC;

/* --- 6. Kiểm tra chống lỗi "1 ca mỗi tháng" -------------------------------
   Nếu MAX(cases) = 1 cho mọi tháng thì hàm tổng hợp đang đếm sai.           */
SELECT CASE WHEN MAX(cases) <= 1
            THEN N'⚠ SAI: cases luôn = 1, kiểm tra lại COUNT(DISTINCT) trong hàm'
            ELSE N'OK — cases có phân bố hợp lý' END AS [KetLuan],
       MIN(cases) AS [ThapNhat], MAX(cases) AS [CaoNhat], AVG(cases * 1.0) AS [TrungBinh]
FROM   dbo.fn_MedForecast_CaBenh(DATEADD(YEAR, -1, CAST(SYSDATETIME() AS date)));
