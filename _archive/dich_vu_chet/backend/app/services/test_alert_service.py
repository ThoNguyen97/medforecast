"""
Unit tests for AlertModule (alert_service.py)

Tests cover:
- severity classification logic
- projected shortage date calculation
- alert generation (create / update / no-op)
- alert auto-resolution when inventory is updated
- end-to-end check_and_generate_alerts flow
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch, call
import pytest

from app.services.alert_service import AlertModule, SEVERITY_THRESHOLDS
from app.models.alert import Alert
from app.models.medical_supply import MedicalSupply
from app.models.supply_requirement import SupplyRequirement
from app.models.inventory import Inventory


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Return a MagicMock that mimics a SQLAlchemy Session."""
    db = MagicMock()
    return db


@pytest.fixture
def alert_module(mock_db):
    return AlertModule(mock_db)


def make_supply(supply_id: int, name: str = "Test Supply") -> MedicalSupply:
    supply = MedicalSupply()
    supply.id = supply_id
    supply.name = name
    supply.category = "PPE"
    supply.unit = "box"
    return supply


def make_alert(
    alert_id: int,
    supply_id: int,
    severity: str = "high",
    is_resolved: bool = False,
) -> Alert:
    alert = Alert()
    alert.id = alert_id
    alert.supply_id = supply_id
    alert.alert_type = "shortage"
    alert.severity = severity
    alert.current_stock = 50
    alert.required_stock = 200
    alert.shortage_date = date.today() + timedelta(days=5)
    alert.message = "Test alert"
    alert.is_resolved = is_resolved
    alert.resolved_at = None
    alert.created_at = datetime.now(timezone.utc)
    return alert


def make_requirement(
    req_id: int, supply_id: int, required: int, req_date: date
) -> SupplyRequirement:
    req = SupplyRequirement()
    req.id = req_id
    req.supply_id = supply_id
    req.required_quantity = required
    req.requirement_date = req_date
    req.disease_type = "dengue_fever"
    req.forecast_id = 1
    return req


# ─────────────────────────────────────────────────────────────────────────────
# 1. Severity classification
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifySeverity:

    def test_critical_zero_days(self):
        assert AlertModule.classify_severity(0) == "critical"

    def test_critical_one_day(self):
        assert AlertModule.classify_severity(1) == "critical"

    def test_critical_exactly_three_days(self):
        assert AlertModule.classify_severity(3) == "critical"

    def test_high_four_days(self):
        assert AlertModule.classify_severity(4) == "high"

    def test_high_exactly_seven_days(self):
        assert AlertModule.classify_severity(7) == "high"

    def test_medium_eight_days(self):
        assert AlertModule.classify_severity(8) == "medium"

    def test_medium_exactly_fourteen_days(self):
        assert AlertModule.classify_severity(14) == "medium"

    def test_none_fifteen_days(self):
        assert AlertModule.classify_severity(15) is None

    def test_none_large_value(self):
        assert AlertModule.classify_severity(100) is None

    def test_negative_days_treated_as_critical(self):
        # Negative value means stock has already run out → critical
        assert AlertModule.classify_severity(-1) == "critical"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Shortage date calculation
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateShortageDate:

    def test_basic_calculation(self):
        today = date(2024, 1, 1)
        result = AlertModule.calculate_shortage_date(100, 10.0, today=today)
        assert result == date(2024, 1, 11)  # 100/10 = 10 days

    def test_zero_daily_demand_returns_none(self):
        result = AlertModule.calculate_shortage_date(100, 0.0)
        assert result is None

    def test_negative_daily_demand_returns_none(self):
        result = AlertModule.calculate_shortage_date(100, -5.0)
        assert result is None

    def test_zero_stock_returns_today(self):
        today = date(2024, 6, 15)
        result = AlertModule.calculate_shortage_date(0, 10.0, today=today)
        assert result == today  # 0/10 = 0 days → today

    def test_fractional_demand_truncates(self):
        today = date(2024, 1, 1)
        # 100 / 3.0 = 33.33... → 33 days
        result = AlertModule.calculate_shortage_date(100, 3.0, today=today)
        assert result == today + timedelta(days=33)

    def test_uses_today_by_default(self):
        today = date.today()
        result = AlertModule.calculate_shortage_date(50, 5.0)
        expected = today + timedelta(days=10)
        assert result == expected


