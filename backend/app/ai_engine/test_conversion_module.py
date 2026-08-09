"""
Unit Tests for Conversion Module

This module contains comprehensive unit tests for the ConversionModule class.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from .conversion_module import ConversionModule
from .config import DEFAULT_CONVERSION_RATIOS


# Test fixtures
@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return Mock()


@pytest.fixture
def conversion_module(mock_db_session):
    """Create a ConversionModule instance with mock database."""
    return ConversionModule(mock_db_session)


@pytest.fixture
def sample_conversion_ratios():
    """Sample conversion ratios from database."""
    return [
        ('dengue_fever', Decimal('2.0'), 1, 'masks'),
        ('dengue_fever', Decimal('4.0'), 2, 'gloves'),
        ('dengue_fever', Decimal('1.0'), 3, 'test_kits'),
        ('dengue_fever', Decimal('0.5'), 4, 'disinfectant'),
        ('seasonal_flu', Decimal('2.5'), 1, 'masks'),  # Override default
        ('seasonal_flu', Decimal('4.0'), 2, 'gloves'),
    ]


@pytest.fixture
def mock_db_with_ratios(mock_db_session, sample_conversion_ratios):
    """Mock database session with conversion ratios."""
    # Create mock query result
    mock_query = Mock()
    mock_query.join.return_value = mock_query
    mock_query.all.return_value = sample_conversion_ratios
    
    mock_db_session.query.return_value = mock_query
    
    return mock_db_session


class TestConversionModuleInitialization:
    """Test ConversionModule initialization."""
    
    def test_initialization(self, mock_db_session):
        """Test that ConversionModule initializes correctly."""
        module = ConversionModule(mock_db_session)
        
        assert module.db == mock_db_session
        assert module.conversion_ratios == {}
        assert module.supply_name_to_id == {}
    
    def test_initialization_with_none_db(self):
        """Test initialization with None database raises no error."""
        # Should not raise an error during initialization
        module = ConversionModule(None)
        assert module.db is None


class TestLoadConversionRatios:
    """Test loading conversion ratios from database."""
    
    def test_load_conversion_ratios_success(self, mock_db_with_ratios):
        """Test successful loading of conversion ratios."""
        module = ConversionModule(mock_db_with_ratios)
        ratios = module.load_conversion_ratios()
        
        # Verify ratios were loaded
        assert len(ratios) == 6
        assert ('dengue_fever', 'masks') in ratios
        assert ratios[('dengue_fever', 'masks')] == 2.0
        assert ratios[('dengue_fever', 'gloves')] == 4.0
        assert ratios[('dengue_fever', 'test_kits')] == 1.0
        assert ratios[('dengue_fever', 'disinfectant')] == 0.5
        
        # Verify supply name to ID mapping
        assert module.supply_name_to_id['masks'] == 1
        assert module.supply_name_to_id['gloves'] == 2
        assert module.supply_name_to_id['test_kits'] == 3
        assert module.supply_name_to_id['disinfectant'] == 4
    
    def test_load_conversion_ratios_empty_database(self, mock_db_session):
        """Test loading when database has no ratios."""
        # Mock empty result
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = []
        mock_db_session.query.return_value = mock_query
        
        module = ConversionModule(mock_db_session)
        ratios = module.load_conversion_ratios()
        
        assert len(ratios) == 0
        assert len(module.supply_name_to_id) == 0
    
    def test_load_conversion_ratios_database_error(self, mock_db_session):
        """Test handling of database errors during loading."""
        # Mock database error
        mock_db_session.query.side_effect = Exception("Database connection error")
        
        module = ConversionModule(mock_db_session)
        
        with pytest.raises(Exception) as exc_info:
            module.load_conversion_ratios()
        
        assert "Database connection error" in str(exc_info.value)


class TestGetConversionRatio:
    """Test getting conversion ratios."""
    
    def test_get_ratio_from_database(self, mock_db_with_ratios):
        """Test getting ratio that exists in database."""
        module = ConversionModule(mock_db_with_ratios)
        module.load_conversion_ratios()
        
        ratio = module.get_conversion_ratio('dengue_fever', 'masks')
        assert ratio == 2.0
    
    def test_get_ratio_from_defaults(self, conversion_module):
        """Test getting ratio from default config when not in database."""
        # Don't load from database, so it falls back to defaults
        ratio = conversion_module.get_conversion_ratio('dengue_fever', 'masks')
        
        # Should get default ratio
        assert ratio == DEFAULT_CONVERSION_RATIOS['dengue_fever']['masks']
    
    def test_get_ratio_database_overrides_default(self, mock_db_with_ratios):
        """Test that database ratios override default ratios."""
        module = ConversionModule(mock_db_with_ratios)
        module.load_conversion_ratios()
        
        # seasonal_flu masks has custom ratio 2.5 in database
        ratio = module.get_conversion_ratio('seasonal_flu', 'masks')
        assert ratio == 2.5  # Database value
        assert ratio != DEFAULT_CONVERSION_RATIOS['seasonal_flu']['masks']  # Not default
    
    def test_get_ratio_not_found(self, conversion_module):
        """Test getting ratio that doesn't exist."""
        ratio = conversion_module.get_conversion_ratio('unknown_disease', 'unknown_supply')
        assert ratio is None
    
    def test_get_ratio_disease_exists_supply_not(self, conversion_module):
        """Test getting ratio for valid disease but invalid supply."""
        ratio = conversion_module.get_conversion_ratio('dengue_fever', 'nonexistent_supply')
        assert ratio is None


