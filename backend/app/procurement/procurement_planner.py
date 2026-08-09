"""
Procurement Planner for Medical Supply Forecasting System

This module calculates optimal procurement plans for medical supplies based on:
- Current inventory levels and safety stock requirements
- Forecasted supply requirements
- Lead times for each supply
- Minimum order quantities
- Storage capacity constraints
- Unit prices for cost estimation
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.inventory import Inventory
from app.models.medical_supply import MedicalSupply
from app.models.procurement_plan import ProcurementPlan
from app.models.supply_requirement import SupplyRequirement

logger = logging.getLogger(__name__)


@dataclass
class ProcurementPlanItem:
    """
    Represents a single line item in a procurement plan.

    Attributes:
        supply_id:              ID of the medical supply to order.
        supply_name:            Human-readable name of the supply.
        order_quantity:         Recommended order quantity (units).
        order_date:             Recommended date to place the order.
        expected_delivery_date: Expected arrival date (order_date + lead_time).
        estimated_cost:         Estimated cost of the order (order_qty × unit_price).
        priority:               Order priority – 'critical', 'high', or 'normal'.
        current_stock:          Stock on hand at plan-generation time.
        safety_stock:           Minimum desired stock level.
        required_quantity:      Total quantity required during the forecast window.
        shortage_quantity:      Units short (required - current_stock, floored at 0).
        lead_time_days:         Lead time used when computing the order date.
        notes:                  Freeform notes / explanations for this line item.
    """

    supply_id: int
    supply_name: str
    order_quantity: int
    order_date: date
    expected_delivery_date: date
    estimated_cost: float
    priority: str
    current_stock: int
    safety_stock: int
    required_quantity: int
    shortage_quantity: int
    lead_time_days: int
    notes: str = ""


class ProcurementPlanner:
    """
    Generate optimal procurement plans for medical supplies.

    The planner examines every supply that has a pending requirement and
    determines whether an order is needed, when to place it, how many units
    to order, and what it will cost.

    Key rules applied:
    - **Safety stock**: order quantity must bring stock up to at least
      ``safety_stock + required_quantity`` so safety levels are maintained
      throughout the forecast window.
    - **Lead time**: the order must be placed ``lead_time_days`` before the
      earliest requirement date so the goods arrive in time.
    - **Minimum order quantity (MOQ)**: if the calculated quantity is below
      the supply's MOQ, the MOQ is used instead.
    - **Storage capacity**: the final order quantity is capped so that
      ``current_stock + order_quantity <= storage_capacity``.
    - **Cost estimation**: ``estimated_cost = order_quantity × unit_price``.
    - **Priority**: inherited from any open Alert for the supply, or 'normal'
      when there is no active alert.

    Example::

        planner = ProcurementPlanner(db_session)
        plan = planner.generate_plan(forecast_days=14)
        for item in plan:
            print(item.supply_name, item.order_quantity, item.estimated_cost)
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _get_current_stock(self, supply_id: int) -> int:
        """Return the total on-hand stock for *supply_id* across all locations."""
        result = (
            self.db.query(func.sum(Inventory.current_stock))
            .filter(Inventory.supply_id == supply_id)
            .scalar()
        )
        return int(result) if result is not None else 0

    def _get_safety_stock(self, supply_id: int) -> int:
        """Return the maximum safety-stock target across all inventory rows."""
        result = (
            self.db.query(func.max(Inventory.safety_stock))
            .filter(Inventory.supply_id == supply_id)
            .scalar()
        )
        return int(result) if result is not None else 0

    def _get_total_required(
        self,
        supply_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        """Return the total required quantity for a supply over a date range."""
        query = self.db.query(
            func.sum(SupplyRequirement.required_quantity)
        ).filter(SupplyRequirement.supply_id == supply_id)

        if start_date:
            query = query.filter(SupplyRequirement.requirement_date >= start_date)
        if end_date:
            query = query.filter(SupplyRequirement.requirement_date <= end_date)

        result = query.scalar()
        return int(result) if result is not None else 0

    def _get_earliest_requirement_date(
        self,
        supply_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Optional[date]:
        """Return the earliest requirement date for a supply within the window."""
        query = self.db.query(
            func.min(SupplyRequirement.requirement_date)
        ).filter(SupplyRequirement.supply_id == supply_id)

        if start_date:
            query = query.filter(SupplyRequirement.requirement_date >= start_date)
        if end_date:
            query = query.filter(SupplyRequirement.requirement_date <= end_date)

        return query.scalar()

    def _get_supply(self, supply_id: int) -> Optional[MedicalSupply]:
        """Fetch a MedicalSupply ORM object by primary key."""
        return (
            self.db.query(MedicalSupply)
            .filter(MedicalSupply.id == supply_id)
            .first()
        )

    def _get_active_alert_severity(self, supply_id: int) -> Optional[str]:
        """
        Return the severity of the highest-priority open alert for *supply_id*.

        Returns None when there are no unresolved alerts.
        """
        alert = (
            self.db.query(Alert)
            .filter(Alert.supply_id == supply_id, Alert.is_resolved == False)  # noqa: E712
            .order_by(Alert.created_at.desc())
            .first()
        )
        return alert.severity if alert else None

    # ──────────────────────────────────────────────────────────────────────────
    # Pure calculation helpers (static – no DB access, fully unit-testable)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_order_quantity(
        required_quantity: int,
        current_stock: int,
        safety_stock: int,
        minimum_order_quantity: int = 1,
        storage_capacity: Optional[int] = None,
    ) -> int:
        """
        Calculate the optimal order quantity for a supply.

        The order quantity is determined by the following logic:

        1. **Shortfall** = max(0, required_quantity + safety_stock - current_stock)
           This ensures that after the order arrives we have enough stock for
           the entire forecast window *plus* the safety buffer.
        2. Apply the minimum order quantity (MOQ): if the shortfall is below
           the MOQ we still order at least MOQ units.
        3. Cap at storage capacity: we never order so many units that
           ``current_stock + order_qty > storage_capacity``.
        4. If applying the capacity cap would result in an order of 0 or less
           (i.e. the warehouse is already full), return 0.

        Args:
            required_quantity:       Total units required during the forecast window.
            current_stock:           Current units on hand.
            safety_stock:            Minimum desired buffer stock.
            minimum_order_quantity:  Smallest order the supplier will accept (default 1).
            storage_capacity:        Maximum total units the warehouse can hold
                                     (``None`` means no limit).

        Returns:
            Recommended order quantity (≥ 0).

        Examples:
            >>> ProcurementPlanner.calculate_order_quantity(100, 20, 10, moq=50)
            90  # shortfall = 90, already ≥ moq
            >>> ProcurementPlanner.calculate_order_quantity(100, 120, 10, moq=50)
            50  # no shortfall, but must meet MOQ
            >>> ProcurementPlanner.calculate_order_quantity(100, 20, 10, moq=50,
            ...                                             storage_capacity=60)
            40  # cap: 60 - 20 = 40 available space
        """
        # Step 1 – how many units are needed to cover requirements + safety stock?
        shortfall = max(0, required_quantity + safety_stock - current_stock)

        if shortfall == 0 and minimum_order_quantity <= 0:
            return 0

        # Step 2 – apply MOQ
        order_qty = max(shortfall, minimum_order_quantity) if shortfall > 0 else 0

        # If there is no shortfall, no order is placed (MOQ only applies when
        # an order is actually needed)
        if shortfall == 0:
            return 0

        # Step 3 – apply storage capacity cap
        if storage_capacity is not None and storage_capacity > 0:
            available_space = storage_capacity - current_stock
            if available_space <= 0:
                logger.warning(
                    "Storage already at or over capacity for supply "
                    "(current_stock=%d, storage_capacity=%d)",
                    current_stock,
                    storage_capacity,
                )
                return 0
            order_qty = min(order_qty, available_space)

        return max(0, order_qty)

    @staticmethod
    def calculate_order_date(
        earliest_requirement_date: date,
        lead_time_days: int,
        today: Optional[date] = None,
    ) -> date:
        """
        Calculate the latest safe date to place an order.

        The order must be placed at least *lead_time_days* before the earliest
        requirement date so that goods arrive before they are needed.

        If the computed order date is in the past, today's date is returned
        so that the order can be placed immediately.

        Args:
            earliest_requirement_date: The first date on which the supply is needed.
            lead_time_days:            Number of days from order to delivery.
            today:                     Reference date (defaults to ``date.today()``).

        Returns:
            The recommended order date.

        Examples:
            >>> ProcurementPlanner.calculate_order_date(date(2024,2,10), 7)
            date(2024, 2, 3)
            >>> ProcurementPlanner.calculate_order_date(date(2024,1,1), 7)  # past
            date.today()
        """
        if today is None:
            today = date.today()

        order_date = earliest_requirement_date - timedelta(days=lead_time_days)
        return max(order_date, today)

    @staticmethod
    def calculate_delivery_date(order_date: date, lead_time_days: int) -> date:
        """
        Return the expected delivery date given an order date and lead time.

        Args:
            order_date:      Date the order is placed.
            lead_time_days:  Days from order placement to delivery.

        Returns:
            Expected delivery date.
        """
        return order_date + timedelta(days=lead_time_days)

    @staticmethod
    def estimate_cost(order_quantity: int, unit_price: Optional[float]) -> float:
        """
        Estimate the total cost of an order.

        Returns 0.0 when *unit_price* is None or non-positive.

        Args:
            order_quantity: Number of units to order.
            unit_price:     Price per unit (may be None if not configured).

        Returns:
            Estimated cost as a float.
        """
        if unit_price is None or unit_price <= 0:
            return 0.0
        return round(order_quantity * unit_price, 2)

    @staticmethod
    def determine_priority(alert_severity: Optional[str]) -> str:
        """
        Map an alert severity to an order priority string.

        ``critical`` → ``'critical'``
        ``high``     → ``'high'``
        anything else (including ``None``) → ``'normal'``

        Args:
            alert_severity: Severity string from an open Alert, or None.

        Returns:
            Priority string for the procurement plan.
        """
        if alert_severity in ("critical", "high"):
            return alert_severity
        return "normal"

    # ──────────────────────────────────────────────────────────────────────────
    # Core plan generation
    # ──────────────────────────────────────────────────────────────────────────

    def plan_for_supply(
        self,
        supply_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        today: Optional[date] = None,
    ) -> Optional[ProcurementPlanItem]:
        """
        Generate a procurement plan item for a single supply.

        Returns ``None`` when no order is needed (sufficient stock, no
        requirements, or storage is at capacity).

        Args:
            supply_id:   ID of the supply to plan for.
            start_date:  Start of the requirement window (default: today).
            end_date:    End of the requirement window (default: today + 30 days).
            today:       Reference date for order-date calculation.

        Returns:
            A :class:`ProcurementPlanItem`, or ``None`` if no order is needed.
        """
        if today is None:
            today = date.today()
        if start_date is None:
            start_date = today
        if end_date is None:
            end_date = today + timedelta(days=30)

        supply = self._get_supply(supply_id)
        if supply is None:
            logger.warning("Supply id=%d not found – skipping.", supply_id)
            return None

        # Gather data
        current_stock = self._get_current_stock(supply_id)
        safety_stock = self._get_safety_stock(supply_id)
        required_quantity = self._get_total_required(supply_id, start_date, end_date)

        if required_quantity == 0:
            logger.debug("No requirements for supply_id=%d – skipping.", supply_id)
            return None

        earliest_req_date = self._get_earliest_requirement_date(
            supply_id, start_date, end_date
        )

        # Supply-level parameters (with safe defaults)
        lead_time_days = supply.lead_time_days or 0
        min_order_qty = supply.minimum_order_quantity or 1
        storage_capacity = supply.storage_capacity  # may be None
        unit_price = float(supply.unit_price) if supply.unit_price is not None else None

        # Calculate order quantity
        order_quantity = self.calculate_order_quantity(
            required_quantity=required_quantity,
            current_stock=current_stock,
            safety_stock=safety_stock,
            minimum_order_quantity=min_order_qty,
            storage_capacity=storage_capacity,
        )

        if order_quantity <= 0:
            logger.info(
                "No order needed for supply_id=%d (current=%d, required=%d, "
                "safety=%d, capacity=%s).",
                supply_id,
                current_stock,
                required_quantity,
                safety_stock,
                storage_capacity,
            )
            return None

        # Calculate dates
        if earliest_req_date is not None:
            order_date = self.calculate_order_date(
                earliest_req_date, lead_time_days, today=today
            )
        else:
            order_date = today

        delivery_date = self.calculate_delivery_date(order_date, lead_time_days)

        # Cost & priority
        estimated_cost = self.estimate_cost(order_quantity, unit_price)
        alert_severity = self._get_active_alert_severity(supply_id)
        priority = self.determine_priority(alert_severity)

        shortage_quantity = max(0, required_quantity - current_stock)

        notes = (
            f"Required: {required_quantity}, "
            f"Current stock: {current_stock}, "
            f"Safety stock: {safety_stock}, "
            f"Lead time: {lead_time_days} days"
        )
        if storage_capacity is not None:
            notes += f", Storage capacity: {storage_capacity}"

        item = ProcurementPlanItem(
            supply_id=supply_id,
            supply_name=supply.name,
            order_quantity=order_quantity,
            order_date=order_date,
            expected_delivery_date=delivery_date,
            estimated_cost=estimated_cost,
            priority=priority,
            current_stock=current_stock,
            safety_stock=safety_stock,
            required_quantity=required_quantity,
            shortage_quantity=shortage_quantity,
            lead_time_days=lead_time_days,
            notes=notes,
        )

        logger.info(
            "Plan item for supply_id=%d (%s): order %d units on %s, "
            "delivery %s, cost %.2f, priority=%s.",
            supply_id,
            supply.name,
            order_quantity,
            order_date,
            delivery_date,
            estimated_cost,
            priority,
        )
        return item

    def generate_plan(
        self,
        forecast_days: int = 30,
        start_date: Optional[date] = None,
        today: Optional[date] = None,
    ) -> List[ProcurementPlanItem]:
        """
        Generate a complete procurement plan for all supplies with pending requirements.

        The method scans every supply ID that has at least one
        :class:`~app.models.supply_requirement.SupplyRequirement` record within
        the forecast window and calls :meth:`plan_for_supply` for each.  Items
        are returned sorted by priority (critical → high → normal).

        Args:
            forecast_days: Number of days ahead to look for requirements
                           (default 30).
            start_date:    Start of the requirement window (default: today).
            today:         Reference date (default: ``date.today()``).

        Returns:
            A list of :class:`ProcurementPlanItem` objects, sorted by priority.
        """
        if today is None:
            today = date.today()
        if start_date is None:
            start_date = today

        end_date = start_date + timedelta(days=forecast_days)

        logger.info(
            "Generating procurement plan for window %s → %s (%d days).",
            start_date,
            end_date,
            forecast_days,
        )

        # Find all supply IDs with requirements in the window
        rows = (
            self.db.query(SupplyRequirement.supply_id)
            .filter(
                SupplyRequirement.requirement_date >= start_date,
                SupplyRequirement.requirement_date <= end_date,
            )
            .distinct()
            .all()
        )

        supply_ids = [row.supply_id for row in rows]
        logger.info("Found %d supplies with requirements in window.", len(supply_ids))

        plan_items: List[ProcurementPlanItem] = []
        for supply_id in supply_ids:
            item = self.plan_for_supply(
                supply_id=supply_id,
                start_date=start_date,
                end_date=end_date,
                today=today,
            )
            if item is not None:
                plan_items.append(item)

        # Sort by priority: critical first, then high, then normal
        priority_order = {"critical": 0, "high": 1, "normal": 2}
        plan_items.sort(key=lambda x: priority_order.get(x.priority, 3))

        logger.info(
            "Generated %d procurement plan items (critical=%d, high=%d, normal=%d).",
            len(plan_items),
            sum(1 for i in plan_items if i.priority == "critical"),
            sum(1 for i in plan_items if i.priority == "high"),
            sum(1 for i in plan_items if i.priority == "normal"),
        )
        return plan_items

    def save_plan(
        self,
        plan_items: List[ProcurementPlanItem],
        created_by: Optional[int] = None,
    ) -> List[ProcurementPlan]:
        """
        Persist a list of plan items as :class:`~app.models.procurement_plan.ProcurementPlan`
        records in the database.

        Existing *pending* plans for the same supply are deleted before the new
        ones are inserted to avoid accumulation of stale plans.

        Args:
            plan_items:  List of plan items to persist.
            created_by:  Optional user ID of the planner who triggered generation.

        Returns:
            List of newly-created :class:`ProcurementPlan` ORM objects.
        """
        created_plans: List[ProcurementPlan] = []

        for item in plan_items:
            # Remove stale pending plans for this supply
            self.db.query(ProcurementPlan).filter(
                ProcurementPlan.supply_id == item.supply_id,
                ProcurementPlan.status == "pending",
            ).delete(synchronize_session=False)

            plan = ProcurementPlan(
                supply_id=item.supply_id,
                order_quantity=item.order_quantity,
                order_date=item.order_date,
                expected_delivery_date=item.expected_delivery_date,
                estimated_cost=item.estimated_cost,
                priority=item.priority,
                status="pending",
                notes=item.notes,
                created_by=created_by,
            )
            self.db.add(plan)
            created_plans.append(plan)

        try:
            self.db.commit()
            for plan in created_plans:
                self.db.refresh(plan)
        except Exception as exc:
            logger.error("Error saving procurement plans: %s", exc)
            self.db.rollback()
            raise

        logger.info("Saved %d procurement plans to database.", len(created_plans))
        return created_plans
