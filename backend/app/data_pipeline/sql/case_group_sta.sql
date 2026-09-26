-- Số ca theo nhóm ICD, đọc từ MEDFORECAST_DW trên STA.
--
-- Không cộng từ case_sta.sql: một lượt khám có thể mang hai mã cùng nhóm
-- (J01 chính + J06 phụ đều thuộc J00-J06), cộng mã con sẽ đếm lượt đó hai lần.
-- Chỉ PROD còn TIEPNHAN_ID để đếm DISTINCT mức nhóm, nên PROD tính sẵn vào MF_CaBenh_Nhom.
--
-- Hạt: (tháng × nhóm × vùng). region = 'TOAN_QUOC' là dòng toàn quốc, đếm DISTINCT
-- riêng chứ không phải tổng các tỉnh.
--
-- Dùng: PIPELINE_CASE_GROUP_SQL_FILE=case_group_sta.sql
SELECT [month],
       disease_group,
       disease_group_name,
       region,
       cases
FROM   dbo.vw_MedForecast_CaBenhNhom
WHERE  Period >= :since_date
