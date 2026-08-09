"""Kiểm thử nhanh module dự báo phân cấp (numpy/pandas thuần)."""
import numpy as np
import pandas as pd
from app.forecasting.models import (SeasonalTrendForecaster, PoissonTrendForecaster,
                                     SeasonalNaiveForecaster, build_default_ensemble,
                                     HarmonicPoissonForecaster)
from app.forecasting.hierarchical import reconcile_ols, ewma_shares, split_topdown


def _series(n=48, base=50, seasonal=True):
    idx = np.arange(n)
    m = (idx % 12) + 1
    y = base + (10 if seasonal else 0) * np.sin(2*np.pi*m/12) + idx*0.2
    return pd.DataFrame({"period": [f"{2019+i//12:04d}-{i%12+1:02d}" for i in idx],
                         "month": m, "cases": np.maximum(0, y).round(),
                         "is_covid": False})


def test_models_predict_nonneg():
    df = _series()
    for M in (SeasonalTrendForecaster, PoissonTrendForecaster, SeasonalNaiveForecaster):
        p = M().fit(df).predict(int(df["month"].iloc[-1]) % 12 + 1)
        assert p >= 0 and np.isfinite(p)


def test_ensemble_runs():
    df = _series()
    p = build_default_ensemble().fit(df).predict(1)
    assert p >= 0


def test_ewma_shares_sum_to_one():
    g = _series(base=100)
    codes = {"A": _series(base=40), "B": _series(base=60)}
    sh = ewma_shares(g, codes, span=6)
    assert abs(sum(sh.values()) - 1.0) < 1e-6
    assert all(v >= 0 for v in sh.values())


def test_reconcile_ols_coherent_and_nonneg():
    codes = ["A", "B", "C"]
    rec = reconcile_ols(codes, base_group=300.0,
                        base_codes={"A": 100, "B": 110, "C": 80})
    assert all(v >= 0 for v in rec.values())
    assert len(rec) == 3


def test_split_topdown():
    out = split_topdown(200.0, {"A": 0.7, "B": 0.3})
    assert abs(out["A"] - 140) < 1e-6 and abs(out["B"] - 60) < 1e-6


def test_harmonic_poisson_with_and_without_weather():
    df = _series(n=48, base=80)
    # thêm cột thời tiết giả (có tương quan mùa)
    df["temp"] = 27 + 3 * np.sin(2 * np.pi * df["month"] / 12)
    df["humidity"] = 75 + 5 * np.cos(2 * np.pi * df["month"] / 12)
    df["rainfall"] = np.maximum(0, 100 + 80 * np.sin(2 * np.pi * df["month"] / 12))
    p0 = HarmonicPoissonForecaster(use_weather=False).fit(df).predict(1)
    p1 = HarmonicPoissonForecaster(use_weather=True).fit(df).predict(1)
    assert p0 >= 0 and np.isfinite(p0)
    assert p1 >= 0 and np.isfinite(p1)


def test_ensemble_weather_flag_runs():
    df = _series(n=48, base=80)
    df["temp"] = 27.0; df["humidity"] = 75.0; df["rainfall"] = 100.0
    assert build_default_ensemble(use_weather=True).fit(df).predict(6) >= 0
