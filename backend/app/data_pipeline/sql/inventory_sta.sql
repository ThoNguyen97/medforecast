/* inventory_sta.sql — STA, vw_MedForecast_TonKho: tồn kho đã gộp theo mã vật tư, áp bảng ánh xạ MF_MapVatTu nếu có. */
SELECT supply_code,
       drug_code,
       ten_hoat_chat,
       unit,
       group_name,
       category,
       stock_quantity,
       [description]
FROM   dbo.vw_MedForecast_TonKho
