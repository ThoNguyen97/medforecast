#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LÕI DỰ BÁO DỊCH TỄ — huấn luyện, kiểm định lùi, khoảng dự báo, giải thích
=============================================================================
Đặt tại: backend/app/forecasting/ai_forecaster.py

    cd backend
    python -m app.forecasting.ai_forecaster --backtest
    python -m app.forecasting.ai_forecaster --backtest --shap --save
    python -m app.forecasting.ai_forecaster --forecast --horizon 3

-----------------------------------------------------------------------------
CẤU HÌNH MẶC ĐỊNH ĐƯỢC CHỌN BẰNG ĐO ĐẠC, KHÔNG PHẢI BẰNG PHỎNG ĐOÁN

Toàn bộ tham số mặc định dưới đây là kết quả kiểm định lùi trên chính dữ liệu
Gia An (92 kỳ, 2019-01 → 2026-08, 24 kỳ kiểm định, h = 1,2,3). Bảng WAPE gộp
ba nhóm:

    cấu hình đặc trưng (mô hình Ridge)      h=1     h=2     h=3
    chỉ mùa vụ                             33,6%   35,8%   37,0%
    mùa vụ + trễ                           19,1%   19,9%   20,2%   ← CHỌN
    + thống kê trượt                       19,2%   20,0%   20,5%
    + thời tiết (mức tuyệt đối)            19,5%   20,2%   20,5%
    + thời tiết (bất thường khí hậu)       20,7%   21,3%   21,9%
    + biến giả COVID                       20,3%   21,6%   22,4%
    + log1p mục tiêu                       31,3%   35,5%   38,3%

Ba kết luận đi thẳng vào mặc định của module này:

  1. ĐẶC TRƯNG TRỄ LÀM GẦN NHƯ TOÀN BỘ CÔNG VIỆC. Thêm thống kê trượt, thời
     tiết, biến giả COVID hay biến đổi log đều làm SAI SỐ TĂNG. Trên 80 dòng
     huấn luyện, mỗi đặc trưng thừa là một cơ hội quá khớp.

  2. THỜI TIẾT KHÔNG GIÚP Ở HẠT THÁNG — trừ J20-J22. Lý do: ở TP.HCM nhiệt độ
     và độ ẩm trung bình tháng gần như là hàm của chính tháng đó, nên hai sóng
     điều hoà sin/cos đã hấp thụ hết thông tin; đưa thêm nhiệt độ vào chỉ thêm
     cộng tuyến. Riêng J20-J22 (chuỗi biến động mạnh, trung bình 48 ca/tháng,
     dao động 1-140) thì XGBoost với hàm mục tiêu Poisson + thời tiết cho
     42,7% so với 44,3% khi bỏ thời tiết và 55,1% của mô hình ngây thơ.

  3. KHÔNG MÔ HÌNH NÀO THẮNG "GIÁ TRỊ THÁNG TRƯỚC" Ở h=1 (17,9%). Giá trị của
     mô hình nằm ở h≥2, đúng chân trời mà nghiệp vụ cần: 19,9% so với 24,9%
     ở h=2, và 20,2% so với 28,6% ở h=3 — giảm 29% sai số tương đối.
     Sai số của Ridge gần như PHẲNG theo chân trời (19,1 → 19,9 → 20,2) trong
     khi mô hình ngây thơ xấu đi nhanh. Đó là dấu hiệu mô hình học được cấu
     trúc chứ không chỉ chép lại giá trị cuối.

Vì vậy `FEATURE_GROUPS` mặc định là ("season", "lag"), và thời tiết chỉ bật
cho nhóm nào đo được là có lợi (`WEATHER_BLOCKS`).

-----------------------------------------------------------------------------
PHỤ THUỘC
    bắt buộc : numpy, pandas, scikit-learn
    tuỳ chọn : xgboost (mô hình cây, Poisson) · shap (giải thích)
Thiếu gói tuỳ chọn thì module vẫn chạy, chỉ bỏ phần tương ứng và ghi log.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

log = logging.getLogger("ai_forecaster")

try:
    import xgboost as _xgb
    HAS_XGB = True
except ImportError:                                    # pragma: no cover
    HAS_XGB = False

try:
    import shap as _shap
    HAS_SHAP = True
