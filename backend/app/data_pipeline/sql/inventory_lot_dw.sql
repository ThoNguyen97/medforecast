/* inventory_lot_dw.sql (view vw_MedForecast_TonKhoLo_MoiNhat): tồn kho theo lô kèm hạn dùng, nền của FEFO.
   Ảnh chụp tại NgaySnapshot mới nhất, không nạp tăng dần.
   Giữ dòng lot_id = 0 (không tra được lô), bỏ thì sinh cảnh báo thiếu hụt sai.
   Dùng `co_han_dung` để biết mã tính được FEFO, không suy từ `expiry_date IS NULL`. */
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
