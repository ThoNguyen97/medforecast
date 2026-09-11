"""Kiểm định walk-forward (mở rộng cửa sổ, dự báo 1 bước) & so sánh các hướng.

So sánh ở MỨC MÃ cho 4 hướng: bottom-up, top-down cố định, top-down động,
hoà giải OLS. Mọi tham số mô hình lấy từ `config.PRODUCTION_CONFIG` (M1) —
đây là điểm khác biệt cốt lõi so với bản trước 11/09/2026, vốn đo một cấu
hình không màn hình nào dùng.

CHỈ SỐ (M3, M5, M7):
  MAE, RMSE   như cũ.
  RelMAE      MAE / MAE(seasonal-naive chạy OUT-OF-SAMPLE trên cùng các bước).
              Bản cũ gọi đây là "MASE" — không đúng: MASE (Hyndman & Koehler
              2006) chuẩn hoá theo naive IN-SAMPLE. Mẫu số out-of-sample là
              lựa chọn CÓ CHỦ Ý và công bằng hơn (so cùng điều kiện), chỉ cần
              gọi đúng tên. < 1 nghĩa là thắng seasonal-naive.
  ME, MPE%    sai số CÓ DẤU (dự báo − thực tế) và tỷ lệ so với thực tế. Đây là
              chỉ số DUY NHẤT phát hiện được lệch hệ thống một chiều — MAE,
              RMSE, RelMAE đều triệt tiêu dấu. Âm = hụt.
  sMAPE, WAPE cam kết đề cương.
  coverage    độ phủ THỰC của khoảng dự báo mức nhóm (M9): tỷ lệ bước mà
              thực tế rơi trong khoảng dựng từ phân vị phần dư quá khứ.
"""
from __future__ import annotations
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from . import data_access as da
from .config import ForecastConfig, PRODUCTION_CONFIG
from .models import build_default_ensemble, has_enough_weather, SeasonalNaiveForecaster
from .hierarchical import ewma_shares, reconcile_ols, split_topdown
from .group_forecast import run_group_walk_forward, make_ensemble

METHODS = ["bottom_up", "top_down_fixed", "top_down_dynamic", "ols_reconcile"]
# tên cũ "mint" vẫn được chấp nhận ở đầu vào để không vỡ script cũ
_ALIAS = {"mint": "ols_reconcile"}


def _ens(df: pd.DataFrame, cfg: ForecastConfig):
    """Ensemble MỚI cho mỗi lần fit (M6). Giữ tên cũ; thân hàm ở group_forecast."""
    return make_ensemble(df, cfg)


def _metrics_block(a: np.ndarray, p: np.ndarray, sn: np.ndarray) -> dict:
    e = p - a
    ae = np.abs(e)
    mae = float(ae.mean())
    scale = float(np.mean(np.abs(sn - a))) or 1.0
    denom_s = np.abs(a) + np.abs(p)
    smape = float(np.mean(np.where(denom_s > 0, 2 * ae / np.where(denom_s > 0, denom_s, 1), 0.0)) * 100)
    tot_a = float(np.abs(a).sum())
    return {
        "MAE": mae,
        "RMSE": float(np.sqrt(np.mean(e ** 2))),
        "RelMAE": mae / scale,
        "ME": float(e.mean()),
        "MPE_pct": float(e.sum() / tot_a * 100) if tot_a > 0 else 0.0,
        "sMAPE_pct": smape,
        "WAPE_pct": float(ae.sum() / tot_a * 100) if tot_a > 0 else 0.0,
    }


def empirical_interval(pred: float, rel_resid: np.ndarray, level: float):
    """Khoảng dự báo từ phân vị của tỷ số (thực tế / dự báo) trong quá khứ.

    Phân vị thực nghiệm: bất đối xứng tự nhiên, không
    giả định phân phối, và KHÔNG thể âm. Cần ≥ 8 phần dư; ít hơn thì trả
    None để nơi gọi nói rõ "chưa đủ lịch sử", không bịa khoảng.
    """
    r = np.asarray(rel_resid, float)
    r = r[np.isfinite(r) & (r > 0)]
    if len(r) < 8:
        return None
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    return float(pred * np.quantile(r, lo_q)), float(pred * np.quantile(r, hi_q))


