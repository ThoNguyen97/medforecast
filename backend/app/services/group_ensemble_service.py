# -*- coding: utf-8 -*-
"""Dự báo số ca theo NHÓM ICD bằng ensemble đã kiểm chứng — engine cho trang
Phân tích & Dự báo.

VÌ SAO CẦN SERVICE NÀY
Trang Phân tích trước đây tính bằng heuristic "trung bình cùng kỳ 5 năm × hệ
số" rồi ghi đè bằng MonthlyForecaster — cả hai đều tựa vào mức trung bình
nhiều năm, nên với chuỗi có DỊCH CHUYỂN MỨC NỀN (J09-J18 tăng 3,66×) chúng bị
kéo tụt về quá khứ. Đo trên tháng đã có kết quả: dự báo 65 ca cho tháng thực tế
~110 ca — hụt ~40%.

Ensemble ở app/forecasting/models.py (SeasonalTrend + Poisson + Harmonic-thời
-tiết + SARIMAX) học xu hướng + mùa vụ + biến ngoại sinh trên TOÀN chuỗi, đã
kiểm walk-forward 66–67 bước trên dữ liệu HIS thật: MASE mức nhóm 0,51–0,65,
thời tiết giảm 28–33% MAE cho hai nhóm nhạy thời tiết. Cùng engine với trang
Kế hoạch nhập kho — hai màn hình hết cảnh mỗi nơi một số.

CHỐNG RÒ RỈ THỜI GIAN: khi tháng đích nằm trong quá khứ (người dùng chọn để
đối chiếu), mô hình CHỈ học trên các tháng trước tháng đích — dự báo "như thể
chưa biết kết quả", so sánh mới công bằng.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.forecasting.models import build_default_ensemble
from app.models.disease_case import DiseaseCase
from app.models.environmental_data import EnvironmentalData
from app.utils.icd_groups import dieu_kien_benh

logger = logging.getLogger(__name__)

SO_THANG_TOI_THIEU = 18       # dưới mức này ensemble không đáng tin → trả None
SO_BUOC_DO_CHINH_XAC = 6      # backtest nhanh N bước cuối để hiện "độ chính xác"


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
    """Trung bình tháng [period, temp, humidity, rainfall] — đúng 3 cột mà
    HarmonicPoissonForecaster dùng (models.py WCOLS)."""
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
    """Tháng mới nhất có mặt trong disease_cases, dạng "YYYY-MM".

    Tra trên TOÀN BỘ bảng (không lọc bệnh/khu vực) vì mức độ đầy đủ của dữ
    liệu là tính chất của đợt đồng bộ HIS, không phải của riêng chuỗi nào.
    Nhờ vậy mọi khu vực đều bị cắt tại cùng một mốc lịch.
    """
    moi_nhat = db.query(func.max(DiseaseCase.recorded_at)).scalar()
    if moi_nhat is None:
        return None
    return f"{moi_nhat.year}-{moi_nhat.month:02d}"


def du_bao_nhom(db: Session, disease: str, region: Optional[str],
                target_year: int, target_month: int) -> Optional[Dict[str, Any]]:
    """Dự báo 1 tháng cho nhóm/mã × vùng. None = không đủ dữ liệu (để caller
    rơi về fallback thay vì nhận một con số kém tin cậy)."""
    df = _chuoi_thang(db, disease, region)
    moc = f"{target_year}-{target_month:02d}"

    # Tháng mới nhất luôn bị coi là CHƯA CHỐT SỐ và bị loại khỏi chuỗi huấn
    # luyện. Lý do: đợt đồng bộ HIS gần nhất thường mới nạp một phần tháng đó,
    # nên nó vào chuỗi như một cú sụt giả và kéo tụt dự báo.
    #
    # Đo thật (J00-J06, T10/2026): T9/2026 toàn quốc mới có 1 ca. Giữ lại thì
    # toàn quốc dự báo 189 ca trong khi riêng TP.HCM 193 ca — phần lớn hơn
    # toàn thể. Nguyên nhân: TP.HCM tháng đó KHÔNG có dòng nào nên chuỗi của
    # nó không chứa điểm rác, còn chuỗi toàn quốc thì có. Bỏ tháng cuối:
    # toàn quốc 244 / TP.HCM 197 — đúng tỷ lệ lịch sử ~78%.
    #
    # PHẢI cắt theo mốc lịch CHUNG chứ không phải "bỏ dòng cuối mỗi chuỗi":
    # chuỗi thiếu hẳn tháng đó sẽ bị cắt nhầm một tháng lành và lệch lại tái
    # diễn. Với tháng đích nằm trong quá khứ thì `moc` nhỏ hơn, ràng buộc
    # chống rò rỉ thời gian vẫn giữ nguyên hiệu lực.
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
    dung_thoi_tiet = (not w.empty) and hist["temp"].notna().sum() >= 12

    pred = build_default_ensemble(use_weather=dung_thoi_tiet).fit(hist).predict(target_month)
    predicted = int(round(max(0.0, pred)))

    # Backtest nhanh N bước cuối cùng điều kiện (fit lại từng bước, không nhìn
    # tương lai) → WAPE cho ô "độ chính xác mô hình". Không phải con số chính
    # thức của báo cáo (con số đó từ run_eval walk-forward đầy đủ) — đây là
    # thước đo tại-chỗ cho đúng chuỗi người dùng đang xem.
    sai_so, thuc_te = [], []
    n = len(hist)
    for t in range(max(SO_THANG_TOI_THIEU, n - SO_BUOC_DO_CHINH_XAC), n):
        h, dong = hist.iloc[:t], hist.iloc[t]
        try:
            p = build_default_ensemble(use_weather=dung_thoi_tiet).fit(h).predict(int(dong["month"]))
            sai_so.append(abs(float(p) - float(dong["cases"])))
            thuc_te.append(float(dong["cases"]))
        except Exception:
            continue

    accuracy = None
    if sai_so and sum(thuc_te) > 0:
        wape = 100.0 * sum(sai_so) / sum(thuc_te)
        accuracy = {
            "mae": round(float(np.mean(sai_so)), 2),
            "wape": round(wape, 1),
            "accuracy_pct": round(max(0.0, 100.0 - wape), 1),
            "n_steps": len(sai_so),
        }

    return {
        "predicted": predicted,
        "model_used": "group_ensemble_v1",
        "use_weather": dung_thoi_tiet,
        "n_history_months": int(n),
        "accuracy": accuracy,
    }
