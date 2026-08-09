/* =============================================================================
   00 — DÒ SCHEMA HIS PROD
   =============================================================================
   Chạy trên: HIS PROD (hoặc STA nếu đã có bản sao), bằng tài khoản chỉ đọc.
   Mục đích:  tìm đúng tên bảng/cột thật để điền vào file 01_linked_server.sql.
   An toàn:   chỉ đọc metadata và COUNT/MIN/MAX, không sửa gì.

   Xuất kết quả của TỪNG mục ra file (Results to File trong SSMS) rồi gửi lại.
============================================================================= */

/* --- 1. Bảng ứng viên theo từ khoá tên ------------------------------------ */
SELECT  s.name  AS [Schema],
        t.name  AS [Bang],
        p.rows  AS [SoDong]
FROM    sys.tables  t
JOIN    sys.schemas s ON s.schema_id = t.schema_id
JOIN    sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
WHERE   t.name LIKE '%Kham%'    OR t.name LIKE '%Visit%'   OR t.name LIKE '%Encounter%'
     OR t.name LIKE '%ChanDoan%'OR t.name LIKE '%Diagnos%' OR t.name LIKE '%ICD%'
     OR t.name LIKE '%BenhNhan%'OR t.name LIKE '%Patient%'
     OR t.name LIKE '%VatTu%'   OR t.name LIKE '%Thuoc%'   OR t.name LIKE '%Drug%'
     OR t.name LIKE '%Medic%'   OR t.name LIKE '%Supply%'
     OR t.name LIKE '%TonKho%'  OR t.name LIKE '%Stock%'   OR t.name LIKE '%Inventor%'
     OR t.name LIKE '%SuDung%'  OR t.name LIKE '%Usage%'   OR t.name LIKE '%Dispens%'
ORDER BY p.rows DESC;

/* --- 2. Cột của các bảng ứng viên ----------------------------------------- */
SELECT  s.name AS [Schema], t.name AS [Bang], c.column_id AS [STT],
        c.name AS [Cot], ty.name AS [Kieu], c.max_length AS [DoDai],
        c.is_nullable AS [ChoNull]
FROM    sys.columns c
JOIN    sys.tables  t  ON t.object_id = c.object_id
JOIN    sys.schemas s  ON s.schema_id = t.schema_id
JOIN    sys.types   ty ON ty.user_type_id = c.user_type_id
WHERE   t.name IN (
        /* ⚙ ĐIỀN tên bảng tìm được ở mục 1 vào đây rồi chạy lại mục này */
        'KhamBenh', 'ChanDoan', 'BenhNhan', 'VatTu', 'SuDungVatTu', 'TonKho'
)
ORDER BY t.name, c.column_id;

/* --- 3. Khoá ngoại: xác nhận cách các bảng nối với nhau ------------------- */
SELECT  fk.name                       AS [KhoaNgoai],
        OBJECT_NAME(fk.parent_object_id)     AS [BangCon],
        cp.name                       AS [CotCon],
        OBJECT_NAME(fk.referenced_object_id) AS [BangCha],
        cr.name                       AS [CotCha]
FROM    sys.foreign_keys fk
JOIN    sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
JOIN    sys.columns cp ON cp.object_id = fkc.parent_object_id
                      AND cp.column_id = fkc.parent_column_id
JOIN    sys.columns cr ON cr.object_id = fkc.referenced_object_id
                      AND cr.column_id = fkc.referenced_column_id
ORDER BY [BangCha], [BangCon];

/* --- 4. Index trên cột ngày (quyết định truy vấn tăng dần có nhanh không) -- */
SELECT  OBJECT_NAME(i.object_id) AS [Bang], i.name AS [Index],
        c.name AS [Cot], ic.key_ordinal AS [ThuTu]
FROM    sys.indexes i
JOIN    sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN    sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE   c.name LIKE '%Ngay%' OR c.name LIKE '%Date%' OR c.name LIKE '%Time%'
ORDER BY [Bang], i.name, ic.key_ordinal;

/* --- 5. Miền giá trị: khoảng ngày, trạng thái, mã ICD hô hấp -------------- */
/* ⚙ Đổi tên bảng/cột cho khớp kết quả mục 1-2 trước khi chạy 5 câu dưới     */

-- 5a. Khoảng thời gian dữ liệu khám
SELECT MIN(NgayKham) AS [NgaySomNhat], MAX(NgayKham) AS [NgayMoiNhat],
       COUNT(*) AS [TongLuotKham]
FROM   dbo.KhamBenh;

-- 5b. Các giá trị trạng thái lượt khám (để biết lọc cái nào là "đã chốt")
SELECT TrangThai, COUNT(*) AS [SoDong]
FROM   dbo.KhamBenh
GROUP BY TrangThai
ORDER BY [SoDong] DESC;

-- 5c. Định dạng mã ICD đang lưu ('J01' hay 'J01.0' hay 'J010')
SELECT TOP 50 MaICD, COUNT(*) AS [SoDong]
FROM   dbo.ChanDoan
WHERE  MaICD LIKE 'J%'
GROUP BY MaICD
ORDER BY [SoDong] DESC;

-- 5d. Có cột đánh dấu chẩn đoán chính không, giá trị thế nào
SELECT LaChinh, COUNT(*) AS [SoDong]
FROM   dbo.ChanDoan
GROUP BY LaChinh;

-- 5e. Tỉnh/thành lưu bằng TÊN hay bằng MÃ SỐ
SELECT TOP 30 Tinh, COUNT(*) AS [SoDong]
FROM   dbo.BenhNhan
GROUP BY Tinh
ORDER BY [SoDong] DESC;

/* --- 6. Đối chiếu số ca 1 tháng bất kỳ với báo cáo của phòng KHTH ---------
   Con số này PHẢI khớp báo cáo thống kê của bệnh viện. Lệch quá 2% nghĩa là
   điều kiện lọc (TrangThai / LaChinh) chưa đúng — dừng lại, đừng chạy tiếp.   */
SELECT  LEFT(CONVERT(varchar(10), k.NgayKham, 120), 7) AS [Thang],
        cd.MaICD,
        COUNT(DISTINCT k.Id) AS [SoCa]
FROM    dbo.KhamBenh k
JOIN    dbo.ChanDoan cd ON cd.KhamBenhId = k.Id
WHERE   k.NgayKham >= '2026-05-01' AND k.NgayKham < '2026-06-01'
  AND   cd.MaICD LIKE 'J%'
GROUP BY LEFT(CONVERT(varchar(10), k.NgayKham, 120), 7), cd.MaICD
ORDER BY [SoCa] DESC;
