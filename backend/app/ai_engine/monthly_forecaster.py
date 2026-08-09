"""
Monthly Disease Case Forecaster - Module 3

Công thức dự báo:
    Số ca dự báo = Ca nền cùng kỳ × Hệ số thời tiết × Hệ số xu hướng gần đây

Trong đó:
- Ca nền cùng kỳ = Trung bình số ca bệnh cùng tháng các năm trước
- Hệ số thời tiết = 1 + (correlation × (weather_forecast - weather_avg) / weather_std)
- Hệ số xu hướng = Số ca tháng trước / Trung bình 3 tháng gần nhất

Kết hợp thêm hồi quy tuyến tính để tinh chỉnh.
"""

import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from .config import SAVED_MODELS_DIR

logger = logging.getLogger(__name__)


class MonthlyForecaster:
    """
    Dự báo số ca bệnh theo tháng.
    
    Công thức chính:
        Dự báo = Ca_nền_cùng_kỳ × Hệ_số_thời_tiết × Hệ_số_xu_hướng
    
    Sau đó dùng hồi quy tuyến tính để hiệu chỉnh kết quả.
    """
    
    def __init__(self, disease_type: str):
        self.disease_type = disease_type
        self.is_trained = False
        self.training_metrics: Dict[str, float] = {}
        
        # Learned parameters
        self.monthly_baselines: Dict[int, float] = {}  # Ca nền theo tháng
        self.weather_correlations: Dict[str, float] = {}  # Hệ số tương quan thời tiết
        self.weather_means: Dict[str, float] = {}  # Trung bình thời tiết
        self.weather_stds: Dict[str, float] = {}  # Độ lệch chuẩn thời tiết
        self.regression_coef: float = 1.0  # Hệ số hiệu chỉnh hồi quy (legacy)
        self.regression_intercept: float = 0.0
        # Hồi quy đa biến: vector hệ số cho [intercept, baseline, prev, same_year,
        # recent3, temp_dev, humidity_dev, rainfall_dev, aqi_dev]
        self.feature_coefs: Optional[list] = None
        
        logger.info(f"Initialized MonthlyForecaster for {disease_type}")
    
    def train(
        self,
        monthly_cases: pd.DataFrame,
        weather_data: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        Train model từ dữ liệu lịch sử.
        
        Args:
            monthly_cases: DataFrame với columns [YearMonth, year, month, cases_*]
            weather_data: DataFrame với columns [YearMonth, temp, humidity, rainfall, aqi]
        """
        logger.info(f"Training MonthlyForecaster for {self.disease_type}")
        
        case_col = self._get_case_column()
        if case_col not in monthly_cases.columns:
            case_col = 'total_cases'
        
        df = monthly_cases.copy().sort_values('YearMonth')
        
        # 1. Tính ca nền cùng kỳ (trung bình theo tháng)
        for month in range(1, 13):
            month_data = df[df['month'] == month][case_col]
            self.monthly_baselines[month] = month_data.mean() if len(month_data) > 0 else 0
        
        # 2. Tính hệ số tương quan thời tiết
        if weather_data is not None and len(weather_data) > 0:
            merged = df.merge(weather_data, on='YearMonth', how='inner')
            for col in ['temp', 'humidity', 'rainfall', 'aqi']:
                if col in merged.columns:
                    valid = merged[[col, case_col]].dropna()
                    if len(valid) >= 3:
                        r, _ = scipy_stats.pearsonr(valid[col], valid[case_col])
                        self.weather_correlations[col] = float(r)
                        self.weather_means[col] = float(valid[col].mean())
                        self.weather_stds[col] = float(valid[col].std()) if valid[col].std() > 0 else 1.0
                    else:
                        self.weather_correlations[col] = 0.0
                        self.weather_means[col] = 0.0
                        self.weather_stds[col] = 1.0
        
        # 3. Fit hồi quy ĐA BIẾN để dự báo chính xác hơn.
        # Thay vì chỉ baseline×trend, dùng nhiều yếu tố dự báo:
        #   - baseline mùa (ca nền theo tháng)
        #   - số ca tháng trước (yếu tố mạnh nhất với chuỗi thời gian)
        #   - số ca cùng kỳ năm trước (yếu tố mùa vụ)
        #   - trung bình 3 tháng gần nhất
        #   - độ lệch thời tiết so với trung bình (temp/humidity/rainfall/aqi)
        wcols = [c for c in ['temp', 'humidity', 'rainfall', 'aqi']
                 if c in self.weather_correlations]
        merged_w = None
        if weather_data is not None and len(weather_data) > 0:
            merged_w = df.merge(weather_data, on='YearMonth', how='left')
        else:
            merged_w = df.copy()

        feat_rows: list[list[float]] = []
        targets: list[float] = []
        df_indexed = df.reset_index(drop=True)
        for i in range(len(df_indexed)):
            row = df_indexed.iloc[i]
            month = int(row['month'])
            year = int(row['year'])

            baseline = self.monthly_baselines.get(month, 0.0)
            prev_cases = float(df_indexed.iloc[i - 1][case_col]) if i >= 1 else baseline
            recent_avg = (
                float(df_indexed.iloc[max(0, i - 3):i][case_col].mean())
                if i >= 1 else baseline
            )
            # Cùng kỳ năm trước
            same = df_indexed[
                (df_indexed['year'] == year - 1) & (df_indexed['month'] == month)
            ][case_col]
            same_year = float(same.iloc[0]) if len(same) else baseline

            feat = [baseline, prev_cases, same_year, recent_avg]

            # Độ lệch thời tiết chuẩn hoá
            for c in wcols:
                val = merged_w.iloc[i].get(c) if i < len(merged_w) else None
                mean = self.weather_means.get(c, 0.0)
                std = self.weather_stds.get(c, 1.0) or 1.0
                dev = ((float(val) - mean) / std) if (val is not None and not pd.isna(val)) else 0.0
                feat.append(dev)

            feat_rows.append(feat)
            targets.append(float(row[case_col]))

        X = np.array(feat_rows, dtype=float)
        y = np.array(targets, dtype=float)

        n_feat = X.shape[1] if X.ndim == 2 else 0
        # Cần đủ mẫu so với số biến để hồi quy ổn định (tránh overfit).
        if len(y) >= n_feat + 2 and n_feat > 0:
            # Thêm cột intercept
            X_design = np.hstack([np.ones((X.shape[0], 1)), X])
            # Ridge nhẹ để ổn định khi biến tương quan (lambda nhỏ).
            # Dùng hồi quy thường (OLS) để dự báo SÁT giá trị thật — không
            # dùng trọng số 1/y² vì nó bóp méo dự báo các tháng số ca lớn.
            lam = 1.0
            I = np.eye(X_design.shape[1])
            I[0, 0] = 0.0  # không phạt intercept
            try:
                coefs = np.linalg.solve(
                    X_design.T @ X_design + lam * I, X_design.T @ y
                )
                self.feature_coefs = coefs.tolist()
                final_preds = np.maximum(X_design @ coefs, 0)
            except np.linalg.LinAlgError:
                self.feature_coefs = None
                final_preds = X[:, 0]  # fallback baseline
        else:
            # Quá ít dữ liệu → fallback công thức cũ (baseline × trend)
            self.feature_coefs = None
            final_preds = []
            for i in range(len(df_indexed)):
                month = int(df_indexed.iloc[i]['month'])
                baseline = self.monthly_baselines.get(month, 0.0)
                prev = float(df_indexed.iloc[i - 1][case_col]) if i >= 1 else baseline
                recent = float(df_indexed.iloc[max(0, i - 3):i][case_col].mean()) if i >= 1 else baseline
                tf = max(0.5, min(2.0, prev / recent)) if recent > 0 else 1.0
                final_preds.append(baseline * tf)
            final_preds = np.maximum(np.array(final_preds), 0)

        if len(y) >= 2:
            mae = float(np.mean(np.abs(y - final_preds)))
            rmse = float(np.sqrt(np.mean((y - final_preds) ** 2)))
            # MAPE: chỉ tính trên các tháng có số ca thật ĐỦ LỚN. Tháng có số ca
            # quá nhỏ (1-2 ca) khi chia sẽ tạo độ lệch % khổng lồ (vd sai 9 ca
            # trên nền 1 ca = 900%), bóp méo trung bình. Ngưỡng = max(5, 10% TB).
            mean_y = float(np.mean(y)) if len(y) else 0.0
            floor = max(5.0, 0.1 * mean_y)
            mask = y >= floor
            if mask.sum() >= 2:
                mape = float(
                    np.mean(np.abs((y[mask] - final_preds[mask]) / y[mask])) * 100
                )
            else:
                # Không đủ tháng "đủ lớn" → fallback dùng toàn bộ với sàn mẫu số
                mape = float(
                    np.mean(np.abs((y - final_preds) / np.maximum(y, 1))) * 100
                )
            ss_res = float(np.sum((y - final_preds) ** 2))
            ss_tot = float(np.sum((y - np.mean(y)) ** 2))
            r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

            self.training_metrics = {
                'mae': mae,
                'rmse': rmse,
                'mape': mape,
                'r2': float(r2),
                'n_samples': len(y),
                'monthly_baselines': self.monthly_baselines,
                'weather_correlations': self.weather_correlations,
                'weather_cols': wcols,
            }
        else:
            self.training_metrics = {'mae': 0, 'rmse': 0, 'mape': 0, 'r2': 0, 'n_samples': len(y)}
        
        self.is_trained = True
        logger.info(f"Training complete. MAE={self.training_metrics['mae']:.1f}, R²={self.training_metrics['r2']:.3f}")
        
        return self.training_metrics
    
    def predict(
        self,
        prev_month_cases: int,
        prev_month_weather: Dict[str, float],
        forecast_weather: Dict[str, float],
        target_month: int,
        same_month_prev_year_cases: Optional[int] = None,
        cases_trend: int = 0,
        recent_3month_avg: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Dự báo số ca bệnh tháng tiếp theo.
        
        Công thức: Dự báo = Ca nền cùng kỳ × Hệ số thời tiết × Hệ số xu hướng
        
        Args:
            prev_month_cases: Số ca bệnh tháng trước
            prev_month_weather: Thời tiết tháng trước
            forecast_weather: Dự báo thời tiết tháng tới
            target_month: Tháng cần dự báo (1-12)
            same_month_prev_year_cases: Ca bệnh cùng tháng năm trước
            cases_trend: Xu hướng (ca tháng trước - ca tháng trước nữa)
            recent_3month_avg: Trung bình 3 tháng gần nhất
        """
        if not self.is_trained:
            raise ValueError("Model chưa được train.")
        
        # 1. Ca nền cùng kỳ
        baseline = self.monthly_baselines.get(target_month, prev_month_cases)

        # Hệ số thời tiết (để hiển thị giải thích, không bắt buộc cho dự báo)
        weather_factor = 1.0
        for col in ['temp', 'humidity', 'rainfall', 'aqi']:
            if col in self.weather_correlations and col in forecast_weather:
                corr = self.weather_correlations[col]
                mean = self.weather_means.get(col, 0)
                std = self.weather_stds.get(col, 1)
                forecast_val = forecast_weather.get(col, mean)
                if std > 0 and forecast_val is not None:
                    deviation = (forecast_val - mean) / std
                    weather_factor += corr * deviation * 0.1
        weather_factor = max(0.7, min(1.5, weather_factor))

        # Hệ số xu hướng (hiển thị)
        if recent_3month_avg and recent_3month_avg > 0:
            trend_factor = prev_month_cases / recent_3month_avg
        elif prev_month_cases > 0 and baseline > 0:
            trend_factor = prev_month_cases / baseline
        else:
            trend_factor = 1.0
        trend_factor = max(0.5, min(2.0, trend_factor))

        # ── Dự báo bằng hồi quy đa biến (nếu đã học được) ──────────────────
        if self.feature_coefs is not None:
            same_year = (
                float(same_month_prev_year_cases)
                if same_month_prev_year_cases and same_month_prev_year_cases > 0
                else baseline
            )
            recent = recent_3month_avg if recent_3month_avg else prev_month_cases
            feat = [baseline, float(prev_month_cases), same_year, float(recent)]
            wcols = self.training_metrics.get('weather_cols', [])
            for c in wcols:
                mean = self.weather_means.get(c, 0.0)
                std = self.weather_stds.get(c, 1.0) or 1.0
                val = forecast_weather.get(c)
                dev = ((float(val) - mean) / std) if val is not None else 0.0
                feat.append(dev)
            coefs = self.feature_coefs
            # coefs[0] = intercept; phần còn lại nhân với feat
            x = [1.0] + feat
            # An toàn nếu số chiều lệch (model cũ): cắt/đệm
            n = min(len(x), len(coefs))
            prediction = sum(x[i] * coefs[i] for i in range(n))
            prediction = max(0.0, prediction)
            raw_prediction = prediction
        else:
            # Fallback công thức cũ
            if same_month_prev_year_cases and same_month_prev_year_cases > 0:
                baseline = (baseline + same_month_prev_year_cases) / 2
            raw_prediction = baseline * weather_factor * trend_factor
            prediction = max(0.0, raw_prediction * self.regression_coef + self.regression_intercept)

        # Confidence interval theo MAE
        mae = self.training_metrics.get('mae', prediction * 0.15)
        confidence_lower = max(0, prediction - 1.96 * mae)
        confidence_upper = prediction + 1.96 * mae
        
        result = {
            'predicted_cases': int(round(prediction)),
            'confidence_lower': int(round(confidence_lower)),
            'confidence_upper': int(round(confidence_upper)),
            'target_month': target_month,
            'disease_type': self.disease_type,
            'formula_details': {
                'baseline': round(baseline, 1),
                'weather_factor': round(weather_factor, 3),
                'trend_factor': round(trend_factor, 3),
                'raw_prediction': round(raw_prediction, 1),
                'regression_adjusted': round(prediction, 1),
            },
            'model_metrics': self.training_metrics
        }
        
        logger.info(
            f"Forecast {self.disease_type} month {target_month}: "
            f"{result['predicted_cases']} cases (multivariate)"
        )
        
        return result
    
    def save(self, version: str = "latest") -> Path:
        """Save model to disk."""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        filepath = SAVED_MODELS_DIR / f"monthly_{self.disease_type}_{version}.pkl"
        model_data = {
            'monthly_baselines': self.monthly_baselines,
            'weather_correlations': self.weather_correlations,
            'weather_means': self.weather_means,
            'weather_stds': self.weather_stds,
            'regression_coef': self.regression_coef,
            'regression_intercept': self.regression_intercept,
            'feature_coefs': self.feature_coefs,
            'training_metrics': self.training_metrics,
            'disease_type': self.disease_type,
            'trained_at': datetime.now().isoformat()
        }
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        logger.info(f"Model saved to {filepath}")
        return filepath
    
    def load(self, version: str = "latest") -> bool:
        """Load model from disk."""
        filepath = SAVED_MODELS_DIR / f"monthly_{self.disease_type}_{version}.pkl"
        if not filepath.exists():
            return False
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.monthly_baselines = data['monthly_baselines']
        self.weather_correlations = data['weather_correlations']
        self.weather_means = data['weather_means']
        self.weather_stds = data['weather_stds']
        self.regression_coef = data['regression_coef']
        self.regression_intercept = data['regression_intercept']
        self.feature_coefs = data.get('feature_coefs')
        self.training_metrics = data['training_metrics']
        self.is_trained = True
        return True
    
    def _get_case_column(self) -> str:
        mapping = {
            'respiratory_disease': 'cases_respiratory',
            'seasonal_flu': 'cases_flu',
            'viral_infection': 'cases_viral',
            'dengue_fever': 'cases_dengue',
        }
        return mapping.get(self.disease_type, 'total_cases')
