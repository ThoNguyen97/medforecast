/* =============================================================================
   G1 — BƯỚC 3: BẢNG NHẬN DỮ LIỆU, NGƯỠNG CẢNH BÁO, TẬP THEO DÕI
   =============================================================================
   Chạy trên: DB local của ứng dụng — backend/data/medforecast.db (SQLite)

       cd backend
       cp data/medforecast.db data/saoluu_truoc_G1_medforecast.db
       sqlite3 data/medforecast.db ".read ../sql_his/phase0/G1_03_LOCAL_cau_hinh.sql"

   ⚠ File này CÓ GHI. Sao lưu trước.

   -----------------------------------------------------------------------------
   BA VIỆC, VÀ VÌ SAO

   §1  Bảng fact_usage_total — nhận tiêu hao TOÀN VIỆN từ STA. Đây là mẫu số
       đúng của DOI. Trước đây mẫu số chỉ có phần hô hấp nên DOI bị thổi lên
       gấp khoảng bảy lần (đo được: trung vị 53,8 → 22,3 ngày sau khi sửa).

   §2  Ngưỡng cảnh báo 18 / 36 ngày — suy từ chu kỳ nhập thật (Đ9-C: trung vị
       18 ngày trên 1.992 mã bổ sung đều), thay cho 7 / 14 chọn tay.

   §3  Hai tập con của danh mục, dùng chung cho mọi màn hình:
         • DANH MỤC CÒN HOẠT ĐỘNG — có xuất trong 3 kỳ gần nhất. Là mẫu số
           đúng của mọi tỷ lệ phần trăm; toàn bộ 5.041 mã thì phần lớn là mã
           đã ngừng dùng.
         • TẬP THEO DÕI TRỌNG TÂM — mã có tỷ trọng hô hấp ≥ 25% (đo được 547
           mã). Lý do phải có tập này nằm ở §3 bên dưới; đây là điều chỉnh
           thiết kế quan trọng nhất phát sinh từ Đ10.
============================================================================= */

PRAGMA foreign_keys = OFF;
BEGIN;


/* ═════════════════════════════════════════════════════════════════════════
   §1 · BẢNG NHẬN TIÊU HAO TOÀN VIỆN
   Tên cột giữ NGUYÊN như bên STA để đoạn nạp chỉ là INSERT thẳng — mỗi phép
   đổi tên là một chỗ để sai.
   ═════════════════════════════════════════════════════════════════════════ */
CREATE TABLE IF NOT EXISTS fact_usage_total (
    period              VARCHAR(7)  NOT NULL,     -- 'YYYY-MM'
    supply_code         VARCHAR(60) NOT NULL,
    supply_name         VARCHAR(500),
    supply_unit         VARCHAR(40),
    is_vtyt             INTEGER NOT NULL DEFAULT 0,
    so_luong_toan_vien  FLOAT   NOT NULL,          -- MẪU SỐ của DOI
    so_luong_hohap      FLOAT   NOT NULL DEFAULT 0,
    d_baseline_thang    FLOAT,                     -- = toàn viện − hô hấp
    ty_trong_hohap      FLOAT,                     -- 0..100
    so_dong_toa         INTEGER,
    so_luot             INTEGER,
    PRIMARY KEY (period, supply_code)
);
CREATE INDEX IF NOT EXISTS ix_fut_supply ON fact_usage_total (supply_code, period);


/* ═════════════════════════════════════════════════════════════════════════
   §2 · NGƯỠNG CẢNH BÁO VÀ CÁC GIẢ ĐỊNH
   -------------------------------------------------------------------------
   Mọi hằng số của tầng cảnh báo nằm ở ĐÚNG MỘT CHỖ này. Không viết cứng trong
   mã Python hay TypeScript — hợp đồng dữ liệu dashboard v2 có khối
   `meta.assumptions` để lộ chúng ra giao diện, và giao diện đọc từ đây.

   doi_red_days = 18   ← Đ9-C, trung vị chu kỳ nhập của 1.992 mã bổ sung đều
   doi_amber_days = 36 ← gấp đôi: còn một đợt nhập làm đệm

   Vì sao KHÔNG lấy 14 ngày của Đ9-B: Đ9-B gộp mọi khoảng cách lại rồi lấy
   trung vị, nên mã quay vòng nhanh (đóng góp rất nhiều khoảng ngắn) chi phối
   kết quả. Đ9-C lấy trung vị của TỪNG MÃ rồi mới lấy trung vị của các trung vị
   đó — đúng câu hỏi "một mã điển hình được bổ sung sau bao nhiêu ngày".
   ═════════════════════════════════════════════════════════════════════════ */
