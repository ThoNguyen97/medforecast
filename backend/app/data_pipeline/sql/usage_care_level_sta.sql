/* Tiêu hao theo (tháng × nhóm ICD × rổ chăm sóc × vật tư), là tử số của định mức.
   Nguồn: STA · vw_MedForecast_TieuHaoPhanCap

   Định mức = so_luong / cases(nhóm, rổ). Dùng số lượng, không dùng số dòng toa:
   số dòng/lượt và số đơn vị/dòng biến thiên ngược chiều giữa ngoại trú và nội trú.

   is_vtyt = 1: y lệnh vật tư không mang phân cấp chăm sóc, tầng sau phải
   gộp NT1+NT2+NT3+NT0 trước khi chia. */
SELECT  Period,
        [month],
        disease_group,
        ro,
        supply_code,
        supply_name,
        supply_unit,
        supply_category,
        note,
        is_vtyt,
        so_luong,
        so_dong_toa
FROM    dbo.vw_MedForecast_TieuHaoPhanCap
WHERE   Period >= :since_date
ORDER BY Period, disease_group, ro, supply_code;
