USE GIAAN115_HIS
GO

/* ═════════════════════════════════════════════════════════════════════════
   G2_04 — Sửa phân loại "Dịch truyền" trong #DrugMeta của usp_MedForecast_DayDuLieu
   (13/09/2026)

   Đo trên medforecast.db: 3.001/5.051 mã mang category = N'Dịch truyền', trong
   đó 665 mã nhóm "12. THUỐC TIM MẠCH", 441 mã "17. THUỐC ĐƯỜNG TIÊU HÓA",
   232 mã "18. HOCMON…" — rõ ràng không phải dịch truyền. Nhánh CASE hiện có

       OR pld.TENPHANLOAIDUOC LIKE N'%dịch truyền%'

   khớp một phân loại rộng của TM_PHANLOAIDUOC (kiểu "Thuốc, dịch truyền…")
   nên nuốt gần toàn bộ thuốc kê đơn. Cột này nuôi bộ lọc "Danh mục" ở trang
   Cảnh báo và biểu đồ "DOI theo danh mục" ở Tổng quan.

   ĐÃ KIỂM CHỨNG (13/09, trừ ngược từ medical_supplies — group_name chính là
   nd.TENNHOMDUOC, ten_hoat_chat chính là D.TENHOATCHAT):

       vế TENHOATCHAT (natri clorid/glucose/ringer) ...   138 mã
       vế TENNHOMDUOC LIKE '%dịch truyền%'          ...     0 mã  ← vô dụng
       phần dư, chỉ có thể do TENPHANLOAIDUOC       ... 2.863 mã  ← thủ phạm

   Mô phỏng CASE mới trên dữ liệu app: "Dịch truyền" còn 130 mã (thay vì 3.001).
   ĐVT của natri clorid/glucose: Chai 98 · Túi 20 · Lọ 2 (giữ) — Gói 6 · Viên 2
   (loại đúng: gói bù nước uống và viên không phải dịch truyền).

   → KHỐI A giờ là TUỲ CHỌN, chỉ để xem nhãn TENPHANLOAIDUOC cụ thể là gì.
     Có thể đi thẳng vào bước 2.

   Cách chạy:
     1) (tuỳ chọn) KHỐI A — xem TENPHANLOAIDUOC nào đang khớp và kéo bao nhiêu mã.
     2) Trong file G1_00_PROD_store_cabenh_v3.sql (thân usp_MedForecast_DayDuLieu,
        khối #DrugMeta), thay nhánh Dịch truyền như KHỐI B rồi ALTER lại thủ tục.
     3) Chạy KHỐI C (chỉ đọc) — đếm lại phân bố category sau khi sửa.
     4) EXEC dbo.usp_MedForecast_DayDuLieu; rồi Đồng bộ HIS trên ứng dụng.
   ═════════════════════════════════════════════════════════════════════════ */

/* ── KHỐI A (tuỳ chọn) — chỉ đọc: phân loại nào đang khớp '%dịch truyền%' ── */
SELECT pld.PHANLOAIDUOC, pld.TENPHANLOAIDUOC, COUNT(*) AS SoMa
FROM   TM_DUOC D
JOIN   TM_LOAIDUOC ld ON ld.LOAIDUOC_ID = D.LOAIDUOC_ID
LEFT JOIN TM_PHANLOAIDUOC pld ON pld.PHANLOAIDUOC = D.PHANLOAIDUOC
WHERE  ld.LOAIVATTU_ID = 'T'
  AND  pld.TENPHANLOAIDUOC LIKE N'%dịch truyền%'
GROUP BY pld.PHANLOAIDUOC, pld.TENPHANLOAIDUOC
ORDER BY SoMa DESC;

SELECT nd.TENNHOMDUOC, COUNT(*) AS SoMa
FROM   TM_DUOC D
JOIN   TM_LOAIDUOC ld ON ld.LOAIDUOC_ID = D.LOAIDUOC_ID
LEFT JOIN TM_NHOMDUOC nd ON nd.NHOMDUOC_ID = D.NHOMDUOC_ID
WHERE  ld.LOAIVATTU_ID = 'T'
  AND  nd.TENNHOMDUOC LIKE N'%dịch truyền%'
GROUP BY nd.TENNHOMDUOC
ORDER BY SoMa DESC;
GO