def walk_forward_block(db_path: str, block: str,
                       cfg: ForecastConfig = PRODUCTION_CONFIG,
                       *, min_train: Optional[int] = None,
                       ewma_span: Optional[int] = None,
                       from_period: Optional[str] = "__cfg__") -> Dict:
    """Walk-forward mở rộng cửa sổ, dự báo 1 bước, cho một nhóm ICD — đọc từ DB.

    Tham số mô hình đến từ `cfg`. Ba kwargs còn lại chỉ để script cũ chạy
    được; giá trị mặc định của chúng cũng là cfg. Thân hàm ở
    `walk_forward_frames` để bộ huấn luyện xuất ra file (dataset.py) chạy
    được y hệt mà không cần DB.
    """
    from_period = cfg.from_period if from_period == "__cfg__" else from_period
    group = da.group_series(db_path, block, from_period=from_period)
    codes_ser = da.code_series(db_path, block, from_period=from_period)
    shares_fixed = da.fixed_shares(db_path, block)
    weather = da.weather_series(db_path) if cfg.use_weather else pd.DataFrame()
    return walk_forward_frames(block, group, codes_ser, shares_fixed, weather, cfg,
                               min_train=min_train, ewma_span=ewma_span)


def walk_forward_frames(block: str, group: pd.DataFrame,
                        codes_ser: Dict[str, pd.DataFrame],
                        shares_fixed: Dict[str, float],
                        weather: pd.DataFrame,
                        cfg: ForecastConfig = PRODUCTION_CONFIG,
                        *, min_train: Optional[int] = None,
                        ewma_span: Optional[int] = None) -> Dict:
    """Walk-forward trên DataFrame đã nạp (từ DB hoặc từ dataset/v1/*.csv).

    `group`      [period, year, month, cases, is_covid] của cả nhóm
    `codes_ser`  {icd_code: DataFrame cùng cột} cho từng mã
    `shares_fixed` {icd_code: tỷ trọng cố định} (top-down cố định)
    `weather`    [period, temp, humidity, rainfall] hoặc rỗng
    """
    min_train = cfg.min_train if min_train is None else min_train
    ewma_span = cfg.ewma_span if ewma_span is None else ewma_span
    codes = sorted(codes_ser.keys())

    # M2: ghép thời tiết vào CẢ nhóm lẫn mã — bản cũ không ghép nên backtest
    # chạy mù thời tiết dù kết luận là "thời tiết bật".
    if not cfg.use_weather:
        weather = pd.DataFrame()
    group = da.join_weather(group, weather)
    codes_ser = {c: da.join_weather(d, weather) for c, d in codes_ser.items()}
    weather_active = has_enough_weather(group, cfg.weather_min_months)

    periods = list(group["period"])
    code_map = {c: codes_ser[c].set_index("period") for c in codes}

    preds = {m: {c: [] for c in codes} for m in METHODS}
    snaive = {c: [] for c in codes}
    actuals = {c: [] for c in codes}
    failed_count: Dict[str, int] = {}
    failed_why: Dict[str, str] = {}

    # ── MỨC NHÓM: một đường đi chung với service (M12) ───────────────────
    gwf = run_group_walk_forward(group, cfg, start=min_train)
    group_pred, group_actual, snaive_g = gwf.pred, gwf.actual, gwf.snaive
    members_hist = [list(mp.keys()) for mp in gwf.member_preds]
    for nm, cnt in gwf.members_failed_count.items():
        failed_count[nm] = cnt
        failed_why[nm] = gwf.members_failed_example.get(nm, "")

    # M9: độ phủ khoảng dự báo nhóm — khoảng của bước t dựng từ phần dư
    # tương đối của các bước TRƯỚC t (tối đa interval_n_back)
    rel_resid: List[float] = []
    cov_hits, cov_total, widths = 0, 0, []
    for a_g, p_g in zip(group_actual, group_pred):
        iv = empirical_interval(p_g, rel_resid[-cfg.interval_n_back:], cfg.interval_level)
        if iv is not None:
            cov_total += 1
            cov_hits += int(iv[0] <= a_g <= iv[1])
            widths.append((iv[1] - iv[0]) / max(a_g, 1.0))
        if p_g > 0:
            rel_resid.append(a_g / p_g)

    # ── MỨC MÃ: chia Ŷ_g (đã kết hợp thích ứng) về từng mã ───────────────
    for k, t in enumerate(range(min_train, len(periods))):
        tgt_month = int(group["month"].iloc[t])
        hist_g = group.iloc[:t]
        past = set(periods[:t])
        hist_c = {c: codes_ser[c][codes_ser[c]["period"].isin(past)].reset_index(drop=True)
                  for c in codes}
        base_group = group_pred[k]

        base_codes = {}
        for c in codes:
            e_c = make_ensemble(hist_c[c], cfg).fit(hist_c[c])
            base_codes[c] = e_c.predict(tgt_month)
            for nm, why in e_c.members_failed.items():
                key = f"{nm} (mức mã)"
                failed_count[key] = failed_count.get(key, 0) + 1
                failed_why.setdefault(key, why)

        shares_dyn = ewma_shares(hist_g, hist_c, span=ewma_span)
        td_fixed = split_topdown(base_group, {c: shares_fixed.get(c, 1.0 / len(codes)) for c in codes})
        td_dyn = split_topdown(base_group, shares_dyn)
        bu = dict(base_codes)
        ols = reconcile_ols(codes, base_group, base_codes)
        by_method = {"bottom_up": bu, "top_down_fixed": td_fixed,
                     "top_down_dynamic": td_dyn, "ols_reconcile": ols}

        period_t = periods[t]
        for c in codes:
            av = code_map[c]["cases"].get(period_t, np.nan)
            if np.isnan(av):
                continue
            actuals[c].append(float(av))
            snaive[c].append(SeasonalNaiveForecaster().fit(hist_c[c]).predict(tgt_month))
            for m in METHODS:
                preds[m][c].append(by_method[m].get(c, 0.0))

    def metrics(method):
        rows, ws = [], []
        for c in codes:
            a = np.array(actuals[c])
            if len(a) == 0:
                continue
            p = np.array(preds[method][c][:len(a)])
            sn = np.array(snaive[c][:len(a)])
            rows.append(_metrics_block(a, p, sn)); ws.append(a.sum())
        if not rows:
            return {}
        w = np.array(ws, float); w = w / w.sum() if w.sum() > 0 else np.ones(len(w)) / len(w)
        return {k: float(np.average([r[k] for r in rows], weights=w)) for k in rows[0]}

    res = {m: metrics(m) for m in METHODS}
    ga, gp, gs = np.array(group_actual), np.array(group_pred), np.array(snaive_g)
    res["_group"] = _metrics_block(ga, gp, gs) if len(ga) else {}
    res["_group"]["coverage_pct"] = (cov_hits / cov_total * 100) if cov_total else None
    res["_group"]["coverage_n"] = cov_total
    res["_group"]["interval_width_rel"] = float(np.median(widths)) if widths else None

    n_steps = len(group_actual)
    used_counts: Dict[str, int] = {}
    for lst in members_hist:
        for nm in lst:
            used_counts[nm] = used_counts.get(nm, 0) + 1
    res["_meta"] = {
        "block": block, "codes": codes, "n_steps": n_steps,
        "weather_active": bool(weather_active),
        "config": cfg.as_record(),
        "members_used_pct": {nm: round(v / n_steps * 100, 1) for nm, v in used_counts.items()} if n_steps else {},
        "members_failed_count": failed_count,
        "members_failed_example": failed_why,
        "n_code_fits": n_steps * len(codes),
        # M12: trạng thái kết hợp ở bước cuối — để báo cáo nói được "ai được tin"
        "combiner": gwf.combiner.describe() if gwf.combiner else {},
        "bias_mean": float(np.mean(gwf.bias)) if gwf.bias else 1.0,
    }
    return res


