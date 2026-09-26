-- Ca bệnh từ MEDFORECAST_DW trên STA, đã tổng hợp sẵn bên PROD theo
-- (tháng × mã ICD × tỉnh × vật tư): mã ICD gom về 3 ký tự, `cases` là
-- COUNT(DISTINCT lượt khám) lặp trên mọi dòng vật tư, tỉnh đã đổi từ mã sang tên.
--
-- Period là ngày 01 của tháng; lọc trên cột này để dùng được index.
-- `disease_group` là nhóm ICD (TM_ICD.PHANNHOM, vd 'J00-J06') nên pipeline không cần tra TM_ICD.xlsx.
--
-- Dùng: PIPELINE_CASE_SQL_FILE=case_sta.sql
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
