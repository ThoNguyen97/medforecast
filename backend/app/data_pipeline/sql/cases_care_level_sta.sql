/* Số ca theo (tháng × nhóm ICD × rổ chăm sóc) — MẪU SỐ của định mức.
   Nguồn: STA · vw_MedForecast_CaBenhPhanCap

   Rổ: NGT | NT1 | NT2 | NT3 | NT0. Số ca đã đếm DISTINCT ở MỨC NHÓM bên HIS —
   một lượt mang J01 và J06 (cùng thuộc J00-J06) chỉ tính một lần.

   Bảng này KHÔNG có chiều vùng: tỷ trọng phân cấp phải là con số thật, không
   bị bước gộp ô nhỏ (k-ẩn danh) làm mờ. */
SELECT  Period,
        [month],
        disease_group,
        disease_group_name,
        ro,
        cases
FROM    dbo.vw_MedForecast_CaBenhPhanCap
WHERE   Period >= :since_date
ORDER BY Period, disease_group, ro;