def weather_effect(db_path: str, block: str,
                   cfg: ForecastConfig = PRODUCTION_CONFIG,
                   *, min_train: Optional[int] = None,
                   from_period: Optional[str] = "__cfg__") -> dict:
    """So sánh ENSEMBLE mức nhóm CÓ vs KHÔNG thời tiết (walk-forward 1 bước).

    Bản cũ so sánh HarmonicPoisson ĐỨNG MỘT MÌNH — con số đó không nói gì về
    ensemble sản xuất. Nay so đúng cấu hình sản xuất, chỉ bật/tắt thời tiết.
    """
    from dataclasses import replace
    min_train = cfg.min_train if min_train is None else min_train
    from_period = cfg.from_period if from_period == "__cfg__" else from_period
    g = da.group_series(db_path, block, from_period=from_period)
    gw = da.join_weather(g, da.weather_series(db_path))
    has_w = has_enough_weather(gw, cfg.weather_min_months)

    def wf(use_w: bool):
        c = replace(cfg, use_weather=use_w)
        r = run_group_walk_forward(gw, c, start=min_train)
        return _metrics_block(np.array(r.actual), np.array(r.pred), np.array(r.snaive))

    res = {"block": block, "has_weather": bool(has_w),
           "without_weather": wf(False),
           "with_weather": wf(True) if has_w else None}
    if has_w:
        d = res["without_weather"]["MAE"]
        res["mae_improve_pct"] = round((d - res["with_weather"]["MAE"]) / d * 100, 1)
    return res


