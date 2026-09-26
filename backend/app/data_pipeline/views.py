# -*- coding: utf-8 -*-
"""Đối tượng CSDL ngoài `Base.metadata`: 6 bảng tự quản, 2 dòng cấu hình DSS, 4 view; `dam_bao_luoc_do()` dựng lúc khởi động.

Các view chỉ lấy kỳ đã chốt (tháng dở dang kéo thấp d_daily, thổi phồng DOI) và chỉ thuốc
(is_vtyt = 0, vì VTYT không có tồn kho lẫn định mức).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Kỳ đã chốt = kỳ nhỏ hơn tháng hiện tại.
_KY_DA_CHOT = "period < strftime('%Y-%m', 'now', 'localtime')"

# ── v_supply_active: thuốc có xuất trong 3 kỳ chốt gần nhất ──
V_SUPPLY_ACTIVE = f"""
CREATE VIEW v_supply_active AS
SELECT DISTINCT u.supply_code
FROM   fact_usage_total u
WHERE  u.so_luong_toan_vien > 0
  AND  u.is_vtyt = 0
  AND  u.{_KY_DA_CHOT}
  AND  u.period >= (
        SELECT MIN(p) FROM (
          SELECT DISTINCT period AS p FROM fact_usage_total
          WHERE {_KY_DA_CHOT}
          ORDER BY period DESC LIMIT 3))
"""

# ── v_supply_focus: thuốc còn hoạt động, tỷ trọng hô hấp ≥ 25% trên 12 kỳ chốt ──
V_SUPPLY_FOCUS = f"""
CREATE VIEW v_supply_focus AS
WITH cua_so AS (
    SELECT DISTINCT period AS p FROM fact_usage_total
    WHERE  {_KY_DA_CHOT}
    ORDER BY period DESC LIMIT 12
), n_ky AS (SELECT COUNT(*) * 1.0 AS n FROM cua_so)
SELECT supply_code,
       ROUND(100.0 * SUM(so_luong_hohap) / NULLIF(SUM(so_luong_toan_vien), 0), 2) AS ty_trong_hohap,
       ROUND(SUM(so_luong_toan_vien) / (SELECT n FROM n_ky), 3)                   AS tb_thang_toan_vien,
       ROUND(SUM(d_baseline_thang)  / (SELECT n FROM n_ky), 3)                    AS d_baseline_thang,
       COUNT(*)                                                                   AS so_ky
FROM   fact_usage_total
WHERE  is_vtyt = 0
  AND  period IN (SELECT p FROM cua_so)
GROUP BY supply_code
HAVING SUM(so_luong_toan_vien) > 0
   AND 100.0 * SUM(so_luong_hohap) / SUM(so_luong_toan_vien) >= 25.0
   AND COUNT(*) >= 3
   AND supply_code IN (SELECT supply_code FROM v_supply_active)
"""

# ── v_supply_daily_demand: d = tiêu hao toàn viện trung bình tháng / 30 trên 12 kỳ chốt ──
# Chia cho số kỳ của cửa sổ chứ không COUNT(*), nếu không mã xuất thưa bị thổi phồng d_daily và sinh Đỏ giả.
V_SUPPLY_DAILY_DEMAND = f"""
CREATE VIEW v_supply_daily_demand AS
WITH cua_so AS (
    SELECT DISTINCT period AS p FROM fact_usage_total
    WHERE  {_KY_DA_CHOT}
    ORDER BY period DESC LIMIT 12
), n_ky AS (SELECT COUNT(*) * 1.0 AS n FROM cua_so)
SELECT  supply_code,
        COUNT(*)                                                     AS so_ky,
        ROUND(SUM(so_luong_toan_vien) / (SELECT n FROM n_ky) / 30.0, 6) AS d_daily,
        ROUND(SUM(so_luong_hohap)     / (SELECT n FROM n_ky) / 30.0, 6) AS d_daily_hohap,
        ROUND(SUM(d_baseline_thang)   / (SELECT n FROM n_ky) / 30.0, 6) AS d_daily_baseline,
        ROUND(100.0 * SUM(so_luong_hohap) / NULLIF(SUM(so_luong_toan_vien),0), 2) AS ty_trong_hohap
FROM    fact_usage_total
WHERE   is_vtyt = 0
  AND   period IN (SELECT p FROM cua_so)
