/* usage_total_dw.sql (view vw_MedForecast_TieuHaoTong): tiêu hao toàn viện theo tháng × thuốc, mẫu số của DOI.
   Không lọc theo nhóm bệnh vì tồn kho là của toàn viện, lấy riêng hô hấp sẽ thổi phồng DOI.
   Nạp tăng dần theo tham số since_date (ngày 01 của kỳ bắt đầu). */
SELECT  Period,
        [month],
        supply_code,
        supply_name,
        supply_unit,
        is_vtyt,
        so_luong_toan_vien,
        so_luong_hohap,
        d_baseline_thang,
        ty_trong_hohap,
        so_dong_toa,
        so_luot
FROM    dbo.vw_MedForecast_TieuHaoTong
WHERE   Period >= :since_date
ORDER BY Period, supply_code;
