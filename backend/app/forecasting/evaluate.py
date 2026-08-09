"""Kiểm định walk-forward (mở rộng cửa sổ, dự báo 1 bước) & so sánh các hướng.

Chỉ số: MAE, RMSE, MASE (chuẩn hóa theo seasonal-naive in-sample).
So sánh ở MỨC MÃ cho 4 hướng: bottom-up, top-down cố định, top-down động, MinT.
"""
from __future__ import annotations
from typing import Dict, List
import numpy as np
import pandas as pd

from . import data_access as da
from .models import build_default_ensemble, SeasonalNaiveForecaster
from .hierarchical import ewma_shares, reconcile_ols, split_topdown

METHODS = ["bottom_up", "top_down_fixed", "top_down_dynamic", "mint"]




def walk_forward_block(db_path: str, block: str, min_train: int = 24,
                       ewma_span: int = 6, from_period: str | None = None) -> Dict:
    group = da.group_series(db_path, block, from_period=from_period)
    codes_ser = da.code_series(db_path, block, from_period=from_period)
    codes = sorted(codes_ser.keys())
    shares_fixed = da.fixed_shares(db_path, block)

    periods = list(group["period"])
    # căn chuỗi mã theo period của nhóm
    code_map = {c: codes_ser[c].set_index("period") for c in codes}
    # MASE scale = MAE của seasonal-naive chạy OUT-OF-SAMPLE (so cùng điều kiện)

    preds = {m: {c: [] for c in codes} for m in METHODS}
    snaive = {c: [] for c in codes}
    snaive_g = []
    actuals = {c: [] for c in codes}
    group_pred, group_actual = [], []

    ens = build_default_ensemble()
    for t in range(min_train, len(periods)):
        tgt_month = int(group["month"].iloc[t])
        hist_g = group.iloc[:t]
        past = set(periods[:t])   # căn theo period, không phụ thuộc vị trí dòng
        hist_c = {c: codes_ser[c][codes_ser[c]["period"].isin(past)].reset_index(drop=True)
                  for c in codes}

        sn_g = SeasonalNaiveForecaster().fit(hist_g).predict(tgt_month)
        base_group = ens.fit(hist_g).predict(tgt_month)
        base_codes = {c: ens.fit(hist_c[c]).predict(tgt_month) for c in codes}

        shares_dyn = ewma_shares(hist_g, hist_c, span=ewma_span)
        td_fixed = split_topdown(base_group, {c: shares_fixed.get(c, 1.0/len(codes)) for c in codes})
        td_dyn = split_topdown(base_group, shares_dyn)
        bu = dict(base_codes)
        mint = reconcile_ols(codes, base_group, base_codes)

        by_method = {"bottom_up": bu, "top_down_fixed": td_fixed,
                     "top_down_dynamic": td_dyn, "mint": mint}
        period_t = periods[t]
        for c in codes:
            av = code_map[c]["cases"].get(period_t, np.nan)
            if np.isnan(av):
                continue
            actuals[c].append(float(av))
            snaive[c].append(SeasonalNaiveForecaster().fit(hist_c[c]).predict(tgt_month))
            for m in METHODS:
                preds[m][c].append(by_method[m].get(c, 0.0))
        group_pred.append(base_group)
        snaive_g.append(sn_g)
        group_actual.append(float(group["cases"].iloc[t]))

    # tổng hợp chỉ số
    def metrics(method):
        maes, rmses, mases, ws = [], [], [], []
        for c in codes:
            a = np.array(actuals[c]); p = np.array(preds[method][c][:len(a)])
            if len(a) == 0:
                continue
            e = p - a
            maes.append(np.mean(np.abs(e)))
            rmses.append(np.sqrt(np.mean(e**2)))
            sc = np.mean(np.abs(np.array(snaive[c][:len(a)]) - a)) or 1.0
            mases.append(np.mean(np.abs(e)) / sc)
            ws.append(a.sum())
        ws = np.array(ws) if ws else np.array([1.0])
        w = ws / ws.sum()
        return {"MAE": float(np.average(maes, weights=w)),
                "RMSE": float(np.average(rmses, weights=w)),
                "MASE": float(np.average(mases, weights=w))}

    res = {m: metrics(m) for m in METHODS}
    # chỉ số mức nhóm (tham chiếu)
    ga, gp = np.array(group_actual), np.array(group_pred)
    gscale = (np.mean(np.abs(np.array(snaive_g) - ga)) or 1.0)
    res["_group"] = {"MAE": float(np.mean(np.abs(gp-ga))),
                     "RMSE": float(np.sqrt(np.mean((gp-ga)**2))),
                     "MASE": float(np.mean(np.abs(gp-ga))/gscale)}
    res["_meta"] = {"block": block, "codes": codes, "n_steps": len(group_actual)}
    return res


def weather_effect(db_path: str, block: str, min_train: int = 24,
                   from_period: str | None = None) -> dict:
    """So sánh mô hình nhóm CÓ vs KHÔNG dùng thời tiết (walk-forward 1 bước, group-level).

    Thời tiết dùng ở ĐỘ TRỄ (lag) nên không rò rỉ tương lai. Trả MAE/RMSE/MASE.
    """
    from .models import HarmonicPoissonForecaster, SeasonalNaiveForecaster
    from . import data_access as da
    g = da.group_series(db_path, block, from_period=from_period)
    w = da.weather_series(db_path)
    gw = da.join_weather(g, w)
    has_w = ("temp" in gw.columns) and gw["temp"].notna().any()

    def wf(use_w):
        errs, sn = [], []
        for t in range(min_train, len(gw)):
            hist = gw.iloc[:t]; tm = int(gw["month"].iloc[t]); act = float(gw["cases"].iloc[t])
            mdl = HarmonicPoissonForecaster(use_weather=use_w)
            errs.append(abs(mdl.fit(hist).predict(tm) - act))
            sn.append(abs(SeasonalNaiveForecaster().fit(hist).predict(tm) - act))
        e = np.array(errs); scale = (np.mean(sn) or 1.0)
        return {"MAE": float(e.mean()), "RMSE": float(np.sqrt((e**2).mean())),
                "MASE": float(e.mean() / scale)}

    res = {"block": block, "has_weather": bool(has_w),
           "without_weather": wf(False),
           "with_weather": wf(True) if has_w else None}
    if has_w:
        d = res["without_weather"]["MAE"]
        res["mae_improve_pct"] = round((d - res["with_weather"]["MAE"]) / d * 100, 1)
    return res
