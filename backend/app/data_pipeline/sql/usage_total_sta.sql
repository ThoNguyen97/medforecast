/* Tiêu hao toàn viện theo tháng × vật tư, là mẫu số của DOI.
   Nguồn: STA · MEDFORECAST_DW · vw_MedForecast_TieuHaoTong (do usp_MedForecast_DayTieuHaoToanVien nạp).

   Không lọc theo nhóm bệnh: tồn kho là của toàn viện nên mẫu số cũng phải toàn viện,
   nếu chỉ lấy tiêu hao nhóm hô hấp thì DOI bị thổi phồng.

   :since_date  ngày 01 của kỳ bắt đầu nạp lại (pipeline tự truyền vào). */
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
