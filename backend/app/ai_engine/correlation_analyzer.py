"""
Correlation Analyzer - Phân tích tương quan thời tiết - số ca bệnh

Module này phân tích mối liên hệ giữa:
- Nhiệt độ ↔ Số ca bệnh
- Độ ẩm ↔ Số ca bệnh
- Lượng mưa ↔ Số ca bệnh
- AQI ↔ Số ca bệnh

Output:
- Hệ số tương quan (Pearson, Spearman)
- Độ trễ tối ưu (lag) giữa thời tiết và ca bệnh
- Biểu đồ scatter + heatmap data
- Kết luận: yếu tố nào ảnh hưởng mạnh nhất
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class CorrelationAnalyzer:
    """
    Phân tích tương quan giữa yếu tố môi trường và số ca bệnh.
    
    Theo sơ đồ luồng: Sau khi tiền xử lý dữ liệu, cần phân tích
    tương quan thời tiết - số ca bệnh để hiểu yếu tố nào ảnh hưởng.
    
    Example:
        >>> analyzer = CorrelationAnalyzer()
        >>> results = analyzer.analyze(monthly_cases, weather_data)
        >>> print(results['correlations'])
        >>> print(results['strongest_factor'])
    """
    
    def __init__(self):
        self.results: Optional[Dict] = None
    
    def analyze(
        self,
        monthly_cases: pd.DataFrame,
        weather_data: pd.DataFrame,
        disease_type: str = 'total_cases'
    ) -> Dict:
        """
        Phân tích tương quan đầy đủ.
        
        Args:
            monthly_cases: DataFrame với columns [YearMonth, year, month, cases_*]
                (output từ CSVDataProcessor.get_monthly_summary())
            weather_data: DataFrame với columns [YearMonth, temp, humidity, rainfall, aqi]
            disease_type: Column name cho số ca bệnh (default: 'total_cases')
            
        Returns:
            Dict chứa:
            - correlations: Hệ số tương quan cho từng yếu tố
            - lag_analysis: Phân tích độ trễ
            - strongest_factor: Yếu tố ảnh hưởng mạnh nhất
            - scatter_data: Data cho biểu đồ scatter
            - summary: Tóm tắt kết quả
        """
        logger.info(f"Analyzing correlations for {disease_type}")
        
        # Merge data
        merged = monthly_cases.merge(weather_data, on='YearMonth', how='inner')
        
        if len(merged) < 3:
            logger.warning("Not enough data for correlation analysis")
            return {'error': 'Insufficient data (need at least 3 months)'}
        
        weather_cols = ['temp', 'humidity', 'rainfall', 'aqi']
        available_cols = [c for c in weather_cols if c in merged.columns]
        
        if not available_cols:
            return {'error': 'No weather columns found in data'}
        
        case_col = disease_type if disease_type in merged.columns else 'total_cases'
        
        # 1. Pearson correlation (linear)
        pearson_corr = {}
        for col in available_cols:
            valid = merged[[col, case_col]].dropna()
            if len(valid) >= 3:
                r, p_value = stats.pearsonr(valid[col], valid[case_col])
                pearson_corr[col] = {
                    'coefficient': round(float(r), 4),
                    'p_value': round(float(p_value), 4),
                    'significant': bool(p_value < 0.05),
                    'strength': self._classify_strength(abs(float(r)))
                }
        
        # 2. Spearman correlation (non-linear/monotonic)
        spearman_corr = {}
        for col in available_cols:
            valid = merged[[col, case_col]].dropna()
            if len(valid) >= 3:
                rho, p_value = stats.spearmanr(valid[col], valid[case_col])
                spearman_corr[col] = {
                    'coefficient': round(float(rho), 4),
                    'p_value': round(float(p_value), 4),
                    'significant': bool(p_value < 0.05),
                    'strength': self._classify_strength(abs(float(rho)))
                }
        
        # 3. Lag analysis (thời tiết tháng trước ảnh hưởng tháng sau?)
        lag_analysis = self._analyze_lag(merged, available_cols, case_col)
        
        # 4. Find strongest factor
        strongest = self._find_strongest_factor(pearson_corr, spearman_corr)
        
        # 5. Scatter data for visualization
        scatter_data = {}
        for col in available_cols:
            valid = merged[[col, case_col]].dropna()
            scatter_data[col] = {
                'x': [float(v) for v in valid[col].tolist()],
                'y': [float(v) for v in valid[case_col].tolist()],
                'x_label': self._get_label(col),
                'y_label': 'Số ca bệnh'
            }
        
        # 6. Monthly trend data
        trend_data = merged[['YearMonth', case_col] + available_cols].copy()
        trend_data['YearMonth'] = trend_data['YearMonth'].astype(str)
        
        # 7. Summary
        summary = self._generate_summary(pearson_corr, spearman_corr, lag_analysis, strongest)
        
        self.results = {
            'correlations': {
                'pearson': pearson_corr,
                'spearman': spearman_corr
            },
            'lag_analysis': lag_analysis,
            'strongest_factor': strongest,
            'scatter_data': scatter_data,
            'trend_data': trend_data.to_dict('records'),
            'summary': summary,
            'n_months': int(len(merged)),
            'disease_type': disease_type
        }
        
        logger.info(f"Correlation analysis complete. Strongest factor: {strongest}")
        
        return self.results
    
    def analyze_without_weather_api(
        self,
        monthly_cases: pd.DataFrame,
        disease_type: str = 'total_cases'
    ) -> Dict:
        """
        Phân tích tương quan chỉ dựa trên yếu tố mùa vụ (không cần weather API).
        
        Phân tích: tháng nào trong năm có nhiều ca bệnh nhất?
        
        Args:
            monthly_cases: DataFrame từ CSVDataProcessor.get_monthly_summary()
            disease_type: Column name cho số ca bệnh
            
        Returns:
            Dict chứa seasonal analysis
        """
        logger.info(f"Analyzing seasonal patterns for {disease_type}")
        
        case_col = disease_type if disease_type in monthly_cases.columns else 'total_cases'
        
        # Group by month to find seasonal pattern
        seasonal = (
            monthly_cases
            .groupby('month')[case_col]
            .agg(['mean', 'std', 'min', 'max', 'count'])
            .reset_index()
        )
        seasonal.columns = ['month', 'avg_cases', 'std_cases', 'min_cases', 'max_cases', 'n_years']
        # Replace NaN with 0
        seasonal = seasonal.fillna(0)
        
        # Find peak months
        peak_month = seasonal.loc[seasonal['avg_cases'].idxmax(), 'month']
        low_month = seasonal.loc[seasonal['avg_cases'].idxmin(), 'month']
        
        # Seasonal variation ratio
        if seasonal['avg_cases'].min() > 0:
            variation_ratio = seasonal['avg_cases'].max() / seasonal['avg_cases'].min()
        else:
            variation_ratio = float('inf')
        
        result = {
            'seasonal_pattern': [
                {k: (0 if (isinstance(v, float) and (v != v)) else v) for k, v in row.items()}
                for row in seasonal.to_dict('records')
            ],
            'peak_month': int(peak_month),
            'low_month': int(low_month),
            'variation_ratio': round(float(variation_ratio), 2),
            'has_strong_seasonality': bool(variation_ratio > 1.5),
            'summary': (
                f"Tháng cao điểm: tháng {peak_month} "
                f"(TB {seasonal[seasonal['month']==peak_month]['avg_cases'].values[0]:.0f} ca). "
                f"Tháng thấp nhất: tháng {low_month} "
                f"(TB {seasonal[seasonal['month']==low_month]['avg_cases'].values[0]:.0f} ca). "
                f"Biên độ dao động: {variation_ratio:.1f}x."
            )
        }
        
        return result
    
    def _analyze_lag(
        self,
        data: pd.DataFrame,
        weather_cols: List[str],
        case_col: str,
        max_lag: int = 2
    ) -> Dict:
        """
        Phân tích độ trễ: thời tiết tháng trước ảnh hưởng ca bệnh tháng sau?
        
        VD: Lượng mưa tháng 5 → Sốt xuất huyết tháng 6 (lag=1)
        """
        lag_results = {}
        
        for col in weather_cols:
            best_lag = 0
            best_corr = 0
            lag_corrs = {}
            
            for lag in range(0, max_lag + 1):
                if lag == 0:
                    x = data[col].values
                    y = data[case_col].values
                else:
                    x = data[col].values[:-lag]
                    y = data[case_col].values[lag:]
                
                # Remove NaN
                valid_mask = ~(np.isnan(x) | np.isnan(y))
                x_valid = x[valid_mask]
                y_valid = y[valid_mask]
                
                if len(x_valid) >= 3:
                    r, _ = stats.pearsonr(x_valid, y_valid)
                    lag_corrs[f'lag_{lag}'] = round(float(r), 4)
                    
                    if abs(r) > abs(best_corr):
                        best_corr = r
                        best_lag = lag
            
            lag_results[col] = {
                'best_lag_months': best_lag,
                'best_correlation': round(float(best_corr), 4),
                'all_lags': lag_corrs,
                'interpretation': (
                    f"{self._get_label(col)} có tương quan mạnh nhất với ca bệnh "
                    f"sau {best_lag} tháng (r={best_corr:.3f})"
                    if best_lag > 0 else
                    f"{self._get_label(col)} ảnh hưởng trực tiếp trong cùng tháng (r={best_corr:.3f})"
                )
            }
        
        return lag_results
    
    def _find_strongest_factor(
        self,
        pearson: Dict,
        spearman: Dict
    ) -> Dict:
        """Tìm yếu tố ảnh hưởng mạnh nhất."""
        max_corr = 0
        strongest = None
        
        for col, data in pearson.items():
            if abs(data['coefficient']) > abs(max_corr):
                max_corr = data['coefficient']
                strongest = col
        
        if strongest:
            return {
                'factor': strongest,
                'factor_label': self._get_label(strongest),
                'correlation': max_corr,
                'direction': 'positive' if max_corr > 0 else 'negative',
                'interpretation': (
                    f"{self._get_label(strongest)} có ảnh hưởng "
                    f"{'thuận' if max_corr > 0 else 'nghịch'} "
                    f"mạnh nhất đến số ca bệnh (r={max_corr:.3f})"
                )
            }
        
        return {'factor': None, 'interpretation': 'Không đủ dữ liệu để xác định'}
    
    def _generate_summary(
        self,
        pearson: Dict,
        spearman: Dict,
        lag_analysis: Dict,
        strongest: Dict
    ) -> str:
        """Tạo tóm tắt phân tích."""
        lines = ["## Kết quả phân tích tương quan thời tiết - số ca bệnh\n"]
        
        # Strongest factor
        if strongest.get('factor'):
            lines.append(f"**Yếu tố ảnh hưởng mạnh nhất:** {strongest['interpretation']}")
        
        # All correlations
        lines.append("\n**Chi tiết tương quan:**")
        for col, data in pearson.items():
            sig = "✓ có ý nghĩa" if data['significant'] else "✗ chưa có ý nghĩa thống kê"
            lines.append(
                f"- {self._get_label(col)}: r={data['coefficient']:.3f} "
                f"({data['strength']}, {sig})"
            )
        
        # Lag effects
        lines.append("\n**Phân tích độ trễ:**")
        for col, data in lag_analysis.items():
            lines.append(f"- {data['interpretation']}")
        
        return "\n".join(lines)
    
    @staticmethod
    def _classify_strength(abs_r: float) -> str:
        """Phân loại mức độ tương quan."""
        if abs_r >= 0.7:
            return "mạnh"
        elif abs_r >= 0.4:
            return "trung bình"
        elif abs_r >= 0.2:
            return "yếu"
        else:
            return "rất yếu"
    
    @staticmethod
    def _get_label(col: str) -> str:
        """Get Vietnamese label for weather column."""
        labels = {
            'temp': 'Nhiệt độ',
            'humidity': 'Độ ẩm',
            'rainfall': 'Lượng mưa',
            'aqi': 'Chỉ số AQI (chất lượng không khí)'
        }
        return labels.get(col, col)
