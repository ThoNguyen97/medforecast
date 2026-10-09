/* usage_care_level_dw.sql (view vw_MedForecast_TieuHaoPhanCap): tiêu hao theo (tháng × nhóm ICD × rổ × thuốc), tử số định mức.
   Định mức = so_luong / cases(nhóm, rổ); dùng số lượng vì số dòng toa biến thiên ngược chiều giữa ngoại trú và nội trú.
   is_vtyt = 1 không mang phân cấp chăm sóc, tầng sau gộp NT1+NT2+NT3+NT0 trước khi chia. */
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
