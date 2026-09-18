# -*- coding: utf-8 -*-
"""Đối tượng CSDL nằm ngoài `Base.metadata`: 6 bảng tự quản, 2 dòng cấu hình DSS, 4 view.

`create_all` chỉ lo 29 bảng ORM. Bốn bảng fact của dss_loader, hai bảng cache
của dss_dashboard và bốn view bên dưới trước đây chỉ xuất hiện khi người dùng
đồng bộ HIS / mở Dashboard / chạy tay G1_03, G1_04 — một DB dựng lại từ đầu
vì thế thiếu view và Tầng 2/3 mù mà không ném lỗi nào. `dam_bao_luoc_do()`
gom cả ba nhóm về một lệnh, gọi lúc khởi động ứng dụng; mọi câu đều idempotent.

Quy ước chung cho 4 view (13/09/2026):
  * KỲ DỞ DANG BỊ LOẠI: chỉ lấy `period < tháng hiện tại`. Tháng đang chạy mới
    có vài ngày tiêu hao, để lọt vào cửa sổ 12 kỳ thì d_daily bị kéo thấp và
    DOI phồng lên — cùng loại lỗi +6500% đã sửa ở KPI ca bệnh.
  * CHỈ THUỐC (`is_vtyt = 0`): thủ tục DayDuLieu và DayKhoCungUng chạy với
    @GomVTYT = 0 nên VTYT không có tồn kho lẫn định mức; giữ VTYT trong mẫu số
    chỉ sinh ra mã Xám vô nghĩa (86 mã đo ngày 13/09).
Định nghĩa gốc ở sql_his/phase0/G1_03_LOCAL_cau_hinh.sql và
G1_04_LOCAL_cuasodphancap.sql — sửa thì sửa cả hai nơi.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Kỳ đã chốt = mọi kỳ nhỏ hơn tháng hiện tại (SQLite so chuỗi 'YYYY-MM').
_KY_DA_CHOT = "period < strftime('%Y-%m', 'now', 'localtime')"

# ── 3a · Danh mục còn hoạt động: thuốc có xuất trong 3 kỳ ĐÃ CHỐT gần nhất ───
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

# ── 3b · Tập trọng tâm: thuốc CÒN HOẠT ĐỘNG, tỷ trọng hô hấp ≥ 25% / 12 kỳ chốt ─
# Phải nằm trong v_supply_active (13/09/2026): mã đã ngừng xuất không cần cảnh
# báo tồn, mà chúng chiếm 54/91 dòng Xám và làm loãng mọi tỷ lệ phần trăm của
# tập theo dõi. Đo trên DB thật: siết lại còn 242/304 mã, Xám 91 → 37.
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

# ── 3c · Mẫu số hằng ngày dùng chung cho DOI ─────────────────────────────────
# d = tiêu hao TOÀN VIỆN trung bình tháng / 30 trên 12 kỳ đã chốt. Không lấy
# tiêu hao hô hấp làm mẫu số (lỗi đã sửa ở G1).
# MẪU SỐ LÀ SỐ KỲ CỦA CỬA SỔ, KHÔNG PHẢI SỐ KỲ CÓ DÒNG (18/09/2026). Trước đây
# chia cho COUNT(*) — số kỳ mà RIÊNG mã đó có xuất — nên một mã chỉ xuất 1 kỳ
# trong 12 kỳ có d_daily ngang một mã xuất đều cả 12 kỳ, và tồn ít của nó thành
# Đỏ giả. Đo 14/09 trên toàn danh mục: trong 284 mã Đỏ có 8 mã chỉ 1 kỳ, 19 mã
# 2 kỳ, 10 mã 3 kỳ. Nay chia cho (SELECT n FROM n_ky) = số kỳ đã chốt thực có
# trong cửa sổ, tối đa 12 — giống nhau cho mọi mã. Cột `so_ky` giữ nguyên nghĩa
# cũ (số kỳ mã đó có xuất) để chẩn đoán.
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

# ── Tỷ trọng phân cấp chăm sóc theo khối — đầu vào định mức thực nghiệm ──────
# Mọi tham chiếu system_config bọc COALESCE: thiếu dòng 'dss.care_level' thì
# `LIMIT NULL` làm SQLite ném "datatype mismatch" lúc SELECT view.
# `dam_bao_cau_hinh()` gieo sẵn dòng đó; COALESCE là lớp chặn thứ hai.
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

# ── Cấu hình DSS mặc định ────────────────────────────────────────────────────
# Toàn bộ núm vặn của Tầng 2 và Tầng 3. Giá trị khớp THRESHOLDS_DEFAULT
# (dss_alerts) và CARE_LEVEL_DEFAULT (dss_demand). Chỉ chèn khi THIẾU — không
# ghi đè giá trị người dùng đã sửa ở Quản trị → Tham số DSS.
CAU_HINH_MAC_DINH = {
    "dss.care_level": (
        '{"window_periods": 12, "min_period": "2025-04", '
        '"min_cases_per_bucket": 30, "shrink_k0": 6}',
        "Tầng 2 — cửa sổ tính p̂(g,ro) và định mức thực nghiệm. "
        "Sửa ở Quản trị → Tham số DSS.",
    ),
    "dss.thresholds": (
        '{"doi_red_days": 18, "doi_amber_days": 36, "horizon_days": 30, '
        '"fefo_window_days": 30, "active_period_lookback": 3, '
        '"focus_min_resp_share": 25, "overstock_factor": 2, '
        '"incoming_stock_considered": false}',
        "Tầng 3 — ngưỡng DOI và chân trời nhu cầu. "
        "Sửa ở Quản trị → Tham số DSS.",
    ),
}


def dam_bao_cau_hinh(engine=None) -> dict:
    """Gieo `dss.care_level` / `dss.thresholds` nếu system_config chưa có.

    Trả {config_key: 'đã gieo' | 'đã có' | 'lỗi: ...'}.
    """
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


# THỨ TỰ QUAN TRỌNG: v_supply_focus tham chiếu v_supply_active nên phải đứng sau.
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


def tao_bang_tu_quan(db=None) -> dict:
    """Tạo 6 bảng tự quản (4 bảng fact của dss_loader, 2 bảng cache của
    dss_dashboard). Toàn bộ là CREATE TABLE IF NOT EXISTS."""
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
    """Dựng ĐỦ mọi đối tượng ngoài ORM: 6 bảng tự quản, 2 dòng cấu hình DSS,
    rồi 4 view.

    Thứ tự bắt buộc — view dựa trên fact_usage_total và
    fact_cases_by_care_level, tạo view trước thì chúng bị bỏ qua; và
    v_care_level_share đọc `dss.care_level` trong system_config.
    """
    out = dict(tao_bang_tu_quan(db))
    out.update(dam_bao_cau_hinh(engine))
    out.update(tao_views(engine))
    return out


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
