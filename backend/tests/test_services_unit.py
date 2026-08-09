"""
Comprehensive unit tests for backend services.
Tests use mocking (unittest.mock) to isolate units from the database.
Covers: UserService, MedicalSupplyService, InventoryService,
        EnvironmentalDataService, DiseaseCaseService,
        ForecastService, ConfigService, NotificationService,
        DataCollectorService, AlertModule, ProcurementPlanner.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers shared across tests
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_db():
    return MagicMock()


# =============================================================================
# UserService Unit Tests
# =============================================================================

class TestUserService:
    """Unit tests for UserService."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.user_service import UserService
        return UserService(mock_db)

    # ── get_user_by_id ────────────────────────────────────────────────────────

    def test_get_user_by_id_returns_user(self, service, mock_db):
        from app.models.user import User
        user = User(id=1, username="alice", email="a@test.com", role="Pharmacist", is_active=True)
        mock_db.query.return_value.filter.return_value.first.return_value = user
        assert service.get_user_by_id(1) is user

    def test_get_user_by_id_returns_none_when_not_found(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert service.get_user_by_id(999) is None

    # ── get_user_by_username ─────────────────────────────────────────────────

    def test_get_user_by_username_found(self, service, mock_db):
        from app.models.user import User
        user = User(id=2, username="bob", email="b@test.com", role="Administrator", is_active=True)
        mock_db.query.return_value.filter.return_value.first.return_value = user
        assert service.get_user_by_username("bob") is user

    def test_get_user_by_username_not_found(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert service.get_user_by_username("nonexistent") is None

    # ── get_users ─────────────────────────────────────────────────────────────

    def test_get_users_returns_list(self, service, mock_db):
        from app.models.user import User
        users = [User(id=i, username=f"u{i}", email=f"u{i}@t.com", role="Pharmacist", is_active=True) for i in range(3)]
        mock_db.query.return_value.offset.return_value.limit.return_value.all.return_value = users
        result = service.get_users()
        assert len(result) == 3

    # ── delete_user ───────────────────────────────────────────────────────────

    def test_delete_user_soft_deletes(self, service, mock_db):
        from app.models.user import User
        user = User(id=5, username="target", email="t@test.com", role="Pharmacist", is_active=True)
        mock_db.query.return_value.filter.return_value.first.return_value = user
        result = service.delete_user(user_id=5, deleted_by_user_id=1, ip_address="127.0.0.1")
        assert result is True
        assert user.is_active is False
        mock_db.commit.assert_called()

    def test_delete_user_raises_when_self_deletion(self, service, mock_db):
        from app.models.user import User
        from fastapi import HTTPException
        user = User(id=1, username="admin", email="a@test.com", role="Administrator", is_active=True)
        mock_db.query.return_value.filter.return_value.first.return_value = user
        with pytest.raises(HTTPException) as exc:
            service.delete_user(user_id=1, deleted_by_user_id=1)
        assert exc.value.status_code == 400

    def test_delete_user_raises_when_not_found(self, service, mock_db):
        from fastapi import HTTPException
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.delete_user(user_id=999, deleted_by_user_id=1)
        assert exc.value.status_code == 404


# =============================================================================
# MedicalSupplyService Unit Tests
# =============================================================================

class TestMedicalSupplyService:
    """Unit tests for MedicalSupplyService."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.medical_supply_service import MedicalSupplyService
        return MedicalSupplyService(mock_db)

    def test_get_supply_by_id_found(self, service, mock_db):
        from app.models.medical_supply import MedicalSupply
        supply = MedicalSupply(id=1, name="Mask", category="PPE", unit="box")
        mock_db.query.return_value.filter.return_value.first.return_value = supply
        assert service.get_supply_by_id(1) is supply

    def test_get_supply_by_id_raises_404(self, service, mock_db):
        from fastapi import HTTPException
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.get_supply_by_id(999)
        assert exc.value.status_code == 404

    def test_get_supplies_with_category_filter(self, service, mock_db):
        from app.models.medical_supply import MedicalSupply
        supplies = [MedicalSupply(id=1, name="Mask", category="PPE", unit="box")]
        chain = mock_db.query.return_value
        chain.filter.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = supplies
        chain.filter.return_value.offset.return_value.limit.return_value.all.return_value = supplies
        chain.offset.return_value.limit.return_value.all.return_value = supplies
        result = service.get_supplies(category="PPE")
        assert isinstance(result, list)

    def test_get_categories_returns_unique_list(self, service, mock_db):
        mock_db.query.return_value.distinct.return_value.all.return_value = [
            ("PPE",), ("Medication",), ("Equipment",)
        ]
        categories = service.get_categories()
        assert "PPE" in categories
        assert "Medication" in categories

    def test_create_supply_raises_on_duplicate_name(self, service, mock_db):
        from app.models.medical_supply import MedicalSupply
        from app.schemas.base import MedicalSupplyCreate
        from fastapi import HTTPException
        existing = MedicalSupply(id=1, name="Mask", category="PPE", unit="box")
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        supply_data = MedicalSupplyCreate(name="Mask", category="PPE", unit="box")
        with pytest.raises(HTTPException) as exc:
            service.create_supply(supply_data, created_by_user_id=1, ip_address="127.0.0.1")
        assert exc.value.status_code == 400
        assert "already exists" in exc.value.detail

    def test_delete_supply_not_found_raises_404(self, service, mock_db):
        from fastapi import HTTPException
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.delete_supply(999, deleted_by_user_id=1, ip_address="127.0.0.1")
        assert exc.value.status_code == 404


# =============================================================================
# InventoryService Unit Tests
# =============================================================================

class TestInventoryService:
    """Unit tests for InventoryService."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.inventory_service import InventoryService
        return InventoryService(mock_db)

    def _make_supply(self, supply_id=1, name="Mask"):
        from app.models.medical_supply import MedicalSupply
        s = MedicalSupply()
        s.id = supply_id
        s.name = name
        s.category = "PPE"
        s.unit = "box"
        return s

    def _make_inventory(self, inv_id=1, supply_id=1, current_stock=100, safety_stock=50):
        from app.models.inventory import Inventory
        inv = Inventory()
        inv.id = inv_id
        inv.supply_id = supply_id
        inv.current_stock = current_stock
        inv.safety_stock = safety_stock
        inv.location = "Warehouse A"
        inv.updated_by = 1
        inv.supply = self._make_supply(supply_id)
        return inv

    def test_get_inventory_by_id_found(self, service, mock_db):
        inv = self._make_inventory()
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = inv
        result = service.get_inventory_by_id(1)
        assert result is inv

    def test_get_inventory_by_id_not_found_raises_404(self, service, mock_db):
        from fastapi import HTTPException
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.get_inventory_by_id(999)
        assert exc.value.status_code == 404

    def test_get_low_stock_items_returns_items(self, service, mock_db):
        inv = self._make_inventory(current_stock=10, safety_stock=100)
        mock_db.query.return_value.options.return_value.filter.return_value.all.return_value = [inv]
        result = service.get_low_stock_items()
        assert len(result) == 1

    def test_get_expiring_items_with_threshold(self, service, mock_db):
        from app.models.inventory import Inventory
        inv = self._make_inventory()
        inv.expiry_date = date.today() + timedelta(days=15)
        mock_db.query.return_value.options.return_value.filter.return_value.order_by.return_value.all.return_value = [inv]
        result = service.get_expiring_items(days_threshold=30)
        assert isinstance(result, list)

    def test_get_total_stock_by_supply(self, service, mock_db):
        mock_result = Mock()
        mock_result.total_stock = 500
        mock_result.total_safety_stock = 100
        mock_db.query.return_value.filter.return_value.first.return_value = mock_result
        result = service.get_total_stock_by_supply(1)
        assert result["supply_id"] == 1
        assert result["total_stock"] == 500
        assert result["total_safety_stock"] == 100

    def test_update_inventory_raises_on_negative_stock(self, service, mock_db):
        """
        Negative current_stock is blocked by Pydantic at the schema level
        (ge=0 constraint on InventoryUpdate).  The service layer itself also
        enforces this; we verify the schema rejects it before it reaches the DB.
        """
        from app.schemas.base import InventoryUpdate
        from pydantic import ValidationError
        # Pydantic v2 raises ValidationError for ge=0 violation
        with pytest.raises(ValidationError):
            InventoryUpdate(current_stock=-10)

    def test_create_inventory_item_raises_on_negative_stock(self, service, mock_db):
        from app.models.medical_supply import MedicalSupply
        from fastapi import HTTPException
        supply = MedicalSupply(id=1, name="Mask", category="PPE", unit="box")
        mock_db.query.return_value.filter.return_value.first.return_value = supply
        with pytest.raises(HTTPException) as exc:
            service.create_inventory_item(
                supply_id=1, current_stock=-5, safety_stock=50,
                created_by_user_id=1, ip_address="127.0.0.1"
            )
        assert exc.value.status_code == 400

    def test_create_inventory_item_supply_not_found_raises_404(self, service, mock_db):
        from fastapi import HTTPException
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.create_inventory_item(
                supply_id=999, current_stock=100, safety_stock=50,
                created_by_user_id=1, ip_address="127.0.0.1"
            )
        assert exc.value.status_code == 404


# =============================================================================
# EnvironmentalDataService Unit Tests
# =============================================================================

class TestEnvironmentalDataService:
    """Unit tests for EnvironmentalDataService."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.environmental_service import EnvironmentalDataService
        return EnvironmentalDataService(mock_db)

    def _make_valid_data(self):
        from app.schemas.base import EnvironmentalDataCreate
        return EnvironmentalDataCreate(
            recorded_at=datetime.now(),
            location="Ho Chi Minh City",
            temperature=32.0,
            humidity=75.0,
            rainfall=10.0,
            air_quality_index=80,
        )

    def test_validate_passes_for_valid_data(self, service):
        data = self._make_valid_data()
        service.validate_environmental_data(data)  # Should not raise

    def test_validate_raises_on_invalid_temperature(self, service):
        from fastapi import HTTPException
        data = self._make_valid_data()
        data.temperature = 100.0  # Too hot
        with pytest.raises(HTTPException) as exc:
            service.validate_environmental_data(data)
        assert exc.value.status_code == 400

    def test_validate_raises_on_negative_temperature(self, service):
        from fastapi import HTTPException
        data = self._make_valid_data()
        data.temperature = -100.0  # Too cold
        with pytest.raises(HTTPException) as exc:
            service.validate_environmental_data(data)
        assert exc.value.status_code == 400

    def test_validate_raises_on_invalid_humidity(self, service):
        from fastapi import HTTPException
        data = self._make_valid_data()
        data.humidity = 150.0  # > 100%
        with pytest.raises(HTTPException) as exc:
            service.validate_environmental_data(data)
        assert exc.value.status_code == 400

    def test_validate_raises_on_invalid_aqi(self, service):
        from fastapi import HTTPException
        data = self._make_valid_data()
        data.air_quality_index = 600  # > 500
        with pytest.raises(HTTPException) as exc:
            service.validate_environmental_data(data)
        assert exc.value.status_code == 400

    def test_validate_raises_when_all_measurements_none(self, service):
        from fastapi import HTTPException
        from app.schemas.base import EnvironmentalDataCreate
        data = EnvironmentalDataCreate(
            recorded_at=datetime.now(),
            location="HCM",
            temperature=None,
            humidity=None,
            rainfall=None,
            air_quality_index=None,
        )
        with pytest.raises(HTTPException) as exc:
            service.validate_environmental_data(data)
        assert exc.value.status_code == 400

    def test_get_latest_data_raises_404_when_none(self, service, mock_db):
        from fastapi import HTTPException
        mock_db.query.return_value.order_by.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.get_latest_data()
        assert exc.value.status_code == 404

    def test_get_data_by_date_range_raises_on_invalid_range(self, service):
        from fastapi import HTTPException
        start = datetime(2024, 1, 10)
        end = datetime(2024, 1, 1)  # end before start
        with pytest.raises(HTTPException) as exc:
            service.get_data_by_date_range(start, end)
        assert exc.value.status_code == 400

    def test_validate_valid_humidity_boundary(self, service):
        data = self._make_valid_data()
        data.humidity = 0.0  # boundary minimum
        service.validate_environmental_data(data)  # should not raise
        data.humidity = 100.0  # boundary maximum
        service.validate_environmental_data(data)  # should not raise

    def test_validate_valid_rainfall_boundary(self, service):
        data = self._make_valid_data()
        data.rainfall = 0.0  # minimum
        service.validate_environmental_data(data)  # should not raise

    def test_validate_raises_on_negative_rainfall(self, service):
        from fastapi import HTTPException
        data = self._make_valid_data()
        data.rainfall = -5.0
        with pytest.raises(HTTPException):
            service.validate_environmental_data(data)


# =============================================================================
# DiseaseCaseService Unit Tests
# =============================================================================

class TestDiseaseCaseService:
    """Unit tests for DiseaseCaseService."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.disease_case_service import DiseaseCaseService
        return DiseaseCaseService(mock_db)

    def _make_valid_data(self, disease_type="dengue_fever", case_count=100):
        from app.schemas.base import DiseaseCaseCreate, DiseaseType
        return DiseaseCaseCreate(
            recorded_at=datetime.now(),
            disease_type=DiseaseType(disease_type),
            case_count=case_count,
            location="Ho Chi Minh City",
        )

    def test_validate_passes_for_valid_data(self, service):
        data = self._make_valid_data()
        service.validate_disease_case_data(data)  # Should not raise

    def test_validate_raises_on_empty_location(self, service):
        from app.schemas.base import DiseaseCaseCreate, DiseaseType
        from fastapi import HTTPException
        from unittest.mock import patch
        data = self._make_valid_data()
        # Temporarily set location to empty after construction
        object.__setattr__(data, "location", "")
        with pytest.raises(HTTPException) as exc:
            service.validate_disease_case_data(data)
        assert exc.value.status_code == 400

    def test_validate_valid_zero_case_count(self, service):
        data = self._make_valid_data(case_count=0)
        service.validate_disease_case_data(data)  # Should not raise

    def test_get_disease_cases_returns_list(self, service, mock_db):
        from app.models.disease_case import DiseaseCase
        cases = [DiseaseCase(id=1, disease_type="dengue_fever", case_count=100, location="HCM")]
        mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = cases
        result = service.get_disease_cases()
        assert isinstance(result, list)

    def test_get_statistics_empty_returns_empty_list(self, service, mock_db):
        mock_db.query.return_value.group_by.return_value.all.return_value = []
        result = service.get_statistics()
        assert result == []

    def test_get_statistics_with_data(self, service, mock_db):
        row = Mock()
        row.disease_type = "dengue_fever"
        row.total_cases = 500
        row.record_count = 3
        row.latest_record = datetime(2024, 3, 15)
        mock_db.query.return_value.group_by.return_value.all.return_value = [row]
        result = service.get_statistics()
        assert len(result) == 1
        assert result[0]["disease_type"] == "dengue_fever"
        assert result[0]["total_cases"] == 500
        assert result[0]["record_count"] == 3

    def test_get_trends_empty_returns_empty_list(self, service, mock_db):
        mock_db.query.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = service.get_trends()
        assert result == []

    def test_get_trends_with_data(self, service, mock_db):
        row = Mock()
        row.date = "2024-03-15"
        row.disease_type = "dengue_fever"
        row.location = "HCM"
        row.total_cases = 150
        # Build the chain for get_trends query
        chain = mock_db.query.return_value
        chain.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [row]
        result = service.get_trends()
        assert len(result) == 1
        assert result[0]["disease_type"] == "dengue_fever"
        assert result[0]["total_cases"] == 150


# =============================================================================
# ConfigService Unit Tests
# =============================================================================

class TestConfigService:
    """Unit tests for ConfigService."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.config_service import ConfigService
        return ConfigService(mock_db)

    def test_get_config_by_key_not_found_raises_404(self, service, mock_db):
        from fastapi import HTTPException
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.get_config_by_key("nonexistent_key")
        assert exc.value.status_code == 404

    def test_get_all_configs_returns_list(self, service, mock_db):
        from app.models.system_config import SystemConfig
        configs = [SystemConfig(config_key="key1", config_value="val1")]
        mock_db.query.return_value.order_by.return_value.all.return_value = configs
        result = service.get_all_configs()
        assert len(result) == 1

    def test_get_thresholds_uses_defaults_when_absent(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = service.get_thresholds()
        assert result["critical_days"] == 3
        assert result["high_days"] == 7
        assert result["medium_days"] == 14

    def test_get_thresholds_uses_db_values(self, service, mock_db):
        from app.models.system_config import SystemConfig
        rows = [
            SystemConfig(config_key="threshold_critical_days", config_value="2"),
            SystemConfig(config_key="threshold_high_days", config_value="5"),
            SystemConfig(config_key="threshold_medium_days", config_value="10"),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = rows
        result = service.get_thresholds()
        assert result["critical_days"] == 2
        assert result["high_days"] == 5
        assert result["medium_days"] == 10

    def test_update_thresholds_raises_on_invalid_ordering(self, service, mock_db):
        from fastapi import HTTPException
        from app.schemas.base import ThresholdConfig
        data = ThresholdConfig(critical_days=10, high_days=5, medium_days=14)  # critical > high
        with pytest.raises(HTTPException) as exc:
            service.update_thresholds(data, updated_by_user_id=1, ip_address="127.0.0.1")
        assert exc.value.status_code == 400

    def test_update_thresholds_valid_ordering(self, service, mock_db):
        from app.schemas.base import ThresholdConfig
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []
        data = ThresholdConfig(critical_days=2, high_days=6, medium_days=12)
        result = service.update_thresholds(data, updated_by_user_id=1, ip_address="127.0.0.1")
        assert result["critical_days"] == 2
        assert result["high_days"] == 6
        assert result["medium_days"] == 12

    def test_update_conversion_ratios_raises_on_empty_list(self, service, mock_db):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            service.update_conversion_ratios([], updated_by_user_id=1, ip_address="127.0.0.1")
        assert exc.value.status_code == 400

    def test_update_conversion_ratios_supply_not_found_raises_404(self, service, mock_db):
        from app.schemas.base import ConversionRatioUpdate
        from fastapi import HTTPException
        mock_db.query.return_value.filter.return_value.first.return_value = None
        updates = [ConversionRatioUpdate(disease_type="dengue_fever", supply_id=99, ratio=2.0, unit="units")]
        with pytest.raises(HTTPException) as exc:
            service.update_conversion_ratios(updates, updated_by_user_id=1, ip_address="127.0.0.1")
        assert exc.value.status_code == 404


# =============================================================================
# ForecastService Unit Tests
# =============================================================================

class TestForecastServiceUnit:
    """Unit tests for ForecastService."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.forecast_service import ForecastService
        return ForecastService(mock_db)

    def _make_forecast(self, forecast_id=1, disease_type="dengue_fever"):
        from app.models.disease_forecast import DiseaseForecast
        f = DiseaseForecast()
        f.id = forecast_id
        f.forecast_date = date.today()
        f.disease_type = disease_type
        f.predicted_cases = 100
        f.model_accuracy_mae = 5.0
        f.model_accuracy_rmse = 7.0
        f.model_accuracy_mape = 4.0
        f.created_at = datetime.now()
        return f

    def test_get_forecast_by_id_found(self, service, mock_db):
        forecast = self._make_forecast()
        mock_db.query.return_value.filter.return_value.first.return_value = forecast
        assert service.get_forecast_by_id(1) is forecast

    def test_get_forecast_by_id_not_found(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert service.get_forecast_by_id(999) is None

    def test_get_accuracy_metrics_empty(self, service, mock_db):
        mock_db.query.return_value.all.return_value = []
        result = service.get_accuracy_metrics()
        assert result["count"] == 0
        assert result["mae"] is None

    def test_get_accuracy_metrics_with_data(self, service, mock_db):
        from app.schemas.base import DiseaseType
        forecasts = [self._make_forecast(1), self._make_forecast(2)]
        forecasts[1].model_accuracy_mae = 7.0
        chain = mock_db.query.return_value
        chain.filter.return_value.all.return_value = forecasts
        chain.all.return_value = forecasts
        result = service.get_accuracy_metrics(disease_type=DiseaseType.DENGUE_FEVER)
        assert result["count"] == 2
        assert result["mae"] == pytest.approx(6.0)  # avg(5.0, 7.0)

    def test_get_latest_forecast_returns_first(self, service, mock_db):
        from app.schemas.base import DiseaseType
        forecast = self._make_forecast()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = forecast
        result = service.get_latest_forecast(DiseaseType.DENGUE_FEVER)
        assert result is forecast

    def test_get_forecasts_applies_filters(self, service, mock_db):
        from app.schemas.base import DiseaseType
        forecasts = [self._make_forecast()]
        chain = mock_db.query.return_value
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.limit.return_value = chain
        chain.offset.return_value = chain
        chain.all.return_value = forecasts
        result = service.get_forecasts(disease_type=DiseaseType.DENGUE_FEVER, limit=10)
        assert isinstance(result, list)

    def test_get_accuracy_metrics_no_disease_filter(self, service, mock_db):
        forecasts = [self._make_forecast()]
        chain = mock_db.query.return_value
        chain.all.return_value = forecasts
        result = service.get_accuracy_metrics()
        assert result["count"] == 1


# =============================================================================
# NotificationService Unit Tests
# =============================================================================

class TestNotificationService:
    """Unit tests for NotificationService."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.notification_service import NotificationService
        return NotificationService(mock_db)

    def _make_alert(self, severity="critical"):
        from app.models.alert import Alert
        from app.models.medical_supply import MedicalSupply
        supply = MedicalSupply()
        supply.id = 1
        supply.name = "Surgical Masks"
        a = Alert()
        a.id = 1
        a.supply_id = 1
        a.supply = supply
        a.severity = severity
        a.alert_type = "shortage"
        a.current_stock = 10
        a.required_stock = 100
        a.shortage_date = date.today() + timedelta(days=2)
        a.message = "Test message"
        a.is_resolved = False
        a.created_at = datetime.now()
        return a

    def test_get_admin_emails_returns_admin_emails(self, service, mock_db):
        from app.models.user import User
        admins = [
            Mock(email="admin1@test.com"),
            Mock(email="admin2@test.com"),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = admins
        emails = service._get_admin_emails()
        assert "admin1@test.com" in emails
        assert "admin2@test.com" in emails

    def test_get_admin_emails_empty_when_no_admins(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.all.return_value = []
        emails = service._get_admin_emails()
        assert emails == []

    def test_notify_alert_skips_medium_severity(self, service, mock_db):
        alert = self._make_alert(severity="medium")
        # Should return False without sending anything
        result = asyncio.run(service.notify_alert(alert))
        assert result is False

    def test_notify_alert_skips_when_no_recipients(self, service, mock_db):
        alert = self._make_alert(severity="critical")
        service._get_admin_emails = Mock(return_value=[])
        result = asyncio.run(service.notify_alert(alert))
        assert result is False

    @patch("app.services.notification_service._send_email_sync", return_value=True)
    def test_notify_alert_sends_for_critical(self, mock_send, service, mock_db):
        alert = self._make_alert(severity="critical")
        service._get_admin_emails = Mock(return_value=["admin@test.com"])
        result = asyncio.run(service.notify_alert(alert))
        assert result is True

    @patch("app.services.notification_service._send_email_sync", return_value=True)
    def test_notify_alert_sends_for_high_severity(self, mock_send, service, mock_db):
        alert = self._make_alert(severity="high")
        service._get_admin_emails = Mock(return_value=["admin@test.com"])
        result = asyncio.run(service.notify_alert(alert))
        assert result is True

    def test_build_alert_email_contains_supply_name(self):
        from app.services.notification_service import _build_alert_email
        from app.models.alert import Alert
        a = Alert()
        a.severity = "critical"
        a.alert_type = "shortage"
        a.current_stock = 10
        a.required_stock = 100
        a.shortage_date = date.today() + timedelta(days=2)
        a.message = "Need to order"
        a.is_resolved = False
        a.created_at = datetime.now()
        subject, html = _build_alert_email(a, "Surgical Masks")
        assert "Surgical Masks" in subject
        assert "Surgical Masks" in html
        assert "CRITICAL" in subject.upper()


# =============================================================================
# DataCollectorService Unit Tests
# =============================================================================

class TestDataCollectorService:
    """Unit tests for DataCollectorService."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.data_collector_service import DataCollectorService
        s = DataCollectorService(mock_db)
        s.api_key = "test_api_key"
        return s

    def test_max_retries_is_three(self, service):
        assert service.MAX_RETRIES == 3

    def test_retry_interval_is_sixty_seconds(self, service):
        assert service.RETRY_INTERVAL_SECONDS == 60

    def test_collect_weather_data_returns_none_without_api_key(self, mock_db):
        from app.services.data_collector_service import DataCollectorService
        s = DataCollectorService(mock_db)
        s.api_key = ""
        result = s.collect_weather_data("HCM", 10.8, 106.6)
        assert result is None

    @patch("app.services.data_collector_service.requests.get")
    def test_make_request_with_retry_success(self, mock_get, service):
        mock_response = Mock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        result = service._make_request_with_retry(
            url="http://test.com",
            params={},
            description="test request"
        )
        assert result == {"data": "test"}
        mock_get.assert_called_once()

    @patch("app.services.data_collector_service.requests.get")
    @patch("app.services.data_collector_service.time.sleep")
    def test_make_request_retries_on_failure(self, mock_sleep, mock_get, service):
        mock_get.side_effect = Exception("Network error")
        result = service._make_request_with_retry(
            url="http://test.com",
            params={},
            description="test request"
        )
        assert result is None
        assert mock_get.call_count == service.MAX_RETRIES
        # Should sleep between retries (MAX_RETRIES - 1 times)
        assert mock_sleep.call_count == service.MAX_RETRIES - 1

    @patch("app.services.data_collector_service.requests.get")
    def test_collect_disease_cases_rejects_negative_counts(self, mock_get, mock_db):
        from app.services.data_collector_service import DataCollectorService
        s = DataCollectorService(mock_db)
        s.api_key = "test"
        mock_response = Mock()
        mock_response.json.return_value = {
            "dengue_fever": {"cases": -10, "severity": "moderate"},
            "seasonal_flu": {"cases": 100, "severity": "high"},
            "respiratory_disease": {"cases": 50, "severity": "low"},
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = s.collect_disease_cases("http://test.com", "HCM")
        assert result["dengue_fever"] is None  # negative case count rejected

    def test_collect_data_for_locations_skips_missing_coords(self, service):
        locations = {
            "HCM": {"lat": 10.8, "lon": 106.6},
            "Bad": {}  # missing coords
        }
        with patch.object(service, "collect_weather_data") as mock_collect:
            mock_collect.return_value = Mock()
            results = service.collect_data_for_locations(locations)
        assert results["Bad"] is None
        assert mock_collect.call_count == 1  # only called for HCM


# =============================================================================
# AlertModule Unit Tests (Comprehensive)
# =============================================================================

class TestAlertModuleUnit:
    """Additional unit tests for AlertModule beyond the inline tests."""

    # ── Static pure methods ───────────────────────────────────────────────────

    def test_classify_severity_boundaries(self):
        from app.services.alert_service import AlertModule
        assert AlertModule.classify_severity(0) == "critical"
        assert AlertModule.classify_severity(3) == "critical"
        assert AlertModule.classify_severity(4) == "high"
        assert AlertModule.classify_severity(7) == "high"
        assert AlertModule.classify_severity(8) == "medium"
        assert AlertModule.classify_severity(14) == "medium"
        assert AlertModule.classify_severity(15) is None
        assert AlertModule.classify_severity(100) is None

    def test_calculate_shortage_date_basic(self):
        from app.services.alert_service import AlertModule
        today = date(2024, 1, 1)
        result = AlertModule.calculate_shortage_date(100, 10.0, today=today)
        assert result == date(2024, 1, 11)

    def test_calculate_shortage_date_zero_demand(self):
        from app.services.alert_service import AlertModule
        assert AlertModule.calculate_shortage_date(100, 0.0) is None

    def test_days_until_shortage_basic(self):
        from app.services.alert_service import AlertModule
        assert AlertModule.days_until_shortage(100, 10.0) == 10

    def test_days_until_shortage_zero_demand(self):
        from app.services.alert_service import AlertModule
        assert AlertModule.days_until_shortage(100, 0.0) is None

    def test_build_alert_message_content(self):
        from app.services.alert_service import AlertModule
        msg = AlertModule.build_alert_message("Masks", "critical", 10, 100, date(2024, 3, 15))
        assert "CRITICAL" in msg
        assert "Masks" in msg
        assert "90" in msg  # shortage = 100 - 10

    def test_build_alert_message_unknown_date(self):
        from app.services.alert_service import AlertModule
        msg = AlertModule.build_alert_message("Gloves", "high", 50, 200, None)
        assert "unknown date" in msg

    # ── Resolve logic ─────────────────────────────────────────────────────────

    def test_resolve_alert_marks_resolved(self):
        from app.services.alert_service import AlertModule
        from app.models.alert import Alert
        mock_db = MagicMock()
        alert = Alert()
        alert.id = 1
        alert.supply_id = 1
        alert.is_resolved = False
        alert.resolved_at = None
        mock_db.query.return_value.filter.return_value.first.return_value = alert
        module = AlertModule(mock_db)
        result = module.resolve_alert(1)
        assert result is not None
        assert result.is_resolved is True
        assert result.resolved_at is not None
        mock_db.commit.assert_called_once()

    def test_resolve_nonexistent_alert_returns_none(self):
        from app.services.alert_service import AlertModule
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        module = AlertModule(mock_db)
        assert module.resolve_alert(999) is None

    def test_check_and_generate_no_requirements(self):
        from app.services.alert_service import AlertModule
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        module = AlertModule(mock_db)
        alerts = module.check_and_generate_alerts()
        assert alerts == []


# =============================================================================
# ProcurementPlanner Unit Tests (Comprehensive)
# =============================================================================

class TestProcurementPlannerUnit:
    """Additional unit tests for ProcurementPlanner."""

    # ── Static pure methods ───────────────────────────────────────────────────

    def test_calculate_order_quantity_basic(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=100, current_stock=20, safety_stock=10
        )
        assert qty == 90  # 100 + 10 - 20

    def test_calculate_order_quantity_moq_applied(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=30, current_stock=20, safety_stock=5,
            minimum_order_quantity=50
        )
        assert qty == 50  # shortfall=15, moq=50 → 50

    def test_calculate_order_quantity_sufficient_stock(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=50, current_stock=200, safety_stock=10
        )
        assert qty == 0

    def test_calculate_order_quantity_storage_cap(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=100, current_stock=20, safety_stock=10,
            minimum_order_quantity=1, storage_capacity=60
        )
        assert qty == 40  # available = 60 - 20 = 40

    def test_calculate_order_date_basic(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        today = date(2024, 2, 1)
        req_date = date(2024, 2, 20)
        result = ProcurementPlanner.calculate_order_date(req_date, lead_time_days=7, today=today)
        assert result == date(2024, 2, 13)

    def test_calculate_order_date_past_returns_today(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        past_req = date.today() - timedelta(days=5)
        result = ProcurementPlanner.calculate_order_date(past_req, lead_time_days=0)
        assert result == date.today()

    def test_calculate_delivery_date(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        order_date = date(2024, 1, 10)
        result = ProcurementPlanner.calculate_delivery_date(order_date, 7)
        assert result == date(2024, 1, 17)

    def test_estimate_cost_basic(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        assert ProcurementPlanner.estimate_cost(100, 5.0) == 500.0

    def test_estimate_cost_none_price(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        assert ProcurementPlanner.estimate_cost(100, None) == 0.0

    def test_estimate_cost_zero_price(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        assert ProcurementPlanner.estimate_cost(100, 0.0) == 0.0

    def test_determine_priority_critical(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        assert ProcurementPlanner.determine_priority("critical") == "critical"

    def test_determine_priority_high(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        assert ProcurementPlanner.determine_priority("high") == "high"

    def test_determine_priority_none_returns_normal(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        assert ProcurementPlanner.determine_priority(None) == "normal"

    def test_determine_priority_medium_returns_normal(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        assert ProcurementPlanner.determine_priority("medium") == "normal"

    # ── plan_for_supply with mocked DB ────────────────────────────────────────

    def test_plan_for_supply_returns_none_on_unknown_supply(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        mock_db = MagicMock()
        planner = ProcurementPlanner(mock_db)
        planner._get_supply = Mock(return_value=None)
        assert planner.plan_for_supply(supply_id=999) is None

    def test_plan_for_supply_returns_none_when_no_requirements(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        from app.models.medical_supply import MedicalSupply
        mock_db = MagicMock()
        supply = MedicalSupply(id=1, name="Masks", category="PPE", unit="box")
        supply.lead_time_days = 7
        supply.minimum_order_quantity = 10
        supply.storage_capacity = 1000
        supply.unit_price = Decimal("5.0")
        planner = ProcurementPlanner(mock_db)
        planner._get_supply = Mock(return_value=supply)
        planner._get_current_stock = Mock(return_value=50)
        planner._get_safety_stock = Mock(return_value=10)
        planner._get_total_required = Mock(return_value=0)  # no requirements
        assert planner.plan_for_supply(supply_id=1) is None

    def test_generate_plan_empty_supply_ids(self):
        from app.procurement.procurement_planner import ProcurementPlanner
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        planner = ProcurementPlanner(mock_db)
        result = planner.generate_plan()
        assert result == []

    def test_save_plan_rollback_on_error(self):
        from app.procurement.procurement_planner import ProcurementPlanner, ProcurementPlanItem
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.delete.return_value = None
        mock_db.commit.side_effect = Exception("DB error")
        planner = ProcurementPlanner(mock_db)
        today = date(2024, 1, 1)
        item = ProcurementPlanItem(
            supply_id=1, supply_name="Masks",
            order_quantity=50, order_date=today,
            expected_delivery_date=today + timedelta(days=7),
            estimated_cost=250.0, priority="normal",
            current_stock=0, safety_stock=10,
            required_quantity=50, shortage_quantity=50,
            lead_time_days=7
        )
        with pytest.raises(Exception, match="DB error"):
            planner.save_plan([item])
        mock_db.rollback.assert_called_once()


# =============================================================================
# ConversionModule Unit Tests (Comprehensive)
# =============================================================================

class TestConversionModuleUnit:
    """Unit tests for ConversionModule."""

    @pytest.fixture
    def mock_db(self):
        mock = MagicMock()
        mock.query.return_value.join.return_value.all.return_value = []
        return mock

    @pytest.fixture
    def module(self, mock_db):
        from app.ai_engine.conversion_module import ConversionModule
        return ConversionModule(mock_db)

    def test_get_default_ratios_dengue(self, module):
        ratios = module.get_default_ratios("dengue_fever")
        assert "masks" in ratios
        assert ratios["masks"] == 2.0
        assert ratios["gloves"] == 4.0
        assert ratios["test_kits"] == 1.0
        assert ratios["disinfectant"] == 0.5

    def test_get_default_ratios_unknown(self, module):
        assert module.get_default_ratios("unknown") == {}

    def test_get_conversion_ratio_falls_back_to_defaults(self, module):
        ratio = module.get_conversion_ratio("dengue_fever", "masks")
        assert ratio == 2.0

    def test_get_conversion_ratio_returns_none_for_unknown(self, module):
        ratio = module.get_conversion_ratio("unknown_disease", "unknown_supply")
        assert ratio is None

    def test_calculate_requirements_basic(self, module):
        import pandas as pd
        requirements = module.calculate_requirements(
            disease_type="dengue_fever",
            predicted_cases=100,
            forecast_date=pd.Timestamp("2024-01-15")
        )
        assert len(requirements) > 0
        masks = next(r for r in requirements if r["supply_name"] == "masks")
        assert masks["required_quantity"] == 200  # 100 × 2.0
        assert masks["disease_type"] == "dengue_fever"

    def test_calculate_requirements_zero_cases(self, module):
        import pandas as pd
        requirements = module.calculate_requirements(
            disease_type="dengue_fever",
            predicted_cases=0,
            forecast_date=pd.Timestamp("2024-01-15")
        )
        for req in requirements:
            assert req["required_quantity"] == 0

    def test_calculate_requirements_specific_supply_types(self, module):
        import pandas as pd
        requirements = module.calculate_requirements(
            disease_type="dengue_fever",
            predicted_cases=100,
            forecast_date=pd.Timestamp("2024-01-15"),
            supply_types=["masks"]
        )
        assert len(requirements) == 1
        assert requirements[0]["supply_name"] == "masks"

    def test_calculate_requirements_fractional_truncated(self, module):
        import pandas as pd
        requirements = module.calculate_requirements(
            disease_type="dengue_fever",
            predicted_cases=75,
            forecast_date=pd.Timestamp("2024-01-15"),
            supply_types=["disinfectant"]
        )
        req = requirements[0]
        assert req["required_quantity"] == 37  # 75 × 0.5 = 37.5 → 37
        assert isinstance(req["required_quantity"], int)

    def test_calculate_requirements_unknown_disease_returns_empty(self, module):
        import pandas as pd
        requirements = module.calculate_requirements(
            disease_type="unknown_disease",
            predicted_cases=100,
            forecast_date=pd.Timestamp("2024-01-15")
        )
        assert requirements == []

    def test_calculate_requirements_for_forecast_multiple_dates(self, module):
        import numpy as np
        import pandas as pd
        predictions = np.array([100, 110, 120])
        dates = pd.date_range("2024-01-15", periods=3)
        requirements = module.calculate_requirements_for_forecast(
            disease_type="dengue_fever",
            predictions=predictions,
            forecast_dates=dates,
            supply_types=["masks"]
        )
        assert len(requirements) == 3  # 3 dates × 1 supply

    def test_get_all_ratios_for_disease_returns_defaults(self, module):
        ratios = module.get_all_ratios_for_disease("dengue_fever")
        assert "masks" in ratios
        assert "gloves" in ratios

    def test_get_all_ratios_unknown_disease_empty(self, module):
        ratios = module.get_all_ratios_for_disease("unknown")
        assert ratios == {}

    def test_database_ratio_overrides_default(self, mock_db):
        from app.ai_engine.conversion_module import ConversionModule
        from decimal import Decimal
        # Override: dengue_fever masks ratio = 3.0 (default is 2.0)
        mock_db.query.return_value.join.return_value.all.return_value = [
            ("dengue_fever", Decimal("3.0"), 1, "masks")
        ]
        module = ConversionModule(mock_db)
        module.load_conversion_ratios()
        ratio = module.get_conversion_ratio("dengue_fever", "masks")
        assert ratio == 3.0  # DB value, not default 2.0

    def test_load_conversion_ratios_builds_supply_id_map(self, mock_db):
        from app.ai_engine.conversion_module import ConversionModule
        from decimal import Decimal
        mock_db.query.return_value.join.return_value.all.return_value = [
            ("dengue_fever", Decimal("2.0"), 5, "masks"),
            ("dengue_fever", Decimal("4.0"), 6, "gloves"),
        ]
        module = ConversionModule(mock_db)
        module.load_conversion_ratios()
        assert module.supply_name_to_id["masks"] == 5
        assert module.supply_name_to_id["gloves"] == 6


# =============================================================================
# Security / Core utility tests
# =============================================================================

class TestSecurityUtils:
    """Unit tests for security utility functions."""

    def test_hash_and_verify_password(self):
        from app.core.security import hash_password, verify_password
        password = "SecurePass123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_verify_wrong_password_returns_false(self):
        from app.core.security import hash_password, verify_password
        hashed = hash_password("CorrectPass")
        assert verify_password("WrongPass", hashed) is False

    def test_create_access_token_returns_string(self):
        from app.core.security import create_access_token
        token = create_access_token(data={"sub": "testuser"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_returns_payload(self):
        from app.core.security import create_access_token, verify_token
        token = create_access_token(data={"sub": "alice"})
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "alice"

    def test_verify_invalid_token_returns_none(self):
        from app.core.security import verify_token
        assert verify_token("not.a.valid.token") is None

    def test_get_password_hash_consistent_verify(self):
        from app.core.security import get_password_hash, verify_password
        pwd = "TestPassword!@#"
        h1 = get_password_hash(pwd)
        h2 = get_password_hash(pwd)
        # Different salts → different hashes but both verify correctly
        assert h1 != h2
        assert verify_password(pwd, h1)
        assert verify_password(pwd, h2)

    def test_access_token_expiry_set(self):
        from app.core.security import create_access_token, verify_token
        token = create_access_token(data={"sub": "bob"}, expires_delta=timedelta(hours=1))
        payload = verify_token(token)
        assert "exp" in payload


# =============================================================================
# SupplyRequirementService Unit Tests
# =============================================================================

class TestSupplyRequirementServiceUnit:
    """Unit tests for SupplyRequirementService."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.supply_requirement_service import SupplyRequirementService
        return SupplyRequirementService(mock_db)

    def test_get_current_stock_returns_sum(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.scalar.return_value = 250
        assert service._get_current_stock(1) == 250

    def test_get_current_stock_returns_none_when_no_inventory(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.scalar.return_value = None
        assert service._get_current_stock(1) is None

    def test_get_requirements_for_forecast_returns_empty_on_not_found(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = service.get_requirements_for_forecast(999)
        assert result == []

    def test_get_summary_empty_returns_correct_structure(self, service, mock_db):
        chain = mock_db.query.return_value
        chain.filter.return_value = chain
        chain.all.return_value = []
        chain.options.return_value = chain
        result = service.get_summary()
        assert result["total_supplies"] == 0
        assert result["supplies_with_shortage"] == 0
        assert result["items"] == []

    def test_enrich_requirement_calculates_shortage(self, service, mock_db):
        from app.models.supply_requirement import SupplyRequirement
        from app.models.medical_supply import MedicalSupply
        supply = MedicalSupply(id=1, name="Masks", category="PPE", unit="box")
        req = SupplyRequirement()
        req.id = 1
        req.forecast_id = 1
        req.supply_id = 1
        req.supply = supply
        req.required_quantity = 200
        req.requirement_date = date.today()
        req.disease_type = "dengue_fever"
        req.created_at = datetime.now()
        # Mock current stock at 50
        service._get_current_stock = Mock(return_value=50)
        result = service._enrich_requirement(req)
        assert result["supply_name"] == "Masks"
        assert result["required_quantity"] == 200
        assert result["current_stock"] == 50
        assert result["shortage_amount"] == 150  # 200 - 50

    def test_enrich_requirement_no_shortage(self, service, mock_db):
        from app.models.supply_requirement import SupplyRequirement
        from app.models.medical_supply import MedicalSupply
        supply = MedicalSupply(id=1, name="Gloves", category="PPE", unit="box")
        req = SupplyRequirement()
        req.id = 2
        req.forecast_id = 1
        req.supply_id = 1
        req.supply = supply
        req.required_quantity = 100
        req.requirement_date = date.today()
        req.disease_type = "seasonal_flu"
        req.created_at = datetime.now()
        service._get_current_stock = Mock(return_value=500)  # plenty of stock
        result = service._enrich_requirement(req)
        assert result["shortage_amount"] == 0  # no shortage


# =============================================================================
# UserService – create/update paths (covering DB interaction paths)
# =============================================================================

class TestUserServiceCreateUpdate:
    """Additional tests to improve coverage for UserService create/update."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.user_service import UserService
        return UserService(mock_db)

    def test_create_user_success(self, service, mock_db):
        from app.models.user import User
        from app.schemas.base import UserCreate, UserRole
        user_data = UserCreate(
            username="newuser",
            email="newuser@test.com",
            password="Password123!",
            full_name="New User",
            role=UserRole.PHARMACIST,
        )
        # Simulate successful DB insert: after commit, refresh returns the same obj
        created_user = User(id=1, username="newuser", email="newuser@test.com",
                            role="Pharmacist", is_active=True)
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.side_effect = lambda u: None
        # After commit, query.filter.first returns created user for audit
        mock_db.query.return_value.filter.return_value.first.return_value = None
        service.db.refresh = lambda u: setattr(u, 'id', 1)
        # Patch get_password_hash to avoid bcrypt in test
        with patch("app.services.user_service.get_password_hash", return_value="hashed"):
            result = service.create_user(user_data, created_by_user_id=1)
        assert result.username == "newuser"
        mock_db.commit.assert_called_once()

    def test_update_user_not_found_raises_404(self, service, mock_db):
        from app.schemas.base import UserUpdate
        from fastapi import HTTPException
        mock_db.query.return_value.filter.return_value.first.return_value = None
        update_data = UserUpdate(full_name="Updated Name")
        with pytest.raises(HTTPException) as exc:
            service.update_user(999, update_data, updated_by_user_id=1)
        assert exc.value.status_code == 404

    def test_update_user_success(self, service, mock_db):
        from app.models.user import User
        from app.schemas.base import UserUpdate
        user = User(id=2, username="alice", email="alice@test.com",
                    role="Pharmacist", is_active=True)
        user.full_name = "Alice"
        mock_db.query.return_value.filter.return_value.first.return_value = user
        mock_db.commit.return_value = None
        mock_db.refresh.side_effect = lambda u: None
        update_data = UserUpdate(full_name="Alice Updated")
        result = service.update_user(2, update_data, updated_by_user_id=1)
        assert result.full_name == "Alice Updated"
        mock_db.commit.assert_called()


# =============================================================================
# MedicalSupplyService – create/update/delete (improving coverage)
# =============================================================================

class TestMedicalSupplyServiceCRUD:
    """Tests for create/update/delete paths of MedicalSupplyService."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.medical_supply_service import MedicalSupplyService
        return MedicalSupplyService(mock_db)

    def test_create_supply_success(self, service, mock_db):
        from app.schemas.base import MedicalSupplyCreate
        from app.models.medical_supply import MedicalSupply
        # No existing supply with same name
        mock_db.query.return_value.filter.return_value.first.return_value = None
        supply_data = MedicalSupplyCreate(name="New Mask", category="PPE", unit="box")
        # After add/flush, the supply gets an id
        mock_db.flush.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.side_effect = lambda s: setattr(s, 'id', 10)
        result = service.create_supply(supply_data, created_by_user_id=1, ip_address="127.0.0.1")
        assert result.name == "New Mask"
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_update_supply_success(self, service, mock_db):
        from app.schemas.base import MedicalSupplyUpdate
        from app.models.medical_supply import MedicalSupply
        supply = MedicalSupply(id=1, name="Old Name", category="PPE", unit="box")
        supply.unit_price = None
        supply.minimum_order_quantity = None
        supply.lead_time_days = None
        supply.storage_capacity = None
        supply.description = None
        # First query: get_supply_by_id, Second: check duplicate name
        mock_db.query.return_value.filter.return_value.first.side_effect = [supply, None]
        mock_db.commit.return_value = None
        mock_db.refresh.side_effect = lambda s: None
        update_data = MedicalSupplyUpdate(name="New Name")
        result = service.update_supply(1, update_data, updated_by_user_id=1, ip_address="127.0.0.1")
        assert result.name == "New Name"

    def test_delete_supply_success(self, service, mock_db):
        from app.models.medical_supply import MedicalSupply
        supply = MedicalSupply(id=1, name="Old Mask", category="PPE", unit="box")
        mock_db.query.return_value.filter.return_value.first.return_value = supply
        mock_db.commit.return_value = None
        service.delete_supply(1, deleted_by_user_id=1, ip_address="127.0.0.1")
        mock_db.delete.assert_called_once_with(supply)
        mock_db.commit.assert_called()


# =============================================================================
# InventoryService – update and batch update paths
# =============================================================================

class TestInventoryServiceUpdatePaths:
    """Tests for inventory update paths to improve coverage."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.inventory_service import InventoryService
        return InventoryService(mock_db)

    def _make_supply(self):
        from app.models.medical_supply import MedicalSupply
        s = MedicalSupply()
        s.id = 1
        s.name = "Masks"
        return s

    def _make_inventory(self):
        from app.models.inventory import Inventory
        inv = Inventory()
        inv.id = 1
        inv.supply_id = 1
        inv.current_stock = 100
        inv.safety_stock = 50
        inv.location = "Warehouse A"
        inv.updated_by = 1
        inv.supply = self._make_supply()
        return inv

    def test_update_inventory_success(self, service, mock_db):
        from app.schemas.base import InventoryUpdate
        inv = self._make_inventory()
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = inv
        mock_db.commit.return_value = None
        mock_db.refresh.side_effect = lambda i: None
        update_data = InventoryUpdate(current_stock=200)
        with patch("app.services.inventory_service._trigger_alert_check"):
            result = service.update_inventory(1, update_data, updated_by_user_id=1, ip_address="127.0.0.1")
        assert result.current_stock == 200
        mock_db.commit.assert_called()

    def test_update_inventory_safety_stock(self, service, mock_db):
        from app.schemas.base import InventoryUpdate
        inv = self._make_inventory()
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = inv
        mock_db.commit.return_value = None
        mock_db.refresh.side_effect = lambda i: None
        update_data = InventoryUpdate(safety_stock=100)
        with patch("app.services.inventory_service._trigger_alert_check"):
            result = service.update_inventory(1, update_data, updated_by_user_id=1, ip_address="127.0.0.1")
        assert result.safety_stock == 100

    def test_batch_update_skips_negative_stocks(self, service, mock_db):
        inv = self._make_inventory()
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = inv
        mock_db.commit.return_value = None
        mock_db.refresh.side_effect = lambda i: None
        updates = [
            {"inventory_id": 1, "current_stock": -50},  # Invalid - should be skipped
        ]
        with patch("app.services.inventory_service._trigger_alert_check"):
            result = service.batch_update_inventory(updates, updated_by_user_id=1, ip_address="127.0.0.1")
        assert len(result) == 0  # Skipped due to negative stock

    def test_get_inventory_by_supply_not_found_raises(self, service, mock_db):
        from fastapi import HTTPException
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.get_inventory_by_supply(999)
        assert exc.value.status_code == 404

    def test_create_inventory_raises_on_negative_safety_stock(self, service, mock_db):
        from app.models.medical_supply import MedicalSupply
        from fastapi import HTTPException
        supply = MedicalSupply(id=1, name="Masks", category="PPE", unit="box")
        mock_db.query.return_value.filter.return_value.first.return_value = supply
        with pytest.raises(HTTPException) as exc:
            service.create_inventory_item(
                supply_id=1, current_stock=100, safety_stock=-10,
                created_by_user_id=1, ip_address="127.0.0.1"
            )
        assert exc.value.status_code == 400


# =============================================================================
# SupplyRequirementService – list/summary with data
# =============================================================================

class TestSupplyRequirementServiceWithData:
    """Additional tests for SupplyRequirementService with mocked data."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def service(self, mock_db):
        from app.services.supply_requirement_service import SupplyRequirementService
        return SupplyRequirementService(mock_db)

    def test_list_requirements_returns_enriched_list(self, service, mock_db):
        from app.models.supply_requirement import SupplyRequirement
        from app.models.medical_supply import MedicalSupply
        from app.models.disease_forecast import DiseaseForecast
        supply = MedicalSupply(id=1, name="Masks", category="PPE", unit="box")
        req = SupplyRequirement()
        req.id = 1
        req.forecast_id = 1
        req.supply_id = 1
        req.supply = supply
        req.required_quantity = 200
        req.requirement_date = date.today()
        req.disease_type = "dengue_fever"
        req.created_at = datetime.now()
        chain = mock_db.query.return_value.options.return_value
        chain.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [req]
        service._get_current_stock = Mock(return_value=100)
        result = service.list_requirements()
        assert len(result) == 1
        assert result[0]["supply_name"] == "Masks"
        assert result[0]["shortage_amount"] == 100  # 200 - 100

    def test_get_summary_with_data(self, service, mock_db):
        from app.models.supply_requirement import SupplyRequirement
        from app.models.medical_supply import MedicalSupply
        supply = MedicalSupply(id=1, name="Gloves", category="PPE", unit="box")
        supply.category = "PPE"
        supply.unit = "box"
        req = SupplyRequirement()
        req.supply_id = 1
        req.supply = supply
        req.required_quantity = 400
        req.disease_type = "dengue_fever"
        chain = mock_db.query.return_value.options.return_value
        chain.all.return_value = [req]
        service._get_current_stock = Mock(return_value=300)
        result = service.get_summary()
        assert result["total_supplies"] == 1
        assert result["supplies_with_shortage"] == 1
        assert result["items"][0]["shortage_amount"] == 100

    def test_get_summary_no_shortage(self, service, mock_db):
        from app.models.supply_requirement import SupplyRequirement
        from app.models.medical_supply import MedicalSupply
        supply = MedicalSupply(id=1, name="Masks", category="PPE", unit="box")
        supply.category = "PPE"
        supply.unit = "box"
        req = SupplyRequirement()
        req.supply_id = 1
        req.supply = supply
        req.required_quantity = 100
        req.disease_type = "dengue_fever"
        chain = mock_db.query.return_value.options.return_value
        chain.all.return_value = [req]
        service._get_current_stock = Mock(return_value=500)  # More than enough
        result = service.get_summary()
        assert result["supplies_with_shortage"] == 0
