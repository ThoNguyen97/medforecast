/* =============================================================================
   PHASE 0 — BƯỚC 4: BẢNG NHẬN DỮ LIỆU MỚI, DỌN NHÃN VÙNG, PHÂN LỚP ABC-XYZ
   =============================================================================
   Chạy trên: DB local của ứng dụng — backend/data/medforecast.db (SQLite).

       cd backend
       sqlite3 data/medforecast.db ".read ../Phase0_04_LOCAL_masterdata_abcxyz.sql"

   ⚠ SAO LƯU TRƯỚC. File này CÓ GHI (khác ba file trước, chỉ đọc PROD).
       cp data/medforecast.db data/saoluu_truoc_phase0_medforecast.db

   -----------------------------------------------------------------------------
   BỐN VIỆC, THEO THỨ TỰ

   §1  Tạo 5 bảng nhận dữ liệu từ các bảng STA mới (chưa nạp, chỉ tạo vỏ).
   §2  Dọn nhãn vùng — 49 dòng 'Không Xác Định Tỉnh' đang hiện lên như một tỉnh.
   §3  Phân lớp ABC-XYZ và cột is_managed — quyết định vật tư nào được áp
       công thức tồn an toàn theo phân phối chuẩn, vật tư nào KHÔNG.
   §4  Nạp bốn cột master data đang rỗng, và GỠ vòng lặp safety_stock.

   -----------------------------------------------------------------------------
   VÌ SAO §3 QUAN TRỌNG HƠN VẺ NGOÀI CỦA NÓ

   Công thức SS = Z·√[(T+L̄)σ²_d + d̄²σ²_L] giả định nhu cầu xấp xỉ phân phối
   chuẩn. Đ6 đo được 376/1.529 vật tư (24,6%) có CV > 1 — nhu cầu gián đoạn,
   tháng có tháng không. Với nhóm đó, σ tính ra là con số vô nghĩa và công
   thức cho tồn an toàn sai cả hai chiều: thừa với vật tư gần như không dùng,
   thiếu với vật tư dùng theo đợt.

   Nhóm Z phải đi đường khác (đặt theo lô cố định, hoặc theo yêu cầu khoa
   phòng), và giao diện phải nói rõ điều đó thay vì hiện một con số giả vờ
   chính xác. Cột `phuong_phap_ss` trong bảng supply_class là chỗ ghi nhận.
============================================================================= */

PRAGMA foreign_keys = OFF;

BEGIN;


/* ═════════════════════════════════════════════════════════════════════════
   §1 · BẢNG NHẬN DỮ LIỆU TỪ STA
   Vỏ bảng thôi — pipeline (backend/app/data_pipeline/) sẽ nạp ở Phase 1.
   Tên cột giữ NGUYÊN như bên STA để đoạn nạp chỉ là INSERT thẳng, không
   phải ánh xạ tên — mỗi phép đổi tên là một chỗ để sai.
   ═════════════════════════════════════════════════════════════════════════ */

/* 1.1 — Tồn kho theo lô (FEFO) */
CREATE TABLE IF NOT EXISTS inventory_lots (
    snapshot_date  DATE      NOT NULL,
    supply_code    VARCHAR(60) NOT NULL,
    lot_id         INTEGER   NOT NULL,
    lot_code       VARCHAR(100),
    expiry_date    DATE,
    has_expiry     INTEGER   NOT NULL DEFAULT 0,
    quantity       FLOAT     NOT NULL,
    warehouse_count INTEGER,
    unit_price_mua  FLOAT,
    unit_price_thau FLOAT,
    unit_price_von  FLOAT,
    PRIMARY KEY (snapshot_date, supply_code, lot_id)
);
CREATE INDEX IF NOT EXISTS ix_inv_lots_exp
    ON inventory_lots (snapshot_date, expiry_date);

