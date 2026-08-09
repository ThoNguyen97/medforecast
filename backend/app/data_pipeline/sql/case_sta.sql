-- Đọc ca bệnh từ DB trung chuyển MEDFORECAST_DW (máy chủ STAGING).
--
-- Dữ liệu ở đây ĐÃ ĐƯỢC TỔNG HỢP SẴN bên PROD theo (tháng × mã ICD × tỉnh ×
-- vật tư): mã ICD đã gom về 3 ký tự, `cases` đã là COUNT(DISTINCT lượt khám)
-- và lặp trên mọi dòng vật tư, tỉnh đã đổi từ mã sang tên. Xem
-- sql_his/03_PROD_store_tong_hop.sql.
--
-- Period là ngày 01 của tháng — lọc trên cột này để dùng được index.
--
-- Dùng: PIPELINE_CASE_SQL_FILE=case_sta.sql
--
-- `disease_group` là nhóm ICD (TM_ICD.PHANNHOM, vd 'J00-J06'). Có cột này thì
-- pipeline không cần tra TM_ICD.xlsx nữa — nguồn duy nhất là HIS.
SELECT [month],
       disease_code,
       disease_name,
       disease_group,
       region,
       cases,
       supply_code,
       supply_name,
       supply_quantity,
       supply_unit,
       supply_category,
       note
FROM   dbo.vw_MedForecast_CaBenh
WHERE  Period >= :since_date