def smearing_effect(db_path: str, block: str,
                    cfg: ForecastConfig = PRODUCTION_CONFIG) -> dict:
    """M8: đo lệch hệ thống (ME, MPE%) của ensemble nhóm CÓ vs KHÔNG smearing.

    Đây là bằng chứng cho luận điểm "hụt hệ thống nguy hiểm hơn nhiễu" — đưa
    thẳng vào chương 4.
    """
    from dataclasses import replace
    g = da.group_series(db_path, block, from_period=cfg.from_period)
    gw = da.join_weather(g, da.weather_series(db_path))

    def wf(sm: bool):
        c = replace(cfg, smearing=sm)
        r = run_group_walk_forward(gw, c, start=cfg.min_train)
        return _metrics_block(np.array(r.actual), np.array(r.pred), np.array(r.snaive))

    return {"block": block, "without_smearing": wf(False), "with_smearing": wf(True)}


def combine_effect(db_path: str, block: str,
                   cfg: ForecastConfig = PRODUCTION_CONFIG,
                   variants: Optional[Dict[str, dict]] = None) -> dict:
    """M12: so sánh cách KẾT HỢP thành viên ở mức nhóm, cùng một ensemble.

    Thành viên được khớp và ghi dự báo MỘT lần (với đầy đủ ứng viên, kể cả
    ETS nếu có statsmodels); mỗi biến thể chỉ chạy lại combiner trên bản ghi
    đó — nên so được nhiều biến thể mà không tốn thêm lần khớp SARIMAX.

    Biến thể mặc định (nền cfg):
        mean            trung bình đều (hành vi cũ)                    — không ETS
        inv_mae         trọng số nghịch đảo MAE, cửa sổ 12             — không ETS
        mean+bias       trung bình đều + hệ số lệch                    — không ETS
        inv_mae+bias    cả hai                                         — không ETS
        *+ets           bốn biến thể trên có thêm ETS
    Mỗi biến thể trả chỉ số nhóm + độ phủ khoảng + trọng số cuối.
    """
    from dataclasses import replace
    from .group_forecast import replay
    from .combine import combiner_from_config
    g = da.group_series(db_path, block, from_period=cfg.from_period)
    gw = da.join_weather(g, da.weather_series(db_path))

    # ghi một lần với siêu tập thành viên
    rec = run_group_walk_forward(gw, replace(cfg, use_ets=True), start=cfg.min_train)
    has_ets = any("ets" in mp for mp in rec.member_preds)

    base = {
        "mean":         {"combine": "mean", "bias_correct": False},
        "inv_mae":      {"combine": "inv_mae", "bias_correct": False},
        "mean+bias":    {"combine": "mean", "bias_correct": True},
        "inv_mae+bias": {"combine": "inv_mae", "bias_correct": True},
    }
    if variants is None:
        variants = {k: {**v, "use_ets": False} for k, v in base.items()}
        if has_ets:
            variants.update({f"{k}+ets": {**v, "use_ets": True} for k, v in base.items()})

    out = {"block": block, "n_steps": len(rec.actual), "has_ets": has_ets,
           "members": sorted({k for mp in rec.member_preds for k in mp})}
    for name, kw in variants.items():
        c = replace(cfg, **kw)
        drop = [] if getattr(c, "use_ets", False) else ["ets"]
        comb = combiner_from_config(c)
        rp = replay(rec.member_preds, rec.actual, comb, drop=drop)
        m = _metrics_block(np.array(rec.actual), np.array(rp["pred"]), np.array(rec.snaive))
        rel: List[float] = []; hits = tot = 0
        for a, p in zip(rec.actual, rp["pred"]):
            iv = empirical_interval(p, rel[-c.interval_n_back:], c.interval_level)
            if iv is not None:
                tot += 1; hits += int(iv[0] <= a <= iv[1])
            if p > 0:
                rel.append(a / p)
        m["coverage_pct"] = (hits / tot * 100) if tot else None
        m["bias_mean"] = float(np.mean(rp["bias"])) if rp["bias"] else 1.0
        m["weights_last"] = comb.describe().get("weights", {})
        out[name] = m
    return out