/* 1.2 — Thuộc tính vật tư suy từ lịch sử nhập */
CREATE TABLE IF NOT EXISTS supply_attributes (
    supply_code            VARCHAR(60) PRIMARY KEY,
    so_lan_nhap            INTEGER,
    so_nha_cung_cap        INTEGER,
    lead_time_median       INTEGER,
    lead_time_mean         FLOAT,
    lead_time_sd           FLOAT,     -- σ_L, vào thẳng công thức SS
    lead_time_p90          INTEGER,
    lead_time_source       VARCHAR(12),  -- THAU | NOIBO | MACDINH
    review_cycle_median    INTEGER,   -- chu kỳ nhập thật, đối chiếu với T=30
    moq                    FLOAT,
    moq_source             VARCHAR(12),
    fill_rate_mean         FLOAT,     -- tỷ lệ giao đủ
    unit_price_mua         FLOAT,
    unit_price_thau        FLOAT,
    unit_price_von         FLOAT,
    last_receipt_date      DATE,
    updated_at             DATETIME DEFAULT CURRENT_TIMESTAMP
);

/* 1.3 — Số ca theo phân cấp chăm sóc (mẫu số định mức) */
CREATE TABLE IF NOT EXISTS fact_cases_by_care_level (
    period         VARCHAR(7)  NOT NULL,
    block_code     VARCHAR(20) NOT NULL,   -- J00-J06 | J09-J18 | J20-J22
    ro             VARCHAR(4)  NOT NULL,   -- NGT | NT1 | NT2 | NT3 | NT0
    cases          INTEGER     NOT NULL,
    PRIMARY KEY (period, block_code, ro)
);

/* 1.4 — Tiêu hao theo rổ (tử số định mức) */
CREATE TABLE IF NOT EXISTS fact_usage_by_care_level (
    period         VARCHAR(7)  NOT NULL,
    block_code     VARCHAR(20) NOT NULL,
    ro             VARCHAR(4)  NOT NULL,
    supply_code    VARCHAR(60) NOT NULL,
    is_vtyt        INTEGER     NOT NULL DEFAULT 0,
    quantity       FLOAT       NOT NULL,
    line_count     INTEGER,
    PRIMARY KEY (period, block_code, ro, supply_code)
);

/* 1.5 — Phân lớp ABC-XYZ (§3 sẽ nạp) */
CREATE TABLE IF NOT EXISTS supply_class (
    supply_code      VARCHAR(60) PRIMARY KEY,
    so_thang_co_xuat INTEGER,
    nhu_cau_thang_tb FLOAT,
    nhu_cau_thang_sd FLOAT,     -- σ_d
    cv               FLOAT,
    lop_xyz          VARCHAR(1),   -- X | Y | Z
    gia_tri_nam      FLOAT,
    ty_trong_luy_ke  FLOAT,
    lop_abc          VARCHAR(1),   -- A | B | C
    is_managed       INTEGER NOT NULL DEFAULT 0,
    phuong_phap_ss   VARCHAR(20),  -- CHUAN | LO_CO_DINH | THEO_YEU_CAU
    ly_do            VARCHAR(200),
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);


/* ═════════════════════════════════════════════════════════════════════════
   §2 · DỌN NHÃN VÙNG
   -------------------------------------------------------------------------
   'Không Xác Định Tỉnh' là một dòng placeholder do người dùng tự tạo trong
   TM_DONVIHANHCHINH của HIS, không phải tỉnh. Nó đang nằm trong dim_region
   và hiện lên giao diện như một địa phương thật (49 dòng fact_supply_usage,
   1 dòng mart, 1 dòng fact_disease_case).

   Thủ tục PROD bản 2 đã bắt nhãn này ở bước 3a (so khớp LIKE, không so bằng),
   nên sau khi chạy @NapLaiToanBo = 1 dữ liệu mới sẽ sạch. Khối dưới dọn phần
   ĐÃ NẠP TRƯỚC ĐÓ, để không phải chờ nạp lại toàn bộ mới thấy đúng.

   Gộp vào 'Tỉnh khác' chứ KHÔNG xoá: xoá sẽ làm hụt tổng số ca và mô hình
   học lệch đúng phần đó.
   ═════════════════════════════════════════════════════════════════════════ */

