-- Đọc tồn kho từ DB trung chuyển MEDFORECAST_DW (máy chủ STAGING).
-- View đã gộp theo mã vật tư và áp bảng ánh xạ MF_MapVatTu (nếu có).
--
-- Dùng: PIPELINE_INVENTORY_SQL_FILE=inventory_sta.sql
SELECT supply_code,
       drug_code,
       ten_hoat_chat,
       unit,
       group_name,
       category,
       stock_quantity,
       [description]
FROM   dbo.vw_MedForecast_TonKho
