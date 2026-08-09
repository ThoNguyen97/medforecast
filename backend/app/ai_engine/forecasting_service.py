"""
Forecasting Service - Main Pipeline

Luồng chính theo đề tài:
1. Import CSV → Trích xuất số ca bệnh + lượng vật tư tiêu thụ theo tháng
2. AI học từ dữ liệu → Tìm pattern (bệnh nào dùng thuốc gì, mùa nào tăng)
3. Kết hợp thời tiết → Dự báo thời tiết tháng tới + thời tiết tháng trước
4. Dự báo → Số ca bệnh tháng tới + nhu cầu vật tư cụ thể

Input cho dự báo:
    - Nhiệt độ, độ ẩm, lượng mưa tháng trước
    - Số ca bệnh tháng trước
    - Số ca bệnh cùng tháng năm trước (yếu tố mùa vụ)
    - Dự báo thời tiết tháng tới (từ API hoặc user input)
    
Output:
    - Số ca bệnh dự kiến tháng tới (theo nhóm bệnh)
    - Nhu cầu vật tư/thuốc cụ thể (theo DrugName thực tế)
    - So sánh với tồn kho → Cảnh báo thiếu hụt
    - Đề xuất nhập hàng
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from .csv_data_processor import CSVDataProcessor, NHOM_BENH_MAPPING
from .monthly_forecaster import MonthlyForecaster
from .supply_demand_calculator import SupplyDemandCalculator

logger = logging.getLogger(__name__)

# Default CSV data directory
DATA_DIR = Path(__file__).parent.parent.parent.parent  # project root


class ForecastingService:
    """
    Service chính điều phối toàn bộ pipeline dự báo.
    
    Workflow:
        1. load_training_data() - Load CSV files
        2. train_models() - Train model cho từng nhóm bệnh
        3. forecast_next_month() - Dự báo tháng tới
        4. calculate_supply_demand() - Tính nhu cầu vật tư
        5. compare_with_inventory() - So sánh với tồn kho
        6. generate_suggestions() - Đề xuất nhập hàng
    
    Example:
        >>> service = ForecastingService()
        >>> service.load_training_data()
        >>> service.train_models()
        >>> result = service.forecast_next_month(
        ...     prev_month_weather={'temp': 30, 'humidity': 80, 'rainfall': 200},
        ...     forecast_weather={'temp': 31, 'humidity': 82, 'rainfall': 250},
        ...     target_month=6
        ... )
    """
    
    def __init__(self, csv_dir: Optional[str] = None):
        """
        Args:
            csv_dir: Thư mục chứa file CSV. Mặc định là project root.
        """
        self.csv_dir = Path(csv_dir) if csv_dir else DATA_DIR
        self.csv_processor = CSVDataProcessor()
        self.supply_calculator = SupplyDemandCalculator()
        self.forecasters: Dict[str, MonthlyForecaster] = {}
        self.monthly_summary: Optional[pd.DataFrame] = None
        self.is_data_loaded = False
        self.is_trained = False
        
        logger.info(f"ForecastingService initialized. CSV dir: {self.csv_dir}")
    
    def load_training_data(self, file_paths: Optional[List[str]] = None) -> Dict:
        """
        Bước 1: Load CSV files và trích xuất dữ liệu.
        
        Args:
            file_paths: Danh sách file CSV. Nếu None, tự tìm trong csv_dir.
            
        Returns:
            Dict summary về dữ liệu đã load
        """
        logger.info("=== Step 1: Loading training data from CSV ===")
        
        if file_paths is None:
            # Auto-discover CSV files
            file_paths = sorted([
                str(f) for f in self.csv_dir.glob("*.csv")
            ])
        
        if not file_paths:
            raise FileNotFoundError(
                f"No CSV files found in {self.csv_dir}. "
                f"Expected files like data_HM_2025_1.csv"
            )
        
        # Load all CSV files
        self.csv_processor.load_csv_files(file_paths)
        
        # Extract monthly cases
        monthly_cases = self.csv_processor.get_monthly_cases()
        
        # Extract monthly supply consumption
        monthly_supply = self.csv_processor.get_monthly_supply_consumption()
        
        # Get monthly summary for model training
        self.monthly_summary = self.csv_processor.get_monthly_summary()
        
        # Learn conversion ratios from data
        self.supply_calculator.learn_ratios_from_data(self.csv_processor)
        
        self.is_data_loaded = True
        
        summary = {
            'files_loaded': len(file_paths),
            'total_records': len(self.csv_processor.raw_data),
            'date_range': {
                'from': str(self.csv_processor.raw_data['AdmissionDate'].min().date()),
                'to': str(self.csv_processor.raw_data['AdmissionDate'].max().date()),
            },
            'months_available': len(self.monthly_summary),
            'disease_groups': list(monthly_cases['NhomBenh'].unique()),
            'total_drug_types': len(self.supply_calculator.ratios) if self.supply_calculator.ratios is not None else 0,
            'monthly_cases_summary': self.monthly_summary[['YearMonth', 'total_cases']].to_dict('records')
        }
        
        logger.info(f"Data loaded: {summary['total_records']:,} records, "
                   f"{summary['months_available']} months")
        
        return summary
    
    def train_models(
        self, 
        weather_data: Optional[pd.DataFrame] = None
    ) -> Dict[str, Dict]:
        """
        Bước 2: Train model dự báo cho từng nhóm bệnh.
        
        Args:
            weather_data: Dữ liệu thời tiết theo tháng (optional)
                DataFrame với columns [YearMonth, temp, humidity, rainfall, aqi]
                Nếu None, tự động dùng historical average từ WeatherForecast module.
                
        Returns:
            Dict {disease_type: training_metrics}
        """
        if not self.is_data_loaded:
            raise ValueError("Data chưa load. Gọi load_training_data() trước.")
        
        logger.info("=== Step 2: Training forecasting models ===")
        
        # Auto-generate weather data if not provided
        if weather_data is None:
            from .weather_forecast import WeatherForecast
            weather_service = WeatherForecast()
            months = self.monthly_summary['YearMonth'].tolist()
            weather_data = weather_service.build_weather_dataframe(months)
            logger.info("Using historical average weather data for training")
        
        all_metrics = {}
        
        # Train model cho từng nhóm bệnh có đủ dữ liệu
        disease_types = ['respiratory_disease', 'viral_infection', 'seasonal_flu', 'dengue_fever']
        
        for disease_type in disease_types:
            # Map disease_type to column name
            col_mapping = {
                'respiratory_disease': 'cases_respiratory',
                'viral_infection': 'cases_viral',
                'seasonal_flu': 'cases_flu',
                'dengue_fever': 'cases_dengue',
            }
            case_col = col_mapping.get(disease_type, f'cases_{disease_type}')
            
            # Check if we have enough data for this disease type
            if case_col in self.monthly_summary.columns:
                non_zero_months = (self.monthly_summary[case_col] > 0).sum()
                if non_zero_months < 3:
                    logger.warning(
                        f"Skipping {disease_type}: only {non_zero_months} months with data"
                    )
                    continue
            else:
                logger.warning(f"Column {case_col} not found in monthly summary")
                continue
            
            try:
                forecaster = MonthlyForecaster(disease_type=disease_type)
                metrics = forecaster.train(self.monthly_summary, weather_data)
                forecaster.save()
                
                self.forecasters[disease_type] = forecaster
                all_metrics[disease_type] = metrics
                
                logger.info(f"  {disease_type}: MAE={metrics['mae']:.1f}, R²={metrics['r2']:.3f}")
                
            except Exception as e:
                logger.error(f"Error training {disease_type}: {str(e)}")
                all_metrics[disease_type] = {'error': str(e)}
        
        self.is_trained = True
        logger.info(f"Training complete. {len(self.forecasters)} models trained.")
        
        return all_metrics
    
    def forecast_next_month(
        self,
        prev_month_weather: Dict[str, float],
        forecast_weather: Dict[str, float],
        target_month: int,
        target_year: int = None
    ) -> Dict:
        """
        Bước 3+4: Dự báo số ca bệnh tháng tới.
        
        Kết hợp:
        - Thời tiết tháng trước (actual)
        - Dự báo thời tiết tháng tới (từ API hoặc user input)
        - Số ca bệnh tháng trước (từ data)
        - Yếu tố mùa vụ (cùng tháng năm trước)
        
        Args:
            prev_month_weather: Thời tiết tháng trước
                {'temp': 30, 'humidity': 80, 'rainfall': 200, 'aqi': 100}
            forecast_weather: Dự báo thời tiết tháng tới
                {'temp': 31, 'humidity': 82, 'rainfall': 250, 'aqi': 110}
            target_month: Tháng cần dự báo (1-12)
            target_year: Năm cần dự báo (default: năm hiện tại)
            
        Returns:
            Dict với predicted_cases cho từng nhóm bệnh + tổng
        """
        if not self.is_trained:
            raise ValueError("Models chưa train. Gọi train_models() trước.")
        
        if target_year is None:
            target_year = datetime.now().year
        
        logger.info(f"=== Step 3-4: Forecasting for {target_month}/{target_year} ===")
        
        # Get previous month data from monthly summary
        prev_month = target_month - 1 if target_month > 1 else 12
        prev_year = target_year if target_month > 1 else target_year - 1
        
        predictions = {}
        total_predicted = 0
        
        for disease_type, forecaster in self.forecasters.items():
            case_col = forecaster._get_case_column()
            
            # Số ca bệnh tháng trước
            prev_data = self.monthly_summary[
                (self.monthly_summary['year'] == prev_year) &
                (self.monthly_summary['month'] == prev_month)
            ]
            
            if len(prev_data) > 0 and case_col in prev_data.columns:
                prev_month_cases = int(prev_data[case_col].values[0])
            else:
                # Fallback: dùng trung bình
                prev_month_cases = int(self.monthly_summary[case_col].mean()) if case_col in self.monthly_summary.columns else 0
            
            # Số ca bệnh cùng tháng năm trước
            same_month_data = self.monthly_summary[
                (self.monthly_summary['year'] == target_year - 1) &
                (self.monthly_summary['month'] == target_month)
            ]
            
            if len(same_month_data) > 0 and case_col in same_month_data.columns:
                same_month_prev_year = int(same_month_data[case_col].values[0])
            else:
                same_month_prev_year = prev_month_cases
            
            # Trend (ca tháng trước - ca tháng trước nữa)
            prev_prev_month = prev_month - 1 if prev_month > 1 else 12
            prev_prev_year = prev_year if prev_month > 1 else prev_year - 1
            prev_prev_data = self.monthly_summary[
                (self.monthly_summary['year'] == prev_prev_year) &
                (self.monthly_summary['month'] == prev_prev_month)
            ]
            
            if len(prev_prev_data) > 0 and case_col in prev_prev_data.columns:
                cases_trend = prev_month_cases - int(prev_prev_data[case_col].values[0])
            else:
                cases_trend = 0
            
            # Predict
            try:
                # Tính trung bình 3 tháng gần nhất
                recent_data = self.monthly_summary.sort_values('YearMonth').tail(3)
                recent_3month_avg = float(recent_data[case_col].mean()) if case_col in recent_data.columns else None
                
                result = forecaster.predict(
                    prev_month_cases=prev_month_cases,
                    prev_month_weather=prev_month_weather,
                    forecast_weather=forecast_weather,
                    target_month=target_month,
                    same_month_prev_year_cases=same_month_prev_year,
                    cases_trend=cases_trend,
                    recent_3month_avg=recent_3month_avg
                )
                
                predictions[disease_type] = result
                total_predicted += result['predicted_cases']
                
            except Exception as e:
                logger.error(f"Error predicting {disease_type}: {str(e)}")
                predictions[disease_type] = {'error': str(e)}
        
        forecast_result = {
            'target_month': target_month,
            'target_year': target_year,
            'predictions': predictions,
            'total_predicted_cases': total_predicted,
            'weather_input': {
                'prev_month': prev_month_weather,
                'forecast': forecast_weather
            },
            'generated_at': datetime.now().isoformat()
        }
        
        logger.info(f"Forecast complete. Total predicted: {total_predicted} cases")
        
        return forecast_result
    
    def calculate_supply_demand(
        self,
        forecast_result: Dict,
        top_n: int = 30
    ) -> pd.DataFrame:
        """
        Bước 4 (tiếp): Tính nhu cầu vật tư từ số ca bệnh dự báo.
        
        Args:
            forecast_result: Output từ forecast_next_month()
            top_n: Top N vật tư cho mỗi nhóm bệnh
            
        Returns:
            DataFrame nhu cầu vật tư
        """
        logger.info("=== Calculating supply demand ===")
        
        # Extract predicted cases per disease type
        predicted_cases = {}
        for disease_type, pred in forecast_result['predictions'].items():
            if isinstance(pred, dict) and 'predicted_cases' in pred:
                predicted_cases[disease_type] = pred['predicted_cases']
        
        if not predicted_cases:
            logger.warning("No valid predictions to calculate demand")
            return pd.DataFrame()
        
        demand = self.supply_calculator.calculate_demand(
            predicted_cases=predicted_cases,
            top_n=top_n
        )
        
        logger.info(f"Supply demand calculated: {len(demand)} items")
        
        return demand
    
    def compare_and_suggest(
        self,
        demand_df: pd.DataFrame,
        current_inventory: Dict[str, float]
    ) -> Dict:
        """
        Bước 5+6: So sánh với tồn kho + Đề xuất nhập hàng.
        
        Theo sơ đồ luồng:
        - Tồn kho đủ? → Đề xuất duy trì / giảm nhập
        - Thiếu? → Cảnh báo + Đề xuất số lượng cần nhập
        
        Args:
            demand_df: Output từ calculate_supply_demand()
            current_inventory: Dict {DrugName: current_stock}
            
        Returns:
            Dict với comparison, suggestions, alerts
        """
        logger.info("=== Comparing with inventory & generating suggestions ===")
        
        # So sánh
        comparison = self.supply_calculator.compare_with_inventory(
            demand_df, current_inventory
        )
        
        # Đề xuất
        suggestions = self.supply_calculator.generate_procurement_suggestion(comparison)
        
        # Critical alerts
        critical_items = self.supply_calculator.get_top_critical_supplies(comparison)
        
        # Summary stats
        status_counts = comparison['status'].value_counts().to_dict()
        
        result = {
            'comparison': comparison.to_dict('records'),
            'suggestions': suggestions.to_dict('records'),
            'critical_alerts': critical_items,
            'summary': {
                'total_items': len(comparison),
                'critical': status_counts.get('critical', 0),
                'low': status_counts.get('low', 0),
                'warning': status_counts.get('warning', 0),
                'sufficient': status_counts.get('sufficient', 0),
                'total_shortage_items': status_counts.get('critical', 0) + status_counts.get('low', 0),
            }
        }
        
        logger.info(f"Results: {result['summary']}")
        
        return result
    
    def run_full_pipeline(
        self,
        prev_month_weather: Dict[str, float],
        forecast_weather: Dict[str, float],
        target_month: int,
        target_year: int = None,
        current_inventory: Optional[Dict[str, float]] = None,
        csv_files: Optional[List[str]] = None
    ) -> Dict:
        """
        Chạy toàn bộ pipeline từ đầu đến cuối.
        
        Args:
            prev_month_weather: Thời tiết tháng trước
            forecast_weather: Dự báo thời tiết tháng tới
            target_month: Tháng cần dự báo
            target_year: Năm cần dự báo
            current_inventory: Tồn kho hiện tại {DrugName: quantity}
            csv_files: Danh sách file CSV (optional, auto-discover nếu None)
            
        Returns:
            Dict chứa toàn bộ kết quả pipeline
        """
        logger.info("=" * 60)
        logger.info("RUNNING FULL FORECASTING PIPELINE")
        logger.info("=" * 60)
        
        # Step 1: Load data (skip if đã load)
        if self.is_data_loaded and not csv_files:
            logger.info("=== Step 1: Skipped — data đã được load ===")
            data_summary = {
                'files_loaded': 0,
                'total_records': len(self.csv_processor.raw_data) if self.csv_processor.raw_data is not None else 0,
                'date_range': {'from': '', 'to': ''},
                'months_available': 0,
                'disease_groups': [],
            }
        else:
            data_summary = self.load_training_data(csv_files)
        
        # Step 2: Train models (skip if đã train)
        if self.is_trained and not csv_files:
            logger.info("=== Step 2: Skipped — models đã được train ===")
            training_metrics = {}
        else:
            training_metrics = self.train_models()
        
        # Step 3-4: Forecast
        forecast_result = self.forecast_next_month(
            prev_month_weather=prev_month_weather,
            forecast_weather=forecast_weather,
            target_month=target_month,
            target_year=target_year
        )
        
        # Step 4 (cont): Calculate supply demand
        demand_df = self.calculate_supply_demand(forecast_result)
        
        # Step 5-6: Compare & suggest (if inventory provided)
        inventory_result = None
        if current_inventory is not None and not demand_df.empty:
            inventory_result = self.compare_and_suggest(demand_df, current_inventory)
        
        # Final result
        pipeline_result = {
            'data_summary': data_summary,
            'training_metrics': training_metrics,
            'forecast': forecast_result,
            'supply_demand': demand_df.to_dict('records') if not demand_df.empty else [],
            'inventory_comparison': inventory_result,
            'pipeline_completed_at': datetime.now().isoformat()
        }
        
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)
        
        return pipeline_result
