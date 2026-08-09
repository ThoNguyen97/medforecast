"""Supply Requirement service for managing supply requirements."""
import logging
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.disease_forecast import DiseaseForecast
from app.models.inventory import Inventory
from app.models.medical_supply import MedicalSupply
from app.models.supply_requirement import SupplyRequirement
from app.ai_engine.conversion_module import ConversionModule

logger = logging.getLogger(__name__)


class SupplyRequirementService:
    """Service for managing supply requirements."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _get_current_stock(self, supply_id: int) -> Optional[int]:
        """Return total current stock for a supply across all inventory rows."""
        result = self.db.query(
            func.sum(Inventory.current_stock)
        ).filter(Inventory.supply_id == supply_id).scalar()
        return int(result) if result is not None else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_requirements(
        self,
        forecast_id: Optional[int] = None,
        supply_id: Optional[int] = None,
        disease_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """List supply requirements with optional filters.

        Returns a list of requirement dicts enriched with supply name and
        current stock comparison.
        """
        query = self.db.query(SupplyRequirement).options(
            joinedload(SupplyRequirement.supply)
        )

        if forecast_id is not None:
            query = query.filter(SupplyRequirement.forecast_id == forecast_id)
        if supply_id is not None:
            query = query.filter(SupplyRequirement.supply_id == supply_id)
        if disease_type:
            query = query.filter(SupplyRequirement.disease_type == disease_type)
        if start_date:
            query = query.filter(SupplyRequirement.requirement_date >= start_date)
        if end_date:
            query = query.filter(SupplyRequirement.requirement_date <= end_date)

        requirements = query.order_by(
            SupplyRequirement.requirement_date
        ).offset(offset).limit(limit).all()

        return [self._enrich_requirement(req) for req in requirements]

    def get_requirements_for_forecast(self, forecast_id: int) -> List[Dict]:
        """Return all supply requirements linked to a specific forecast."""
        forecast = self.db.query(DiseaseForecast).filter(
            DiseaseForecast.id == forecast_id
        ).first()
        if not forecast:
            return []

        requirements = self.db.query(SupplyRequirement).options(
            joinedload(SupplyRequirement.supply)
        ).filter(
            SupplyRequirement.forecast_id == forecast_id
        ).order_by(SupplyRequirement.requirement_date).all()

        return [self._enrich_requirement(req) for req in requirements]

    def get_summary(
        self,
        disease_type: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict:
        """Aggregate supply requirements by supply type.

        Returns total required quantities per supply, compared against current
        stock levels.
        """
        query = self.db.query(SupplyRequirement).options(
            joinedload(SupplyRequirement.supply)
        )

        if disease_type:
            query = query.filter(SupplyRequirement.disease_type == disease_type)
        if start_date:
            query = query.filter(SupplyRequirement.requirement_date >= start_date)
        if end_date:
            query = query.filter(SupplyRequirement.requirement_date <= end_date)
        if category:
            query = query.join(MedicalSupply).filter(MedicalSupply.category == category)

        requirements = query.all()

        # Aggregate by supply_id
        supply_data: Dict[int, Dict] = {}
        for req in requirements:
            sid = req.supply_id
            if sid not in supply_data:
                supply_name = req.supply.name if req.supply else "Unknown"
                supply_category = req.supply.category if req.supply else None
                supply_unit = req.supply.unit if req.supply else None
                supply_data[sid] = {
                    "supply_id": sid,
                    "supply_name": supply_name,
                    "supply_category": supply_category,
                    "supply_unit": supply_unit,
                    "total_required_quantity": 0,
                    "disease_types": set(),
                    "requirement_count": 0,
                }
            supply_data[sid]["total_required_quantity"] += req.required_quantity
            if req.disease_type:
                supply_data[sid]["disease_types"].add(req.disease_type)
            supply_data[sid]["requirement_count"] += 1

        # Enrich with current stock
        items = []
        supplies_with_shortage = 0
        for sid, data in supply_data.items():
            current_stock = self._get_current_stock(sid)
            total_required = data["total_required_quantity"]
            shortage_amount: Optional[int] = None
            if current_stock is not None:
                shortage_amount = max(0, total_required - current_stock)
                if shortage_amount > 0:
                    supplies_with_shortage += 1

            items.append({
                "supply_id": sid,
                "supply_name": data["supply_name"],
                "supply_category": data["supply_category"],
                "supply_unit": data["supply_unit"],
                "total_required_quantity": total_required,
                "current_stock": current_stock,
                "shortage_amount": shortage_amount,
                "disease_types": list(data["disease_types"]),
                "requirement_count": data["requirement_count"],
            })

        # Sort by shortage descending so critical items appear first
        items.sort(key=lambda x: x["shortage_amount"] or 0, reverse=True)

        return {
            "total_supplies": len(items),
            "supplies_with_shortage": supplies_with_shortage,
            "items": items,
        }

    # ------------------------------------------------------------------
    # Auto-generation (called after forecast creation)
    # ------------------------------------------------------------------

    def generate_requirements_for_forecast(
        self, forecast_id: int
    ) -> List[SupplyRequirement]:
        """Auto-calculate and persist supply requirements for a forecast.

        This integrates ConversionModule with the forecast result.

        Args:
            forecast_id: ID of the DiseaseForecast record that was just created.

        Returns:
            List of persisted SupplyRequirement objects.
        """
        logger.info(f"Auto-generating supply requirements for forecast_id={forecast_id}")

        # Load all forecasts with the same created_at group — but since we
        # store one record per forecast_date, fetch by the latest batch that
        # shares the same forecast_period and disease type via the ID group.
        # The simplest approach: find all rows with forecast_id in the
        # supply_requirements table for this forecast or, if none, generate fresh.

        # Fetch the parent forecast record
        forecast = self.db.query(DiseaseForecast).filter(
            DiseaseForecast.id == forecast_id
        ).first()
        if not forecast:
            logger.error(f"Forecast {forecast_id} not found")
            return []

        # Gather all forecasts from the same generation run:
        # They share disease_type and forecast_period_days, created very close together.
        # We use a simpler heuristic: get all forecasts for the same disease_type
        # that were created at the same time (within 1 second) — or just this single
        # record if it was a single-date forecast.
        from sqlalchemy import and_
        from datetime import timedelta

        if forecast.created_at:
            window_start = forecast.created_at - timedelta(seconds=5)
            window_end = forecast.created_at + timedelta(seconds=5)
            forecast_batch = self.db.query(DiseaseForecast).filter(
                and_(
                    DiseaseForecast.icd_code == forecast.icd_code,
                    DiseaseForecast.created_at >= window_start,
                    DiseaseForecast.created_at <= window_end,
                )
            ).all()
        else:
            forecast_batch = [forecast]

        if not forecast_batch:
            forecast_batch = [forecast]

        logger.info(
            f"Found {len(forecast_batch)} forecast records in batch for "
            f"icd_code={forecast.icd_code}"
        )

        # Delete any previously generated requirements for these forecasts
        # to avoid duplicates on re-generation
        forecast_ids_in_batch = [f.id for f in forecast_batch]
        self.db.query(SupplyRequirement).filter(
            SupplyRequirement.forecast_id.in_(forecast_ids_in_batch)
        ).delete(synchronize_session="fetch")
        self.db.flush()

        # ⭐ Tránh đếm trùng theo khu vực chồng lấn: với mỗi (icd, tháng), chỉ
        # giữ requirements của forecast MỚI NHẤT. Xoá requirements của mọi
        # forecast khác cùng (icd, forecast_month) — vì "Toàn thành phố",
        # "TP. HCM", "Quận 1" chồng lấn nhau, cộng dồn sẽ sai.
        from sqlalchemy import extract as _extract
        stale_forecast_ids = []
        for fc in forecast_batch:
            others = (
                self.db.query(DiseaseForecast.id)
                .filter(
                    DiseaseForecast.icd_code == fc.icd_code,
                    DiseaseForecast.forecast_month == fc.forecast_month,
                    DiseaseForecast.id != fc.id,
                )
                .all()
            )
            stale_forecast_ids.extend([o[0] for o in others])
        if stale_forecast_ids:
            self.db.query(SupplyRequirement).filter(
                SupplyRequirement.forecast_id.in_(stale_forecast_ids)
            ).delete(synchronize_session="fetch")
            self.db.flush()
            logger.info(
                "Cleared requirements of %d overlapping-region forecasts "
                "to avoid double counting", len(stale_forecast_ids),
            )

        # Compute requirements for each forecast record in the batch.
        # Priority order:
        #   0) ⭐ severity_rate × disease_supply_norm (logic chuẩn mục 4-7).
        #      Phân bổ ca theo Nhẹ/TB/Nặng × định mức × (1 + 15% dự phòng).
        #   1) Ratio thực từ case_supply_usage (lịch sử ca bệnh đã import từ CSV).
        #      Chỉ dùng các thuốc đã được dùng cho ĐÚNG disease_type này — tránh
        #      đề xuất thuốc của bệnh khác.
        #   2) Fallback ConversionModule (conversion_ratios cấu hình thủ công).
        from app.models.severity_rate import SeverityRate
        from app.models.disease_supply_norm import DiseaseSupplyNorm

        DEFAULT_BUFFER_RATE = 15.0
        created_requirements: List[SupplyRequirement] = []

        for fc in forecast_batch:
            # ── Path 0: severity_rate × disease_supply_norm (chuẩn mới) ──
            severity = (
                self.db.query(SeverityRate)
                .filter(SeverityRate.icd_code == fc.icd_code)
                .first()
            )
            norms = (
                self.db.query(DiseaseSupplyNorm, MedicalSupply)
                .join(MedicalSupply, MedicalSupply.id == DiseaseSupplyNorm.supply_id)
                .filter(DiseaseSupplyNorm.icd_code == fc.icd_code)
                .all()
            )

            if severity and norms:
                logger.info(
                    f"Using severity_rate × disease_supply_norm for forecast id={fc.id} "
                    f"({fc.icd_code}, predicted={fc.predicted_cases})"
                )
                # Phân bổ ca theo Nhẹ/TB/Nặng (mục 5.1)
                mild_cases = round(fc.predicted_cases * float(severity.mild_rate) / 100)
                moderate_cases = round(fc.predicted_cases * float(severity.moderate_rate) / 100)
                severe_cases = fc.predicted_cases - mild_cases - moderate_cases
                if severe_cases < 0:
                    severe_cases = 0

                # Group norms by supply_id
                supply_map: Dict[int, Dict[str, int]] = {}
                for norm, supply in norms:
                    sid = supply.id
                    if sid not in supply_map:
                        supply_map[sid] = {"mild": 0, "moderate": 0, "severe": 0}
                    if norm.severity in ("mild", "moderate", "severe"):
                        supply_map[sid][norm.severity] = norm.quantity_per_case

                for sid, qty_by_severity in supply_map.items():
                    # Nhu cầu trước dự phòng = Σ(ca × định mức) (mục 6)
                    need_before = (
                        mild_cases * qty_by_severity["mild"]
                        + moderate_cases * qty_by_severity["moderate"]
                        + severe_cases * qty_by_severity["severe"]
                    )
                    if need_before <= 0:
                        continue
                    # Nhu cầu cuối = need_before × (1 + buffer%)
                    final_need = round(need_before * (1 + DEFAULT_BUFFER_RATE / 100))
                    if final_need <= 0:
                        continue
                    req = SupplyRequirement(
                        forecast_id=fc.id,
                        supply_id=sid,
                        required_quantity=final_need,
                        requirement_date=fc.forecast_date,
                        disease_type=fc.icd_code,
                    )
                    self.db.add(req)
                    created_requirements.append(req)
                continue

            # ── Path 1: actual usage history (legacy fallback) ──
            actual_supplies = self._compute_actual_ratios(
                disease_type=fc.icd_code,
                location=fc.location,
            )

            if actual_supplies:
                # Có lịch sử thật → dùng ratio thực (per_case = total_qty / total_cases)
                logger.info(
                    f"Using actual usage history for forecast id={fc.id} "
                    f"({len(actual_supplies)} supplies)"
                )
                for s in actual_supplies:
                    required_qty = int(round(fc.predicted_cases * s["ratio"]))
                    if required_qty <= 0:
                        continue
                    req = SupplyRequirement(
                        forecast_id=fc.id,
                        supply_id=s["supply_id"],
                        required_quantity=required_qty,
                        requirement_date=fc.forecast_date,
                        disease_type=fc.icd_code,
                    )
                    self.db.add(req)
                    created_requirements.append(req)
                continue

            # Fallback — không có usage history → dùng ConversionModule
            logger.info(
                f"No actual usage for {fc.icd_code}, falling back to "
                f"conversion_ratios"
            )
            conversion_module = ConversionModule(self.db)
            try:
                conversion_module.load_conversion_ratios()
            except Exception as e:
                logger.warning(
                    f"Could not load conversion ratios from DB: {e}. "
                    "Using default ratios."
                )

            import pandas as pd
            requirements = conversion_module.calculate_requirements(
                disease_type=fc.icd_code,
                predicted_cases=fc.predicted_cases,
                forecast_date=pd.Timestamp(fc.forecast_date),
            )

            for req_data in requirements:
                supply_id = req_data.get("supply_id")
                if supply_id is None and req_data.get("supply_name"):
                    supply = self.db.query(MedicalSupply).filter(
                        MedicalSupply.ten_hoat_chat == req_data["supply_name"]
                    ).first()
                    supply_id = supply.id if supply else None
                if supply_id is None:
                    logger.warning(
                        f"Skipping requirement for supply "
                        f"'{req_data.get('supply_name')}': not found"
                    )
                    continue
                req = SupplyRequirement(
                    forecast_id=fc.id,
                    supply_id=supply_id,
                    required_quantity=req_data["required_quantity"],
                    requirement_date=req_data["forecast_date"],
                    disease_type=fc.icd_code,
                )
                self.db.add(req)
                created_requirements.append(req)

        try:
            self.db.commit()
            for req in created_requirements:
                self.db.refresh(req)
            logger.info(
                f"Persisted {len(created_requirements)} supply requirements "
                f"for forecast batch (root id={forecast_id})"
            )
        except Exception as e:
            logger.error(f"Error persisting supply requirements: {e}")
            self.db.rollback()
            raise

        return created_requirements

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_actual_ratios(
        self,
        disease_type: str,
        location: Optional[str] = None,
    ) -> List[Dict]:
        """Tính ratio thực từ lịch sử case_supply_usage cho 1 disease_type.

        Logic:
        - Tổng hợp tất cả ca bệnh đã import (case_count) cho disease_type
        - JOIN với case_supply_usage để lấy số lượng thực tế từng supply đã dùng
        - ratio_per_case = SUM(usage.quantity) / SUM(case.case_count)
        - location filter: nếu có, ưu tiên đúng tỉnh; nếu không có usage cho tỉnh
          đó, nới lỏng dùng toàn quốc.

        Trả về list dict: [{supply_id, supply_name, ratio, total_qty, total_cases}, ...]
        Nếu không có lịch sử → list rỗng → caller fallback sang conversion_ratios.
        """
        from app.models.disease_case import DiseaseCase
        from app.models.case_supply_usage import CaseSupplyUsage

        def _query(loc_filter: Optional[str]) -> List[Dict]:
            from app.models.case_supply_usage import CaseSupplyUsage as _CSU

            # Bước 1: Chỉ lấy các CASE có ghi nhận supply usage (DISTINCT case_id từ
            # case_supply_usage). Bỏ qua các ca chỉ có case_count, không có chi tiết
            # thuốc — vì chia cả các ca này sẽ làm ratio bị pha loãng.
            cases_q = (
                self.db.query(DiseaseCase.id, DiseaseCase.case_count)
                .filter(DiseaseCase.icd_code == disease_type)
                .filter(DiseaseCase.id.in_(
                    self.db.query(_CSU.case_id).distinct()
                ))
            )
            if loc_filter:
                cases_q = cases_q.filter(DiseaseCase.location == loc_filter)
            cases = cases_q.all()
            if not cases:
                return []
            case_ids = [c[0] for c in cases]
            total_cases = sum(c[1] or 0 for c in cases)
            if total_cases == 0:
                return []

            # Bước 2: Aggregate usage per supply trong đúng các case đó
            usages = (
                self.db.query(
                    CaseSupplyUsage.supply_id,
                    func.sum(CaseSupplyUsage.quantity).label("total_qty"),
                )
                .filter(CaseSupplyUsage.case_id.in_(case_ids))
                .group_by(CaseSupplyUsage.supply_id)
                .all()
            )
            if not usages:
                return []

            results: List[Dict] = []
            for supply_id, total_qty in usages:
                total_qty = int(total_qty or 0)
                if total_qty <= 0:
                    continue
                supply = self.db.query(MedicalSupply).filter(
                    MedicalSupply.id == supply_id
                ).first()
                if not supply:
                    continue
                results.append({
                    "supply_id": supply_id,
                    "supply_name": supply.name,
                    "ratio": total_qty / total_cases,
                    "total_qty": total_qty,
                    "total_cases": total_cases,
                })
            return results

        # Ưu tiên đúng tỉnh nếu có
        if location:
            data = _query(location)
            if data:
                return data
        # Fallback toàn quốc cho cùng disease
        return _query(None)

    def _enrich_requirement(self, req: SupplyRequirement) -> Dict:
        """Build a dict from a SupplyRequirement ORM object, including stock info."""
        supply_name = req.supply.name if req.supply else "Unknown"
        current_stock = self._get_current_stock(req.supply_id)
        shortage_amount: Optional[int] = None
        if current_stock is not None:
            shortage_amount = max(0, req.required_quantity - current_stock)

        return {
            "id": req.id,
            "forecast_id": req.forecast_id,
            "supply_id": req.supply_id,
            "supply_name": supply_name,
            "required_quantity": req.required_quantity,
            "requirement_date": req.requirement_date,
            "disease_type": req.disease_type,
            "current_stock": current_stock,
            "shortage_amount": shortage_amount,
            "created_at": req.created_at,
        }