class TestCalculateRequirements:
    """Test calculating supply requirements."""
    
    def test_calculate_requirements_basic(self, mock_db_with_ratios):
        """Test basic requirement calculation."""
        module = ConversionModule(mock_db_with_ratios)
        module.load_conversion_ratios()
        
        requirements = module.calculate_requirements(
            disease_type='dengue_fever',
            predicted_cases=100,
            forecast_date=pd.Timestamp('2024-01-15')
        )
        
        # Should have requirements for all dengue_fever supplies
        assert len(requirements) > 0
        
        # Check masks requirement
        masks_req = next(r for r in requirements if r['supply_name'] == 'masks')
        assert masks_req['required_quantity'] == 200  # 100 cases × 2.0 ratio
        assert masks_req['disease_type'] == 'dengue_fever'
        assert masks_req['forecast_date'] == date(2024, 1, 15)
        assert masks_req['conversion_ratio'] == 2.0
        assert masks_req['supply_id'] == 1
        
        # Check gloves requirement
        gloves_req = next(r for r in requirements if r['supply_name'] == 'gloves')
        assert gloves_req['required_quantity'] == 400  # 100 cases × 4.0 ratio
        
        # Check test_kits requirement
        test_kits_req = next(r for r in requirements if r['supply_name'] == 'test_kits')
        assert test_kits_req['required_quantity'] == 100  # 100 cases × 1.0 ratio
        
        # Check disinfectant requirement
        disinfectant_req = next(r for r in requirements if r['supply_name'] == 'disinfectant')
        assert disinfectant_req['required_quantity'] == 50  # 100 cases × 0.5 ratio
    
    def test_calculate_requirements_with_defaults(self, conversion_module):
        """Test calculation using default ratios when database is empty."""
        requirements = conversion_module.calculate_requirements(
            disease_type='dengue_fever',
            predicted_cases=100,
            forecast_date=pd.Timestamp('2024-01-15')
        )
        
        # Should have requirements based on default ratios
        assert len(requirements) > 0
        
        # Verify default ratios are applied
        masks_req = next(r for r in requirements if r['supply_name'] == 'masks')
        assert masks_req['required_quantity'] == 200  # Default ratio is 2.0
    
    def test_calculate_requirements_specific_supplies(self, mock_db_with_ratios):
        """Test calculation for specific supply types only."""
        module = ConversionModule(mock_db_with_ratios)
        module.load_conversion_ratios()
        
        requirements = module.calculate_requirements(
            disease_type='dengue_fever',
            predicted_cases=100,
            forecast_date=pd.Timestamp('2024-01-15'),
            supply_types=['masks', 'gloves']
        )
        
        # Should only have masks and gloves
        assert len(requirements) == 2
        supply_names = [r['supply_name'] for r in requirements]
        assert 'masks' in supply_names
        assert 'gloves' in supply_names
        assert 'test_kits' not in supply_names
    
    def test_calculate_requirements_zero_cases(self, mock_db_with_ratios):
        """Test calculation with zero predicted cases."""
        module = ConversionModule(mock_db_with_ratios)
        module.load_conversion_ratios()
        
        requirements = module.calculate_requirements(
            disease_type='dengue_fever',
            predicted_cases=0,
            forecast_date=pd.Timestamp('2024-01-15')
        )
        
        # Should have requirements but all quantities should be 0
        for req in requirements:
            assert req['required_quantity'] == 0
    
    def test_calculate_requirements_fractional_result(self, mock_db_with_ratios):
        """Test that fractional results are converted to integers."""
        module = ConversionModule(mock_db_with_ratios)
        module.load_conversion_ratios()
        
        requirements = module.calculate_requirements(
            disease_type='dengue_fever',
            predicted_cases=75,  # 75 × 0.5 = 37.5
            forecast_date=pd.Timestamp('2024-01-15'),
            supply_types=['disinfectant']
        )
        
        disinfectant_req = requirements[0]
        assert disinfectant_req['required_quantity'] == 37  # Truncated to int
        assert isinstance(disinfectant_req['required_quantity'], int)
    
    def test_calculate_requirements_unknown_disease(self, conversion_module):
        """Test calculation for unknown disease type."""
        requirements = conversion_module.calculate_requirements(
            disease_type='unknown_disease',
            predicted_cases=100,
            forecast_date=pd.Timestamp('2024-01-15')
        )
        
        # Should return empty list since no ratios exist
        assert len(requirements) == 0


