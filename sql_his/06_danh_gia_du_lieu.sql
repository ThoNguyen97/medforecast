/* =============================================================================
   06 — ĐÁNH GIÁ CHUỖI DỮ LIỆU TRƯỚC KHI HUẤN LUYỆN
   =============================================================================
   Mục 1–5 chạy trên STA (MEDFORECAST_DW). Mục 6 chạy trên PROD.

   VÌ SAO CÓ FILE NÀY
   Script 05 trả lời "dữ liệu có đúng không". File này trả lời câu khác, khó hơn:
   "chuỗi này có HỌC ĐƯỢC không".

   Dữ liệu sạch mà chuỗi có đứt gãy cấu trúc thì mô hình vẫn ra số — chỉ là số
   sai, và sai một cách thuyết phục. Ba thứ giết mô hình chuỗi thời gian mà
   không báo lỗi:
     • mã bệnh mới xuất hiện giữa chừng (đổi cách mã hoá, mở khoa mới)
     • mức nền dịch chuyển hẳn (bệnh viện tăng quy mô, đổi phân tuyến)
     • tháng khuyết bị hiểu nhầm thành "tháng không có ca"

   Chạy đủ 6 mục rồi mới quyết định cắt lịch sử từ đâu.
============================================================================= */

USE MEDFORECAST_DW;
GO

/* =============================================================================
   1 — MA TRẬN NĂM × MÃ BỆNH: từng mã xuất hiện từ khi nào?
   -----------------------------------------------------------------------------
   Ô trống hoặc 0 ở các năm đầu rồi bật lên ở năm sau = mã đó KHÔNG PHẢI mới có
   bệnh, mà là mới được mã hoá. Đưa cả chuỗi vào mô hình sẽ học ra một "xu hướng
   tăng" hoàn toàn giả.

   Cách đọc: nhìn dòng J18. Nếu 2019–2022 nhỏ mà 2024–2026 lớn gấp nhiều lần,
   phải xác minh với phòng KHTH xem có đổi quy ước mã hoá không.
============================================================================= */
;WITH g AS (
    SELECT YEAR(Period) AS Nam, disease_group, disease_code, Period, region,
           MAX(cases) AS cases
    FROM   dbo.MF_CaBenh_VatTu
    GROUP BY YEAR(Period), disease_group, disease_code, Period, region
)
SELECT disease_group, disease_code,
       SUM(CASE WHEN Nam = 2019 THEN cases ELSE 0 END) AS [2019],
       SUM(CASE WHEN Nam = 2020 THEN cases ELSE 0 END) AS [2020],
       SUM(CASE WHEN Nam = 2021 THEN cases ELSE 0 END) AS [2021],
       SUM(CASE WHEN Nam = 2022 THEN cases ELSE 0 END) AS [2022],
       SUM(CASE WHEN Nam = 2023 THEN cases ELSE 0 END) AS [2023],
       SUM(CASE WHEN Nam = 2024 THEN cases ELSE 0 END) AS [2024],
       SUM(CASE WHEN Nam = 2025 THEN cases ELSE 0 END) AS [2025],
       SUM(CASE WHEN Nam = 2026 THEN cases ELSE 0 END) AS [2026_den_nay],
       SUM(cases)                                      AS TongCong,
       MIN(Period)                                     AS ThangDauTien
FROM   g
GROUP BY disease_group, disease_code
ORDER BY disease_group, TongCong DESC;

/* =============================================================================
   2 — CHUỖI THEO NHÓM, THEO NĂM (con số mô hình thật sự học)
   -----------------------------------------------------------------------------
   Lấy từ MF_CaBenh_Nhom, dòng TOAN_QUOC — đã đếm DISTINCT đúng ở mức nhóm.
   Cột TangSoVoiNamTruoc là thứ cần nhìn: nhảy trên 50% là phải giải thích được
   bằng sự kiện có thật, không thì đó là đứt gãy dữ liệu.

   Lưu ý 2026 chưa đủ năm — đừng so trực tiếp với các năm trước.
============================================================================= */
;WITH n AS (
    SELECT YEAR(Period) AS Nam, disease_group,
           SUM(cases)            AS TongCa,
           COUNT(DISTINCT Period) AS SoThang
    FROM   dbo.MF_CaBenh_Nhom
    WHERE  region = N'TOAN_QUOC'
    GROUP BY YEAR(Period), disease_group
)
SELECT n.disease_group, n.Nam, n.SoThang, n.TongCa,
       CAST(1.0 * n.TongCa / NULLIF(n.SoThang, 0) AS decimal(10,1)) AS CaMoiThang,
       CAST(100.0 * (1.0 * n.TongCa / NULLIF(n.SoThang, 0))
            / NULLIF(1.0 * p.TongCa / NULLIF(p.SoThang, 0), 0) - 100
            AS decimal(10,1)) AS TangSoVoiNamTruoc_PhanTram
