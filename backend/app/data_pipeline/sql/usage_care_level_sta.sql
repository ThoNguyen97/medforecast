/* Tiêu hao theo (tháng × nhóm ICD × rổ chăm sóc × vật tư) — TỬ SỐ của định mức.
   Nguồn: STA · vw_MedForecast_TieuHaoPhanCap

   Định mức = so_luong / cases(nhóm, rổ).  Dùng cột SỐ LƯỢNG, không dùng số
   dòng toa: Đ5 đo được ngoại trú 4,72 dòng/lượt nhưng 18,29 đơn vị/dòng, còn
   nội trú cấp 3 là 16,89 dòng/lượt và 3,33 đơn vị/dòng — hai chiều ngược nhau,
   nên tính theo số dòng sẽ sai hệ thống.

   is_vtyt = 1: y lệnh vật tư KHÔNG mang phân cấp chăm sóc, nên tầng sau phải
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