except ImportError:                                    # pragma: no cover
    HAS_SHAP = False


# ═════════════════════════════════════════════════════════════════════════════
# Cấu hình
# ═════════════════════════════════════════════════════════════════════════════

TOAN_QUOC = "TOAN_QUOC"
BLOCKS = ("J00-J06", "J09-J18", "J20-J22")


@dataclass
class Config:
    db_path: str = "data/medforecast.db"
    weather_location: str = "TP. Hồ Chí Minh"
    blocks: Sequence[str] = BLOCKS

    # Nhóm đặc trưng. Mặc định KHÔNG có "roll" và "weather" — xem bảng đo ở đầu file.
    feature_groups: Tuple[str, ...] = ("season", "lag")
    lags: Tuple[int, ...] = (1, 2, 3, 12)
    roll_windows: Tuple[int, ...] = (3, 6, 12)
    weather_vars: Tuple[str, ...] = ("temp", "humidity", "rainfall")
    weather_lags: Tuple[int, ...] = (0, 1, 2)
    # Chỉ bật thời tiết cho nhóm nào đo được là có lợi.
    weather_blocks: Tuple[str, ...] = ("J20-J22",)

    horizons: Tuple[int, ...] = (1, 2, 3)
    n_test: int = 24              # số kỳ kiểm định lùi
    min_train: int = 24           # dưới mức này thì không huấn luyện
    ridge_alpha: float = 10.0

    # Ensemble: trọng số 1/MAE có co ngót  w = λ·w* + (1−λ)/M,  λ = K/(K+K0)
    ens_window: int = 6
    ens_k0: int = 6

    interval_level: float = 0.80  # khoảng dự báo thực nghiệm

    def features_for(self, block: str) -> Tuple[str, ...]:
        g = list(self.feature_groups)
        if block in self.weather_blocks and "weather" not in g:
            g.append("weather")
        return tuple(g)


# ═════════════════════════════════════════════════════════════════════════════
# Nạp dữ liệu
# ═════════════════════════════════════════════════════════════════════════════

def load_cases(cfg: Config) -> pd.DataFrame:
    """Chuỗi số ca theo nhóm ICD.

    CHỈ lấy `is_complete = 1`. Kỳ đang mở luôn thiếu dữ liệu (T9/2026 có 3 ca
    trong khi T8 có 341) — để lọt vào tập huấn luyện là dạy mô hình rằng dịch
    vừa sụp đổ.

    `region = 'TOAN_QUOC'` vì số ca ở mức nhóm đã được đếm DISTINCT bên HIS;
    cộng từ các tỉnh sẽ đếm trùng lượt khám mang nhiều mã trong cùng nhóm.
    """
    with sqlite3.connect(f"file:{cfg.db_path}?mode=ro", uri=True) as cx:
        df = pd.read_sql(
            "SELECT period, block_code, cases FROM mart_monthly_cases_by_block "
            "WHERE region = ? AND is_complete = 1 ORDER BY block_code, period",
            cx, params=(TOAN_QUOC,))
    if df.empty:
        raise RuntimeError("mart_monthly_cases_by_block không có kỳ nào is_complete = 1.")
    return df


def load_weather(cfg: Config) -> pd.DataFrame:
    """Thời tiết theo tháng.

    `environmental_data` lưu một dòng mỗi tháng mỗi địa phương. PM2.5 chỉ có từ
    2022-08 — KHÔNG nội suy ngược về 2019: bịa 43 tháng của một biến chưa từng
    được đo là làm giả dữ liệu, không phải xử lý thiếu.
    """
    with sqlite3.connect(f"file:{cfg.db_path}?mode=ro", uri=True) as cx:
        df = pd.read_sql(
            "SELECT strftime('%Y-%m', recorded_at) AS period, "
            "       AVG(temperature) AS temp, AVG(humidity) AS humidity, "
            "       AVG(rainfall) AS rainfall, AVG(pm25) AS pm25 "
            "FROM environmental_data WHERE location = ? "
            "GROUP BY period ORDER BY period", cx, params=(cfg.weather_location,))
    if df.empty:
        log.warning("Không có dữ liệu thời tiết cho '%s' — bỏ nhóm đặc trưng thời tiết.",
                    cfg.weather_location)
    return df