class TestDaysUntilShortage:

    def test_basic(self):
        result = AlertModule.days_until_shortage(100, 10.0)
        assert result == 10

    def test_zero_demand_returns_none(self):
        assert AlertModule.days_until_shortage(100, 0.0) is None

    def test_zero_stock(self):
        assert AlertModule.days_until_shortage(0, 5.0) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 3. Build alert message
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildAlertMessage:

    def test_message_contains_severity(self):
        msg = AlertModule.build_alert_message(
            "Masks", "critical", 10, 100, date(2024, 1, 5)
        )
        assert "CRITICAL" in msg

    def test_message_contains_supply_name(self):
        msg = AlertModule.build_alert_message(
            "Surgical Gloves", "high", 50, 200, date(2024, 1, 10)
        )
        assert "Surgical Gloves" in msg

    def test_message_contains_shortage_date(self):
        shortage_date = date(2024, 3, 15)
        msg = AlertModule.build_alert_message("PPE", "medium", 80, 100, shortage_date)
        assert "2024-03-15" in msg

    def test_message_with_no_shortage_date(self):
        msg = AlertModule.build_alert_message("PPE", "critical", 0, 100, None)
        assert "unknown date" in msg

    def test_message_includes_shortage_amount(self):
        msg = AlertModule.build_alert_message("Masks", "high", 30, 130, None)
        # shortage = 130 - 30 = 100
        assert "100" in msg


# ─────────────────────────────────────────────────────────────────────────────
# 4. _get_current_stock helper
# ─────────────────────────────────────────────────────────────────────────────

class TestGetCurrentStock:

    def test_returns_sum_of_stock(self, mock_db):
        mock_db.query.return_value.filter.return_value.scalar.return_value = 250
        module = AlertModule(mock_db)
        assert module._get_current_stock(1) == 250

    def test_returns_zero_when_no_inventory(self, mock_db):
        mock_db.query.return_value.filter.return_value.scalar.return_value = None
        module = AlertModule(mock_db)
        assert module._get_current_stock(1) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 5. generate_alert_for_supply
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateAlertForSupply:
    """Tests for the generate_alert_for_supply method."""

    def _setup_db_for_stock(self, mock_db, stock_value):
        """Helper: make mock_db._get_current_stock return stock_value."""
        scalar_mock = Mock(return_value=stock_value)
        mock_db.query.return_value.filter.return_value.scalar.return_value = stock_value

    def test_no_alert_when_stock_sufficient(self, alert_module, mock_db):
        """No alert created when current_stock >= required_stock."""
        # Patch _get_current_stock to return high value
        alert_module._get_current_stock = Mock(return_value=500)
        # Patch _resolve_alert_for_supply
        alert_module._resolve_alert_for_supply = Mock(return_value=False)

        result = alert_module.generate_alert_for_supply(
            supply_id=1, required_stock=100
        )
        assert result is None
        alert_module._resolve_alert_for_supply.assert_called_once_with(1)

    def test_alert_created_for_shortage(self, alert_module, mock_db):
        """Alert created when current_stock < required_stock."""
        supply = make_supply(1, "Surgical Masks")
        alert_module._get_current_stock = Mock(return_value=10)
        alert_module._get_daily_demand = Mock(return_value=5.0)

        # No existing alert
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            supply,   # supply lookup
            None,     # existing alert lookup
        ]

        result = alert_module.generate_alert_for_supply(
            supply_id=1, required_stock=100
        )
        assert result is not None
        assert result.severity in ("critical", "high", "medium")
        assert result.current_stock == 10
        assert result.required_stock == 100
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called()

    def test_existing_alert_is_updated(self, alert_module, mock_db):
        """Existing unresolved alert is updated instead of creating a new one."""
        existing = make_alert(1, supply_id=1, severity="medium")
        supply = make_supply(1, "Test Masks")

        alert_module._get_current_stock = Mock(return_value=10)
        alert_module._get_daily_demand = Mock(return_value=5.0)

        # Supply query returns supply; alert query returns existing alert
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            supply,
            existing,
        ]

        result = alert_module.generate_alert_for_supply(
            supply_id=1, required_stock=100
        )
        assert result is existing
        # Severity should have been recalculated
        assert result.severity in ("critical", "high", "medium")
        # No new add() call because we updated the existing object
        mock_db.add.assert_not_called()

    def test_severity_resolved_when_far_shortage(self, alert_module, mock_db):
        """Alert resolved when computed shortage date is beyond 14 days."""
        alert_module._get_current_stock = Mock(return_value=1000)
        alert_module._get_daily_demand = Mock(return_value=1.0)
        alert_module._resolve_alert_for_supply = Mock(return_value=False)

        # current_stock (1000) < required_stock (2000) but demand is 1/day
        # → days_until = 1000 → severity None → resolve
        shortage_date = date.today() + timedelta(days=1000)
        result = alert_module.generate_alert_for_supply(
            supply_id=1,
            required_stock=2000,
            shortage_date=shortage_date,
        )
        assert result is None
        alert_module._resolve_alert_for_supply.assert_called_once_with(1)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Severity correct for specific shortage_date values
