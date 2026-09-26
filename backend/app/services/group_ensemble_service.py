# -*- coding: utf-8 -*-
"""Dự báo số ca theo nhóm ICD (tỉnh hoặc toàn quốc) cho trang Phân tích, cùng ensemble với backtest.
Tháng đích trong quá khứ chỉ học trên các tháng trước đó để tránh rò rỉ thời gian.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.forecasting.config import PRODUCTION_CONFIG
from app.forecasting.group_forecast import forecast_group_next
from app.models.disease_case import DiseaseCase
from app.models.environmental_data import EnvironmentalData
from app.utils.icd_groups import dieu_kien_benh

logger = logging.getLogger(__name__)

SO_THANG_TOI_THIEU = 18       # dưới ngưỡng này không chạy ensemble, trả None
SO_BUOC_DO_CHINH_XAC = 6      # số bước walk-forward cuối dùng tính "độ chính xác"


def _chuoi_thang(db: Session, disease: str, region: Optional[str]) -> pd.DataFrame:
    """Chuỗi tháng [period, year, month, cases, is_covid] cho nhóm/mã + vùng."""
    q = db.query(
        extract("year", DiseaseCase.recorded_at).label("y"),
        extract("month", DiseaseCase.recorded_at).label("m"),
        func.sum(DiseaseCase.case_count).label("cases"),
    ).filter(dieu_kien_benh(DiseaseCase, disease))
    if region:
        from app.utils.province_alias import province_aliases
        q = q.filter(DiseaseCase.location.in_(province_aliases(region)))
    rows = q.group_by("y", "m").order_by("y", "m").all()
    if not rows:
        return pd.DataFrame(columns=["period", "year", "month", "cases", "is_covid"])
    df = pd.DataFrame(rows, columns=["year", "month", "cases"]).astype(
        {"year": int, "month": int, "cases": float})
    df["period"] = df["year"].astype(str) + "-" + df["month"].map("{:02d}".format)
    df["is_covid"] = df["year"].isin((2020, 2021))
    return df[["period", "year", "month", "cases", "is_covid"]]


def _thoi_tiet_thang(db: Session, region: Optional[str]) -> pd.DataFrame:
    """Trung bình tháng [period, temp, humidity, rainfall], khớp WCOLS của HarmonicPoissonForecaster."""
    q = db.query(
        extract("year", EnvironmentalData.recorded_at).label("y"),
        extract("month", EnvironmentalData.recorded_at).label("m"),
        func.avg(EnvironmentalData.temperature).label("temp"),
        func.avg(EnvironmentalData.humidity).label("humidity"),
        func.avg(EnvironmentalData.rainfall).label("rainfall"),
    )
    if region:
        from app.utils.province_alias import province_aliases
        q = q.filter(EnvironmentalData.location.in_(province_aliases(region)))
    rows = q.group_by("y", "m").all()
    if not rows:
        return pd.DataFrame(columns=["period", "temp", "humidity", "rainfall"])
    w = pd.DataFrame(rows, columns=["year", "month", "temp", "humidity", "rainfall"])
    w["period"] = w["year"].astype(int).astype(str) + "-" + \
        w["month"].astype(int).map("{:02d}".format)
    for c in ("temp", "humidity", "rainfall"):
        w[c] = pd.to_numeric(w[c], errors="coerce")
    return w[["period", "temp", "humidity", "rainfall"]]


def _ky_du_lieu_moi_nhat(db: Session) -> Optional[str]:
    """Tháng mới nhất trong disease_cases ("YYYY-MM"), tra toàn bảng để mọi khu vực cắt cùng một mốc."""
    moi_nhat = db.query(func.max(DiseaseCase.recorded_at)).scalar()
    if moi_nhat is None:
        return None
    return f"{moi_nhat.year}-{moi_nhat.month:02d}"


def du_bao_nhom(db: Session, disease: str, region: Optional[str],
                target_year: int, target_month: int) -> Optional[Dict[str, Any]]:
    """Dự báo 1 tháng cho nhóm/mã × vùng; None khi không đủ dữ liệu."""
    df = _chuoi_thang(db, disease, region)
    moc = f"{target_year}-{target_month:02d}"

    # Tháng mới nhất coi là chưa chốt (đồng bộ HIS mới nạp một phần), loại khỏi chuỗi huấn luyện
    # theo mốc lịch chung, không bỏ dòng cuối mỗi chuỗi.
    ky_moi_nhat = _ky_du_lieu_moi_nhat(db)
    gioi_han = min(moc, ky_moi_nhat) if ky_moi_nhat else moc
    hist = df[df["period"] < gioi_han].reset_index(drop=True)
    if ky_moi_nhat and gioi_han == ky_moi_nhat:
        logger.info(
            "Bỏ tháng %s (chưa chốt số) khỏi chuỗi huấn luyện %s/%s.",
            ky_moi_nhat, disease, region or "toàn quốc",
        )
    if len(hist) < SO_THANG_TOI_THIEU:
        logger.info("Chuỗi %s/%s chỉ có %d tháng trước %s — không dùng ensemble.",
                    disease, region or "toàn quốc", len(hist), moc)
        return None

    w = _thoi_tiet_thang(db, region)
    if not w.empty:
        hist = hist.merge(w, on="period", how="left")
    dung_thoi_tiet = (PRODUCTION_CONFIG.use_weather and (not w.empty)
                      and hist["temp"].notna().sum() >= PRODUCTION_CONFIG.weather_min_months)

    # Cùng đường với backtest; walk-forward bên trong cho "độ chính xác tại chỗ".
    gf = forecast_group_next(hist, target_month, PRODUCTION_CONFIG)
    predicted = int(round(max(0.0, float(gf["point"]))))

    wf = gf.get("walk_forward") or {}
    acts = [float(a) for a in wf.get("actual", [])][-SO_BUOC_DO_CHINH_XAC:]
    preds = [float(p) for p in wf.get("pred", [])][-SO_BUOC_DO_CHINH_XAC:]
    sai_so = [abs(p - a) for p, a in zip(preds, acts)]
    accuracy = None
    if sai_so and sum(acts) > 0:
        wape = 100.0 * sum(sai_so) / sum(acts)
        accuracy = {
            "mae": round(float(np.mean(sai_so)), 2),
            "wape": round(wape, 1),
            "accuracy_pct": round(max(0.0, 100.0 - wape), 1),
            "n_steps": len(sai_so),
        }
    n = len(hist)

    return {
        "predicted": predicted,
        "model_used": "group_ensemble_v1",
        "use_weather": dung_thoi_tiet,
        "n_history_months": int(n),
        "accuracy": accuracy,
        "interval": {"lower": (int(round(gf["lower"])) if gf["lower"] is not None else None),
                     "upper": (int(round(gf["upper"])) if gf["upper"] is not None else None),
                     "level": gf["level"], "n_resid": gf["n_resid"]},
        "model": {"members_used": gf["members_used"], "members_failed": gf["members_failed"],
                  "weights": gf["weights"], "bias_factor": gf["bias_factor"],
                  "point_raw": round(gf["point_raw"], 1),
                  "config": PRODUCTION_CONFIG.as_record()},
    }