INSERT INTO system_config (config_key, config_value, description, updated_at)
SELECT 'dss.thresholds',
       json_object(
         'doi_red_days',            18,
         'doi_amber_days',          36,
         'horizon_days',            30,
         'fefo_window_days',        30,
         'active_period_lookback',   3,
         'focus_min_resp_share',    25,
         'overstock_factor',         2,
         'incoming_stock_considered', json('false'),
         'nguon',                   'Đ9-C ngày 06/09/2026 · trung vị chu kỳ nhập 1.992 mã bổ sung đều'
       ),
       'Ngưỡng và giả định của tầng cảnh báo DSS (G1)',
       datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM system_config WHERE config_key = 'dss.thresholds');

UPDATE system_config
SET    config_value = json_set(config_value,
                        '$.doi_red_days', 18,
                        '$.doi_amber_days', 36),
       updated_at   = datetime('now')
WHERE  config_key = 'dss.thresholds';

/* admin.safety_rate (0.15) là hệ số dự phòng của công thức cũ. Phạm vi DSS
   không dùng nó nữa — đánh dấu để không ai vô tình nối lại vào công thức.   */
UPDATE system_config
SET    description = 'KHÔNG CÒN DÙNG từ G1 — hệ số dự phòng của công thức đề xuất nhập kho cũ. Giữ lại để đối chiếu số cũ.'
WHERE  config_key = 'admin.safety_rate';


/* ═════════════════════════════════════════════════════════════════════════
   §3 · HAI TẬP CON CỦA DANH MỤC
   -------------------------------------------------------------------------
   ĐIỀU CHỈNH THIẾT KẾ QUAN TRỌNG NHẤT PHÁT SINH TỪ Đ10

   Đo trên 30 mã tiêu hao lớn nhất toàn viện: trung vị tỷ trọng hô hấp chỉ
   0,8%, và chỉ 4/30 mã đạt ≥ 25%.

   Nghĩa là hai tập gần như KHÔNG GIAO NHAU:
       • mã chi phối khối lượng kho  — mô hình dịch tễ nói được rất ít
       • mã do dịch hô hấp lái       — khối lượng nhỏ hơn nhiều

   Nếu dashboard xếp hạng theo khối lượng hay giá trị, nó sẽ bị lấp đầy bởi
   nhóm thứ nhất, và phần dự báo dịch tễ — đóng góp chính của đề tài — trở nên
   vô hình. Người dùng sẽ hỏi đúng câu hội đồng sẽ hỏi: "mô hình AI ảnh hưởng
   gì tới mấy con số này?"

   Cách xử lý: KHÔNG bỏ các mã kia (chúng vẫn cần cảnh báo tồn kho), nhưng
   tách thành hai tập có nhãn rõ ràng, và để giao diện lọc được.
   ═════════════════════════════════════════════════════════════════════════ */

/* 13/09/2026 — cả ba view: (1) chỉ THUỐC (is_vtyt = 0) vì DayDuLieu và
   DayKhoCungUng chạy @GomVTYT = 0, VTYT không có tồn/định mức nên chỉ ra Xám;
   (2) LOẠI KỲ DỞ DANG (period < tháng hiện tại) — tháng đang chạy mới có vài
   ngày tiêu hao, lọt vào cửa sổ thì d_daily bị kéo thấp, DOI phồng lên.
   Bản chạy tự động: app/data_pipeline/views.py — sửa phải sửa cả hai. */

