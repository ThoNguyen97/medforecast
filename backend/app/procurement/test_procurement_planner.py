"""
Unit tests for ProcurementPlanner (procurement_planner.py)

Tests cover:
- calculate_order_quantity  (pure static method)
- calculate_order_date      (pure static method)
- calculate_delivery_date   (pure static method)
- estimate_cost             (pure static method)
- determine_priority        (pure static method)
- plan_for_supply           (DB-backed, uses MagicMock session)
- generate_plan             (DB-backed, uses MagicMock session)
- save_plan                 (DB-backed, uses MagicMock session)
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch, call
import pytest

from app.procurement.procurement_planner import ProcurementPlanner, ProcurementPlanItem
from app.models.medical_supply import MedicalSupply
from app.models.procurement_plan import ProcurementPlan
from app.models.alert import Alert


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / factories
# ─────────────────────────────────────────────────────────────────────────────

def make_supply(
    supply_id: int = 1,
    name: str = "Surgical Masks",
    unit_price: float = 5.0,
    min_order_qty: int = 10,
    lead_time_days: int = 7,
    storage_capacity: int = 1000,
) -> MedicalSupply:
    s = MedicalSupply()
    s.id = supply_id
    s.name = name
    s.category = "PPE"
    s.unit = "box"
    s.unit_price = Decimal(str(unit_price)) if unit_price is not None else None
    s.minimum_order_quantity = min_order_qty
    s.lead_time_days = lead_time_days
    s.storage_capacity = storage_capacity
    return s


def make_alert(supply_id: int = 1, severity: str = "high") -> Alert:
    a = Alert()
    a.id = 1
    a.supply_id = supply_id
    a.alert_type = "shortage"
    a.severity = severity
    a.is_resolved = False
    return a


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def planner(mock_db):
    return ProcurementPlanner(mock_db)


# ─────────────────────────────────────────────────────────────────────────────
# 1. calculate_order_quantity
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateOrderQuantity:

    def test_basic_shortfall_no_moq(self):
        """Order quantity equals shortfall when above MOQ."""
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=100, current_stock=20, safety_stock=10
        )
        # shortfall = 100 + 10 - 20 = 90; default MOQ=1 → 90
        assert qty == 90

    def test_moq_applied_when_shortfall_smaller(self):
        """MOQ is respected when shortfall is below it."""
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=30, current_stock=20, safety_stock=5,
            minimum_order_quantity=50
        )
        # shortfall = 30 + 5 - 20 = 15; MOQ=50 → 50
        assert qty == 50

    def test_no_order_when_stock_sufficient(self):
        """No order when current_stock already covers requirement + safety stock."""
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=50, current_stock=200, safety_stock=10
        )
        assert qty == 0

    def test_storage_capacity_cap(self):
        """Order is capped so total stock stays within capacity."""
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=100, current_stock=20, safety_stock=10,
            minimum_order_quantity=1, storage_capacity=60
        )
        # shortfall=90, but only 40 space left (60-20) → 40
        assert qty == 40

    def test_storage_already_full_returns_zero(self):
        """Returns 0 when warehouse is already at capacity."""
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=100, current_stock=1000, safety_stock=10,
            storage_capacity=1000
        )
        assert qty == 0

    def test_no_storage_limit(self):
        """No cap applied when storage_capacity is None."""
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=500, current_stock=0, safety_stock=50,
            minimum_order_quantity=1, storage_capacity=None
        )
        assert qty == 550  # 500 + 50 - 0

    def test_zero_required_quantity(self):
        """No order when required_quantity is 0."""
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=0, current_stock=0, safety_stock=0
        )
        assert qty == 0

    def test_exact_safety_stock_boundary(self):
        """No order when current_stock exactly equals required + safety."""
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=100, current_stock=110, safety_stock=10
        )
        assert qty == 0

    def test_moq_not_applied_when_no_shortfall(self):
        """MOQ does NOT trigger an order when there is no shortfall."""
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=50, current_stock=200, safety_stock=5,
            minimum_order_quantity=100
        )
        assert qty == 0

    def test_large_order_within_capacity(self):
        """Large shortfall is returned in full when capacity allows."""
        qty = ProcurementPlanner.calculate_order_quantity(
            required_quantity=1000, current_stock=100, safety_stock=50,
            minimum_order_quantity=1, storage_capacity=2000
        )
        # shortfall = 1000+50-100 = 950; available=2000-100=1900 → 950
        assert qty == 950


# ─────────────────────────────────────────────────────────────────────────────
# 2. calculate_order_date
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateOrderDate:

    def test_basic_lead_time_subtraction(self):
        today = date(2024, 1, 1)  # anchor today so req_date is in the future
        req_date = date(2024, 2, 14)
        result = ProcurementPlanner.calculate_order_date(req_date, lead_time_days=7, today=today)
        assert result == date(2024, 2, 7)

    def test_order_date_in_past_returns_today(self):
        """When order date would be in the past, return today."""
        past_req_date = date.today() - timedelta(days=10)
        result = ProcurementPlanner.calculate_order_date(past_req_date, lead_time_days=3)
        assert result == date.today()

    def test_zero_lead_time(self):
        req_date = date(2024, 5, 20)
        result = ProcurementPlanner.calculate_order_date(
            req_date, lead_time_days=0, today=date(2024, 5, 10)
        )
        assert result == date(2024, 5, 20)

    def test_lead_time_exactly_matches_days_until_req(self):
        today = date(2024, 3, 1)
        req_date = today + timedelta(days=14)
        result = ProcurementPlanner.calculate_order_date(
            req_date, lead_time_days=14, today=today
        )
        assert result == today

    def test_long_lead_time_pushes_to_today(self):
        today = date(2024, 3, 1)
        req_date = today + timedelta(days=5)
        result = ProcurementPlanner.calculate_order_date(
            req_date, lead_time_days=30, today=today
        )
        # 30-day lead for 5-day requirement → place today
        assert result == today


# ─────────────────────────────────────────────────────────────────────────────
# 3. calculate_delivery_date
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateDeliveryDate:

    def test_delivery_date_adds_lead_time(self):
        order_date = date(2024, 1, 10)
        result = ProcurementPlanner.calculate_delivery_date(order_date, 7)
        assert result == date(2024, 1, 17)

    def test_zero_lead_time_same_day_delivery(self):
        order_date = date(2024, 6, 1)
        assert ProcurementPlanner.calculate_delivery_date(order_date, 0) == order_date

    def test_month_boundary(self):
        order_date = date(2024, 1, 28)
        result = ProcurementPlanner.calculate_delivery_date(order_date, 7)
        assert result == date(2024, 2, 4)


# ─────────────────────────────────────────────────────────────────────────────
# 4. estimate_cost
# ─────────────────────────────────────────────────────────────────────────────

class TestEstimateCost:

    def test_basic_cost_calculation(self):
        assert ProcurementPlanner.estimate_cost(100, 5.0) == 500.0

    def test_none_unit_price_returns_zero(self):
        assert ProcurementPlanner.estimate_cost(100, None) == 0.0

    def test_zero_unit_price_returns_zero(self):
        assert ProcurementPlanner.estimate_cost(100, 0.0) == 0.0

    def test_negative_unit_price_returns_zero(self):
        assert ProcurementPlanner.estimate_cost(100, -10.0) == 0.0

    def test_fractional_price_rounded(self):
        result = ProcurementPlanner.estimate_cost(3, 1.005)
        assert result == round(3 * 1.005, 2)

    def test_zero_quantity_returns_zero(self):
        assert ProcurementPlanner.estimate_cost(0, 50.0) == 0.0

    def test_large_order_cost(self):
        assert ProcurementPlanner.estimate_cost(10_000, 2.5) == 25_000.0


# ─────────────────────────────────────────────────────────────────────────────
# 5. determine_priority
# ─────────────────────────────────────────────────────────────────────────────

class TestDeterminePriority:

    def test_critical_severity_maps_to_critical(self):
        assert ProcurementPlanner.determine_priority("critical") == "critical"

    def test_high_severity_maps_to_high(self):
        assert ProcurementPlanner.determine_priority("high") == "high"

    def test_medium_severity_maps_to_normal(self):
        assert ProcurementPlanner.determine_priority("medium") == "normal"

    def test_none_maps_to_normal(self):
        assert ProcurementPlanner.determine_priority(None) == "normal"

    def test_unknown_string_maps_to_normal(self):
        assert ProcurementPlanner.determine_priority("unknown") == "normal"


# ─────────────────────────────────────────────────────────────────────────────
# 6. plan_for_supply
# ─────────────────────────────────────────────────────────────────────────────

class TestPlanForSupply:
    """Tests for ProcurementPlanner.plan_for_supply (uses mock DB)."""

    def _make_planner_with_mocks(self, mock_db, supply, current_stock=0,
                                  safety_stock=10, total_required=100,
                                  earliest_date=None, alert_severity=None):
        """
        Return a planner whose internal helpers are replaced with Mock objects
        to avoid hitting the real database.
        """
        p = ProcurementPlanner(mock_db)
        p._get_supply = Mock(return_value=supply)
        p._get_current_stock = Mock(return_value=current_stock)
        p._get_safety_stock = Mock(return_value=safety_stock)
        p._get_total_required = Mock(return_value=total_required)
        today = date(2024, 3, 1)
        if earliest_date is None:
            earliest_date = today + timedelta(days=14)
        p._get_earliest_requirement_date = Mock(return_value=earliest_date)
        p._get_active_alert_severity = Mock(return_value=alert_severity)
        return p, today

    def test_returns_plan_item_when_order_needed(self, mock_db):
        supply = make_supply(lead_time_days=7, min_order_qty=10, storage_capacity=500)
        p, today = self._make_planner_with_mocks(
            mock_db, supply,
            current_stock=50, safety_stock=20, total_required=100
        )
        item = p.plan_for_supply(supply_id=1, today=today)

        assert item is not None
        assert isinstance(item, ProcurementPlanItem)
        assert item.order_quantity > 0

    def test_returns_none_when_stock_sufficient(self, mock_db):
        supply = make_supply(lead_time_days=7)
        p, today = self._make_planner_with_mocks(
            mock_db, supply,
            current_stock=500, safety_stock=10, total_required=50
        )
        item = p.plan_for_supply(supply_id=1, today=today)
        assert item is None

    def test_returns_none_when_no_requirements(self, mock_db):
        supply = make_supply()
        p, today = self._make_planner_with_mocks(
            mock_db, supply,
            total_required=0
        )
        item = p.plan_for_supply(supply_id=1, today=today)
        assert item is None

    def test_returns_none_when_supply_not_found(self, mock_db):
        p = ProcurementPlanner(mock_db)
        p._get_supply = Mock(return_value=None)
        item = p.plan_for_supply(supply_id=999)
        assert item is None

    def test_priority_reflects_alert_severity(self, mock_db):
        supply = make_supply()
        p, today = self._make_planner_with_mocks(
            mock_db, supply,
            current_stock=10, safety_stock=5, total_required=100,
            alert_severity="critical"
        )
        item = p.plan_for_supply(supply_id=1, today=today)
        assert item is not None
        assert item.priority == "critical"

    def test_priority_normal_when_no_alert(self, mock_db):
        supply = make_supply()
        p, today = self._make_planner_with_mocks(
            mock_db, supply,
            current_stock=0, safety_stock=5, total_required=50,
            alert_severity=None
        )
        item = p.plan_for_supply(supply_id=1, today=today)
        assert item is not None
        assert item.priority == "normal"

    def test_order_quantity_uses_moq(self, mock_db):
        # Shortfall = 15, MOQ = 50 → order 50
        supply = make_supply(min_order_qty=50, lead_time_days=0, storage_capacity=None)
        supply.storage_capacity = None
        p, today = self._make_planner_with_mocks(
            mock_db, supply,
            current_stock=10, safety_stock=5, total_required=20
        )
        item = p.plan_for_supply(supply_id=1, today=today)
        assert item is not None
        assert item.order_quantity >= 50

    def test_delivery_date_respects_lead_time(self, mock_db):
        supply = make_supply(lead_time_days=14)
        ref_today = date(2024, 3, 1)
        p, today = self._make_planner_with_mocks(
            mock_db, supply,
            current_stock=0, safety_stock=0, total_required=50,
            earliest_date=ref_today + timedelta(days=20)
        )
        item = p.plan_for_supply(supply_id=1, today=today)
        assert item is not None
        assert item.expected_delivery_date == item.order_date + timedelta(days=14)

    def test_estimated_cost_calculated(self, mock_db):
        supply = make_supply(unit_price=10.0, min_order_qty=1,
                             lead_time_days=0, storage_capacity=None)
        supply.storage_capacity = None
        p, today = self._make_planner_with_mocks(
            mock_db, supply,
            current_stock=0, safety_stock=0, total_required=100
        )
        item = p.plan_for_supply(supply_id=1, today=today)
        assert item is not None
        assert item.estimated_cost == item.order_quantity * 10.0

    def test_storage_capacity_respected(self, mock_db):
        # Only 30 units of space left
        supply = make_supply(min_order_qty=1, lead_time_days=0, storage_capacity=50)
        p, today = self._make_planner_with_mocks(
            mock_db, supply,
            current_stock=20, safety_stock=0, total_required=200
        )
        item = p.plan_for_supply(supply_id=1, today=today)
        # 30 space available, and order can't exceed that
        assert item is not None
        assert item.order_quantity <= 30

    def test_plan_item_fields_populated(self, mock_db):
        supply = make_supply(supply_id=5, name="Test Gloves")
        p, today = self._make_planner_with_mocks(
            mock_db, supply,
            current_stock=0, safety_stock=10, total_required=50
        )
        item = p.plan_for_supply(supply_id=5, today=today)
        assert item is not None
        assert item.supply_id == 5
        assert item.supply_name == "Test Gloves"
        assert item.current_stock == 0
        assert item.safety_stock == 10
        assert item.required_quantity == 50


# ─────────────────────────────────────────────────────────────────────────────
# 7. generate_plan
# ─────────────────────────────────────────────────────────────────────────────

class TestGeneratePlan:
    """Tests for ProcurementPlanner.generate_plan (uses mock DB)."""

    def _make_row(self, supply_id: int):
        row = Mock()
        row.supply_id = supply_id
        return row

    def test_empty_requirements_returns_empty_list(self, mock_db):
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        p = ProcurementPlanner(mock_db)
        result = p.generate_plan(today=date(2024, 1, 1))
        assert result == []

    def test_generates_item_for_each_supply(self, mock_db):
        rows = [self._make_row(1), self._make_row(2), self._make_row(3)]
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = rows

        p = ProcurementPlanner(mock_db)
        today = date(2024, 1, 1)

        dummy_items = [
            ProcurementPlanItem(
                supply_id=i, supply_name=f"Supply {i}",
                order_quantity=50, order_date=today,
                expected_delivery_date=today + timedelta(days=7),
                estimated_cost=250.0, priority="normal",
                current_stock=0, safety_stock=10,
                required_quantity=50, shortage_quantity=50,
                lead_time_days=7
            )
            for i in [1, 2, 3]
        ]
        p.plan_for_supply = Mock(side_effect=dummy_items)

        result = p.generate_plan(today=today)
        assert len(result) == 3
        assert p.plan_for_supply.call_count == 3

    def test_none_items_excluded(self, mock_db):
        rows = [self._make_row(1), self._make_row(2)]
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = rows

        p = ProcurementPlanner(mock_db)
        today = date(2024, 1, 1)

        item1 = ProcurementPlanItem(
            supply_id=1, supply_name="Supply 1",
            order_quantity=50, order_date=today,
            expected_delivery_date=today + timedelta(days=7),
            estimated_cost=250.0, priority="critical",
            current_stock=0, safety_stock=10,
            required_quantity=50, shortage_quantity=50,
            lead_time_days=7
        )
        p.plan_for_supply = Mock(side_effect=[item1, None])

        result = p.generate_plan(today=today)
        assert len(result) == 1
        assert result[0].supply_id == 1

    def test_results_sorted_by_priority(self, mock_db):
        rows = [self._make_row(1), self._make_row(2), self._make_row(3)]
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = rows

        p = ProcurementPlanner(mock_db)
        today = date(2024, 1, 1)

        def make_item(supply_id, priority):
            return ProcurementPlanItem(
                supply_id=supply_id, supply_name=f"S{supply_id}",
                order_quantity=50, order_date=today,
                expected_delivery_date=today + timedelta(days=7),
                estimated_cost=0.0, priority=priority,
                current_stock=0, safety_stock=0,
                required_quantity=50, shortage_quantity=50,
                lead_time_days=0
            )

        # Return in random priority order
        p.plan_for_supply = Mock(side_effect=[
            make_item(1, "normal"),
            make_item(2, "critical"),
            make_item(3, "high"),
        ])

        result = p.generate_plan(today=today)
        assert [r.priority for r in result] == ["critical", "high", "normal"]


# ─────────────────────────────────────────────────────────────────────────────
# 8. save_plan
# ─────────────────────────────────────────────────────────────────────────────

class TestSavePlan:
    """Tests for ProcurementPlanner.save_plan (uses mock DB)."""

    def _make_item(self, supply_id: int = 1, priority: str = "normal") -> ProcurementPlanItem:
        today = date(2024, 1, 1)
        return ProcurementPlanItem(
            supply_id=supply_id, supply_name="Test Supply",
            order_quantity=100, order_date=today,
            expected_delivery_date=today + timedelta(days=7),
            estimated_cost=500.0, priority=priority,
            current_stock=0, safety_stock=10,
            required_quantity=100, shortage_quantity=100,
            lead_time_days=7,
            notes="Test notes"
        )

    def test_saves_plan_items_to_db(self, mock_db):
        mock_db.query.return_value.filter.return_value.delete.return_value = None
        p = ProcurementPlanner(mock_db)
        items = [self._make_item(1), self._make_item(2)]

        p.save_plan(items, created_by=42)

        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()

    def test_empty_plan_commits_nothing(self, mock_db):
        p = ProcurementPlanner(mock_db)
        result = p.save_plan([], created_by=1)
        assert result == []
        mock_db.commit.assert_called_once()

    def test_rollback_on_commit_failure(self, mock_db):
        mock_db.query.return_value.filter.return_value.delete.return_value = None
        mock_db.commit.side_effect = Exception("DB error")

        p = ProcurementPlanner(mock_db)
        with pytest.raises(Exception, match="DB error"):
            p.save_plan([self._make_item(1)])

        mock_db.rollback.assert_called_once()

    def test_stale_pending_plans_deleted(self, mock_db):
        """Existing pending plans for the supply should be removed first."""
        delete_mock = Mock()
        mock_db.query.return_value.filter.return_value.delete = delete_mock

        p = ProcurementPlanner(mock_db)
        p.save_plan([self._make_item(supply_id=5)])

        delete_mock.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# 9. Parametrized boundary tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOrderQuantityBoundaries:
    """Strict boundary tests for calculate_order_quantity."""

    @pytest.mark.parametrize("required,current,safety,moq,capacity,expected", [
        # (required, current, safety, moq, capacity, expected_order_qty)
        (100, 0,   0,  1,    None, 100),   # basic: all required
        (100, 100, 0,  1,    None, 0),     # exactly covered
        (100, 50,  50, 1,    None, 100),   # need to add safety
        (0,   0,   0,  1,    None, 0),     # zero required
        (10,  0,   0,  25,   None, 25),    # MOQ kicks in (shortfall=10 < MOQ=25)
        (100, 0,   0,  1,    50,   50),    # storage cap limits
        (100, 40,  0,  1,    40,   0),     # storage full
        (100, 40,  10, 1,    200,  70),    # shortfall = 70, within capacity
    ])
    def test_order_quantity_boundary(
        self, required, current, safety, moq, capacity, expected
    ):
        result = ProcurementPlanner.calculate_order_quantity(
            required_quantity=required,
            current_stock=current,
            safety_stock=safety,
            minimum_order_quantity=moq,
            storage_capacity=capacity,
        )
        assert result == expected


class TestOrderDateBoundaries:
    """Parametrized boundary tests for calculate_order_date."""

    @pytest.mark.parametrize("days_to_req,lead_time,expected_days_from_today", [
        (30, 7,  23),    # normal case
        (7,  7,  0),     # lead time == days to req → today
        (5,  7,  0),     # past order date → today
        (0,  7,  0),     # requirement today, past → today
        (14, 0,  14),    # zero lead time
        (14, 14, 0),     # exactly on boundary → today
    ])
    def test_order_date(self, days_to_req, lead_time, expected_days_from_today):
        today = date(2024, 6, 1)
        req_date = today + timedelta(days=days_to_req)
        result = ProcurementPlanner.calculate_order_date(
            req_date, lead_time, today=today
        )
        expected = today + timedelta(days=expected_days_from_today)
        assert result == expected
