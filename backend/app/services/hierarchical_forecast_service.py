"""Service dự báo phân cấp cho FastAPI — đọc trực tiếp từ tầng MART.

Đọc bằng SQLAlchemy (DB-agnostic: SQLite khi làm đồ án, PostgreSQL khi triển khai),
tái sử dụng app.forecasting (mô hình + hòa giải phân cấp).

YÊU CẦU: các bảng mart_* và fact_disease_case phải nằm trong CÙNG DB mà app kết nối
(chạy pipeline với PIPELINE_DB_URL = DATABASE_URL để hợp nhất nguồn dữ liệu).
"""
from __future__ import annotations
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.forecasting.config import PRODUCTION_CONFIG
from app.forecasting.models import build_production_ensemble
from app.forecasting.evaluate import empirical_interval
from app.forecasting.hierarchical import ewma_shares, reconcile_ols, split_topdown

TOAN_QUOC = "TOAN_QUOC"
METHODS = ("top_down_dynamic", "top_down_fixed", "bottom_up", "mint")
# "mint" giữ làm khoá API cho frontend không vỡ; thuật toán thật là HOÀ GIẢI
# OLS (W = I) — xem hierarchical.reconcile_ols. Nhãn hiển thị đã đổi (M5).

# Khoảng dự báo (M9, 11/09/2026): phân vị THỰC NGHIỆM của tỷ số thực tế/dự báo
# trên các bước walk-forward gần nhất — cùng cách với topdown.py, cùng mức
# PRODUCTION_CONFIG.interval_level cho mọi màn hình.
#
# Lịch sử: bản cũ dùng mean ± z·σ với z=1,96, và đã HIỆU CHUẨN bằng độ phủ đo
# thật (z=1,645 phủ 81,5–87%; z=1,96 phủ 87–90,7%, mục tiêu 90%). Kết quả
# hiệu chuẩn đó là lý do config chọn 0,90 chứ không phải 0,95. Cách mới bỏ
# được ba giả định của cách cũ: phân phối chuẩn, đối xứng, và σ biết trước.


def _next_month(year: int, month: int):
    return (year + 1, 1) if month == 12 else (year, month + 1)