FROM   n
LEFT JOIN n p ON p.disease_group = n.disease_group AND p.Nam = n.Nam - 1
ORDER BY n.disease_group, n.Nam;

/* =============================================================================
   3 — THÁNG KHUYẾT: chuỗi có bị đứt không?
   -----------------------------------------------------------------------------
   Tháng không có dòng nào KHÁC HẲN tháng có 0 ca. Mô hình đọc chuỗi thiếu tháng
   sẽ hiểu sai chu kỳ mùa vụ. Câu này phải ra 0 dòng (trừ các tháng thật sự
   trước khi bệnh viện chạy HIS).
============================================================================= */
;WITH lich AS (
    SELECT MIN(Period) AS TuThang, MAX(Period) AS DenThang FROM dbo.MF_CaBenh_Nhom
), chuoi AS (
    SELECT TuThang AS Thang FROM lich
    UNION ALL
    SELECT DATEADD(MONTH, 1, c.Thang)
    FROM   chuoi c CROSS JOIN lich l
    WHERE  DATEADD(MONTH, 1, c.Thang) <= l.DenThang
), nhom AS (
    SELECT DISTINCT disease_group FROM dbo.MF_CaBenh_Nhom
)
SELECT n.disease_group, c.Thang AS ThangKhuyet
FROM   chuoi c CROSS JOIN nhom n
WHERE  NOT EXISTS (SELECT 1 FROM dbo.MF_CaBenh_Nhom k
                   WHERE k.Period = c.Thang AND k.disease_group = n.disease_group
                     AND k.region = N'TOAN_QUOC')
ORDER BY n.disease_group, c.Thang
OPTION (MAXRECURSION 400);

/* =============================================================================
   4 — MÙA VỤ: tháng nào trong năm cao điểm?
   -----------------------------------------------------------------------------
   Đề tài đặt giả thiết bệnh hô hấp biến động theo mùa. Đây là chỗ kiểm chứng
   giả thiết đó bằng số, trước khi bảo SARIMAX đi tìm chu kỳ 12 tháng.
   Nếu chỉ số dao động quanh 100 ở mọi tháng thì KHÔNG có mùa vụ, và phải nói
   thẳng điều đó trong báo cáo thay vì ép mô hình mùa vụ vào.

   Loại năm 2020–2021 (COVID) vì cấu trúc bệnh thời kỳ đó khác hẳn.
============================================================================= */
;WITH n AS (
    SELECT disease_group, MONTH(Period) AS ThangTrongNam, YEAR(Period) AS Nam,
           SUM(cases) AS cases
    FROM   dbo.MF_CaBenh_Nhom
    WHERE  region = N'TOAN_QUOC' AND YEAR(Period) NOT IN (2020, 2021)
    GROUP BY disease_group, MONTH(Period), YEAR(Period)
), tb AS (
    SELECT disease_group, AVG(1.0 * cases) AS TrungBinhChung FROM n GROUP BY disease_group
)
SELECT n.disease_group, n.ThangTrongNam,
       COUNT(*)                                  AS SoNamQuanSat,
       CAST(AVG(1.0 * n.cases) AS decimal(10,1)) AS CaTrungBinh,
       CAST(100.0 * AVG(1.0 * n.cases) / NULLIF(MAX(tb.TrungBinhChung), 0)
            AS decimal(10,1))                    AS ChiSoMuaVu   -- 100 = mức trung bình
FROM   n JOIN tb ON tb.disease_group = n.disease_group
GROUP BY n.disease_group, n.ThangTrongNam
ORDER BY n.disease_group, n.ThangTrongNam;

