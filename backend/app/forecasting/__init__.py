"""Lõi dự báo mức nhóm — chỉ phụ thuộc numpy/pandas; SARIMAX/ETS (statsmodels)
là tuỳ chọn, thiếu thì Ensemble ghi lý do và bỏ qua.

Điểm vào cho app và backtest: `group_forecast.forecast_group_next(df, month, cfg)`
với `cfg = config.PRODUCTION_CONFIG`. Import trực tiếp từ submodule; package
này không re-export.
"""