GROUP BY supply_code
HAVING  SUM(so_luong_toan_vien) > 0
"""

# ── v_care_level_share: tỷ trọng phân cấp chăm sóc theo khối ──
# system_config bọc COALESCE vì thiếu dòng 'dss.care_level' thì `LIMIT NULL` gây "datatype mismatch".
V_CARE_LEVEL_SHARE = f"""
CREATE VIEW v_care_level_share AS
WITH cua_so AS (
    SELECT MAX(p) AS p_max, MIN(p) AS p_min FROM (
        SELECT DISTINCT period AS p
        FROM   fact_cases_by_care_level
        WHERE  {_KY_DA_CHOT}
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
        CASE WHEN SUM(f.cases) < COALESCE((SELECT json_extract(config_value, '$.min_cases_per_bucket')
                                           FROM system_config WHERE config_key = 'dss.care_level'), 30)
             THEN 1 ELSE 0 END                                         AS mau_qua_nho
FROM    fact_cases_by_care_level f, cua_so c
WHERE   f.period >= c.p_min AND f.period <= c.p_max
GROUP BY f.block_code, f.ro
"""

# ── Cấu hình DSS mặc định, khớp THRESHOLDS_DEFAULT và CARE_LEVEL_DEFAULT ──
CAU_HINH_MAC_DINH = {
    "dss.care_level": (
        '{"window_periods": 12, "min_period": "2025-04", '
        '"min_cases_per_bucket": 30, "shrink_k0": 6}',
        "Tầng 2 — cửa sổ tính p̂(g,ro) và định mức thực nghiệm. "
        "Sửa ở Quản trị → Tham số DSS.",
    ),
    "dss.thresholds": (
        '{"doi_red_days": 18, "doi_amber_days": 36, "horizon_days": 30, '
        '"fefo_window_days": 30}',
        "Tầng 3 — ngưỡng DOI và chân trời nhu cầu. "
        "Sửa ở Quản trị → Tham số DSS.",
    ),
}


def dam_bao_cau_hinh(engine=None) -> dict:
    """Gieo `dss.care_level` / `dss.thresholds` nếu chưa có; trả {config_key: 'đã gieo' | 'đã có' | 'lỗi: ...'}."""
    from sqlalchemy import text
    if engine is None:
        from app.database import engine as _e
        engine = _e
    ket_qua: dict[str, str] = {}
    with engine.begin() as conn:
        co_bang = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type = 'table'"))}
        if "system_config" not in co_bang:
            return {"system_config": "bỏ qua: chưa có bảng"}
        for khoa, (gia_tri, mo_ta) in CAU_HINH_MAC_DINH.items():
            try:
                co = conn.execute(text(
                    "SELECT 1 FROM system_config WHERE config_key = :k"),
                    {"k": khoa}).first()
                if co:
                    ket_qua[khoa] = "đã có"
                    continue
                conn.execute(text(
                    "INSERT INTO system_config (config_key, config_value, description) "
                    "VALUES (:k, :v, :d)"), {"k": khoa, "v": gia_tri, "d": mo_ta})
                ket_qua[khoa] = "đã gieo"
            except Exception as exc:                      # noqa: BLE001
                ket_qua[khoa] = f"lỗi: {exc}"
    return ket_qua


# v_supply_focus tham chiếu v_supply_active nên phải đứng sau.
VIEWS = {
    "v_supply_active": V_SUPPLY_ACTIVE,
    "v_supply_focus": V_SUPPLY_FOCUS,
    "v_supply_daily_demand": V_SUPPLY_DAILY_DEMAND,
    "v_care_level_share": V_CARE_LEVEL_SHARE,
}

# Bảng mà mỗi view phụ thuộc; thiếu bảng thì bỏ qua view đó.
PHU_THUOC = {
    "v_supply_active": ("fact_usage_total",),
    "v_supply_focus": ("fact_usage_total",),
    "v_supply_daily_demand": ("fact_usage_total",),
    "v_care_level_share": ("fact_cases_by_care_level", "system_config"),
}


def tao_bang_tu_quan(db=None) -> dict:
    """Tạo 6 bảng tự quản: 4 bảng fact của dss_loader, 2 bảng cache của dss_dashboard."""
    tu_dong = db is None
    if tu_dong:
        from app.database import SessionLocal
        db = SessionLocal()
    ket_qua: dict[str, str] = {}
    try:
        try:
            from app.data_pipeline.dss_loader import ensure_tables
            ensure_tables(db)
            ket_qua["dss_loader (4 bảng fact + index)"] = "đã tạo"
        except Exception as exc:                          # noqa: BLE001
            ket_qua["dss_loader (4 bảng fact + index)"] = f"lỗi: {exc}"
        try:
            from app.services.dss_dashboard import _ensure_cache
            _ensure_cache(db)
            ket_qua["dss_dashboard (cache + forecast_runs)"] = "đã tạo"
        except Exception as exc:                          # noqa: BLE001
            ket_qua["dss_dashboard (cache + forecast_runs)"] = f"lỗi: {exc}"
        db.commit()
    finally:
        if tu_dong:
            db.close()
    return ket_qua


def dam_bao_luoc_do(engine=None, db=None) -> dict:
    """Dựng mọi đối tượng ngoài ORM theo thứ tự bảng → cấu hình → view (view phụ thuộc hai nhóm trước)."""
    out = dict(tao_bang_tu_quan(db))
    out.update(dam_bao_cau_hinh(engine))
    out.update(tao_views(engine))
    return out


def tao_views(engine=None) -> dict:
    """DROP rồi CREATE bốn view (chỉ SQLite); trả {tên_view: 'đã tạo' | 'bỏ qua: ...' | 'lỗi: ...'}."""
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