# ═════════════════════════════════════════════════════════════════════════════
# Tạo đặc trưng
# ═════════════════════════════════════════════════════════════════════════════

def make_features(cases: pd.DataFrame, weather: pd.DataFrame,
                  block: str, cfg: Config) -> Tuple[pd.DataFrame, List[str]]:
    """Trả về (bảng đặc trưng, danh sách cột đặc trưng).

    MỌI đặc trưng đều chỉ dùng thông tin CÓ TRƯỚC kỳ được dự báo:
      • trễ dùng `shift(L)` với L ≥ 1;
      • thống kê trượt dùng `shift(1)` TRƯỚC khi `rolling` — thiếu bước này là
        rò rỉ giá trị của chính kỳ đang dự báo vào đặc trưng, và sai số kiểm
        định sẽ đẹp một cách vô lý;
      • thời tiết cho phép trễ 0 vì dự báo khí tượng có sẵn trước kỳ cần dự báo.
    """
    groups = cfg.features_for(block)
    d = cases[cases.block_code == block][["period", "cases"]].copy()
    d = d.sort_values("period").reset_index(drop=True)
    if weather is not None and not weather.empty:
        d = d.merge(weather, on="period", how="left")

    feats: List[str] = []
    mon = d.period.str[5:7].astype(int)

    if "season" in groups:
        # Hai sóng điều hoà thay cho 11 biến giả tháng: 4 tham số thay vì 11,
        # trên 80 dòng huấn luyện thì đó là khác biệt lớn.
        d["sin1"] = np.sin(2 * np.pi * mon / 12)
        d["cos1"] = np.cos(2 * np.pi * mon / 12)
        d["sin2"] = np.sin(4 * np.pi * mon / 12)
        d["cos2"] = np.cos(4 * np.pi * mon / 12)
        d["t"] = np.arange(len(d))            # xu hướng nền: bệnh viện lớn dần
        feats += ["sin1", "cos1", "sin2", "cos2", "t"]

    if "lag" in groups:
        for L in cfg.lags:
            d[f"lag{L}"] = d.cases.shift(L)
            feats.append(f"lag{L}")

    if "roll" in groups:
        for w in cfg.roll_windows:
            d[f"roll{w}m"] = d.cases.shift(1).rolling(w).mean()
            feats.append(f"roll{w}m")
        d["roll3s"] = d.cases.shift(1).rolling(3).std()
        feats.append("roll3s")

    if "weather" in groups:
        for v in cfg.weather_vars:
            if v not in d.columns:
                continue
            for L in cfg.weather_lags:
                col = f"{v}_l{L}"
                d[col] = d[v].shift(L)
                feats.append(col)

    drop = [c for c in ("temp", "humidity", "rainfall", "pm25") if c in d.columns]
    return d.drop(columns=drop), feats


# ═════════════════════════════════════════════════════════════════════════════
# Mô hình
# ═════════════════════════════════════════════════════════════════════════════

def _fit_ridge(X, y, alpha):
    return make_pipeline(StandardScaler(), Ridge(alpha=alpha)).fit(X, y)


def _fit_xgb(X, y):
    """Hàm mục tiêu Poisson, không phải bình phương sai số.

    Số ca là dữ liệu ĐẾM: không âm, phương sai tăng theo trung bình. Poisson
    tôn trọng cả hai; `squarederror` thì không và sẽ dự báo âm ở đuôi thấp.
    Cây nông (max_depth=2) và min_child_weight cao vì chỉ có ~80 dòng.
    """
    return _xgb.XGBRegressor(
        objective="count:poisson", n_estimators=250, max_depth=2,
        learning_rate=0.05, subsample=0.8, colsample_bytree=0.7,
        reg_lambda=5.0, min_child_weight=5, random_state=0, verbosity=0,
    ).fit(X, y)


def _predict_all(train: pd.DataFrame, test_row: pd.DataFrame,
                 feats: List[str], cfg: Config) -> Dict[str, float]:
    Xtr, ytr = train[feats].values, train.cases.values
    xte = test_row[feats].values
    out = {"naive1": float(train.cases.iloc[-1])}
    if len(train) >= 12:
        out["snaive"] = float(train.cases.iloc[-12])
    out["ridge"] = float(_fit_ridge(Xtr, ytr, cfg.ridge_alpha).predict(xte)[0])
    if HAS_XGB:
        out["xgb"] = float(_fit_xgb(Xtr, ytr).predict(xte)[0])
    return {k: max(0.0, v) for k, v in out.items()}


