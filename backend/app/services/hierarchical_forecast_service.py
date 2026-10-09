"""Dự báo mức nhóm từ tầng MART (kỳ đã chốt), cùng engine với backtest, kèm dấu vân tay làm khoá cache."""
from __future__ import annotations
from typing import List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import logging

from app.forecasting.config import PRODUCTION_CONFIG
from app.forecasting.group_forecast import forecast_group_next
from app.services.group_ensemble_service import SO_THANG_TOI_THIEU

logger = logging.getLogger(__name__)

TOAN_QUOC = "TOAN_QUOC"


def _next_month(year: int, month: int):
    return (year + 1, 1) if month == 12 else (year, month + 1)


class HierarchicalForecastService:
    def __init__(self, db: Session):
        self.db = db

    def _rows(self, sql: str, params: dict | None = None):
        """Chạy SELECT; lỗi SQL thì ghi cảnh báo và trả []."""
        try:
            return self.db.execute(text(sql), params or {}).fetchall()
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.warning("Truy vấn MART lỗi: %s", str(exc)[:200])
            return []

    # Đọc dữ liệu MART
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

    def _weather_df(self, region: str = TOAN_QUOC):
        rows = self._rows(
            "SELECT period, temp, humidity, rainfall FROM mart_monthly_weather "
            "WHERE region=:r ORDER BY period", {"r": region})
        return pd.DataFrame(rows, columns=["period", "temp", "humidity", "rainfall"])

    # Dự báo mức nhóm
    def forecast_group(self, block: str, region: str = TOAN_QUOC,
                       target_year: Optional[int] = None,
                       target_month: Optional[int] = None) -> dict:
        """Ŷ_g và khoảng tin cậy cho một nhóm.
        Kỳ đích bỏ trống là kỳ ngay sau kỳ đã chốt mới nhất; kỳ đích quá khứ chỉ học trên các tháng trước đó.
        """
        group = self._group_df(block, region)
        if group.empty:
            raise ValueError(f"Chưa có dữ liệu MART cho nhóm {block}. Hãy chạy pipeline.")

        if target_year is not None and target_month is not None:
            moc = f"{target_year:04d}-{target_month:02d}"
            group = group[group["period"] < moc].reset_index(drop=True)
            if group.empty or len(group) < SO_THANG_TOI_THIEU:
                raise ValueError(
                    f"Chỉ có {len(group)} tháng dữ liệu trước kỳ {moc} cho nhóm "
                    f"{block}: dưới ngưỡng {SO_THANG_TOI_THIEU} tháng, không đủ tin cậy "
                    "để chạy ensemble.")
            last = group.iloc[-1]
            ty, tm = target_year, target_month
        else:
            last = group.iloc[-1]
            ty, tm = _next_month(int(last["year"]), int(last["month"]))

        cfg = PRODUCTION_CONFIG
        wdf = self._weather_df(region)
        group_w = group.merge(wdf, on="period", how="left") if not wdf.empty else group

        # Ensemble khớp 1 bước sau điểm neo; kỳ đích xa hơn được đánh dấu ngoại suy nhiều bước.
        horizon = (ty - int(last["year"])) * 12 + (tm - int(last["month"]))
        gf = forecast_group_next(group_w, tm, cfg)
        base_group, lo, hi, n_resid = float(gf["point"]), gf["lower"], gf["upper"], gf["n_resid"]
        name_row = self._rows(
            "SELECT block_name FROM mart_monthly_cases_by_block "
            "WHERE block_code=:b LIMIT 1", {"b": block})
        return {
            "block": block,
            "block_name": name_row[0][0] if name_row else block,
            "region": region,
            "anchor_period": str(last["period"]),
            "target_period": f"{ty:04d}-{tm:02d}",
            "point": round(base_group, 1),
            "lower": (int(round(lo)) if lo is not None else None),
            "upper": (int(round(hi)) if hi is not None else None),
            "level": cfg.interval_level,
            "n_resid": n_resid,
            "interval_reason": (None if lo is not None else
                                "chưa đủ bước walk-forward để dựng khoảng (cần ≥ 8)"),
            "n_history_months": int(len(group)),
            "horizon_months": int(horizon),
            "horizon_note": (None if horizon == 1 else
                             f"Kỳ đích cách điểm neo {horizon} tháng, mô hình khớp 1 bước, "
                             "khoảng tin cậy chỉ đúng cho bước kế tiếp."),
            "weather_used": bool(gf["weather_used"]),
            "model": {"members_used": gf["members_used"], "members_failed": gf["members_failed"],
                      "weights": gf["weights"], "bias_factor": gf["bias_factor"],
                      "point_raw": round(gf["point_raw"], 1), "config": cfg.as_record()},
            # Cho nơi gọi tính "độ chính xác tại chỗ" mà không khớp lại.
            "walk_forward": gf.get("walk_forward"),
        }

    def group_series_fingerprint(self, block: str, region: str = TOAN_QUOC) -> str:
        """Dấu vân tay đầu vào dự báo nhóm (chuỗi ca, thời tiết, cấu hình), dùng làm khoá cache."""
        import hashlib, json
        g = self._group_df(block, region)
        w = self._weather_df(region)
        raw = json.dumps({
            "cases": [[str(p), float(c)] for p, c in zip(g["period"], g["cases"])] if not g.empty else [],
            "weather_n": int(len(w)),
            "weather_last": (str(w["period"].iloc[-1]) if not w.empty else None),
            "cfg": PRODUCTION_CONFIG.as_record(),
        }, sort_keys=True)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()