class TestCalculateRequirementsForForecast:
    """Test calculating requirements for multiple forecast dates."""
    
    def test_calculate_for_multiple_dates(self, mock_db_with_ratios):
        """Test calculation for multiple forecast dates."""
        module = ConversionModule(mock_db_with_ratios)
        module.load_conversion_ratios()
        
        predictions = np.array([100, 105, 110, 115, 120, 125, 130])
        forecast_dates = pd.date_range('2024-01-15', periods=7)
        
        requirements = module.calculate_requirements_for_forecast(
            disease_type='dengue_fever',
            predictions=predictions,
            forecast_dates=forecast_dates
        )
        
        # Should have requirements for all dates and supplies
        # 7 dates × 4 supplies (from database) + additional from defaults
        assert len(requirements) > 0
        
        # Verify requirements for first date
        first_date_reqs = [r for r in requirements if r['forecast_date'] == date(2024, 1, 15)]
        assert len(first_date_reqs) > 0
        
        # Verify requirements for last date
        last_date_reqs = [r for r in requirements if r['forecast_date'] == date(2024, 1, 21)]
        assert len(last_date_reqs) > 0
        
        # Verify quantities increase with case counts
        first_masks = next(r for r in first_date_reqs if r['supply_name'] == 'masks')
        last_masks = next(r for r in last_date_reqs if r['supply_name'] == 'masks')
        assert last_masks['required_quantity'] > first_masks['required_quantity']
    
    def test_calculate_for_single_date(self, mock_db_with_ratios):
        """Test calculation for single forecast date."""
        module = ConversionModule(mock_db_with_ratios)
        module.load_conversion_ratios()
        
        predictions = np.array([100])
        forecast_dates = pd.date_range('2024-01-15', periods=1)
        
        requirements = module.calculate_requirements_for_forecast(
            disease_type='dengue_fever',
            predictions=predictions,
            forecast_dates=forecast_dates
        )
        
        # Should have requirements for one date
        assert len(requirements) > 0
        unique_dates = set(r['forecast_date'] for r in requirements)
        assert len(unique_dates) == 1
    
    def test_calculate_for_forecast_with_specific_supplies(self, mock_db_with_ratios):
        """Test calculation for multiple dates with specific supplies."""
        module = ConversionModule(mock_db_with_ratios)
        module.load_conversion_ratios()
        
        predictions = np.array([100, 110, 120])
        forecast_dates = pd.date_range('2024-01-15', periods=3)
        
        requirements = module.calculate_requirements_for_forecast(
            disease_type='dengue_fever',
            predictions=predictions,
            forecast_dates=forecast_dates,
            supply_types=['masks']
        )
        
        # Should have 3 dates × 1 supply = 3 requirements
        assert len(requirements) == 3
        assert all(r['supply_name'] == 'masks' for r in requirements)