/* 3a — DANH MỤC CÒN HOẠT ĐỘNG: thuốc có xuất trong 3 kỳ đã chốt gần nhất.
       Dùng làm MẪU SỐ cho mọi tỷ lệ phần trăm trên dashboard. */
DROP VIEW IF EXISTS v_supply_active;
CREATE VIEW v_supply_active AS
SELECT DISTINCT u.supply_code
FROM   fact_usage_total u
WHERE  u.so_luong_toan_vien > 0
  AND  u.is_vtyt = 0
  AND  u.period < strftime('%Y-%m', 'now', 'localtime')
  AND  u.period >= (
        SELECT MIN(p) FROM (
          SELECT DISTINCT period AS p FROM fact_usage_total
          WHERE period < strftime('%Y-%m', 'now', 'localtime')
          ORDER BY period DESC LIMIT 3));

/* 3b — TẬP THEO DÕI TRỌNG TÂM: tỷ trọng hô hấp ≥ 25% trên 12 kỳ gần nhất.
       Đây là tập mà luận điểm của đề tài thật sự đúng — dự báo dịch tễ lái
       được nhu cầu. Đo Đ10-B: 547 mã (110 + 179 + 258). */
DROP VIEW IF EXISTS v_supply_focus;
CREATE VIEW v_supply_focus AS
WITH cua_so AS (
    SELECT DISTINCT period AS p FROM fact_usage_total
    WHERE  period < strftime('%Y-%m', 'now', 'localtime')
    ORDER BY period DESC LIMIT 12
), n_ky AS (SELECT COUNT(*) * 1.0 AS n FROM cua_so)
SELECT supply_code,
       ROUND(100.0 * SUM(so_luong_hohap) / NULLIF(SUM(so_luong_toan_vien), 0), 2) AS ty_trong_hohap,
       ROUND(SUM(so_luong_toan_vien) / (SELECT n FROM n_ky), 3)                   AS tb_thang_toan_vien,
       ROUND(SUM(d_baseline_thang)  / (SELECT n FROM n_ky), 3)                    AS d_baseline_thang,
       COUNT(*)                                                                    AS so_ky
FROM   fact_usage_total
WHERE  is_vtyt = 0
  AND  period IN (SELECT p FROM cua_so)
GROUP BY supply_code
HAVING SUM(so_luong_toan_vien) > 0
   AND 100.0 * SUM(so_luong_hohap) / SUM(so_luong_toan_vien) >= 25.0
   /* 13/09: phải còn hoạt động — mã đã ngừng xuất không cần cảnh báo tồn và
      chiếm 54/91 dòng Xám. Ràng buộc: tạo v_supply_active TRƯỚC view này. */
   AND supply_code IN (SELECT supply_code FROM v_supply_active)
   /* Ít nhất 3 kỳ có xuất — cùng điều kiện với Đ10-D. Một mã chỉ xuất đúng
      một tháng mà 90% là hô hấp không đủ cơ sở để xếp vào tập trọng tâm. */
   AND COUNT(*) >= 3;

/* 3c — Mẫu số hằng ngày dùng chung cho DOI, tính sẵn một chỗ.
       d = tiêu hao toàn viện trung bình tháng / 30.
       KHÔNG lấy tiêu hao hô hấp làm mẫu số — đó chính là lỗi đã sửa ở G1.
       18/09/2026: mẫu số là SỐ KỲ CỦA CỬA SỔ (n_ky), không phải số kỳ mà
       riêng mã đó có xuất. Chia cho COUNT(*) làm một mã chỉ xuất 1 trong 12 kỳ
       có d_daily ngang mã xuất đều 12 kỳ → tồn ít của nó thành Đỏ giả (đo
       14/09: 284 mã Đỏ có 8 mã 1 kỳ, 19 mã 2 kỳ, 10 mã 3 kỳ). Cột so_ky giữ
       nguyên nghĩa cũ để chẩn đoán. */