/* =============================================================================
   4b — MÙA VỤ, BẢN CHẶT CHẼ: chỉ dùng NĂM TRỌN VẸN
   -----------------------------------------------------------------------------
   Mục 4 có một khiếm khuyết: năm hiện tại mới có 8 tháng, nên T1–T8 được tính
   trên 6 năm còn T9–T12 chỉ trên 5 năm. Hai cột số không cùng mẫu số. Nếu mức
   nền năm hiện tại lệch nhiều so với trung bình thì chỉ số mùa vụ méo theo.

   Câu này chỉ giữ năm có đủ 12 tháng. Kết luận về mùa vụ phải giống mục 4; khác
   nhiều nghĩa là kết luận ở mục 4 đến từ năm dở dang chứ không phải từ mùa vụ.
   Đây là bản nên đưa vào báo cáo.
============================================================================= */
;WITH namdu AS (
    SELECT YEAR(Period) AS Nam
    FROM   dbo.MF_CaBenh_Nhom
    WHERE  region = N'TOAN_QUOC'
    GROUP BY YEAR(Period)
    HAVING COUNT(DISTINCT Period) = 12
), n AS (
    SELECT k.disease_group, MONTH(k.Period) AS ThangTrongNam, YEAR(k.Period) AS Nam,
           SUM(k.cases) AS cases
    FROM   dbo.MF_CaBenh_Nhom k
    JOIN   namdu d ON d.Nam = YEAR(k.Period)
    WHERE  k.region = N'TOAN_QUOC' AND YEAR(k.Period) NOT IN (2020, 2021)
    GROUP BY k.disease_group, MONTH(k.Period), YEAR(k.Period)
), tb AS (
    SELECT disease_group, AVG(1.0 * cases) AS TrungBinhChung FROM n GROUP BY disease_group
)
SELECT n.disease_group, n.ThangTrongNam,
       COUNT(*)                                  AS SoNamQuanSat,   -- phải bằng nhau ở mọi tháng
       CAST(AVG(1.0 * n.cases) AS decimal(10,1)) AS CaTrungBinh,
       CAST(100.0 * AVG(1.0 * n.cases) / NULLIF(MAX(tb.TrungBinhChung), 0)
            AS decimal(10,1))                    AS ChiSoMuaVu
FROM   n JOIN tb ON tb.disease_group = n.disease_group
GROUP BY n.disease_group, n.ThangTrongNam
ORDER BY n.disease_group, n.ThangTrongNam;

/* =============================================================================
   5 — GIAI ĐOẠN COVID: có cần cờ riêng / cắt bỏ không?
============================================================================= */
SELECT disease_group,
       SUM(CASE WHEN YEAR(Period) BETWEEN 2020 AND 2021 THEN cases ELSE 0 END) AS Ca_2020_2021,
       COUNT(DISTINCT CASE WHEN YEAR(Period) BETWEEN 2020 AND 2021 THEN Period END) AS SoThang_Covid,
       SUM(CASE WHEN YEAR(Period) NOT IN (2020, 2021) THEN cases ELSE 0 END) AS Ca_ConLai,
       COUNT(DISTINCT CASE WHEN YEAR(Period) NOT IN (2020, 2021) THEN Period END) AS SoThang_ConLai
FROM   dbo.MF_CaBenh_Nhom
WHERE  region = N'TOAN_QUOC'
GROUP BY disease_group
ORDER BY disease_group;

/* =============================================================================
   6 — MẪU SỐ (chạy trên PROD, không phải STA)
   -----------------------------------------------------------------------------
   Câu hỏi: số ca hô hấp tăng vì BỆNH tăng, hay vì BỆNH VIỆN đông lên?
   Hai chuyện khác nhau hoàn toàn về mặt dự báo. Nếu tỷ lệ hô hấp / tổng lượt
   khám giữ nguyên qua các năm thì phần tăng chỉ là quy mô bệnh viện — và lúc đó
   biến giải thích tốt nhất không phải thời tiết mà là công suất bệnh viện.

   Chạy trên HIS PROD:

   SELECT YEAR(NGAYTIEPNHAN) AS Nam,
          COUNT(*)                        AS TongLuotTiepNhan,
          COUNT(DISTINCT BENHNHAN_ID)     AS SoBenhNhanKhacNhau
   FROM   TT_TIEPNHAN
   WHERE  NGAYTIEPNHAN >= '2019-01-01'
   GROUP BY YEAR(NGAYTIEPNHAN)
   ORDER BY Nam;

   Rồi lấy cột TongCa của mục 2 chia cho TongLuotTiepNhan cùng năm.
============================================================================= */

