/* Tiêu hao TOÀN VIỆN theo tháng × vật tư — mẫu số của DOI.
   Nguồn: STA · MEDFORECAST_DW · vw_MedForecast_TieuHaoTong
   Do usp_MedForecast_DayTieuHaoToanVien (HIS PROD) nạp lên.

   KHÔNG lọc theo nhóm bệnh. Tồn kho là của toàn viện nên mẫu số cũng phải là
   toàn viện — đây chính là chỗ bản trước sai, làm DOI bị thổi lên ~7 lần.

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