/* ── KHỐI B — nhánh CASE thay thế trong #DrugMeta (usp_MedForecast_DayDuLieu) ─
   Thay ĐÚNG nhánh:

       WHEN D.TENHOATCHAT LIKE N'%natri clorid%' OR D.TENHOATCHAT LIKE N'%glucose%' OR D.TENHOATCHAT LIKE N'%ringer%'
         OR nd.TENNHOMDUOC LIKE N'%dịch truyền%' OR pld.TENPHANLOAIDUOC LIKE N'%dịch truyền%' THEN N'Dịch truyền'

   bằng:

       WHEN nd.TENNHOMDUOC LIKE N'%dịch truyền%'
         OR nd.TENNHOMDUOC LIKE N'%dung dịch điều chỉnh nước%'          -- nhóm 26 của DMT BHYT
         OR (D.TENHOATCHAT LIKE N'%natri clorid%'  AND dvt.TENDONVITINH IN (N'Chai', N'Túi', N'Lọ'))
         OR (D.TENHOATCHAT LIKE N'%glucose%'       AND dvt.TENDONVITINH IN (N'Chai', N'Túi', N'Lọ'))
         OR  D.TENHOATCHAT LIKE N'%ringer%'
         THEN N'Dịch truyền'

   Lý do: bỏ hẳn TENPHANLOAIDUOC (phân loại quá rộng); natri clorid/glucose
   chỉ tính dịch truyền khi đóng chai/túi (viên/ống nhỏ mắt/ống tiêm không phải).
   Điều kiện ĐVT lấy từ TM_DONVITINH đã JOIN sẵn trong #DrugMeta (alias dvt).
   ───────────────────────────────────────────────────────────────────────── */

/* ── KHỐI C — chỉ đọc: phân bố category sau khi ALTER thủ tục (chạy tạm CASE
   mới ngoài thủ tục để so trước/sau mà chưa cần đẩy STA) ──────────────── */
SELECT CASE
         WHEN nd.TENNHOMDUOC LIKE N'%kháng sinh%' OR pld.TENPHANLOAIDUOC LIKE N'%kháng sinh%' THEN N'Kháng sinh'
         WHEN D.TENHOATCHAT LIKE N'%paracetamol%' OR D.TENHOATCHAT LIKE N'%ibuprofen%' OR D.TENHOATCHAT LIKE N'%diclofenac%'
           OR nd.TENNHOMDUOC LIKE N'%hạ sốt%' OR nd.TENNHOMDUOC LIKE N'%giảm đau%' OR pld.TENPHANLOAIDUOC LIKE N'%giảm đau%' THEN N'Thuốc hạ sốt giảm đau'
         WHEN D.TENHOATCHAT LIKE N'%acetylcystein%' OR D.TENHOATCHAT LIKE N'%ambroxol%' OR D.TENHOATCHAT LIKE N'%bromhexin%'
           OR D.TENHOATCHAT LIKE N'%carbocistein%' OR nd.TENNHOMDUOC LIKE N'%long đờm%' OR nd.TENNHOMDUOC LIKE N'%tiêu nhầy%' THEN N'Thuốc long đờm'
         WHEN D.TENHOATCHAT LIKE N'%fexofenadin%' OR D.TENHOATCHAT LIKE N'%loratadin%' OR D.TENHOATCHAT LIKE N'%cetirizin%'
           OR D.TENHOATCHAT LIKE N'%chlorpheniramin%' OR nd.TENNHOMDUOC LIKE N'%kháng histamin%' OR nd.TENNHOMDUOC LIKE N'%dị ứng%' THEN N'Kháng histamin'
         WHEN D.TENHOATCHAT LIKE N'%salbutamol%' OR D.TENHOATCHAT LIKE N'%theophyllin%' OR D.TENHOATCHAT LIKE N'%ipratropium%'
           OR D.TENHOATCHAT LIKE N'%formoterol%' OR D.TENHOATCHAT LIKE N'%budesonid%' OR nd.TENNHOMDUOC LIKE N'%giãn phế quản%' THEN N'Thuốc giãn phế quản'
         WHEN D.TENHOATCHAT LIKE N'%prednison%' OR D.TENHOATCHAT LIKE N'%prednisolon%' OR D.TENHOATCHAT LIKE N'%methylprednisolon%'
           OR D.TENHOATCHAT LIKE N'%dexamethason%' OR D.TENHOATCHAT LIKE N'%hydrocortison%'
           OR nd.TENNHOMDUOC LIKE N'%corticoid%' OR pld.TENPHANLOAIDUOC LIKE N'%corticoid%' THEN N'Corticoid'
         WHEN nd.TENNHOMDUOC LIKE N'%dịch truyền%'
           OR nd.TENNHOMDUOC LIKE N'%dung dịch điều chỉnh nước%'
           OR (D.TENHOATCHAT LIKE N'%natri clorid%' AND dvt.TENDONVITINH IN (N'Chai', N'Túi', N'Lọ'))
           OR (D.TENHOATCHAT LIKE N'%glucose%'      AND dvt.TENDONVITINH IN (N'Chai', N'Túi', N'Lọ'))
           OR  D.TENHOATCHAT LIKE N'%ringer%' THEN N'Dịch truyền'
         ELSE N'Khác'
       END AS NoteCategory,
       COUNT(*) AS SoMa