class TestGetDefaultRatios:
    """Test getting default conversion ratios."""
    
    def test_get_default_ratios_dengue_fever(self, conversion_module):
        """Test getting default ratios for dengue fever."""
        ratios = conversion_module.get_default_ratios('dengue_fever')
        
        assert 'masks' in ratios
        assert 'gloves' in ratios
        assert 'test_kits' in ratios
        assert 'disinfectant' in ratios
        
        assert ratios['masks'] == 2.0
        assert ratios['gloves'] == 4.0
        assert ratios['test_kits'] == 1.0
        assert ratios['disinfectant'] == 0.5
    
    def test_get_default_ratios_seasonal_flu(self, conversion_module):
        """Test getting default ratios for seasonal flu."""
        ratios = conversion_module.get_default_ratios('seasonal_flu')
        
        assert 'masks' in ratios
        assert 'gloves' in ratios
        assert ratios['masks'] == 2.0
        assert ratios['gloves'] == 4.0
    
    def test_get_default_ratios_unknown_disease(self, conversion_module):
        """Test getting default ratios for unknown disease."""
        ratios = conversion_module.get_default_ratios('unknown_disease')
        
        assert ratios == {}


class TestGetAllRatiosForDisease:
    """Test getting all ratios for a disease type."""
    
    def test_get_all_ratios_with_database_override(self, mock_db_with_ratios):
        """Test that database ratios override defaults."""
        module = ConversionModule(mock_db_with_ratios)
        module.load_conversion_ratios()
        
        ratios = module.get_all_ratios_for_disease('seasonal_flu')
        
        # Should have database ratio for masks (2.5, not default 2.0)
        assert ratios['masks'] == 2.5
        
        # Should have default ratios for supplies not in database
        assert 'test_kits' in ratios  # From defaults
    
    def test_get_all_ratios_only_defaults(self, conversion_module):
        """Test getting all ratios when only defaults exist."""
        ratios = conversion_module.get_all_ratios_for_disease('dengue_fever')
        
        # Should return default ratios
        assert ratios == DEFAULT_CONVERSION_RATIOS['dengue_fever']
    
    def test_get_all_ratios_unknown_disease(self, conversion_module):
        """Test getting all ratios for unknown disease."""
        ratios = conversion_module.get_all_ratios_for_disease('unknown_disease')
        
        assert ratios == {}


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    def test_full_workflow(self, mock_db_with_ratios):
        """Test complete workflow from initialization to calculation."""
        # Initialize module
        module = ConversionModule(mock_db_with_ratios)
        
        # Load ratios
        module.load_conversion_ratios()
        
        # Calculate requirements
        requirements = module.calculate_requirements(
            disease_type='dengue_fever',
            predicted_cases=150,
            forecast_date=pd.Timestamp('2024-01-15')
        )
        
        # Verify results
        assert len(requirements) > 0
        
        # Verify specific calculations
        masks_req = next(r for r in requirements if r['supply_name'] == 'masks')
        assert masks_req['required_quantity'] == 300  # 150 × 2.0
    
    def test_disease_specific_ratios(self, mock_db_with_ratios):
        """Test that different diseases use different ratios."""
        module = ConversionModule(mock_db_with_ratios)
        module.load_conversion_ratios()
        
        # Calculate for dengue fever
        dengue_reqs = module.calculate_requirements(
            disease_type='dengue_fever',
            predicted_cases=100,
            forecast_date=pd.Timestamp('2024-01-15'),
            supply_types=['masks']
        )
        
        # Calculate for seasonal flu
        flu_reqs = module.calculate_requirements(
            disease_type='seasonal_flu',
            predicted_cases=100,
            forecast_date=pd.Timestamp('2024-01-15'),
            supply_types=['masks']
        )
        
        # Seasonal flu has custom ratio 2.5, dengue has 2.0
        assert dengue_reqs[0]['required_quantity'] == 200
        assert flu_reqs[0]['required_quantity'] == 250