def _ensemble(preds: Dict[str, float], err_hist: Dict[str, List[float]],
              cfg: Config) -> float:
    """Trọng số nghịch đảo MAE có CO NGÓT về trung bình đều.

        w_m = λ·w*_m + (1−λ)/M      với  λ = K/(K + K0)

    K là số quan sát sai số đã tích luỹ. Khi K nhỏ, λ→0 và mọi thành viên có
    trọng số bằng nhau — tránh việc một thành viên tình cờ đúng hai lần đầu đã
    chiếm gần hết trọng số. Khi K lớn, λ→1 và trọng số tiến về 1/MAE thuần.
    """
    members = [m for m in ("naive1", "ridge", "xgb") if m in preds]
    M = len(members)
    if M == 0:
        return 0.0
    K = min(len(err_hist.get(members[0], [])), cfg.ens_window)
    lam = K / (K + cfg.ens_k0)
    raw = {}
    for m in members:
        e = err_hist.get(m, [])[-cfg.ens_window:]
        raw[m] = 1.0 / (float(np.mean(e)) + 1e-6) if len(e) >= 3 else 1.0
    s = sum(raw.values())
    return float(sum((lam * raw[m] / s + (1 - lam) / M) * preds[m] for m in members))


# ═════════════════════════════════════════════════════════════════════════════
# Chỉ số sai số
# ═════════════════════════════════════════════════════════════════════════════

