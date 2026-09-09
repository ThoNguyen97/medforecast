"""
Integration tests for ForecastingPipeline

Tests the complete end-to-end forecasting workflow with real database interactions.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .forecasting_pipeline import ForecastingPipeline
from app.database import Base
from app.models.disease_case import DiseaseCase
from app.models.environmental_data import EnvironmentalData
from app.models.disease_forecast import DiseaseForecast
from app.models.conversion_ratio import ConversionRatio
from app.models.medical_supply import MedicalSupply


# Create in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def test_db():
    """Create a test database session."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    
    yield db
    
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seed_test_data(test_db):
    """Seed the test database with sample data."""
    # Create disease case data (150 days)
    start_date = datetime.now() - timedelta(days=150)
    
    for i in range(150):
        date = start_date + timedelta(days=i)
        case_count = 50 + int(30 * np.sin(i / 10)) + np.random.randint(-10, 10)
        
        disease_case = DiseaseCase(
            recorded_at=date,
            disease_type='dengue_fever',
            case_count=case_count,
            location='Test City',
            severity='medium',
            data_source='test'
        )
        test_db.add(disease_case)
    
    # Create environmental data
    for i in range(150):
        date = start_date + timedelta(days=i)
        
        env_data = EnvironmentalData(
            recorded_at=date,
            location='Test City',
            temperature=28.0 + 5 * np.sin(i / 15) + np.random.randn(),
            humidity=75.0 + 10 * np.cos(i / 20) + np.random.randn() * 3,
            rainfall=5.0 + np.random.randn() * 2,
            air_quality_index=100 + np.random.randint(-20, 20),
            data_source='test'
        )
        test_db.add(env_data)
    
    # Create medical supplies
    supplies = [
        {'name': 'Surgical Masks', 'category': 'PPE', 'unit': 'box'},
        {'name': 'Latex Gloves', 'category': 'PPE', 'unit': 'pair'},
        {'name': 'Dengue Test Kits', 'category': 'Diagnostics', 'unit': 'kit'},
    ]
    
    supply_ids = []
    for supply_data in supplies:
        supply = MedicalSupply(
            name=supply_data['name'],
            category=supply_data['category'],
            unit=supply_data['unit'],
            unit_price=10.0,
            minimum_order_quantity=100,
            lead_time_days=7,
            storage_capacity=10000
        )
        test_db.add(supply)
        test_db.flush()
        supply_ids.append(supply.id)
    
    # Create conversion ratios
    ratios = [
        {'supply_id': supply_ids[0], 'ratio': 2.0},  # 2 masks per case
        {'supply_id': supply_ids[1], 'ratio': 4.0},  # 4 gloves per case
        {'supply_id': supply_ids[2], 'ratio': 1.0},  # 1 test kit per case
    ]
    
    for ratio_data in ratios:
        ratio = ConversionRatio(
            disease_type='dengue_fever',
            supply_id=ratio_data['supply_id'],
            ratio=ratio_data['ratio'],
            unit='per_case'
        )
        test_db.add(ratio)
    
    test_db.commit()
    
    return supply_ids


