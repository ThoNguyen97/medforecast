"""Dự báo phân cấp đọc từ tầng MART + so sánh các phương án hòa giải.

Chỉ phụ thuộc numpy/pandas để chạy được ngay. SARIMAX (statsmodels) là tùy
chọn: nếu cài đặt, tự động thêm vào ensemble; nếu không, bỏ qua — và
Ensemble.describe() sẽ cho biết điều đó.

Điểm vào duy nhất cho app và backtest (M1): `build_production_ensemble(df)`,
đọc tham số từ `PRODUCTION_CONFIG`. Không gọi `build_default_ensemble()` không
tham số trong app — đó là cấu hình "thời tiết tắt".
"""
from .config import ForecastConfig, PRODUCTION_CONFIG
from .models import (NaiveForecaster, SeasonalNaiveForecaster,
                     SeasonalTrendForecaster, PoissonTrendForecaster,
                     HarmonicPoissonForecaster, Ensemble,
                     build_default_ensemble, build_production_ensemble,
                     has_enough_weather)
from .hierarchical import reconcile_ols, ewma_shares, split_topdown
