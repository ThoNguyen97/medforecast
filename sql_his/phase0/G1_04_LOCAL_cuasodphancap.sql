/* =============================================================================
   G1 — BƯỚC 4: CỬA SỔ TÍNH TỶ TRỌNG PHÂN CẤP CHĂM SÓC
   =============================================================================
   Chạy trên: DB local — backend/data/medforecast.db (SQLite)

       cd backend
       sqlite3 data/medforecast.db ".read ../sql_his/phase0/G1_04_LOCAL_cuasodphancap.sql"

   Chạy lại được nhiều lần.

   -----------------------------------------------------------------------------
   VÌ SAO PHẢI CÓ CẤU HÌNH NÀY

   Đ11 phát hiện một ĐỨT GÃY CHẾ ĐỘ GHI NHẬN vào đầu năm 2025. Đo trên toàn bộ
   y lệnh thuốc nội trú của bệnh viện:

       giai đoạn        cấp 1     cấp 2     cấp 3    chưa gán
       2019-2024        98,4%     0,12%     1,49%       0
       2025-2026        26,7%    50,7%     22,5%      30

   Tỷ trọng cấp 2 đi từ 0,12% lên 50,7% — gấp 429 lần. Đây không phải bệnh nhân
   đột nhiên nặng lên; đây là một trường dữ liệu đổi cách dùng.

   BẰNG CHỨNG QUYẾT ĐỊNH: cột "chưa gán" bằng 0 suốt sáu năm 2019-2024, rồi mới
   xuất hiện (2 rồi 28) từ 2025. Một trường KHÔNG BAO GIỜ để trống là một trường
   không ai điền tay — nó đang nhận GIÁ TRỊ MẶC ĐỊNH. Từ 2025, khi bắt đầu được
   đánh giá thật, nó mới có chỗ bỏ sót.

   Kết luận: `PHANCAPCHAMSOC_ID` trước 2025 là hằng số, không mang thông tin lâm
   sàng. Toàn bộ 2019-2024 KHÔNG dùng được để tính tỷ trọng p̂(g,c).

   -----------------------------------------------------------------------------
   SAI SỐ NẾU DÙNG TOÀN BỘ LỊCH SỬ

   Tỷ trọng nội trú của nhóm cúm/viêm phổi:

       tính trên 93 kỳ :  cấp1 66,4%  ·  cấp2 28,3%  ·  cấp3  5,3%
       tính trên 18 kỳ :  cấp1  9,8%  ·  cấp2 74,1%  ·  cấp3 16,1%
       lệch            :       −56,6 điểm    +45,9 điểm

   Dùng toàn bộ lịch sử sẽ dự báo THỪA gấp bảy lần số ca cấp 1 và THIẾU ba lần
   số ca cấp 2 — tức đề xuất sai đúng nhóm thuốc đắt tiền nhất. Cả ba nhóm bệnh
   đều lệch cùng chiều, quanh 50 điểm phần trăm.

   -----------------------------------------------------------------------------
   VÌ SAO CHỌN CỬA SỔ TRƯỢT CHỨ KHÔNG VIẾT CỨNG MỐC 2025-04

   Cửa sổ trượt 12 kỳ tự thích nghi nếu bệnh viện lại đổi quy trình lần nữa —
   không phải sửa mã. 12 kỳ cũng vừa đủ một chu kỳ mùa, quan trọng với bệnh hô
   hấp vì tỷ trọng nặng/nhẹ thay đổi theo mùa.

   `min_period` là chốt chặn cứng: dù cửa sổ trượt có với tới đâu cũng KHÔNG
   được lấy dữ liệu trước 2025-04 (tháng đầu tiên chế độ mới ổn định — Đ11-B).

   Hai tham số này chỉ áp cho TỶ TRỌNG PHÂN CẤP. Dự báo SỐ CA vẫn dùng toàn bộ
   93 kỳ: chuỗi số ca không bị đứt gãy, chỉ trường phân cấp bị.
============================================================================= */

BEGIN;

INSERT INTO system_config (config_key, config_value, description, updated_at)
SELECT 'dss.care_level',
       json_object(
         'window_periods',  12,
         'min_period',      '2025-04',
         'min_cases_per_bucket', 30,
         'shrink_k0',       6,
         'break_detected',  '2025-01',
         'nguon',           'Đ11 ngày 06/09/2026 — đứt gãy chế độ ghi nhận: '
                            || 'cấp 2 đi từ 0,12% (2019-2024) lên 50,7% (2025-2026)'
       ),
       'Cửa sổ tính tỷ trọng phân cấp chăm sóc p̂(g,c) — G1/Đ11',
       datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM system_config WHERE config_key = 'dss.care_level');

