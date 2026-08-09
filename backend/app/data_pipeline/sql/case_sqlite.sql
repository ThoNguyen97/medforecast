-- Bản SQLite của case_mssql.sql (chỉ khác hàm định dạng ngày) — dùng cho môi trường mô phỏng.
-- Đọc ca bệnh + vật tư sử dụng từ HIS (SQL Server / bản sao STA).
--
-- BA NGUYÊN TẮC PHẢI GIỮ KHI CHỈNH THEO SCHEMA THẬT:
--   1. `cases` = COUNT(DISTINCT lượt khám) theo (tháng × mã ICD × tỉnh), LẶP trên
--      mọi dòng vật tư. KHÔNG dùng `1 AS cases` — pipeline lấy max() để khử phần
--      lặp, nên `1 AS cases` sẽ cho ra đúng 1 ca/tháng cho mọi mã bệnh.
--   2. Lọc `:since_date` trên CỘT NGÀY. Không bọc cột trong FORMAT()/CONVERT() ở
--      mệnh đề WHERE — sẽ mất index và quét toàn bảng.
--   3. Không lấy dữ liệu định danh bệnh nhân (họ tên, CCCD, địa chỉ). Chỉ tỉnh/thành.
--
-- Tên cột đầu ra phải khớp CASE_COLUMNS trong connectors.py.
WITH ca AS (                       -- 1 dòng / lượt khám (đã khử trùng chẩn đoán)
    SELECT DISTINCT
           k.Id                      AS encounter_id,
           date(k.NgayKham)  AS ngay_kham,
           cd.MaICD                  AS disease_code,
           cd.TenICD                 AS disease_name,
           bn.Tinh                   AS region
    FROM   KhamBenh k
    JOIN   ChanDoan cd ON cd.KhamBenhId = k.Id
    JOIN   BenhNhan bn ON bn.Id = k.BenhNhanId
    WHERE  k.NgayKham >= :since_date
      AND  k.TrangThai = 'HOAN_TAT'
      AND  cd.LaChinh = 1                     -- chỉ chẩn đoán chính
),
ca_thang AS (                      -- số ca theo tháng × mã ICD × tỉnh
    SELECT strftime('%m/%Y', ngay_kham) AS month,
           disease_code,
           MAX(disease_name)            AS disease_name,
           region,
           COUNT(DISTINCT encounter_id) AS cases
    FROM   ca
    GROUP BY strftime('%m/%Y', ngay_kham), disease_code, region
),
vt_thang AS (                      -- lượng vật tư theo tháng × mã ICD × tỉnh × vật tư
    SELECT strftime('%m/%Y', c.ngay_kham) AS month,
           c.disease_code,
           c.region,
           vt.MaVatTu           AS supply_code,
           MAX(vt.TenVatTu)     AS supply_name,
           SUM(sd.SoLuong)      AS supply_quantity,
           MAX(vt.DonVi)        AS supply_unit,
           MAX(vt.NhomVatTu)    AS supply_category
    FROM   ca c
    JOIN   SuDungVatTu sd ON sd.KhamBenhId = c.encounter_id
    JOIN   VatTu vt       ON vt.Id = sd.VatTuId
    GROUP BY strftime('%m/%Y', c.ngay_kham), c.disease_code, c.region, vt.MaVatTu
)
SELECT ct.month,
       ct.disease_code,
       ct.disease_name,
       ct.region,
       ct.cases,
       vt.supply_code,
       vt.supply_name,
       vt.supply_quantity,
       vt.supply_unit,
       vt.supply_category,
       NULL AS note
FROM      ca_thang ct
LEFT JOIN vt_thang vt
       ON vt.month = ct.month
      AND vt.disease_code = ct.disease_code
      AND vt.region = ct.region
