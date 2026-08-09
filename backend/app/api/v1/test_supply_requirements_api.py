"""Tests for Supply Requirements API endpoints and SupplyRequirementService."""
import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.disease_forecast import DiseaseForecast
from app.models.medical_supply import MedicalSupply
from app.models.inventory import Inventory
from app.models.supply_requirement import SupplyRequirement
from app.services.supply_requirement_service import SupplyRequirementService


# ---------------------------------------------------------------------------
# In-memory SQLite fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory SQLite DB for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _seed_supply(db, name="Masks", category="PPE", unit="units") -> MedicalSupply:
    supply = MedicalSupply(name=name, category=category, unit=unit)
    db.add(supply)
    db.flush()
    return supply


def _seed_inventory(db, supply_id: int, current_stock: int = 500, safety_stock: int = 50) -> Inventory:
    inv = Inventory(supply_id=supply_id, current_stock=current_stock, safety_stock=safety_stock)
    db.add(inv)
    db.flush()
    return inv


def _seed_forecast(db, disease_type="dengue_fever", predicted_cases=100) -> DiseaseForecast:
    fc = DiseaseForecast(
        forecast_date=date(2024, 6, 1),
        disease_type=disease_type,
        predicted_cases=predicted_cases,
        created_at=datetime(2024, 6, 1, 12, 0, 0),
    )
    db.add(fc)
    db.flush()
    return fc


def _seed_requirement(db, forecast_id, supply_id, required_quantity=200) -> SupplyRequirement:
    req = SupplyRequirement(
        forecast_id=forecast_id,
        supply_id=supply_id,
        required_quantity=required_quantity,
        requirement_date=date(2024, 6, 1),
        disease_type="dengue_fever",
    )
    db.add(req)
    db.flush()
    return req


# ---------------------------------------------------------------------------
# SupplyRequirementService unit tests
# ---------------------------------------------------------------------------

class TestSupplyRequirementServiceListRequirements:
    def test_list_requirements_returns_empty_when_no_data(self, db_session):
        service = SupplyRequirementService(db_session)
        result = service.list_requirements()
        assert result == []

    def test_list_requirements_returns_enriched_records(self, db_session):
        supply = _seed_supply(db_session)
        _seed_inventory(db_session, supply_id=supply.id, current_stock=150)
        fc = _seed_forecast(db_session)
        _seed_requirement(db_session, forecast_id=fc.id, supply_id=supply.id, required_quantity=200)
        db_session.commit()

        service = SupplyRequirementService(db_session)
        results = service.list_requirements()

        assert len(results) == 1
        item = results[0]
        assert item["supply_name"] == "Masks"
        assert item["required_quantity"] == 200
        # current_stock = 150, required = 200 → shortage = 50
        assert item["current_stock"] == 150
        assert item["shortage_amount"] == 50

    def test_list_requirements_no_shortage_when_stock_sufficient(self, db_session):
        supply = _seed_supply(db_session)
        _seed_inventory(db_session, supply_id=supply.id, current_stock=1000)
        fc = _seed_forecast(db_session)
        _seed_requirement(db_session, forecast_id=fc.id, supply_id=supply.id, required_quantity=200)
        db_session.commit()

        service = SupplyRequirementService(db_session)
        results = service.list_requirements()

        assert results[0]["shortage_amount"] == 0

    def test_list_requirements_filter_by_forecast_id(self, db_session):
        supply = _seed_supply(db_session)
        fc1 = _seed_forecast(db_session, predicted_cases=100)
        fc2 = _seed_forecast(db_session, predicted_cases=200)
        _seed_requirement(db_session, forecast_id=fc1.id, supply_id=supply.id, required_quantity=100)
        _seed_requirement(db_session, forecast_id=fc2.id, supply_id=supply.id, required_quantity=200)
        db_session.commit()

        service = SupplyRequirementService(db_session)
        results = service.list_requirements(forecast_id=fc1.id)

        assert len(results) == 1
        assert results[0]["required_quantity"] == 100

    def test_list_requirements_filter_by_disease_type(self, db_session):
        supply = _seed_supply(db_session)
        fc = _seed_forecast(db_session, disease_type="dengue_fever")
        req = SupplyRequirement(
            forecast_id=fc.id,
            supply_id=supply.id,
            required_quantity=100,
            requirement_date=date(2024, 6, 1),
            disease_type="dengue_fever",
        )
        req2 = SupplyRequirement(
            forecast_id=fc.id,
            supply_id=supply.id,
            required_quantity=50,
            requirement_date=date(2024, 6, 2),
            disease_type="seasonal_flu",
        )
        db_session.add_all([req, req2])
        db_session.commit()

        service = SupplyRequirementService(db_session)
        results = service.list_requirements(disease_type="seasonal_flu")

        assert len(results) == 1
        assert results[0]["disease_type"] == "seasonal_flu"