UPDATE system_config
SET    config_value = json_set(config_value,
                        '$.window_periods', 12,
                        '$.min_period', '2025-04',
                        '$.min_cases_per_bucket', 30,
                        '$.shrink_k0', 6),
       updated_at   = datetime('now')
WHERE  config_key = 'dss.care_level';

COMMIT;


/* ─────────────────────────────────────────────────────────────────────────────
   VIEW — tỷ trọng p̂(g,c) tính đúng cửa sổ
   Chỉ chạy được sau khi fact_cases_by_care_level đã có dữ liệu.
   ───────────────────────────────────────────────────────────────────────────── */
DROP VIEW IF EXISTS v_care_level_share;
CREATE VIEW v_care_level_share AS
WITH cua_so AS (
    SELECT MAX(p) AS p_max, MIN(p) AS p_min FROM (
        SELECT DISTINCT period AS p
        FROM   fact_cases_by_care_level
        /* COALESCE bắt buộc: thiếu dòng 'dss.care_level' thì truy vấn con trả
           NULL, và LIMIT NULL làm SQLite ném "datatype mismatch" ngay lúc
           SELECT view (không phải lúc tạo view). Xem app/data_pipeline/views.py */
        WHERE  period < strftime('%Y-%m', 'now', 'localtime')          /* 13/09: loại kỳ dở dang */
          AND  period >= COALESCE((SELECT json_extract(config_value, '$.min_period')
                                   FROM system_config WHERE config_key = 'dss.care_level'), '2025-04')
        ORDER BY period DESC
        LIMIT  COALESCE((SELECT json_extract(config_value, '$.window_periods')
                         FROM system_config WHERE config_key = 'dss.care_level'), 12)
    )
)
SELECT  f.block_code,
        f.ro,
        SUM(f.cases)                                                   AS cases,
        ROUND(100.0 * SUM(f.cases)
              / SUM(SUM(f.cases)) OVER (PARTITION BY f.block_code), 2) AS share_pct,
        COUNT(DISTINCT f.period)                                       AS so_ky,
        MIN(f.period)                                                  AS tu_ky,
        MAX(f.period)                                                  AS den_ky,
        /* Rổ dưới ngưỡng mẫu tối thiểu → tầng sau PHẢI co ngót về mức nhóm,
           đừng dùng thẳng tỷ trọng này. Đ11-D đo được có rổ chỉ 5-8 đợt. */
        CASE WHEN SUM(f.cases) < COALESCE((SELECT json_extract(config_value, '$.min_cases_per_bucket')
                                           FROM system_config WHERE config_key = 'dss.care_level'), 30)
             THEN 1 ELSE 0 END                                         AS mau_qua_nho
FROM    fact_cases_by_care_level f, cua_so c
WHERE   f.period >= c.p_min AND f.period <= c.p_max
GROUP BY f.block_code, f.ro;


/* ─────────────────────────────────────────────────────────────────────────────
   KIỂM TRA
   ───────────────────────────────────────────────────────────────────────────── */
SELECT 'cấu hình đã ghi' AS Buoc;
SELECT json_extract(config_value, '$.window_periods')       AS so_ky_cua_so,
       json_extract(config_value, '$.min_period')           AS ky_som_nhat,
       json_extract(config_value, '$.min_cases_per_bucket') AS mau_toi_thieu
FROM   system_config WHERE config_key = 'dss.care_level';

SELECT 'tỷ trọng phân cấp theo cửa sổ' AS Buoc;
SELECT * FROM v_care_level_share ORDER BY block_code, ro;
/* ► ĐỌC THẾ NÀO
   • Cột share_pct của NGT phải giữ nguyên bậc như bảng đã chạy trên HIS
     (J00-J06 ~92%, J20-J22 ~86%, J09-J18 ~55%) — chiều ngoại trú/nội trú
     KHÔNG bị ảnh hưởng bởi đứt gãy, vì nó không phụ thuộc PHANCAPCHAMSOC.
   • Trong nhóm nội trú, cấp 2 phải chiếm đa số (~65-75%), KHÔNG phải cấp 1.
     Nếu cấp 1 vẫn chiếm đa số thì cửa sổ chưa có hiệu lực — kiểm tra
     fact_cases_by_care_level có dữ liệu từ 2025-04 trở đi chưa.
   • Cột mau_qua_nho = 1 đánh dấu rổ cần co ngót ở G3.                        */
