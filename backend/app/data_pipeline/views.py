# -*- coding: utf-8 -*-
"""BỐN VIEW SQLITE CỦA TẦNG 2 VÀ TẦNG 3 (12/09/2026).

Vì sao có file này: bốn view dưới đây trước nay CHỈ được tạo khi ai đó mở
SSMS/DB Browser chạy tay `sql_his/phase0/G1_03_LOCAL_cau_hinh.sql` và
`G1_04_LOCAL_cuasodphancap.sql`. `Base.metadata.create_all` không biết tới
view, `khoi_tao_moi.py` cũng không tạo, và đồng bộ HIS chỉ nạp DỮ LIỆU chứ
không tạo view.

Hậu quả trên máy chưa chạy hai script đó: DB có đủ bảng, đồng bộ HIS báo OK,
nhưng Tầng 2 và Tầng 3 mù hoàn toàn — `dss_alerts` trả `san_sang = False` với
lý do "Thiếu v_supply_daily_demand...", Dashboard hiện "0 mã có mẫu số", biểu
đồ DOI và biểu đồ phân cấp chăm sóc trống trơn. Không có lỗi nào được ném ra,
nên rất khó đoán nguyên nhân.

View không chứa dữ liệu, chỉ là câu truy vấn đặt tên — tạo lại bao nhiêu lần
cũng vô hại. Vì vậy `tao_views()` được gọi ngay lúc khởi động ứng dụng.

Nguồn định nghĩa gốc (giữ nguyên logic, chép lại ở đây để chạy tự động):
  • v_supply_active, v_supply_focus, v_supply_daily_demand → G1_03
  • v_care_level_share                                     → G1_04
Sửa định nghĩa thì phải sửa CẢ HAI nơi.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── 3a · Danh mục còn hoạt động: có xuất trong 3 kỳ gần nhất ─────────────────
V_SUPPLY_ACTIVE = """
CREATE VIEW v_supply_active AS
SELECT DISTINCT u.supply_code
FROM   fact_usage_total u
WHERE  u.so_luong_toan_vien > 0
  AND  u.period >= (
        SELECT MIN(p) FROM (
          SELECT DISTINCT period AS p FROM fact_usage_total
          ORDER BY period DESC LIMIT 3))
"""

# ── 3b · Tập trọng tâm: tỷ trọng hô hấp ≥ 25% trên 12 kỳ gần nhất ────────────
V_SUPPLY_FOCUS = """
CREATE VIEW v_supply_focus AS
SELECT supply_code,
       ROUND(100.0 * SUM(so_luong_hohap) / NULLIF(SUM(so_luong_toan_vien), 0), 2) AS ty_trong_hohap,
       ROUND(SUM(so_luong_toan_vien) / COUNT(*), 3)                               AS tb_thang_toan_vien,
       ROUND(SUM(d_baseline_thang)  / COUNT(*), 3)                                AS d_baseline_thang,
       COUNT(*)                                                                   AS so_ky
FROM   fact_usage_total
WHERE  period >= (
        SELECT MIN(p) FROM (
          SELECT DISTINCT period AS p FROM fact_usage_total
          ORDER BY period DESC LIMIT 12))
GROUP BY supply_code
HAVING SUM(so_luong_toan_vien) > 0
   AND 100.0 * SUM(so_luong_hohap) / SUM(so_luong_toan_vien) >= 25.0
   AND COUNT(*) >= 3
"""

# ── 3c · Mẫu số hằng ngày dùng chung cho DOI ─────────────────────────────────
# d = tiêu hao TOÀN VIỆN trung bình tháng / 30. KHÔNG lấy tiêu hao hô hấp làm
# mẫu số — đó là lỗi đã sửa ở G1, đừng vô tình dựng lại.
V_SUPPLY_DAILY_DEMAND = """
CREATE VIEW v_supply_daily_demand AS
SELECT  supply_code,
        COUNT(*)                                              AS so_ky,
        ROUND(SUM(so_luong_toan_vien) / COUNT(*) / 30.0, 6)   AS d_daily,
        ROUND(SUM(so_luong_hohap)     / COUNT(*) / 30.0, 6)   AS d_daily_hohap,
        ROUND(SUM(d_baseline_thang)   / COUNT(*) / 30.0, 6)   AS d_daily_baseline,
        ROUND(100.0 * SUM(so_luong_hohap) / NULLIF(SUM(so_luong_toan_vien),0), 2) AS ty_trong_hohap
