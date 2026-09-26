/* case_sta.sql — STA, vw_MedForecast_CaBenh: ca bệnh theo (tháng × mã ICD × tỉnh × vật tư).
   `cases` là COUNT(DISTINCT lượt khám) lặp trên mọi dòng vật tư; `disease_group` là nhóm ICD từ PHANNHOM.
   Lọc trên Period (ngày 01 của tháng) để dùng index; nạp tăng dần theo tham số since_date. */
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
