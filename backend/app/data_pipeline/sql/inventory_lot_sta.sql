/* Tồn kho TÁCH THEO LÔ kèm hạn dùng — nền của FEFO.
   Nguồn: STA · MEDFORECAST_DW · vw_MedForecast_TonKhoLo_MoiNhat
   Do usp_MedForecast_DayKhoCungUng (HIS PROD) nạp lên.

   -----------------------------------------------------------------------------
   VÌ SAO LUỒNG NÀY KHÔNG CÓ :since_date

   Ba luồng kia là dữ liệu THEO KỲ (mỗi tháng một lát), nạp tăng dần được.
   Luồng này là ẢNH CHỤP TỒN KHO tại một thời điểm — không có khái niệm "kỳ",
   và view đã tự lọc về đúng NgaySnapshot mới nhất. Nạp tăng dần vô nghĩa:
   ảnh chụp cũ không còn giá trị khi đã có ảnh mới.

   -----------------------------------------------------------------------------
   VÌ SAO GIỮ CẢ DÒNG KHÔNG TRA ĐƯỢC LÔ

   `lot_id = 0` là dòng tồn có SOLONHAP_ID NULL bên HIS — không tra được lô.
   PHẢI giữ: nếu lọc bỏ thì tổng tồn theo lô nhỏ hơn tổng tồn thật, và người
   dùng sẽ thấy "hụt hàng" ở những mã hoàn toàn đủ hàng.

   Cột `co_han_dung` cho phép giao diện và module FEFO nói thật: mã nào tính
   được FEFO, mã nào chỉ có tổng tồn. Đừng suy ra từ `expiry_date IS NULL` —
   một lô có thể có hạn dùng ghi sai định dạng. */
SELECT  NgaySnapshot,
        supply_code,
        lot_id,
        lot_code,
        expiry_date,
        co_han_dung,
        quantity,
        so_kho,
        don_gia_mua,
        don_gia_thau,
        don_gia_von
FROM    dbo.vw_MedForecast_TonKhoLo_MoiNhat
ORDER BY supply_code, expiry_date;