/* Xem trước sẽ đụng bao nhiêu dòng */
SELECT '§2 · trước khi dọn' AS Buoc;
SELECT 'fact_supply_usage'           AS Bang, region, COUNT(*) AS SoDong
FROM   fact_supply_usage           WHERE region LIKE '%ác Định%' OR region LIKE '%ác định%' GROUP BY region
UNION ALL
SELECT 'fact_disease_case',           region, COUNT(*)
FROM   fact_disease_case           WHERE region LIKE '%ác Định%' OR region LIKE '%ác định%' GROUP BY region
UNION ALL
SELECT 'mart_monthly_cases_by_block', region, COUNT(*)
FROM   mart_monthly_cases_by_block WHERE region LIKE '%ác Định%' OR region LIKE '%ác định%' GROUP BY region;

UPDATE fact_supply_usage
SET    region = 'Tỉnh khác'
WHERE  region LIKE '%ác Định%' OR region LIKE '%ác định%';

UPDATE fact_disease_case
SET    region = 'Tỉnh khác'
WHERE  region LIKE '%ác Định%' OR region LIKE '%ác định%';

UPDATE mart_monthly_cases_by_block
SET    region = 'Tỉnh khác'
WHERE  region LIKE '%ác Định%' OR region LIKE '%ác định%';

DELETE FROM dim_region
WHERE  region LIKE '%ác Định%' OR region LIKE '%ác định%';

/* Gộp xong có thể sinh dòng trùng khoá trong mart (hai nhãn cùng thành
   'Tỉnh khác' trong cùng tháng × nhóm). Gộp lại thành một dòng, CỘNG số ca. */
CREATE TEMP TABLE _mart_gop AS
SELECT period, year, month, block_code,
       MAX(block_name) AS block_name, region,
       SUM(cases)      AS cases,
       MAX(is_covid)   AS is_covid,
       MIN(is_complete) AS is_complete
FROM   mart_monthly_cases_by_block
GROUP BY period, year, month, block_code, region;

DELETE FROM mart_monthly_cases_by_block;
INSERT INTO mart_monthly_cases_by_block
       (period, year, month, block_code, block_name, region, cases, is_covid, is_complete)
SELECT  period, year, month, block_code, block_name, region, cases, is_covid, is_complete
FROM   _mart_gop;
DROP TABLE _mart_gop;

SELECT '§2 · sau khi dọn — danh sách vùng còn lại' AS Buoc;
SELECT region, COUNT(*) AS SoDong
FROM   mart_monthly_cases_by_block
GROUP BY region ORDER BY SoDong DESC;


/* ═════════════════════════════════════════════════════════════════════════
   §3 · PHÂN LỚP ABC-XYZ
   -------------------------------------------------------------------------
   XYZ — theo hệ số biến thiên CV của nhu cầu THÁNG:
       X  CV ≤ 0,5   ổn định        → công thức chuẩn dùng được
       Y  CV ≤ 1,0   biến động vừa  → công thức chuẩn dùng được
       Z  CV > 1,0   gián đoạn      → KHÔNG dùng Z·σ

   Điều kiện tối thiểu 6 tháng có xuất. Dưới 6 tháng thì σ không ước lượng
   được, xếp thẳng vào Z bất kể CV.

   ABC — theo GIÁ TRỊ tiêu hao 12 tháng gần nhất (số lượng × đơn giá).
       A  luỹ kế ≤ 80%
       B  luỹ kế ≤ 95%
       C  còn lại
   Vật tư chưa có đơn giá (supply_attributes chưa nạp) tạm xếp C và ghi lý do.

   is_managed = 1 khi lop_xyz ∈ {X, Y}. Đ6 đo được X 142 + Y 1.011 = 1.153
   vật tư — so với 34 vật tư có định mức gõ tay hiện nay là gấp 34 lần.

   phuong_phap_ss:
       CHUAN         X/Y  → SS = Z·√[(T+L̄)σ²_d + d̄²σ²_L]
       LO_CO_DINH    Z nhưng có xuất đều đặn về giá trị (nhóm A/B)
                          → đặt theo lô cố định, tồn tối thiểu = 1 lô
       THEO_YEU_CAU  Z và nhóm C → không dự trữ, đặt khi khoa phòng yêu cầu
   ═════════════════════════════════════════════════════════════════════════ */

