-- Số ca theo NHÓM ICD, đọc từ DB trung chuyển MEDFORECAST_DW (máy chủ STAGING).
--
-- VÌ SAO CẦN CÂU RIÊNG, KHÔNG CỘNG TỪ case_sta.sql
-- Một lượt khám có thể mang hai mã cùng nhóm (J01 chính + J06 phụ, cả hai đều
-- thuộc J00-J06). Cộng số ca của các mã con lại sẽ đếm lượt đó hai lần. Chỉ
-- PROD mới còn TIEPNHAN_ID để đếm DISTINCT ở mức nhóm, nên PROD tính sẵn và đẩy
-- xuống bảng MF_CaBenh_Nhom. Xem sql_his/03_PROD_store_tong_hop.sql bước 7b.
--
-- Hạt: (tháng × nhóm × vùng). region = 'TOAN_QUOC' là dòng toàn quốc, cũng đếm
-- DISTINCT riêng chứ không phải tổng các tỉnh.
--
-- Dùng: PIPELINE_CASE_GROUP_SQL_FILE=case_group_sta.sql
SELECT [month],
       disease_group,
       disease_group_name,
       region,
       cases
FROM   dbo.vw_MedForecast_CaBenhNhom
WHERE  Period >= :since_date
