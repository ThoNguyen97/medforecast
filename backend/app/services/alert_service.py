"""
Alert Module for Medical Supply Forecasting System

This module detects shortages by comparing supply requirements against current
inventory, classifies alert severity, calculates projected shortage dates, and
auto-resolves alerts when inventory is updated.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.alert import Alert
from app.models.inventory import Inventory
from app.models.medical_supply import MedicalSupply
from app.models.supply_requirement import SupplyRequirement

logger = logging.getLogger(__name__)

# ── Severity thresholds (days until shortage) ──────────────────────────────────
SEVERITY_THRESHOLDS = {
    "critical": 3,   # shortage within 3 days
    "high": 7,        # shortage within 7 days
    "medium": 14,     # shortage within 14 days
}


class AlertModule:
    """
    Detects supply shortages and manages alerts.

    Responsibilities:
    - Compare supply_requirements against current inventory to detect shortages
    - Calculate projected shortage date (when current stock runs out)
    - Classify severity: critical (≤3 days), high (≤7 days), medium (≤14 days)
    - Create or update alerts in the database
    - Auto-resolve alerts when inventory is updated and shortage no longer exists

    Example:
        >>> module = AlertModule(db_session)
        >>> alerts = module.check_and_generate_alerts()
    """

    def __init__(self, db: Session):
        self.db = db

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _get_current_stock(self, supply_id: int) -> int:
        """Return total current stock for a supply across all inventory rows."""
        result = (
            self.db.query(func.sum(Inventory.current_stock))
            .filter(Inventory.supply_id == supply_id)
            .scalar()
        )
        return int(result) if result is not None else 0

    def _has_inventory_record(self, supply_id: int) -> bool:
        """Check whether the supply has at least one inventory row tracked."""
        return (
            self.db.query(Inventory.id)
            .filter(Inventory.supply_id == supply_id)
            .first()
            is not None
        )

    def _get_total_required(
        self,
        supply_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        """Sum of required quantities for a supply over the given date range."""
        query = self.db.query(func.sum(SupplyRequirement.required_quantity)).filter(
            SupplyRequirement.supply_id == supply_id
        )
        if start_date:
            query = query.filter(SupplyRequirement.requirement_date >= start_date)
        if end_date:
            query = query.filter(SupplyRequirement.requirement_date <= end_date)
        result = query.scalar()
        return int(result) if result is not None else 0

    def _get_daily_demand(self, supply_id: int, days: int = 30) -> float:
        """
        Estimate average daily demand for a supply based on recent requirements.

        Looks at requirement records over the last `days` days to compute the
        average daily consumption rate.  Returns 0.0 if no data is available.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        total = self._get_total_required(supply_id, start_date, end_date)
        if total == 0:
            return 0.0

        # Count distinct requirement dates to avoid dividing by 0
        distinct_dates = (
            self.db.query(func.count(func.distinct(SupplyRequirement.requirement_date)))
            .filter(
                SupplyRequirement.supply_id == supply_id,
                SupplyRequirement.requirement_date >= start_date,
                SupplyRequirement.requirement_date <= end_date,
            )
            .scalar()
        ) or 1

        return total / distinct_dates

    # ──────────────────────────────────────────────────────────────────────────
    # Core business logic (pure, no DB side-effects)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def classify_severity(days_until_shortage: int) -> Optional[str]:
        """
        Classify alert severity based on days until shortage.

        Args:
            days_until_shortage: Number of days before stock runs out.

        Returns:
            'critical', 'high', 'medium', or None if no alert needed (>14 days).

        Examples:
            >>> AlertModule.classify_severity(2)
            'critical'
            >>> AlertModule.classify_severity(5)
            'high'
            >>> AlertModule.classify_severity(10)
            'medium'
            >>> AlertModule.classify_severity(20)
            None
        """
        if days_until_shortage <= SEVERITY_THRESHOLDS["critical"]:
            return "critical"
        if days_until_shortage <= SEVERITY_THRESHOLDS["high"]:
            return "high"
        if days_until_shortage <= SEVERITY_THRESHOLDS["medium"]:
            return "medium"
        return None

    @staticmethod
    def calculate_shortage_date(
        current_stock: int,
        daily_demand: float,
        today: Optional[date] = None,
    ) -> Optional[date]:
        """
        Calculate the projected date when stock will run out.

        Args:
            current_stock: Current inventory quantity.
            daily_demand:  Average daily consumption rate (units/day).
            today:         Reference date (defaults to date.today()).

        Returns:
            Projected shortage date, or None if daily_demand is 0 or current
            stock will never run out based on demand.

        Examples:
            >>> AlertModule.calculate_shortage_date(100, 10.0)
            date(today + 10 days)
            >>> AlertModule.calculate_shortage_date(100, 0.0)
            None
        """
        if today is None:
            today = date.today()

        if daily_demand <= 0:
            return None

        days_remaining = int(current_stock / daily_demand)
        return today + timedelta(days=days_remaining)

    @staticmethod
    def days_until_shortage(
        current_stock: int,
        daily_demand: float,
        today: Optional[date] = None,
    ) -> Optional[int]:
        """
        Return number of days until stock runs out.

        Returns None when daily_demand is 0 (no consumption → no shortage).
        """
        if today is None:
            today = date.today()

        if daily_demand <= 0:
            return None

        return int(current_stock / daily_demand)

    @staticmethod
    def build_alert_message(
        supply_name: str,
        severity: str,
        current_stock: int,
        required_stock: int,
        shortage_date: Optional[date],
    ) -> str:
        """Build a human-readable alert message."""
        shortage_amount = required_stock - current_stock
        date_str = shortage_date.isoformat() if shortage_date else "unknown date"
        return (
            f"[{severity.upper()}] {supply_name}: "
            f"current stock {current_stock} units is below required {required_stock} units "
            f"(shortage of {shortage_amount} units). "
            f"Projected shortage date: {date_str}."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Alert generation
    # ──────────────────────────────────────────────────────────────────────────

    def generate_alert_for_supply(
        self, supply_id: int, required_stock: int, shortage_date: Optional[date] = None
    ) -> Optional[Alert]:
        """
        Evaluate a single supply and create/update an alert if a shortage exists.

        Logic:
        1. Fetch current stock.
        2. If current_stock >= required_stock → no shortage; resolve any existing
           active alert and return None.
        3. Calculate daily demand and projected shortage date.
        4. Classify severity.  If severity is None (>14 days away) → resolve
           any existing alert and return None.
        5. Upsert the alert in the database.

        Args:
            supply_id:      ID of the medical supply.
            required_stock: Total required stock quantity.
            shortage_date:  Optional externally-computed shortage date.

        Returns:
            The created/updated Alert ORM object, or None if no alert needed.
        """
        # Skip supplies that are not yet tracked in inventory.
        # Tránh sinh cảnh báo "ma" cho vật tư chưa được quản lý trong kho.
        if not self._has_inventory_record(supply_id):
            self._resolve_alert_for_supply(supply_id)
            return None

        current_stock = self._get_current_stock(supply_id)

        if current_stock >= required_stock:
            # No shortage — resolve existing alert if any
            self._resolve_alert_for_supply(supply_id)
            return None

        # Compute projected shortage date from daily demand if not supplied
        if shortage_date is None:
            daily_demand = self._get_daily_demand(supply_id)
            shortage_date = self.calculate_shortage_date(current_stock, daily_demand)

        # Determine days until shortage for severity classification
        today = date.today()
        if shortage_date is not None:
            days_until = (shortage_date - today).days
        else:
            # No demand data — treat as imminent (current stock below requirement)
            days_until = 0

        severity = self.classify_severity(days_until)
        if severity is None:
            # Shortage is far enough away — no alert needed
            self._resolve_alert_for_supply(supply_id)
            return None

        # Fetch supply name for the message
        supply = self.db.query(MedicalSupply).filter(MedicalSupply.id == supply_id).first()
        supply_name = supply.name if supply else f"Supply #{supply_id}"

        message = self.build_alert_message(
            supply_name=supply_name,
            severity=severity,
            current_stock=current_stock,
            required_stock=required_stock,
            shortage_date=shortage_date,
        )

        # Upsert: update existing unresolved alert or create a new one
        existing_alert = (
            self.db.query(Alert)
            .filter(Alert.supply_id == supply_id, Alert.is_resolved == False)  # noqa: E712
            .first()
        )

        if existing_alert:
            existing_alert.severity = severity
            existing_alert.current_stock = current_stock
            existing_alert.required_stock = required_stock
            existing_alert.shortage_date = shortage_date
            existing_alert.message = message
            self.db.flush()
            logger.info(
                f"Updated alert for supply_id={supply_id} severity={severity}"
            )
            return existing_alert
        else:
            alert = Alert(
                supply_id=supply_id,
                alert_type="shortage",
                severity=severity,
                current_stock=current_stock,
                required_stock=required_stock,
                shortage_date=shortage_date,
                message=message,
                is_resolved=False,
            )
            self.db.add(alert)
            self.db.flush()
            logger.info(
                f"Created alert for supply_id={supply_id} severity={severity}"
            )
            return alert

    def check_and_generate_alerts(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Alert]:
        """
        Scan all supply requirements and generate/update alerts for shortages.

        Aggregates requirements by supply over the given date range, compares
        against current inventory, and creates/updates/resolves alerts as needed.

        Args:
            start_date: Start of the requirement window (default: today).
            end_date:   End of the requirement window (default: today + 14 days).

        Returns:
            List of created or updated Alert objects (only those with shortages).
        """
        if start_date is None:
            start_date = date.today()
        if end_date is None:
            end_date = date.today() + timedelta(days=SEVERITY_THRESHOLDS["medium"])

        logger.info(
            f"Checking alerts for requirements from {start_date} to {end_date}"
        )

        # Aggregate total required quantities per supply
        rows = (
            self.db.query(
                SupplyRequirement.supply_id,
                func.sum(SupplyRequirement.required_quantity).label("total_required"),
                func.min(SupplyRequirement.requirement_date).label("earliest_date"),
            )
            .filter(
                SupplyRequirement.requirement_date >= start_date,
                SupplyRequirement.requirement_date <= end_date,
            )
            .group_by(SupplyRequirement.supply_id)
            .all()
        )

        alerts_generated: List[Alert] = []
        supply_ids_with_requirements = set()

        for row in rows:
            supply_id = row.supply_id
            total_required = int(row.total_required)
            supply_ids_with_requirements.add(supply_id)

            alert = self.generate_alert_for_supply(
                supply_id=supply_id,
                required_stock=total_required,
                shortage_date=row.earliest_date,  # earliest upcoming requirement date
            )
            if alert is not None:
                alerts_generated.append(alert)

        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"Error committing alerts: {e}")
            self.db.rollback()
            raise

        logger.info(
            f"Generated/updated {len(alerts_generated)} alerts "
            f"out of {len(rows)} supplies checked"
        )
        return alerts_generated

    # ──────────────────────────────────────────────────────────────────────────
    # Alert resolution
    # ──────────────────────────────────────────────────────────────────────────

    def _resolve_alert_for_supply(self, supply_id: int) -> bool:
        """
        Resolve any open alert for the given supply_id (internal helper).

        Returns True if an alert was resolved, False otherwise.
        """
        alert = (
            self.db.query(Alert)
            .filter(Alert.supply_id == supply_id, Alert.is_resolved == False)  # noqa: E712
            .first()
        )
        if alert:
            alert.is_resolved = True
            alert.resolved_at = datetime.now(timezone.utc)
            self.db.flush()
            logger.info(f"Auto-resolved alert id={alert.id} for supply_id={supply_id}")
            return True
        return False

    def resolve_alert(self, alert_id: int) -> Optional[Alert]:
        """
        Manually resolve an alert by its ID.

        Args:
            alert_id: ID of the alert to resolve.

        Returns:
            The resolved Alert object, or None if not found.
        """
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return None

        if not alert.is_resolved:
            alert.is_resolved = True
            alert.resolved_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(alert)
            logger.info(f"Manually resolved alert id={alert_id}")

        return alert

    def check_and_resolve_alerts_for_supply(self, supply_id: int) -> bool:
        """
        Re-evaluate open alerts for a supply after an inventory update.

        Called automatically when inventory is updated so that resolved
        shortages are cleared immediately.

        Args:
            supply_id: ID of the updated supply.

        Returns:
            True if an alert was resolved, False otherwise.
        """
        logger.info(
            f"Re-evaluating alerts for supply_id={supply_id} after inventory update"
        )

        # Look up the most recently required quantity for this supply
        latest_req = (
            self.db.query(SupplyRequirement)
            .filter(SupplyRequirement.supply_id == supply_id)
            .order_by(SupplyRequirement.requirement_date.desc())
            .first()
        )

        if latest_req is None:
            # No requirements → nothing to alert on; resolve any open alert
            resolved = self._resolve_alert_for_supply(supply_id)
            if resolved:
                self.db.commit()
            return resolved

        current_stock = self._get_current_stock(supply_id)
        required_stock = latest_req.required_quantity

        if current_stock >= required_stock:
            resolved = self._resolve_alert_for_supply(supply_id)
            if resolved:
                self.db.commit()
            return resolved

        # Shortage still exists — update the alert in-place
        self.generate_alert_for_supply(
            supply_id=supply_id,
            required_stock=required_stock,
        )
        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"Error updating alert after inventory change: {e}")
            self.db.rollback()
            raise
        return False

    # ──────────────────────────────────────────────────────────────────────────
    # Query helpers
    # ──────────────────────────────────────────────────────────────────────────

    def get_active_alerts(self, severity: Optional[str] = None) -> List[Alert]:
        """Return all unresolved alerts, optionally filtered by severity."""
        query = (
            self.db.query(Alert)
            .options(joinedload(Alert.supply))
            .filter(Alert.is_resolved == False)  # noqa: E712
        )
        if severity:
            query = query.filter(Alert.severity == severity)
        return query.order_by(Alert.created_at.desc()).all()

    def get_all_alerts(
        self,
        severity: Optional[str] = None,
        is_resolved: Optional[bool] = None,
        supply_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Alert]:
        """Return alerts with optional filters."""
        query = self.db.query(Alert).options(joinedload(Alert.supply))
        if severity:
            query = query.filter(Alert.severity == severity)
        if is_resolved is not None:
            query = query.filter(Alert.is_resolved == is_resolved)
        if supply_id is not None:
            query = query.filter(Alert.supply_id == supply_id)
        return (
            query.order_by(Alert.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_alert_by_id(self, alert_id: int) -> Optional[Alert]:
        """Return a single alert by ID."""
        return (
            self.db.query(Alert)
            .options(joinedload(Alert.supply))
            .filter(Alert.id == alert_id)
            .first()
        )
