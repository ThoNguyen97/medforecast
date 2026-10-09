/* cases_care_level_dw.sql (view vw_MedForecast_CaBenhPhanCap): số ca theo (tháng × nhóm ICD × rổ chăm sóc), mẫu số định mức.
   Rổ: NGT | NT1 | NT2 | NT3 | NT0. Số ca đã đếm DISTINCT mức nhóm bên HIS.
   Không có chiều vùng để tỷ trọng phân cấp không bị bước gộp ô nhỏ làm mờ. */
SELECT  Period,
        [month],
        disease_group,
        disease_group_name,
        ro,
        cases
FROM    dbo.vw_MedForecast_CaBenhPhanCap
WHERE   Period >= :since_date
ORDER BY Period, disease_group, ro;