DELETE FROM supply_class;

/* 3a — nhu cầu theo tháng, chỉ tháng có xuất */
CREATE TEMP TABLE _thang AS
SELECT supply_code, period, SUM(quantity) AS qty
FROM   fact_supply_usage
WHERE  quantity > 0
GROUP  BY supply_code, period;

/* 3b — thống kê từng vật tư. SQLite không có STDEV: dùng
   σ = √(E[x²] − E[x]²), chặn dưới ở 0 để tránh sai số dấu phẩy động
   sinh ra căn của số âm.                                                  */
CREATE TEMP TABLE _tk AS
SELECT supply_code,
       COUNT(*)     AS so_thang,
       AVG(qty)     AS tb,
       SQRT(MAX(AVG(qty*qty) - AVG(qty)*AVG(qty), 0)) AS sd
FROM   _thang
GROUP  BY supply_code;

/* 3c — giá trị tiêu hao 12 tháng gần nhất */
CREATE TEMP TABLE _gt AS
SELECT u.supply_code,
       SUM(u.quantity) AS qty_12t,
       SUM(u.quantity) * COALESCE(sa.unit_price_mua,
                                  sa.unit_price_thau,
                                  sa.unit_price_von,
                                  ms.unit_price)      AS gia_tri
FROM   fact_supply_usage u
LEFT JOIN supply_attributes sa ON sa.supply_code = u.supply_code
LEFT JOIN medical_supplies  ms ON ms.supply_code = u.supply_code
WHERE  u.quantity > 0
GROUP  BY u.supply_code;
/* Cố ý lấy TOÀN BỘ lịch sử, không cắt 12 tháng. Nhiều vật tư mới chỉ có vài
   tháng dữ liệu; cắt cửa sổ sẽ loại oan chúng khỏi phân lớp ABC. Khi dữ liệu
   đã dày (sau vài kỳ đồng bộ) thì thêm điều kiện:
       AND u.period >= <YYYY-MM của 12 tháng trước>
   — so sánh chuỗi hoạt động đúng vì period luôn ở dạng 'YYYY-MM'.          */

/* Luỹ kế theo giá trị giảm dần. Hai cột, và phải dùng đúng cột:
     luy_ke        gồm CẢ vật tư đang xét — dùng để HIỂN THỊ
     luy_ke_truoc  chỉ các vật tư ĐỨNG TRƯỚC — dùng để PHÂN LỚP

   Vì sao không phân lớp bằng luy_ke: nếu một vật tư chiếm 96% tổng giá trị
   thì luy_ke của chính nó đã là 0,96 > 0,95 và nó sẽ bị xếp lớp C — trong
   khi nó chính là vật tư quan trọng nhất kho. Đây là lỗi kinh điển của
   phân lớp ABC viết vội. Dùng luy_ke_truoc thì vật tư đầu tiên luôn có
   luy_ke_truoc = 0 và luôn thuộc lớp A, đúng như định nghĩa.               */
CREATE TEMP TABLE _abc AS
SELECT supply_code, gia_tri,
       ck / tong                  AS luy_ke,
       (ck - gia_tri) / tong      AS luy_ke_truoc