class TestSupplyRequirementServiceGetSummary:
    def test_summary_empty_when_no_requirements(self, db_session):
        service = SupplyRequirementService(db_session)
        summary = service.get_summary()

        assert summary["total_supplies"] == 0
        assert summary["supplies_with_shortage"] == 0
        assert summary["items"] == []

    def test_summary_aggregates_by_supply(self, db_session):
        supply = _seed_supply(db_session, name="Gloves")
        _seed_inventory(db_session, supply_id=supply.id, current_stock=300)
        fc = _seed_forecast(db_session)
        # Two requirements for the same supply
        req1 = SupplyRequirement(
            forecast_id=fc.id, supply_id=supply.id,
            required_quantity=200, requirement_date=date(2024, 6, 1),
            disease_type="dengue_fever"
        )
        req2 = SupplyRequirement(
            forecast_id=fc.id, supply_id=supply.id,
            required_quantity=150, requirement_date=date(2024, 6, 2),
            disease_type="dengue_fever"
        )
        db_session.add_all([req1, req2])
        db_session.commit()

        service = SupplyRequirementService(db_session)
        summary = service.get_summary()

        assert summary["total_supplies"] == 1
        item = summary["items"][0]
        assert item["supply_name"] == "Gloves"
        assert item["total_required_quantity"] == 350
        assert item["requirement_count"] == 2
        # 350 required, 300 in stock → shortage 50
        assert item["shortage_amount"] == 50
        assert summary["supplies_with_shortage"] == 1

    def test_summary_no_shortage_when_stocked(self, db_session):
        supply = _seed_supply(db_session, name="Test Kits")
        _seed_inventory(db_session, supply_id=supply.id, current_stock=1000)
        fc = _seed_forecast(db_session)
        req = SupplyRequirement(
            forecast_id=fc.id, supply_id=supply.id,
            required_quantity=100, requirement_date=date(2024, 6, 1),
            disease_type="dengue_fever"
        )
        db_session.add(req)
        db_session.commit()

        service = SupplyRequirementService(db_session)
        summary = service.get_summary()

        assert summary["supplies_with_shortage"] == 0
        assert summary["items"][0]["shortage_amount"] == 0

    def test_summary_includes_disease_types(self, db_session):
        supply = _seed_supply(db_session)
        fc = _seed_forecast(db_session)
        req1 = SupplyRequirement(
            forecast_id=fc.id, supply_id=supply.id,
            required_quantity=100, requirement_date=date(2024, 6, 1),
            disease_type="dengue_fever"
        )
        req2 = SupplyRequirement(
            forecast_id=fc.id, supply_id=supply.id,
            required_quantity=50, requirement_date=date(2024, 6, 2),
            disease_type="seasonal_flu"
        )
        db_session.add_all([req1, req2])
        db_session.commit()

        service = SupplyRequirementService(db_session)
        summary = service.get_summary()

        disease_types = set(summary["items"][0]["disease_types"])
        assert "dengue_fever" in disease_types
        assert "seasonal_flu" in disease_types