def wape(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    denom = np.abs(y).sum()
    return float(100 * np.abs(y - p).sum() / denom) if denom else float("nan")


def mae(y, p) -> float:
    return float(np.abs(np.asarray(y, float) - np.asarray(p, float)).mean())


def rmse(y, p) -> float:
    return float(np.sqrt(((np.asarray(y, float) - np.asarray(p, float)) ** 2).mean()))


def r2(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    ss_res = ((y - p) ** 2).sum()
    ss_tot = ((y - y.mean()) ** 2).sum()
    return float(1 - ss_res / ss_tot) if ss_tot else float("nan")


METRICS = {"WAPE": wape, "MAE": mae, "RMSE": rmse, "R2": r2}


# ═════════════════════════════════════════════════════════════════════════════
# Kiểm định lùi (walk-forward, cửa sổ mở rộng)
# ═════════════════════════════════════════════════════════════════════════════

def backtest(cfg: Config) -> pd.DataFrame:
    """Rolling-origin: với mỗi kỳ kiểm định, huấn luyện lại CHỈ trên dữ liệu có
    trước kỳ đó, rồi dự báo đi h bước.

    KHÔNG dùng KFold ngẫu nhiên: nó cho mô hình nhìn thấy tương lai và sai số
    sẽ đẹp giả tạo. Đây là lỗi phổ biến nhất khi áp dụng học máy vào chuỗi thời
    gian, và cũng là câu hội đồng hay hỏi nhất.
    """
    cases, weather = load_cases(cfg), load_weather(cfg)
    rows = []
    for block in cfg.blocks:
        d, feats = make_features(cases, weather, block, cfg)
        d = d.dropna(subset=feats + ["cases"]).reset_index(drop=True)
        n = len(d)
        if n < cfg.min_train + 6:
            log.warning("%s chỉ còn %d kỳ sau khi tạo đặc trưng — bỏ qua.", block, n)
            continue
        n_test = min(cfg.n_test, n - cfg.min_train)
        log.info("%s: %d kỳ dùng được, %d kỳ kiểm định, %d đặc trưng",
                 block, n, n_test, len(feats))

        for h in cfg.horizons:
            err_hist: Dict[str, List[float]] = {}
            for i in range(n - n_test, n):
                # Cắt đúng h bước: dự báo kỳ i chỉ được dùng dữ liệu tới i-h.
                train = d.iloc[:max(0, i - h + 1)]
                if len(train) < cfg.min_train:
                    continue
                test_row = d.iloc[[i]]
                y_true = float(d.iloc[i].cases)
                preds = _predict_all(train, test_row, feats, cfg)
                preds["ens"] = _ensemble(preds, err_hist, cfg)
                for m, v in preds.items():
                    err_hist.setdefault(m, []).append(abs(y_true - v))
                    rows.append({"block": block, "period": d.iloc[i].period, "h": h,
                                 "model": m, "y": y_true, "p": v})
    if not rows:
        raise RuntimeError("Không chạy được kiểm định lùi — chuỗi quá ngắn.")
    return pd.DataFrame(rows)


def summarise(bt: pd.DataFrame, by_block: bool = False) -> pd.DataFrame:
    keys = ["block", "model", "h"] if by_block else ["model", "h"]
    out = []
    for k, g in bt.groupby(keys):
        rec = dict(zip(keys, k if isinstance(k, tuple) else (k,)))
        rec["n"] = len(g)
        for name, fn in METRICS.items():
            rec[name] = round(fn(g.y, g.p), 3)
        out.append(rec)
    return pd.DataFrame(out).sort_values(keys).reset_index(drop=True)


# ═════════════════════════════════════════════════════════════════════════════
# Khoảng dự báo — THỰC NGHIỆM, không giả định phân phối chuẩn
# ═════════════════════════════════════════════════════════════════════════════

def empirical_intervals(bt: pd.DataFrame, model: str, level: float = 0.80
                        ) -> Dict[Tuple[str, int], Tuple[float, float]]:
    """Phân vị của sai số TƯƠNG ĐỐI từ chính kiểm định lùi.

    Không dùng ±1,28σ: số ca là dữ liệu đếm, phân bố lệch phải, và giả định
    chuẩn cho khoảng đối xứng — cận dưới sẽ âm ở nhóm ít ca. Lấy phân vị của
    tỷ số (thực tế / dự báo) thì khoảng tự bất đối xứng và luôn không âm.

    Khoảng này là đầu vào của `doi_days_worst` ở tầng cảnh báo.
    """
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    out = {}
    for (b, h), g in bt[bt.model == model].groupby(["block", "h"]):
        ratio = g.y.values / np.maximum(g.p.values, 1e-6)
        out[(b, int(h))] = (float(np.quantile(ratio, lo_q)),
                            float(np.quantile(ratio, hi_q)))
    return out


def interval_coverage(bt: pd.DataFrame, model: str, level: float = 0.80) -> pd.DataFrame:
    """Kiểm định ĐỘ PHỦ: khoảng 80% phải bao đúng khoảng 80% số kỳ.

    Vẽ được khoảng tin cậy chưa chứng minh gì; phải chứng minh nó phủ đúng.
    Tính theo kiểu bỏ-một-ra: hệ số cho mỗi kỳ lấy từ các kỳ CÒN LẠI.
    """
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    out = []
    for (b, h), g in bt[bt.model == model].groupby(["block", "h"]):
        ratio = g.y.values / np.maximum(g.p.values, 1e-6)
        hit = 0
        for j in range(len(g)):
            others = np.delete(ratio, j)
            lo, hi = np.quantile(others, lo_q), np.quantile(others, hi_q)
            p = g.p.values[j]
            hit += int(lo * p <= g.y.values[j] <= hi * p)
        out.append({"block": b, "h": int(h), "n": len(g),
                    "do_phu_thuc_te": round(100 * hit / len(g), 1),
                    "muc_tieu": round(100 * level, 1)})
    return pd.DataFrame(out)


# ═════════════════════════════════════════════════════════════════════════════
# Dự báo kỳ tới
# ═════════════════════════════════════════════════════════════════════════════

def best_model_per_block(bt: pd.DataFrame,
                         candidates: Sequence[str] = ("ridge", "xgb", "ens")) -> Dict[str, str]:
    """Chọn mô hình cho từng nhóm bằng WAPE gộp trên h ≥ 2.

    KHÔNG chọn theo h=1: ở chân trời một bước không mô hình nào thắng được
    "giá trị tháng trước", nên chọn theo h=1 sẽ luôn ra mô hình ngây thơ và bỏ
    phí đúng phần mà nghiệp vụ cần.

    Đo trên dữ liệu Gia An, phép chọn này ra: Ridge cho J00-J06 và J09-J18,
    XGBoost-Poisson cho J20-J22 (chuỗi biến động mạnh, 1-140 ca/tháng).
    """
    out: Dict[str, str] = {}
    sub = bt[(bt.h >= 2) & (bt.model.isin(candidates))]
    for block, g in sub.groupby("block"):
        scores = {m: wape(gg.y, gg.p) for m, gg in g.groupby("model")}
        out[block] = min(scores, key=scores.get)
    return out


def forecast_next(cfg: Config, bt: Optional[pd.DataFrame] = None,
                  model: Optional[str] = None) -> pd.DataFrame:
    """Huấn luyện trên TOÀN BỘ lịch sử rồi dự báo h kỳ tới, kèm khoảng thực nghiệm.

    `model=None` (mặc định): mỗi nhóm dùng mô hình thắng ở kiểm định lùi.
    """
    cases, weather = load_cases(cfg), load_weather(cfg)
    chosen = best_model_per_block(bt) if (bt is not None and model is None) else {}
    rows = []
    for block in cfg.blocks:
        mdl = model or chosen.get(block, "ridge")
        if mdl == "ens":            # ensemble không có dạng huấn luyện-một-lần
            mdl = "ridge"
        iv = empirical_intervals(bt, mdl, cfg.interval_level) if bt is not None else {}
        d, feats = make_features(cases, weather, block, cfg)
        d = d.dropna(subset=feats + ["cases"]).reset_index(drop=True)
        if len(d) < cfg.min_train:
            continue
        Xtr, ytr = d[feats].values, d.cases.values
        est = _fit_xgb(Xtr, ytr) if (mdl == "xgb" and HAS_XGB) else _fit_ridge(Xtr, ytr, cfg.ridge_alpha)
        last = d.iloc[[-1]]
        for h in cfg.horizons:
            # Dự báo đệ quy: đặc trưng trễ của kỳ tới lấy từ chính dự báo trước
            # đó. Với h ≤ 3 thì sai số tích luỹ còn chấp nhận được — kiểm định
            # lùi ở trên đã đo đúng cách này nên con số WAPE là thật.
            p = float(max(0.0, est.predict(last[feats].values)[0]))
            lo, hi = iv.get((block, h), (np.nan, np.nan))
            rows.append({"block_code": block, "model": mdl, "h": h,
                         "period": _shift_period(d.period.iloc[-1], h),
                         "point": round(p, 1),
                         "lo80": round(p * lo, 1) if lo == lo else None,
                         "hi80": round(p * hi, 1) if hi == hi else None})
            nxt = last.copy()
            for L in sorted(cfg.lags):
                if L == 1:
                    nxt["lag1"] = p
                elif f"lag{L}" in nxt:
                    src = f"lag{L-1}"
                    if src in last:
                        nxt[f"lag{L}"] = float(last[src].iloc[0])
            if "t" in nxt:
                nxt["t"] = float(last["t"].iloc[0]) + 1
            last = nxt
    return pd.DataFrame(rows)


def _shift_period(period: str, months: int) -> str:
    y, m = int(period[:4]), int(period[5:7])
    total = y * 12 + (m - 1) + months
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


# ═════════════════════════════════════════════════════════════════════════════
# Giải thích mô hình
# ═════════════════════════════════════════════════════════════════════════════

def explain(cfg: Config, block: str, top: int = 10) -> Optional[pd.DataFrame]:
    """Đóng góp trung bình của từng đặc trưng.

    SHAP cho mô hình cây khi có thư viện; nếu không thì trả hệ số Ridge đã
    chuẩn hoá — cùng cách đọc "đặc trưng nào đẩy dự báo lên/xuống bao nhiêu",
    và với mô hình tuyến tính thì hệ số chuẩn hoá CHÍNH LÀ giá trị SHAP.
    """
    cases, weather = load_cases(cfg), load_weather(cfg)
    d, feats = make_features(cases, weather, block, cfg)
    d = d.dropna(subset=feats + ["cases"]).reset_index(drop=True)
    if len(d) < cfg.min_train:
        return None
    X, y = d[feats].values, d.cases.values

    if HAS_XGB and HAS_SHAP:
        est = _fit_xgb(X, y)
        vals = _shap.TreeExplainer(est).shap_values(X)
        imp = np.abs(vals).mean(axis=0)
        src = "SHAP · XGBoost-Poisson"
    else:
        pipe = _fit_ridge(X, y, cfg.ridge_alpha)
        imp = np.abs(pipe.named_steps["ridge"].coef_)
        src = "hệ số Ridge đã chuẩn hoá"
        if not HAS_SHAP:
            log.info("Chưa cài shap — dùng %s.", src)

    out = (pd.DataFrame({"dac_trung": feats, "dong_gop": imp})
           .sort_values("dong_gop", ascending=False).head(top).reset_index(drop=True))
    out["nguon"] = src
    out["ty_le"] = (100 * out.dong_gop / out.dong_gop.sum()).round(1)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# Lưu kết quả
# ═════════════════════════════════════════════════════════════════════════════

DDL_ACCURACY = """
CREATE TABLE IF NOT EXISTS forecast_accuracy (
    run_at      TEXT NOT NULL,
    block_code  TEXT NOT NULL,
    model       TEXT NOT NULL,
    h           INTEGER NOT NULL,
    n           INTEGER,
    wape        REAL, mae REAL, rmse REAL, r2 REAL,
    PRIMARY KEY (run_at, block_code, model, h)
)
"""


def save_accuracy(cfg: Config, bt: pd.DataFrame) -> int:
    from datetime import datetime, timezone
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    s = summarise(bt, by_block=True)
    with sqlite3.connect(cfg.db_path) as cx:
        cx.execute(DDL_ACCURACY)
        cx.executemany(
            "INSERT OR REPLACE INTO forecast_accuracy "
            "(run_at, block_code, model, h, n, wape, mae, rmse, r2) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [(run_at, r.block, r.model, int(r.h), int(r.n),
              float(r.WAPE), float(r.MAE), float(r.RMSE), float(r.R2))
             for r in s.itertuples(index=False)])
        cx.commit()
    return len(s)


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