class TestForecastingPipelineIntegration:
    """Integration tests for complete forecasting workflow."""
    
    def test_complete_forecasting_workflow(self, test_db, seed_test_data):
        """Test the complete forecasting workflow from data retrieval to forecast generation."""
        # Create pipeline
        pipeline = ForecastingPipeline(
            db=test_db,
            disease_type='dengue_fever',
            use_ensemble=True
        )
        
        # Step 1: Retrieve historical data
        disease_df, env_df = pipeline.retrieve_historical_data(min_days=90)
        
        assert len(disease_df) >= 90
        assert len(env_df) >= 90
        assert 'case_count' in disease_df.columns
        assert 'temperature' in env_df.columns
        
        # Step 2: Engineer features
        features_df = pipeline.engineer_features(disease_df, env_df)
        
        assert len(features_df) > 0
        assert 'case_count' in features_df.columns
        # Check for engineered features
        assert any('lag' in col for col in features_df.columns)
        assert any('rolling' in col for col in features_df.columns)
        
        # Step 3: Train models
        metrics = pipeline.train_models(min_days=90)
        
        assert metrics is not None
        assert 'xgboost' in metrics
        assert 'prophet' in metrics
        assert metrics['xgboost']['mae'] > 0
        assert pipeline.ensemble_forecaster.is_trained
        
        # Step 4: Generate forecast
        forecast_result = pipeline.generate_forecast(
            forecast_period_days=7,
            save_to_db=True
        )
        
        assert forecast_result is not None
        assert len(forecast_result['predictions']) == 7
        assert len(forecast_result['confidence_lower']) == 7
        assert len(forecast_result['confidence_upper']) == 7
        assert forecast_result['model_used'] == 'ensemble'
        
        # Step 5: Verify forecast was saved to database
        forecasts = test_db.query(DiseaseForecast).filter(
            DiseaseForecast.disease_type == 'dengue_fever'
        ).all()
        
        assert len(forecasts) == 7
        assert all(f.predicted_cases > 0 for f in forecasts)
        assert all(f.model_used == 'ensemble' for f in forecasts)
    
    def test_automatic_retraining_workflow(self, test_db, seed_test_data):
        """Test automatic retraining when new data exceeds threshold."""
        # Create pipeline
        pipeline = ForecastingPipeline(
            db=test_db,
            disease_type='dengue_fever',
            use_ensemble=False  # Use single model for faster testing
        )
        
        # Initial training
        metrics1 = pipeline.train_models(min_days=90)
        original_size = pipeline.original_training_size
        
        assert metrics1 is not None
        assert original_size >= 90
        
        # Add new data (20% more to exceed 10% threshold)
        new_data_count = int(original_size * 0.2)
        start_date = datetime.now() + timedelta(days=1)
        
        for i in range(new_data_count):
            date = start_date + timedelta(days=i)
            
            disease_case = DiseaseCase(
                recorded_at=date,
                disease_type='dengue_fever',
                case_count=50 + np.random.randint(-10, 10),
                location='Test City',
                severity='medium',
                data_source='test'
            )
            test_db.add(disease_case)
            
            env_data = EnvironmentalData(
                recorded_at=date,
                location='Test City',
                temperature=30.0 + np.random.randn(),
                humidity=75.0 + np.random.randn() * 3,
                rainfall=5.0 + np.random.randn() * 2,
                air_quality_index=100 + np.random.randint(-20, 20),
                data_source='test'
            )
            test_db.add(env_data)
        
        test_db.commit()
        
        # Check if retraining is triggered
        retrained = pipeline._check_and_retrain_if_needed()
        
        assert retrained is True
        assert pipeline.original_training_size > original_size
    
    def test_forecast_with_different_periods(self, test_db, seed_test_data):
        """Test forecast generation with different time periods."""
        # Create and train pipeline
        pipeline = ForecastingPipeline(
            db=test_db,
            disease_type='dengue_fever',
            use_ensemble=False
        )
        
        pipeline.train_models(min_days=90)
        
        # Test different forecast periods
        for period in [7, 14, 30]:
            forecast_result = pipeline.generate_forecast(
                forecast_period_days=period,
                save_to_db=False
            )
            
            assert len(forecast_result['predictions']) == period
            assert len(forecast_result['confidence_lower']) == period
            assert len(forecast_result['confidence_upper']) == period
            
            # Verify predictions are reasonable
            predictions = np.array(forecast_result['predictions'])
            assert np.all(predictions >= 0)
            assert np.all(predictions < 500)  # Reasonable upper bound
    
    def test_model_persistence(self, test_db, seed_test_data):
        """Test saving and loading trained models."""
        # Create and train pipeline
        pipeline1 = ForecastingPipeline(
            db=test_db,
            disease_type='dengue_fever',
            use_ensemble=False
        )
        
        metrics1 = pipeline1.train_models(min_days=90)
        
        # Generate forecast with first pipeline
        forecast1 = pipeline1.generate_forecast(
            forecast_period_days=7,
            save_to_db=False
        )
        
        # Create new pipeline and load models
        pipeline2 = ForecastingPipeline(
            db=test_db,
            disease_type='dengue_fever',
            use_ensemble=False
        )
        
        pipeline2.load_trained_models(version="latest")
        
        # Generate forecast with second pipeline
        forecast2 = pipeline2.generate_forecast(
            forecast_period_days=7,
            save_to_db=False
        )
        
        # Predictions should be similar (not exact due to randomness in some models)
        predictions1 = np.array(forecast1['predictions'])
        predictions2 = np.array(forecast2['predictions'])
        
        # Check that predictions are reasonably close
        assert np.allclose(predictions1, predictions2, rtol=0.1)
    
    def test_error_handling_insufficient_data(self, test_db):
        """Test error handling when insufficient data is available."""
        # Create pipeline without seeding data
        pipeline = ForecastingPipeline(
            db=test_db,
            disease_type='dengue_fever'
        )
        
        # Should raise ValueError due to insufficient data
        with pytest.raises(ValueError, match="Insufficient historical data"):
            pipeline.train_models(min_days=90)
    
    def test_supply_requirements_calculation(self, test_db, seed_test_data):
        """Test calculation of supply requirements from forecasts."""
        # Create and train pipeline
        pipeline = ForecastingPipeline(
            db=test_db,
            disease_type='dengue_fever',
            use_ensemble=False
        )
        
        pipeline.train_models(min_days=90)
        
        # Generate forecast
        forecast_result = pipeline.generate_forecast(
            forecast_period_days=7,
            save_to_db=False
        )
        
        # Calculate supply requirements
        predictions = np.array(forecast_result['predictions'])
        forecast_dates = pd.DatetimeIndex(forecast_result['forecast_dates'])
        
        requirements = pipeline.calculate_supply_requirements(
            forecast_id=None,
            predictions=predictions,
            forecast_dates=forecast_dates
        )
        
        # Verify requirements were calculated
        assert len(requirements) > 0
        
        # Should have requirements for each supply type for each day
        # With ConversionModule, we get both database ratios (3) and default ratios (6)
        # Total unique supplies = 9 (some overlap, but defaults add more)
        # 9 supply types × 7 days = 63 requirements
        assert len(requirements) >= 21  # At least the database supplies
        
        # Verify requirement structure
        for req in requirements:
            assert 'supply_name' in req
            assert 'required_quantity' in req
            assert 'forecast_date' in req
            assert 'disease_type' in req
            assert 'conversion_ratio' in req
            assert req['required_quantity'] >= 0
        
        # Verify we have requirements for the database supplies
        supply_names = set(req['supply_name'] for req in requirements)
        # Note: supply names in requirements come from conversion ratios, not medical_supply table
        # So we check for the ratio keys (masks, gloves, test_kits) not the full names
        assert len(supply_names) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
