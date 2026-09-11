"""DỰ BÁO MỨC NHÓM — một đường đi cho cả backtest lẫn service (M12, 11/09/2026).

Trước đây ba nơi tự lặp walk-forward mức nhóm theo ba cách hơi khác nhau:
`evaluate.walk_forward_block`, `evaluate.weather_effect`, và
`HierarchicalForecastService._group_interval`. Khi thêm trọng số thích ứng và
hiệu chỉnh lệch, cả ba phải cùng làm một việc — nên gom về đây.

    run_group_walk_forward(group_w, cfg, start)
        → từng bước t ≥ start: fit ensemble trên [:t], dự báo t bằng combiner
          (trọng số + lệch học từ các bước TRƯỚC t), rồi cập nhật combiner.
        Trả lịch sử để backtest chấm điểm, và combiner ở trạng thái cuối để
        service dự báo bước kế tiếp bằng đúng trọng số vừa học.

    forecast_group_next(group_w, cfg, next_month)
        → chạy walk-forward trên `interval_n_back` bước gần nhất (đằng nào
          cũng phải chạy để dựng khoảng), rồi dự báo bước kế tiếp. Trả điểm,
          khoảng, trọng số, hệ số lệch, thành viên — đủ để lưu vết.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .combine import AdaptiveCombiner, combiner_from_config
from .config import ForecastConfig, PRODUCTION_CONFIG
from .models import SeasonalNaiveForecaster, build_default_ensemble, has_enough_weather


def make_ensemble(df: pd.DataFrame, cfg: ForecastConfig):
    """Ensemble MỚI cho mỗi lần fit (M6), tham số từ cfg."""
    use_w = cfg.use_weather and has_enough_weather(df, cfg.weather_min_months)
    return build_default_ensemble(use_weather=use_w, smearing=cfg.smearing,
                                  lam=cfg.ridge_lam,
                                  use_ets=getattr(cfg, "use_ets", False))


@dataclass
class GroupWalkForward:
    periods: List[str] = field(default_factory=list)
    actual: List[float] = field(default_factory=list)
    pred: List[float] = field(default_factory=list)          # sau hiệu chỉnh lệch
    pred_raw: List[float] = field(default_factory=list)      # trước hiệu chỉnh
    snaive: List[float] = field(default_factory=list)
    member_preds: List[Dict[str, float]] = field(default_factory=list)
    weights: List[Dict[str, float]] = field(default_factory=list)
    bias: List[float] = field(default_factory=list)
    members_failed_count: Dict[str, int] = field(default_factory=dict)
    members_failed_example: Dict[str, str] = field(default_factory=dict)
    combiner: Optional[AdaptiveCombiner] = None

    # phần dư tương đối (thực tế / dự báo cuối) — đầu vào của khoảng dự báo
    def rel_resid(self) -> np.ndarray:
        a, p = np.asarray(self.actual, float), np.asarray(self.pred, float)
        ok = p > 0
        return a[ok] / p[ok]


def run_group_walk_forward(group_w: pd.DataFrame, cfg: ForecastConfig = PRODUCTION_CONFIG,
                           start: Optional[int] = None,
                           combiner: Optional[AdaptiveCombiner] = None) -> GroupWalkForward:
    """Walk-forward mở rộng cửa sổ, 1 bước, trên chuỗi nhóm (đã ghép thời tiết).

    `start` mặc định = cfg.min_train. Combiner có thể truyền vào để tiếp tục
    trạng thái; mặc định dựng mới từ cfg.
    """
    start = cfg.min_train if start is None else max(int(start), 1)
    comb = combiner or combiner_from_config(cfg)
    out = GroupWalkForward(combiner=comb)
    n = len(group_w)
    for t in range(start, n):
        hist = group_w.iloc[:t]
        tm = int(group_w["month"].iloc[t])
        actual = float(group_w["cases"].iloc[t])

        ens = make_ensemble(hist, cfg).fit(hist)
        mp = ens.predict_members(tm)
        for nm, why in ens.members_failed.items():
            out.members_failed_count[nm] = out.members_failed_count.get(nm, 0) + 1
            out.members_failed_example.setdefault(nm, why)

        final, raw, w, b = comb.combine(mp)
        comb.update(mp, actual, raw)

        out.periods.append(str(group_w["period"].iloc[t]))
        out.actual.append(actual)
        out.pred.append(final)
        out.pred_raw.append(raw)
        out.snaive.append(float(SeasonalNaiveForecaster().fit(hist).predict(tm)))
        out.member_preds.append(mp)
        out.weights.append(w)
        out.bias.append(b)
    return out


def forecast_group_next(group_w: pd.DataFrame, next_month: int,
                        cfg: ForecastConfig = PRODUCTION_CONFIG) -> dict:
    """Dự báo bước kế tiếp cho nhóm, kèm khoảng thực nghiệm và lưu vết M12.

    Chạy walk-forward trên `interval_n_back` bước gần nhất (không ít hơn
    min_train) để (a) dựng khoảng từ phần dư tương đối và (b) học trọng số +
    hệ số lệch; rồi khớp trên toàn bộ lịch sử và kết hợp bằng trạng thái đó.
    """
    from .evaluate import empirical_interval   # import muộn: tránh vòng

    n = len(group_w)
    start = max(cfg.min_train, n - cfg.interval_n_back)
    wf = run_group_walk_forward(group_w, cfg, start=start)

    ens = make_ensemble(group_w, cfg).fit(group_w)
    mp = ens.predict_members(next_month)
    final, raw, w, b = wf.combiner.combine(mp)

    rel = wf.rel_resid()
    iv = empirical_interval(final, rel, cfg.interval_level)
    return {
        "point": float(final),
        "point_raw": float(raw),
        "lower": (max(0.0, iv[0]) if iv else None),
        "upper": (iv[1] if iv else None),
        "n_resid": int(len(rel)),
        "level": cfg.interval_level,
        "members": {k: round(v, 2) for k, v in mp.items()},
        "weights": {k: round(v, 3) for k, v in w.items()},
        "bias_factor": round(b, 3),
        "members_used": list(mp.keys()),
        "members_failed": dict(ens.members_failed),
        "weather_used": any(k.endswith("_weather") for k in mp),
        "combiner": wf.combiner.describe(),
        "config": cfg.as_record(),
        # lịch sử walk-forward vừa chạy — cho "độ chính xác tại chỗ" của màn hình
        "walk_forward": {"periods": wf.periods, "actual": wf.actual, "pred": wf.pred},
    }


def replay(member_preds: List[Dict[str, float]], actual: List[float],
           combiner: AdaptiveCombiner, drop: Optional[List[str]] = None) -> Dict[str, list]:
    """Chạy lại combiner trên dự báo thành viên ĐÃ GHI (không khớp lại mô hình).

    Dùng để so sánh các cách kết hợp: thành viên dự báo gì không phụ thuộc
    cách kết hợp, nên ghi một lần rồi thay combiner là đủ — nhanh gấp số biến
    thể lần. `drop` loại thành viên khỏi tổ hợp (so "có/không ETS" mà không
    khớp lại).
    """
    drop = set(drop or [])
    pred, raw, ws, bs = [], [], [], []
    for mp, a in zip(member_preds, actual):
        mp2 = {k: v for k, v in mp.items() if k not in drop}
        f, r, w, b = combiner.combine(mp2)
        combiner.update(mp2, a, r)
        pred.append(f); raw.append(r); ws.append(w); bs.append(b)
    return {"pred": pred, "pred_raw": raw, "weights": ws, "bias": bs}