# ─────────────────────────────────────────────────────────────────────────────

class TestSeverityFromShortageDate:
    """Integration: generate_alert_for_supply uses shortage_date to set severity."""

    def test_critical_severity_for_imminent_shortage(self, mock_db):
        module = AlertModule(mock_db)
        module._get_current_stock = Mock(return_value=10)
        module._get_daily_demand = Mock(return_value=5.0)

        supply = make_supply(1, "Masks")
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            supply,
            None,  # no existing alert
        ]

        # Shortage in 2 days → critical
        shortage_date = date.today() + timedelta(days=2)
        alert = module.generate_alert_for_supply(
            supply_id=1, required_stock=100, shortage_date=shortage_date
        )
        assert alert is not None
        assert alert.severity == "critical"

    def test_high_severity_for_week_shortage(self, mock_db):
        module = AlertModule(mock_db)
        module._get_current_stock = Mock(return_value=10)
        module._get_daily_demand = Mock(return_value=2.0)

        supply = make_supply(1, "Gloves")
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            supply,
            None,
        ]

        shortage_date = date.today() + timedelta(days=6)
        alert = module.generate_alert_for_supply(
            supply_id=1, required_stock=100, shortage_date=shortage_date
        )
        assert alert is not None
        assert alert.severity == "high"

    def test_medium_severity_for_two_week_shortage(self, mock_db):
        module = AlertModule(mock_db)
        module._get_current_stock = Mock(return_value=10)
        module._get_daily_demand = Mock(return_value=1.0)

        supply = make_supply(1, "Test Kits")
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            supply,
            None,
        ]

        shortage_date = date.today() + timedelta(days=10)
        alert = module.generate_alert_for_supply(
            supply_id=1, required_stock=100, shortage_date=shortage_date
        )
        assert alert is not None
        assert alert.severity == "medium"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Auto-resolution when inventory is updated
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoResolveAlerts:

    def test_resolve_alert_manually(self, alert_module, mock_db):
        alert = make_alert(1, supply_id=1, is_resolved=False)
        mock_db.query.return_value.filter.return_value.first.return_value = alert

        result = alert_module.resolve_alert(alert_id=1)
        assert result is not None
        assert result.is_resolved is True
        assert result.resolved_at is not None
        mock_db.commit.assert_called_once()

    def test_resolve_already_resolved_alert(self, alert_module, mock_db):
        alert = make_alert(1, supply_id=1, is_resolved=True)
        alert.resolved_at = datetime(2024, 1, 1, 12, 0, 0)
        mock_db.query.return_value.filter.return_value.first.return_value = alert

        result = alert_module.resolve_alert(alert_id=1)
        # Should return the alert without touching it again
        assert result.is_resolved is True
        mock_db.commit.assert_not_called()

    def test_resolve_nonexistent_alert_returns_none(self, alert_module, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = alert_module.resolve_alert(alert_id=999)
        assert result is None

    def test_check_and_resolve_when_stock_sufficient(self, alert_module, mock_db):
        """check_and_resolve_alerts_for_supply resolves alert when stock sufficient."""
        req = make_requirement(1, supply_id=1, required=100, req_date=date.today())
        alert_module._get_current_stock = Mock(return_value=200)  # plenty of stock

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = req
        alert_module._resolve_alert_for_supply = Mock(return_value=True)

        resolved = alert_module.check_and_resolve_alerts_for_supply(supply_id=1)
        assert resolved is True
        alert_module._resolve_alert_for_supply.assert_called_once_with(1)
        mock_db.commit.assert_called()

    def test_check_and_resolve_when_still_shortage(self, alert_module, mock_db):
        """check_and_resolve_alerts_for_supply does NOT resolve when shortage remains."""
        req = make_requirement(1, supply_id=1, required=200, req_date=date.today())
        alert_module._get_current_stock = Mock(return_value=50)

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = req
        alert_module.generate_alert_for_supply = Mock(return_value=make_alert(1, 1))

        resolved = alert_module.check_and_resolve_alerts_for_supply(supply_id=1)
        assert resolved is False
        alert_module.generate_alert_for_supply.assert_called_once()

    def test_check_and_resolve_no_requirements(self, alert_module, mock_db):
        """If no requirements exist, any open alert should be resolved."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        alert_module._resolve_alert_for_supply = Mock(return_value=True)

        resolved = alert_module.check_and_resolve_alerts_for_supply(supply_id=1)
        assert resolved is True
        alert_module._resolve_alert_for_supply.assert_called_once_with(1)


# ─────────────────────────────────────────────────────────────────────────────
# 8. check_and_generate_alerts (end-to-end flow)
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckAndGenerateAlerts:

    def test_no_requirements_generates_no_alerts(self, alert_module, mock_db):
        """When no supply requirements exist, no alerts are created."""
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []

        alerts = alert_module.check_and_generate_alerts()
        assert alerts == []
        mock_db.commit.assert_called_once()

    def test_generates_alert_for_shortage(self, alert_module, mock_db):
        """check_and_generate_alerts generates alerts for each shortage."""
        # Row returned by the aggregation query
        row = Mock()
        row.supply_id = 1
        row.total_required = 200
        row.earliest_date = date.today() + timedelta(days=2)

        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [row]

        # Patch generate_alert_for_supply to return a dummy alert
        dummy_alert = make_alert(1, supply_id=1, severity="critical")
        alert_module.generate_alert_for_supply = Mock(return_value=dummy_alert)

        alerts = alert_module.check_and_generate_alerts()

        assert len(alerts) == 1
        assert alerts[0].severity == "critical"
        alert_module.generate_alert_for_supply.assert_called_once_with(
            supply_id=1,
            required_stock=200,
            shortage_date=row.earliest_date,
        )
        mock_db.commit.assert_called_once()

    def test_none_alerts_not_included(self, alert_module, mock_db):
        """Supplies without shortages (generate returns None) are excluded."""
        row1, row2 = Mock(), Mock()
        row1.supply_id, row1.total_required, row1.earliest_date = 1, 300, date.today()
        row2.supply_id, row2.total_required, row2.earliest_date = 2, 50, date.today() + timedelta(days=20)

        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [row1, row2]

        alert = make_alert(1, supply_id=1, severity="high")
        alert_module.generate_alert_for_supply = Mock(side_effect=[alert, None])

        alerts = alert_module.check_and_generate_alerts()
        assert len(alerts) == 1
        assert alerts[0].supply_id == 1

    def test_rollback_on_commit_error(self, alert_module, mock_db):
        """DB error during commit triggers rollback and re-raises."""
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        mock_db.commit.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            alert_module.check_and_generate_alerts()

        mock_db.rollback.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# 9. Query helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestQueryHelpers:

    def test_get_active_alerts(self, alert_module, mock_db):
        alert = make_alert(1, supply_id=1)
        mock_db.query.return_value.options.return_value.filter.return_value.order_by.return_value.all.return_value = [alert]

        result = alert_module.get_active_alerts()
        assert result == [alert]

    def test_get_active_alerts_filtered_by_severity(self, alert_module, mock_db):
        alert = make_alert(1, supply_id=1, severity="critical")
        mock_db.query.return_value.options.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [alert]

        result = alert_module.get_active_alerts(severity="critical")
        assert result == [alert]

    def test_get_alert_by_id_found(self, alert_module, mock_db):
        alert = make_alert(5, supply_id=2)
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = alert

        result = alert_module.get_alert_by_id(5)
        assert result is alert

    def test_get_alert_by_id_not_found(self, alert_module, mock_db):
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        assert alert_module.get_alert_by_id(999) is None

    def test_get_all_alerts_with_filters(self, alert_module, mock_db):
        alerts = [make_alert(1, 1), make_alert(2, 2)]
        chain = mock_db.query.return_value.options.return_value
        chain.filter.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = alerts

        result = alert_module.get_all_alerts(severity="high", is_resolved=False, limit=10)
        assert len(result) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 10. Threshold boundary tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSeverityBoundaryConditions:
    """Strict boundary tests based on the spec thresholds."""

    @pytest.mark.parametrize("days,expected", [
        (0, "critical"),
        (1, "critical"),
        (2, "critical"),
        (3, "critical"),      # boundary: ≤3 → critical
        (4, "high"),
        (5, "high"),
        (6, "high"),
        (7, "high"),          # boundary: ≤7 → high
        (8, "medium"),
        (9, "medium"),
        (13, "medium"),
        (14, "medium"),       # boundary: ≤14 → medium
        (15, None),
        (30, None),
        (365, None),
    ])
    def test_severity_boundaries(self, days, expected):
        assert AlertModule.classify_severity(days) == expected
