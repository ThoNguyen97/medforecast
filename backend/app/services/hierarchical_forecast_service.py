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

from app.forecasting.models import build_default_ensemble
from app.forecasting.hierarchical import ewma_shares, reconcile_ols, split_topdown

TOAN_QUOC = "TOAN_QUOC"
METHODS = ("top_down_dynamic", "top_down_fixed", "bottom_up", "mint")
# Hệ số khoảng dự báo. Đã HIỆU CHUẨN bằng backtest walk-forward trên dữ liệu
# Gia An (54 bước/nhóm, 2026-07): z=1.645 chỉ phủ 81.5-87% thực tế (mục tiêu 90%)
# vì sigma ước lượng từ mẫu nhỏ (12 sai số) bị hẹp; z=1.96 đạt phủ 87-90.7%.
Z_SERVICE = 1.96


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

    def _group_sigma(self, group_w, weather_used: bool, n_back: int = 12,
                     min_train: int = 18) -> float:
        """Độ lệch chuẩn sai số 1 bước (backtest gần đây) → dựng khoảng dự báo."""
        n = len(group_w)
        start = max(min_train, n - n_back)
        res = []
        for t in range(start, n):
            hist = group_w.iloc[:t]
            tm = int(group_w["month"].iloc[t])
            try:
                pred = build_default_ensemble(use_weather=weather_used).fit(hist).predict(tm)
                res.append(float(group_w["cases"].iloc[t]) - pred)
            except Exception:
                pass
        if len(res) >= 3:
            return float(np.std(res))
        # dự phòng: 20% giá trị trung bình gần nhất
        return float(0.2 * group_w["cases"].tail(6).mean())

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

        # Ghép thời tiết (biến ngoại sinh, dùng có độ trễ) cho dự báo NHÓM
        wdf = self._weather_df(region)
        group_w = group.merge(wdf, on="period", how="left") if not wdf.empty else group
        weather_used = (not wdf.empty) and ("temp" in group_w.columns) and group_w["temp"].notna().any()

        base_group = build_default_ensemble(use_weather=weather_used).fit(group_w).predict(tm)
        code_ens = build_default_ensemble()
        base_codes = {c: code_ens.fit(codes[c]).predict(tm) for c in code_list}

        # Khoảng dự báo nhóm (mức an toàn) + lan sang mã theo tỷ trọng điểm
        sigma_g = self._group_sigma(group_w, weather_used)
        group_lower = max(0.0, base_group - Z_SERVICE * sigma_g)
        group_upper = base_group + Z_SERVICE * sigma_g

        shares_dyn = ewma_shares(group, {c: codes[c] for c in code_list})
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

        return {
            "block": block,
            "region": region,
            "target_period": f"{ty:04d}-{tm:02d}",
            "method": method,
            "group_forecast": round(float(base_group), 1),
            "group_interval": {"lower": int(round(group_lower)), "upper": int(round(group_upper))},
            "by_code": {c: int(round(v)) for c, v in split.items()},
            "by_code_upper": {
                c: int(round(v + Z_SERVICE * sigma_g * (v / base_group if base_group > 0 else 0)))
                for c, v in split.items()
            },
            "shares_used": ({c: round(float(s), 3) for c, s in shares_used.items()}
                            if shares_used else None),
            "n_history_months": int(len(group)),
            "weather_used": bool(weather_used),
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