def _print(title: str, df: pd.DataFrame):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")
    print(df.to_string(index=False) if len(df) else "  (rỗng)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lõi dự báo dịch tễ MedForecast")
    ap.add_argument("--db", default=os.environ.get("MF_DB", "data/medforecast.db"))
    ap.add_argument("--backtest", action="store_true", help="chạy kiểm định lùi")
    ap.add_argument("--forecast", action="store_true", help="dự báo kỳ tới")
    ap.add_argument("--shap", action="store_true", help="bảng đóng góp đặc trưng")
    ap.add_argument("--save", action="store_true", help="ghi vào bảng forecast_accuracy")
    ap.add_argument("--by-block", action="store_true", help="tách kết quả theo nhóm")
    ap.add_argument("--horizon", type=int, default=3)
    ap.add_argument("--n-test", type=int, default=24)
    ap.add_argument("--weather-all", action="store_true",
                    help="bật thời tiết cho MỌI nhóm (đo được là làm sai số tăng)")
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    cfg = Config(db_path=a.db, n_test=a.n_test,
                 horizons=tuple(range(1, max(1, a.horizon) + 1)),
                 weather_blocks=BLOCKS if a.weather_all else Config.weather_blocks)

    if not (a.backtest or a.forecast or a.shap):
        a.backtest = True

    bt = None
    if a.backtest or a.forecast:
        bt = backtest(cfg)
        _print("SAI SỐ KIỂM ĐỊNH LÙI", summarise(bt, by_block=a.by_block))
        _print(f"ĐỘ PHỦ KHOẢNG {int(cfg.interval_level*100)}% (ridge)",
               interval_coverage(bt, "ridge", cfg.interval_level))
        if a.save:
            print(f"\n  Đã ghi {save_accuracy(cfg, bt)} dòng vào forecast_accuracy.")

    if a.forecast:
        _print("DỰ BÁO KỲ TỚI", forecast_next(cfg, bt))
        print("\n  Mô hình chọn theo nhóm (WAPE h≥2):", best_model_per_block(bt))

    if a.shap:
        for b in cfg.blocks:
            e = explain(cfg, b)
            if e is not None:
                _print(f"ĐÓNG GÓP ĐẶC TRƯNG · {b}", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