FROM   TM_DUOC D
JOIN   TM_LOAIDUOC ld ON ld.LOAIDUOC_ID = D.LOAIDUOC_ID
LEFT JOIN TM_DONVITINH    dvt ON dvt.DONVITINH_ID = D.DONVITINH_ID
LEFT JOIN TM_PHANLOAIDUOC pld ON pld.PHANLOAIDUOC = D.PHANLOAIDUOC
LEFT JOIN TM_NHOMDUOC     nd  ON nd.NHOMDUOC_ID   = D.NHOMDUOC_ID
WHERE  ld.LOAIVATTU_ID = 'T'
  AND  D.MADUOC IS NOT NULL AND LTRIM(RTRIM(D.MADUOC)) <> ''
GROUP BY CASE
         WHEN nd.TENNHOMDUOC LIKE N'%kháng sinh%' OR pld.TENPHANLOAIDUOC LIKE N'%kháng sinh%' THEN N'Kháng sinh'
         WHEN D.TENHOATCHAT LIKE N'%paracetamol%' OR D.TENHOATCHAT LIKE N'%ibuprofen%' OR D.TENHOATCHAT LIKE N'%diclofenac%'
           OR nd.TENNHOMDUOC LIKE N'%hạ sốt%' OR nd.TENNHOMDUOC LIKE N'%giảm đau%' OR pld.TENPHANLOAIDUOC LIKE N'%giảm đau%' THEN N'Thuốc hạ sốt giảm đau'
         WHEN D.TENHOATCHAT LIKE N'%acetylcystein%' OR D.TENHOATCHAT LIKE N'%ambroxol%' OR D.TENHOATCHAT LIKE N'%bromhexin%'
           OR D.TENHOATCHAT LIKE N'%carbocistein%' OR nd.TENNHOMDUOC LIKE N'%long đờm%' OR nd.TENNHOMDUOC LIKE N'%tiêu nhầy%' THEN N'Thuốc long đờm'
         WHEN D.TENHOATCHAT LIKE N'%fexofenadin%' OR D.TENHOATCHAT LIKE N'%loratadin%' OR D.TENHOATCHAT LIKE N'%cetirizin%'
           OR D.TENHOATCHAT LIKE N'%chlorpheniramin%' OR nd.TENNHOMDUOC LIKE N'%kháng histamin%' OR nd.TENNHOMDUOC LIKE N'%dị ứng%' THEN N'Kháng histamin'
         WHEN D.TENHOATCHAT LIKE N'%salbutamol%' OR D.TENHOATCHAT LIKE N'%theophyllin%' OR D.TENHOATCHAT LIKE N'%ipratropium%'
           OR D.TENHOATCHAT LIKE N'%formoterol%' OR D.TENHOATCHAT LIKE N'%budesonid%' OR nd.TENNHOMDUOC LIKE N'%giãn phế quản%' THEN N'Thuốc giãn phế quản'
         WHEN D.TENHOATCHAT LIKE N'%prednison%' OR D.TENHOATCHAT LIKE N'%prednisolon%' OR D.TENHOATCHAT LIKE N'%methylprednisolon%'
           OR D.TENHOATCHAT LIKE N'%dexamethason%' OR D.TENHOATCHAT LIKE N'%hydrocortison%'
           OR nd.TENNHOMDUOC LIKE N'%corticoid%' OR pld.TENPHANLOAIDUOC LIKE N'%corticoid%' THEN N'Corticoid'
         WHEN nd.TENNHOMDUOC LIKE N'%dịch truyền%'
           OR nd.TENNHOMDUOC LIKE N'%dung dịch điều chỉnh nước%'
           OR (D.TENHOATCHAT LIKE N'%natri clorid%' AND dvt.TENDONVITINH IN (N'Chai', N'Túi', N'Lọ'))
           OR (D.TENHOATCHAT LIKE N'%glucose%'      AND dvt.TENDONVITINH IN (N'Chai', N'Túi', N'Lọ'))
           OR  D.TENHOATCHAT LIKE N'%ringer%' THEN N'Dịch truyền'
         ELSE N'Khác'
       END
ORDER BY SoMa DESC;
GO