class HierarchicalForecastService:
    def __init__(self, db: Session):
        self.db = db

    def _rows(self, sql: str, params: dict | None = None):
        """Chạy SELECT an toàn: nếu bảng chưa tồn tại (chưa đồng bộ) trả []."""
        try:
            return self.db.execute(text(sql), params or {}).fetchall()
        except SQLAlchemyError:
            self.db.rollback()
            return []

    # ── đọc dữ liệu từ MART / FACT ─────────────────────────────
    def list_blocks(self, region: str = TOAN_QUOC) -> List[str]:
        rows = self._rows(
            "SELECT DISTINCT block_code FROM mart_monthly_cases_by_block "
            "WHERE region=:r ORDER BY block_code", {"r": region})
        return [r[0] for r in rows]

    def _group_df(self, block: str, region: str) -> pd.DataFrame:
        rows = self._rows(
            "SELECT period, year, month, cases, is_covid, is_complete "
            "FROM mart_monthly_cases_by_block WHERE region=:r AND block_code=:b "
            "ORDER BY period", {"r": region, "b": block})
        df = pd.DataFrame(rows, columns=["period", "year", "month", "cases",
                                         "is_covid", "is_complete"])
        if not df.empty:
            df = df[df["is_complete"] == 1].reset_index(drop=True)
            df["cases"] = df["cases"].astype(float)
            df["is_covid"] = df["is_covid"].astype(bool)
        return df

    def _codes_df(self, block: str) -> Dict[str, pd.DataFrame]:
        rows = self._rows(
            # CASE WHEN thay cho MAX/MIN(boolean): Postgres không có max(boolean),
            # SQLite lưu bool = 0/1 — viết kiểu này chạy đúng trên cả hai.
            "SELECT period, year, month, icd_code, SUM(cases) AS cases, "
            "MAX(CASE WHEN is_covid THEN 1 ELSE 0 END) AS is_covid, "
            "MIN(CASE WHEN is_complete THEN 1 ELSE 0 END) AS is_complete "
            "FROM fact_disease_case WHERE block_code=:b "
            "GROUP BY period, year, month, icd_code ORDER BY period",
            {"b": block})
        df = pd.DataFrame(rows, columns=["period", "year", "month", "icd_code",
                                         "cases", "is_covid", "is_complete"])
        out: Dict[str, pd.DataFrame] = {}
        for code, g in df.groupby("icd_code"):
            g = g[g["is_complete"] == 1].sort_values("period").reset_index(drop=True)
            g["cases"] = g["cases"].astype(float)
            g["is_covid"] = g["is_covid"].astype(bool)
            out[code] = g[["period", "year", "month", "cases", "is_covid"]]
        return out

    def _fixed_shares(self, block: str) -> Dict[str, float]:
        rows = self._rows(
            "SELECT icd_code, share FROM mart_icd_share_in_block "
            "WHERE block_code=:b", {"b": block})
        return {r[0]: float(r[1]) for r in rows}

    def _weather_df(self, region: str = TOAN_QUOC):
        rows = self._rows(
            "SELECT period, temp, humidity, rainfall FROM mart_monthly_weather "
            "WHERE region=:r ORDER BY period", {"r": region})
        import pandas as _pd
        return _pd.DataFrame(rows, columns=["period", "temp", "humidity", "rainfall"])

    def _group_interval(self, group_w, base_group: float, tm: int):
        """Khoảng dự báo nhóm từ phần dư TƯƠNG ĐỐI walk-forward gần nhất.

        Trả (lower, upper, n_resid) hoặc (None, None, n) khi chưa đủ lịch sử —
        nơi gọi phải nói rõ "chưa đủ", không bịa khoảng.
        """
        cfg = PRODUCTION_CONFIG
        n = len(group_w)
        start = max(cfg.min_train, n - cfg.interval_n_back)
        rel = []
        for t in range(start, n):
            hist = group_w.iloc[:t]
            m_t = int(group_w["month"].iloc[t])
            try:
                pred = build_production_ensemble(hist).fit(hist).predict(m_t)
                if pred > 0:
                    rel.append(float(group_w["cases"].iloc[t]) / pred)
            except Exception:                                 # noqa: BLE001
                pass
        iv = empirical_interval(base_group, np.array(rel), cfg.interval_level)
        if iv is None:
            return None, None, len(rel)
        return max(0.0, iv[0]), iv[1], len(rel)

    # ── dự báo phân cấp ────────────────────────────────────────
    def forecast(self, block: str, method: str = "top_down_dynamic",
                 region: str = TOAN_QUOC) -> dict:
        if method not in METHODS:
            raise ValueError(f"method phải thuộc {METHODS}")
        group = self._group_df(block, region)
        if group.empty:
            raise ValueError(f"Chưa có dữ liệu MART cho nhóm {block}. Hãy chạy pipeline.")
        codes = self._codes_df(block)
        code_list = sorted(codes.keys())

        last = group.iloc[-1]
        ty, tm = _next_month(int(last["year"]), int(last["month"]))

        # Ghép thời tiết (biến ngoại sinh, có độ trễ) cho CẢ nhóm lẫn mã.
        # Bản cũ: nhóm có thời tiết, mã không — hai mức hai cấu hình (M1).
        cfg = PRODUCTION_CONFIG
        wdf = self._weather_df(region)
        def _w(df):
            return df.merge(wdf, on="period", how="left") if not wdf.empty else df
        group_w = _w(group)
        codes_w = {c: _w(codes[c]) for c in code_list}

        ens_g = build_production_ensemble(group_w).fit(group_w)
        base_group = ens_g.predict(tm)
        weather_used = any(n.endswith("_weather") for n in ens_g.members_used)
        base_codes = {c: build_production_ensemble(codes_w[c]).fit(codes_w[c]).predict(tm)
                      for c in code_list}

        # Khoảng dự báo nhóm (M9) + lan sang mã theo tỷ trọng điểm
        group_lower, group_upper, n_resid = self._group_interval(group_w, base_group, tm)

        shares_dyn = ewma_shares(group, {c: codes[c] for c in code_list}, span=cfg.ewma_span)
        shares_fixed = self._fixed_shares(block)

        if method == "top_down_dynamic":
            split, shares_used = split_topdown(base_group, shares_dyn), shares_dyn
        elif method == "top_down_fixed":
            sf = {c: shares_fixed.get(c, 1.0 / len(code_list)) for c in code_list}
            split, shares_used = split_topdown(base_group, sf), sf
        elif method == "bottom_up":
            split, shares_used = dict(base_codes), None
        else:  # mint
            split, shares_used = reconcile_ols(code_list, base_group, base_codes), None

        # Cận trên mỗi mã = mã × (cận trên nhóm / dự báo nhóm): giữ đúng tỷ lệ,
        # thay cho phép cộng σ tuyến tính cũ.
        up_ratio = (group_upper / base_group) if (group_upper is not None and base_group > 0) else None
        return {
            "block": block,
            "region": region,
            "target_period": f"{ty:04d}-{tm:02d}",
            "method": method,
            "group_forecast": round(float(base_group), 1),
            "group_interval": (
                {"lower": int(round(group_lower)), "upper": int(round(group_upper)),
                 "level": cfg.interval_level, "n_resid": n_resid}
                if group_lower is not None else
                {"lower": None, "upper": None, "level": cfg.interval_level, "n_resid": n_resid,
                 "reason": "chưa đủ bước walk-forward để dựng khoảng (cần ≥ 8)"}
            ),
            "by_code": {c: int(round(v)) for c, v in split.items()},
            "by_code_upper": ({c: int(round(v * up_ratio)) for c, v in split.items()}
                              if up_ratio is not None else None),
            "shares_used": ({c: round(float(s), 3) for c, s in shares_used.items()}
                            if shares_used else None),
            "n_history_months": int(len(group)),
            "weather_used": bool(weather_used),
            # M6 / lưu vết: mô hình nào đã sinh ra con số này
            "model": {**ens_g.describe(), "config": cfg.as_record()},
        }

    # ── báo cáo tồn kho từ MART ────────────────────────────────
    def inventory_report(self, limit: int = 500, group_name: Optional[str] = None) -> List[dict]:
        sql = ("SELECT supply_code, name, drug_code, unit, group_name, category, "
               "stock_quantity, snapshot_date FROM mart_inventory ")
        params = {}
        if group_name:
            sql += "WHERE group_name LIKE :g "
            params["g"] = f"%{group_name}%"
        sql += "ORDER BY stock_quantity DESC LIMIT :lim"
        params["lim"] = limit
        rows = self._rows(sql, params)
        cols = ["supply_code", "name", "drug_code", "unit", "group_name",
                "category", "stock_quantity", "snapshot_date"]
        return [dict(zip(cols, r)) for r in rows]