FROM (
    SELECT supply_code, gia_tri,
           SUM(gia_tri) OVER (ORDER BY gia_tri DESC
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS ck,
           NULLIF((SELECT SUM(gia_tri) FROM _gt WHERE gia_tri IS NOT NULL), 0)  AS tong
    FROM   _gt
    WHERE  gia_tri IS NOT NULL
);

INSERT INTO supply_class
      (supply_code, so_thang_co_xuat, nhu_cau_thang_tb, nhu_cau_thang_sd,
       cv, lop_xyz, gia_tri_nam, ty_trong_luy_ke, lop_abc,
       is_managed, phuong_phap_ss, ly_do)
SELECT
    t.supply_code,
    t.so_thang,
    ROUND(t.tb, 3),
    ROUND(t.sd, 3),
    ROUND(CASE WHEN t.tb > 0 THEN t.sd / t.tb ELSE 99 END, 4)          AS cv,
    CASE WHEN t.so_thang < 6                       THEN 'Z'
         WHEN t.tb <= 0                            THEN 'Z'
         WHEN t.sd / t.tb <= 0.5                   THEN 'X'
         WHEN t.sd / t.tb <= 1.0                   THEN 'Y'
         ELSE                                           'Z' END        AS lop_xyz,
    ROUND(a.gia_tri, 0),
    ROUND(a.luy_ke, 4),
    CASE WHEN a.luy_ke_truoc IS NULL  THEN 'C'
         WHEN a.luy_ke_truoc <  0.80  THEN 'A'
         WHEN a.luy_ke_truoc <  0.95  THEN 'B'
         ELSE                              'C' END                     AS lop_abc,
    CASE WHEN t.so_thang >= 6 AND t.tb > 0 AND t.sd / t.tb <= 1.0
         THEN 1 ELSE 0 END                                             AS is_managed,
    CASE
        WHEN t.so_thang >= 6 AND t.tb > 0 AND t.sd / t.tb <= 1.0 THEN 'CHUAN'
        WHEN a.luy_ke_truoc IS NOT NULL AND a.luy_ke_truoc < 0.95 THEN 'LO_CO_DINH'
        ELSE                                                          'THEO_YEU_CAU'
    END                                                                AS phuong_phap_ss,
    CASE
        WHEN t.so_thang < 6
            THEN 'Chỉ ' || t.so_thang || ' tháng có xuất — chưa đủ để ước lượng độ lệch chuẩn.'
        WHEN t.tb > 0 AND t.sd / t.tb > 1.0
            THEN 'Nhu cầu gián đoạn (CV = ' || ROUND(t.sd / t.tb, 2) || '), phân phối chuẩn không mô tả đúng.'
        ELSE 'Đủ điều kiện áp công thức tồn an toàn theo phân phối chuẩn.'
    END                                                                AS ly_do
FROM   _tk t
LEFT JOIN _abc a ON a.supply_code = t.supply_code;

/* Vật tư chưa từng có dòng tiêu hao nào — vẫn phải có mặt để giao diện
   không hiện ô trống không giải thích được.                               */
INSERT INTO supply_class
      (supply_code, so_thang_co_xuat, nhu_cau_thang_tb, nhu_cau_thang_sd,
       cv, lop_xyz, lop_abc, is_managed, phuong_phap_ss, ly_do)
SELECT d.supply_code, 0, 0, 0, NULL, 'Z', 'C', 0, 'THEO_YEU_CAU',
       'Chưa có dòng tiêu hao nào trong dữ liệu đã đồng bộ.'
FROM   dim_supply d
WHERE  d.supply_code NOT IN (SELECT supply_code FROM supply_class);

DROP TABLE _thang; DROP TABLE _tk; DROP TABLE _gt; DROP TABLE _abc;

SELECT '§3 · kết quả phân lớp' AS Buoc;
SELECT lop_xyz, lop_abc, COUNT(*) AS SoVatTu,
       SUM(is_managed) AS SoDuocQuanLy
FROM   supply_class
GROUP BY lop_xyz, lop_abc
ORDER BY lop_xyz, lop_abc;

SELECT phuong_phap_ss, COUNT(*) AS SoVatTu
FROM   supply_class GROUP BY phuong_phap_ss ORDER BY SoVatTu DESC;


/* ═════════════════════════════════════════════════════════════════════════
   §4 · MASTER DATA VÀ VÒNG LẶP safety_stock
   ═════════════════════════════════════════════════════════════════════════ */

/* 4a — Nạp bốn cột từ supply_attributes.
   Chạy SAU khi pipeline đã nạp supply_attributes từ STA. Chạy trước thì
   không sao: mệnh đề WHERE khiến không dòng nào bị đụng.                  */
UPDATE medical_supplies
SET    lead_time_days          = (SELECT sa.lead_time_median
                                  FROM supply_attributes sa
                                  WHERE sa.supply_code = medical_supplies.supply_code),
       minimum_order_quantity  = (SELECT CAST(sa.moq AS INTEGER)
                                  FROM supply_attributes sa
                                  WHERE sa.supply_code = medical_supplies.supply_code),
       unit_price              = (SELECT COALESCE(sa.unit_price_mua,
                                                  sa.unit_price_thau,
                                                  sa.unit_price_von)
                                  FROM supply_attributes sa
                                  WHERE sa.supply_code = medical_supplies.supply_code),
       updated_at              = CURRENT_TIMESTAMP
WHERE  EXISTS (SELECT 1 FROM supply_attributes sa
               WHERE sa.supply_code = medical_supplies.supply_code);

/* 4b — SỨC CHỨA KHO: để NULL, không bịa.
   HIS không lưu thể tích/diện tích lưu trữ và sẽ không bao giờ có. Đặt NULL
   và để hàm calculate_order_quantity() bỏ qua trần khi NULL (sửa ở Phase 1).
   Nếu sau này muốn có trần vận hành thì đặt tên đúng là "trần dự trữ" và
   tính bằng k × nhu cầu tháng cao nhất — KHÔNG gọi nó là sức chứa kho.     */
UPDATE medical_supplies SET storage_capacity = NULL;

/* 4c — GỠ VÒNG LẶP safety_stock.
   Hiện tại supply_recommendation_service tính
        calculated_safety_stock = need_before_buffer × (1 + 15%)
   rồi inventory.py ghi ngược giá trị đó vào inventory.safety_stock, và lần
   chạy sau lại đọc chính nó ra làm đầu vào. Mỗi vòng nhân thêm 1,15 lần.
   Cột này vì vậy KHÔNG còn là "tồn an toàn" mà là dấu vết của số lần bấm nút.

   Ở đây chỉ LƯU LẠI giá trị hiện tại rồi đưa về NULL. Việc chặn ghi ngược
   nằm ở code (Phase 1, sửa inventory.py:217) — nếu chỉ dọn số mà không sửa
   code thì vòng lặp sẽ dựng lại y nguyên sau lần bấm phân tích kế tiếp.    */
CREATE TABLE IF NOT EXISTS _luu_safety_stock_truoc_phase0 (
    supply_id     INTEGER PRIMARY KEY,
    safety_stock  INTEGER,
    luu_luc       DATETIME DEFAULT CURRENT_TIMESTAMP
);
INSERT OR REPLACE INTO _luu_safety_stock_truoc_phase0 (supply_id, safety_stock)
SELECT supply_id, safety_stock FROM inventory WHERE safety_stock IS NOT NULL;

SELECT '§4 · safety_stock trước khi gỡ' AS Buoc;
SELECT COUNT(*)                              AS SoDongCoGiaTri,
       MIN(safety_stock)                     AS NhoNhat,
       CAST(AVG(safety_stock) AS INT)        AS TrungBinh,
       MAX(safety_stock)                     AS LonNhat
FROM   inventory WHERE safety_stock > 0;

UPDATE inventory SET safety_stock = NULL;

/* 4d — Kiểm tra độ phủ master data sau khi nạp */
SELECT '§4 · độ phủ master data' AS Buoc;
SELECT 'lead_time_days'         AS Cot,
       SUM(CASE WHEN lead_time_days         IS NOT NULL THEN 1 ELSE 0 END) AS DaCo,
       COUNT(*)                                                            AS Tong
FROM medical_supplies
UNION ALL SELECT 'minimum_order_quantity',
       SUM(CASE WHEN minimum_order_quantity IS NOT NULL THEN 1 ELSE 0 END), COUNT(*) FROM medical_supplies
UNION ALL SELECT 'unit_price',
       SUM(CASE WHEN unit_price             IS NOT NULL THEN 1 ELSE 0 END), COUNT(*) FROM medical_supplies
UNION ALL SELECT 'storage_capacity (cố ý NULL)',
       SUM(CASE WHEN storage_capacity       IS NOT NULL THEN 1 ELSE 0 END), COUNT(*) FROM medical_supplies;

COMMIT;

PRAGMA foreign_keys = ON;


/* =============================================================================
   NGHIỆM THU PHASE 0 — SÁU CÂU HỎI, CHẠY SAU KHI HOÀN TẤT CẢ BỐN FILE
   Mỗi câu phải trả lời được bằng một con số, không phải bằng cảm nhận.
   -----------------------------------------------------------------------------

   N1 · Ba bảng phân cấp có dữ liệu chưa, và tỷ trọng có khớp Đ4 không?
        SELECT block_code, ro, SUM(cases) AS ca,
               ROUND(100.0*SUM(cases)/SUM(SUM(cases)) OVER (PARTITION BY block_code),1) AS ty_trong
        FROM   fact_cases_by_care_level GROUP BY block_code, ro ORDER BY block_code, ro;
        ĐẠT khi: tổng ba nhóm cho tỷ trọng NT1/NT2/NT3 nằm quanh 42/41/17
        (Đ4 đo trên toàn viện, ở mức từng nhóm bệnh sẽ lệch — J09-J18 phải
        nặng hơn J00-J06 rõ rệt).
        KHÔNG ĐẠT nếu ba nhóm bệnh cho tỷ trọng gần như nhau: khi đó
        PHANCAPCHAMSOC_ID không phản ánh độ nặng, và Tầng 2 phải thiết kế lại.

   N2 · Định mức thực nghiệm có hợp lý không?
        SELECT u.block_code, u.ro, u.supply_code,
               SUM(u.quantity)/NULLIF(SUM(c.cases),0) AS dinh_muc
        FROM   fact_usage_by_care_level u
        JOIN   fact_cases_by_care_level c
               ON c.period=u.period AND c.block_code=u.block_code AND c.ro=u.ro
        GROUP BY 1,2,3 HAVING SUM(c.cases) >= 30
        ORDER BY dinh_muc DESC LIMIT 30;
        ĐẠT khi: 30 dòng đầu đều giải thích được bằng nghiệp vụ. Một dòng vô
        lý (4.000 viên paracetamol mỗi ca) là dấu hiệu lệch đơn vị tính.

   N3 · So định mức thực nghiệm với 34 định mức gõ tay?
        Chênh dưới 2 lần: chấp nhận, ghi lại để bảo vệ.
        Chênh trên 5 lần: dừng, tìm nguyên nhân trước khi đi tiếp.

   N4 · FEFO phủ được bao nhiêu phần kho?
        SELECT SUM(has_expiry) AS co_han, COUNT(*) AS tong,
               ROUND(100.0*SUM(has_expiry)/COUNT(*),1) AS phan_tram
        FROM   inventory_lots
        WHERE  snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_lots);
        Dưới 50%: màn hình FEFO phải ghi rõ phạm vi áp dụng.

   N5 · σ_L đo được thật hay đang dùng mặc định?
        SELECT lead_time_source, COUNT(*) FROM supply_attributes GROUP BY 1;
        Nếu 'NOIBO' hoặc 'MACDINH' chiếm đa số → Phase 2 phải hiện cảnh báo
        "thời gian giao hàng đang dùng giá trị cấu hình" trên màn hình đề xuất.

   N6 · Chu kỳ nhập thật so với T = 30 ngày?
        SELECT ROUND(AVG(review_cycle_median),1), MIN(review_cycle_median),
               MAX(review_cycle_median) FROM supply_attributes
        WHERE review_cycle_median IS NOT NULL;
        Nếu trung vị > 40 ngày thì T = 30 đang lạc quan và khoảng bảo vệ
        T + L phải tính lại — đây là thay đổi tham số, không phải sửa code.

   -----------------------------------------------------------------------------
   HOÀN TÁC
   Toàn bộ §2 và §4 nằm trong một giao dịch. Nếu cần quay lại:
       cp data/saoluu_truoc_phase0_medforecast.db data/medforecast.db
   Riêng safety_stock có thể phục hồi mà không cần bản sao lưu:
       UPDATE inventory SET safety_stock =
         (SELECT s.safety_stock FROM _luu_safety_stock_truoc_phase0 s
          WHERE s.supply_id = inventory.supply_id);
============================================================================= */
