-- Bản SQLite của inventory_mssql.sql — dùng cho môi trường mô phỏng.
-- Đọc tồn kho hiện tại từ HIS (SQL Server / bản sao STA).
-- Tên cột đầu ra phải khớp INV_COLUMNS trong connectors.py.
SELECT
    vt.MaVatTu         AS supply_code,
    vt.MaThuoc         AS drug_code,
    vt.HoatChat        AS ten_hoat_chat,
    vt.DonVi           AS unit,
    vt.NhomVatTu       AS group_name,
    vt.LoaiVatTu       AS category,
    SUM(tk.SoLuongTon) AS stock_quantity,
    MAX(vt.MoTa)       AS description
FROM   TonKho tk
JOIN   VatTu vt ON vt.Id = tk.VatTuId
WHERE  vt.TrangThai = 1
GROUP BY vt.MaVatTu, vt.MaThuoc, vt.HoatChat, vt.DonVi, vt.NhomVatTu, vt.LoaiVatTu