class TestSupplyRequirementServiceGetRequirementsForForecast:
    def test_returns_empty_for_unknown_forecast(self, db_session):
        service = SupplyRequirementService(db_session)
        result = service.get_requirements_for_forecast(forecast_id=9999)
        assert result == []

    def test_returns_requirements_for_known_forecast(self, db_session):
        supply = _seed_supply(db_session)
        fc = _seed_forecast(db_session)
        _seed_requirement(db_session, forecast_id=fc.id, supply_id=supply.id, required_quantity=100)
        db_session.commit()

        service = SupplyRequirementService(db_session)
        results = service.get_requirements_for_forecast(fc.id)

        assert len(results) == 1
        assert results[0]["forecast_id"] == fc.id
        assert results[0]["supply_name"] == "Masks"


class TestGetCurrentStock:
    def test_get_current_stock_sums_across_locations(self, db_session):
        supply = _seed_supply(db_session)
        inv1 = Inventory(supply_id=supply.id, current_stock=100, safety_stock=10, location="Warehouse A")
        inv2 = Inventory(supply_id=supply.id, current_stock=200, safety_stock=10, location="Warehouse B")
        db_session.add_all([inv1, inv2])
        db_session.commit()

        service = SupplyRequirementService(db_session)
        total = service._get_current_stock(supply.id)

        assert total == 300

    def test_get_current_stock_returns_none_when_no_inventory(self, db_session):
        supply = _seed_supply(db_session)
        db_session.commit()

        service = SupplyRequirementService(db_session)
        total = service._get_current_stock(supply.id)

        assert total is None


class TestGenerateRequirementsForForecast:
    def test_generate_returns_empty_for_unknown_forecast(self, db_session):
        service = SupplyRequirementService(db_session)
        result = service.generate_requirements_for_forecast(forecast_id=9999)
        assert result == []

    def test_generate_uses_default_conversion_ratios_when_db_empty(self, db_session):
        """When no conversion ratios are in DB, default ratios from config are used."""
        # Create supplies matching default ratio names
        from app.ai_engine.config import DEFAULT_CONVERSION_RATIOS
        disease_type = "dengue_fever"
        default_supplies = list(DEFAULT_CONVERSION_RATIOS.get(disease_type, {}).keys())

        created_supplies = {}
        for name in default_supplies:
            s = MedicalSupply(name=name, category="Test", unit="units")
            db_session.add(s)
            db_session.flush()
            created_supplies[name] = s

        fc = _seed_forecast(db_session, disease_type=disease_type, predicted_cases=10)
        db_session.commit()

        service = SupplyRequirementService(db_session)
        requirements = service.generate_requirements_for_forecast(fc.id)

        # Should have generated one requirement per default supply type
        assert len(requirements) > 0
        for req in requirements:
            assert req.forecast_id == fc.id
            assert req.disease_type == disease_type
            assert req.required_quantity >= 0

    def test_generate_idempotent_on_re_run(self, db_session):
        """Running generate twice for the same forecast should not create duplicates."""
        from app.ai_engine.config import DEFAULT_CONVERSION_RATIOS
        disease_type = "dengue_fever"
        default_supplies = list(DEFAULT_CONVERSION_RATIOS.get(disease_type, {}).keys())

        for name in default_supplies:
            s = MedicalSupply(name=name, category="Test", unit="units")
            db_session.add(s)
        db_session.flush()

        fc = _seed_forecast(db_session, disease_type=disease_type, predicted_cases=10)
        db_session.commit()

        service = SupplyRequirementService(db_session)
        first = service.generate_requirements_for_forecast(fc.id)
        second = service.generate_requirements_for_forecast(fc.id)

        # After second run, count in DB should equal second run count (not doubled)
        db_count = db_session.query(SupplyRequirement).filter(
            SupplyRequirement.forecast_id == fc.id
        ).count()
        assert db_count == len(second)
        assert len(first) == len(second)
