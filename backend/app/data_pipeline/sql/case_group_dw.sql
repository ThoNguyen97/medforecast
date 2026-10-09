/* case_group_dw.sql (view vw_MedForecast_CaBenhNhom): số ca theo (tháng × nhóm ICD × vùng).
   Nguồn đếm DISTINCT lượt khám mức nhóm, không cộng từ case_dw.sql vì một lượt có thể mang hai mã cùng nhóm.
   Dòng region = 'TOAN_QUOC' đếm riêng, không phải tổng các tỉnh. Nạp tăng dần theo tham số since_date. */
SELECT [month],
       disease_group,
       disease_group_name,
       region,
       cases
FROM   dbo.vw_MedForecast_CaBenhNhom
WHERE  Period >= :since_date