DROP VIEW IF EXISTS v_supply_daily_demand;
CREATE VIEW v_supply_daily_demand AS
WITH cua_so AS (
    SELECT DISTINCT period AS p FROM fact_usage_total
    WHERE  period < strftime('%Y-%m', 'now', 'localtime')
    ORDER BY period DESC LIMIT 12
), n_ky AS (SELECT COUNT(*) * 1.0 AS n FROM cua_so)
SELECT  supply_code,
        COUNT(*)                                                        AS so_ky,
        ROUND(SUM(so_luong_toan_vien) / (SELECT n FROM n_ky) / 30.0, 6) AS d_daily,
        ROUND(SUM(so_luong_hohap)     / (SELECT n FROM n_ky) / 30.0, 6) AS d_daily_hohap,
        ROUND(SUM(d_baseline_thang)   / (SELECT n FROM n_ky) / 30.0, 6) AS d_daily_baseline,
        ROUND(100.0 * SUM(so_luong_hohap) / NULLIF(SUM(so_luong_toan_vien),0), 2) AS ty_trong_hohap
FROM    fact_usage_total
WHERE   is_vtyt = 0
  AND   period IN (SELECT p FROM cua_so)
GROUP BY supply_code
HAVING  SUM(so_luong_toan_vien) > 0;

COMMIT;
PRAGMA foreign_keys = ON;


/* =============================================================================
   KIỂM TRA SAU KHI CHẠY  (chạy lại sau khi pipeline đã nạp fact_usage_total)
============================================================================= */

SELECT '§2 · ngưỡng đã ghi' AS Buoc;
SELECT config_key,
       json_extract(config_value,'$.doi_red_days')   AS do_ngay,
       json_extract(config_value,'$.doi_amber_days') AS vang_ngay,
       json_extract(config_value,'$.nguon')          AS nguon
FROM   system_config WHERE config_key = 'dss.thresholds';

SELECT '§3 · quy mô hai tập con' AS Buoc;
SELECT (SELECT COUNT(*) FROM dim_supply)            AS DanhMucDayDu,
       (SELECT COUNT(*) FROM v_supply_active)       AS ConHoatDong,
       (SELECT COUNT(*) FROM v_supply_focus)        AS TapTrongTam;
/* ► ĐỌC THẾ NÀO — đối chiếu với số đã đo trên HIS:
     DanhMucDayDu ≈ 5.041   ConHoatDong ≈ 1.900   TapTrongTam ≈ 547
   ConHoatDong ra ~650 nghĩa là pipeline vẫn đang nạp bảng tiêu hao CŨ (chỉ
   hô hấp) chứ không phải fact_usage_total — quay lại G1 bước 2.             */

SELECT '§3 · mẫu số DOI đã sửa chưa' AS Buoc;
SELECT COUNT(*)                                             AS SoMaCoMauSo,
       ROUND(AVG(ty_trong_hohap), 2)                        AS TyTrongTB,
       SUM(CASE WHEN ty_trong_hohap >= 25 THEN 1 ELSE 0 END) AS SoMaHoHapLai
FROM   v_supply_daily_demand;
/* ► TyTrongTB phải quanh mức 7-10%. Nếu ra ~100% thì cột so_luong_hohap đang
   được nạp bằng chính so_luong_toan_vien — mẫu số chưa sửa.                 */


/* =============================================================================
   CÒN LẠI CỦA G1 — không thuộc file này

   1. Nạp dữ liệu: sửa data_pipeline/connectors.py + pipeline.py để đọc
      vw_MedForecast_TieuHaoTong (và ba view phân cấp) từ STA.

   2. Neo mốc thời gian: api/v1/dashboard.py — mọi KPI lấy
      max(period) WHERE is_complete = 1 thay cho max(DiseaseCase.recorded_at).
      Hiện T9/2026 là kỳ đang mở với 3 ca, T8 có 341 ca → xu hướng 6500%.

   3. Một nguồn số ca duy nhất: mart_monthly_cases_by_block. Bỏ mọi truy vấn
      KPI đọc thẳng disease_cases.

   4. Xoá _classify_risk (dashboard.py:644).

   Xem G1_HuongDan.md.
============================================================================= */
