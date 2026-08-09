"""API đề xuất nhập kho từ dự báo phân cấp (có mức an toàn + lead time).

  GET /api/v1/supply-plan/{block}?method=top_down_dynamic
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.supply_planning_service import SupplyPlanningService
from app.services.hierarchical_forecast_service import METHODS

router = APIRouter()


@router.get("/{block}")
def supply_plan(block: str,
                method: str = Query("top_down_dynamic", description=f"một trong {METHODS}"),
                db: Session = Depends(get_db),
                _user: User = Depends(get_current_user)):
    try:
        return SupplyPlanningService(db).plan(block, method=method)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503,
                            detail=f"Chưa sẵn sàng (có thể chưa đồng bộ / thiếu cấu hình): {e}")