FROM    fact_usage_total
WHERE   period >= (
         SELECT MIN(p) FROM (
           SELECT DISTINCT period AS p FROM fact_usage_total
           ORDER BY period DESC LIMIT 12))
GROUP BY supply_code
HAVING  SUM(so_luong_toan_vien) > 0
"""

# ── Tỷ trọng phân cấp chăm sóc theo khối — đầu vào định mức thực nghiệm ──────
V_CARE_LEVEL_SHARE = """
CREATE VIEW v_care_level_share AS
WITH cua_so AS (
    SELECT MAX(p) AS p_max, MIN(p) AS p_min FROM (
        SELECT DISTINCT period AS p
        FROM   fact_cases_by_care_level
        WHERE  period >= (SELECT json_extract(config_value, '$.min_period')
                          FROM system_config WHERE config_key = 'dss.care_level')
        ORDER BY period DESC
        LIMIT  (SELECT json_extract(config_value, '$.window_periods')
                FROM system_config WHERE config_key = 'dss.care_level')
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
        CASE WHEN SUM(f.cases) < (SELECT json_extract(config_value, '$.min_cases_per_bucket')
                                  FROM system_config WHERE config_key = 'dss.care_level')
             THEN 1 ELSE 0 END                                         AS mau_qua_nho
FROM    fact_cases_by_care_level f, cua_so c
WHERE   f.period >= c.p_min AND f.period <= c.p_max
GROUP BY f.block_code, f.ro
"""

VIEWS = {
    "v_supply_active": V_SUPPLY_ACTIVE,
    "v_supply_focus": V_SUPPLY_FOCUS,
    "v_supply_daily_demand": V_SUPPLY_DAILY_DEMAND,
    "v_care_level_share": V_CARE_LEVEL_SHARE,
}

# View nào phụ thuộc bảng nào — thiếu bảng thì bỏ qua view đó, đừng nổ.
PHU_THUOC = {
    "v_supply_active": ("fact_usage_total",),
    "v_supply_focus": ("fact_usage_total",),
    "v_supply_daily_demand": ("fact_usage_total",),
    "v_care_level_share": ("fact_cases_by_care_level", "system_config"),
}


def tao_views(engine=None) -> dict:
    """Tạo lại bốn view. Trả về {tên_view: 'đã tạo' | 'bỏ qua: ...' | 'lỗi: ...'}.

    Chạy lại nhiều lần vô hại: view bị DROP rồi CREATE, không đụng tới dữ liệu.
    Chỉ áp dụng cho SQLite (bản triển khai hiện tại của đề tài).
    """
    from sqlalchemy import text
    if engine is None:
        from app.database import engine as _e
        engine = _e

    ket_qua: dict[str, str] = {}
    with engine.begin() as conn:
        co_bang = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type = 'table'"))}
        for ten, ddl in VIEWS.items():
            thieu = [b for b in PHU_THUOC[ten] if b not in co_bang]
            if thieu:
                ket_qua[ten] = "bỏ qua: chưa có " + ", ".join(thieu)
                continue
            try:
                conn.execute(text(f"DROP VIEW IF EXISTS {ten}"))
                conn.execute(text(ddl))
                ket_qua[ten] = "đã tạo"
            except Exception as exc:                      # noqa: BLE001
                ket_qua[ten] = f"lỗi: {exc}"
    return ket_qua


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from dotenv import load_dotenv
    load_dotenv()
    for k, v in tao_views().items():
        print(f"  {k:26s} {v}")
