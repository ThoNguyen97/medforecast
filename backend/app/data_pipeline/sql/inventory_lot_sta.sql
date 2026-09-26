/* Tồn kho tách theo lô kèm hạn dùng, là nền của FEFO.
   Nguồn: STA · MEDFORECAST_DW · vw_MedForecast_TonKhoLo_MoiNhat (do usp_MedForecast_DayKhoCungUng nạp).

   Không có :since_date: đây là ảnh chụp tồn kho tại một thời điểm, view đã tự lọc về
   NgaySnapshot mới nhất nên không nạp tăng dần.

   `lot_id = 0` là dòng tồn có SOLONHAP_ID NULL bên HIS (không tra được lô). Phải giữ,
   nếu bỏ thì tổng tồn theo lô nhỏ hơn tồn thật và sinh cảnh báo thiếu hụt sai.
   Dùng cột `co_han_dung` để biết mã nào tính được FEFO; không suy từ `expiry_date IS NULL`
   vì hạn dùng có thể bị ghi sai định dạng. */
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