/* =============================================================================
   7 — DỊCH CHUYỂN MỨC NỀN: nên huấn luyện từ năm nào?
   -----------------------------------------------------------------------------
   Đây là câu quyết định cuối cùng trước khi huấn luyện. Chuỗi có mức nền dịch
   chuyển hẳn thì SARIMAX học trên toàn lịch sử sẽ kéo dự báo về mức cũ và dự
   báo hụt liên tục — sai một chiều, không bao giờ tự sửa.

   Cách đọc cột TySo_GanDay_tren_Truoc:
     ~1,0        → mức nền ổn định, dùng được toàn bộ lịch sử
     1,5 – 2,0   → tăng mạnh; giữ lịch sử nhưng phải có thành phần xu hướng
     > 2,0       → ĐỨT GÃY MỨC NỀN; cắt lịch sử, chỉ giữ giai đoạn cùng mức
     < 0,7       → đang giảm; cùng vấn đề, ngược chiều

   Cột SoThangConLai cho biết cắt xong còn bao nhiêu quan sát. Mô hình mùa vụ
   12 tháng cần tối thiểu khoảng 36 tháng (3 chu kỳ) mới ước lượng được.
============================================================================= */
DECLARE @MocGanDay INT = 24;    -- ⚙ số tháng coi là "gần đây"

;WITH t AS (
    SELECT disease_group, Period, cases,
           ROW_NUMBER() OVER (PARTITION BY disease_group ORDER BY Period DESC) AS ThuTuNguoc
    FROM   dbo.MF_CaBenh_Nhom
    WHERE  region = N'TOAN_QUOC'
      AND  Period < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)  -- bỏ tháng dở dang
)
SELECT disease_group,
       CAST(AVG(CASE WHEN ThuTuNguoc <= @MocGanDay THEN 1.0 * cases END) AS decimal(10,1)) AS CaMoiThang_GanDay,
       CAST(AVG(CASE WHEN ThuTuNguoc >  @MocGanDay THEN 1.0 * cases END) AS decimal(10,1)) AS CaMoiThang_TruocDo,
       CAST(AVG(CASE WHEN ThuTuNguoc <= @MocGanDay THEN 1.0 * cases END)
            / NULLIF(AVG(CASE WHEN ThuTuNguoc > @MocGanDay THEN 1.0 * cases END), 0)
            AS decimal(10,2))                                                              AS TySo_GanDay_tren_Truoc,
       SUM(CASE WHEN ThuTuNguoc <= @MocGanDay THEN 1 ELSE 0 END)                           AS SoThangConLai
FROM   t
GROUP BY disease_group
ORDER BY disease_group;

/* Xem mức nền từng năm cạnh nhau để chọn điểm cắt bằng mắt */
SELECT disease_group,
       CAST(AVG(CASE WHEN YEAR(Period) = 2019 THEN 1.0 * cases END) AS decimal(10,1)) AS [2019],
       CAST(AVG(CASE WHEN YEAR(Period) = 2020 THEN 1.0 * cases END) AS decimal(10,1)) AS [2020],
       CAST(AVG(CASE WHEN YEAR(Period) = 2021 THEN 1.0 * cases END) AS decimal(10,1)) AS [2021],
       CAST(AVG(CASE WHEN YEAR(Period) = 2022 THEN 1.0 * cases END) AS decimal(10,1)) AS [2022],
       CAST(AVG(CASE WHEN YEAR(Period) = 2023 THEN 1.0 * cases END) AS decimal(10,1)) AS [2023],
       CAST(AVG(CASE WHEN YEAR(Period) = 2024 THEN 1.0 * cases END) AS decimal(10,1)) AS [2024],
       CAST(AVG(CASE WHEN YEAR(Period) = 2025 THEN 1.0 * cases END) AS decimal(10,1)) AS [2025],
       CAST(AVG(CASE WHEN YEAR(Period) = 2026 THEN 1.0 * cases END) AS decimal(10,1)) AS [2026]
FROM   dbo.MF_CaBenh_Nhom
WHERE  region = N'TOAN_QUOC'
GROUP BY disease_group
ORDER BY disease_group;

