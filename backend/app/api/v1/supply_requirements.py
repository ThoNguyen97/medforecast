"""GET /api/v1/supply-requirements/summary — tóm tắt thiếu hụt cho trang Báo cáo.

Chỉ còn một endpoint. Ba endpoint cũ (list, /forecast/{id}, /generate/{id})
thuộc "đường thứ ba" tính nhu cầu qua bảng supply_requirements — đã archive
13/09/2026 (_archive/duong_thu_ba/), giao diện không còn gọi.
"""
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.base import SupplyRequirementSummaryResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["supply-requirements"])


@router.get("/summary", response_model=SupplyRequirementSummaryResponse)
async def get_supply_requirements_summary(
    disease_type: Optional[str] = Query(None, description="Không còn dùng — engine DSS hợp nhất không tách thuốc theo bệnh; giữ tham số để tương thích API cũ."),
    category: Optional[str] = Query(None, description="Filter by supply category"),
    start_date: Optional[date] = Query(None, description="Không còn dùng — đây là ảnh chụp hiện tại, không phải tổng theo khoảng ngày."),
    end_date: Optional[date] = Query(None, description="Không còn dùng — xem start_date."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Một dòng mỗi mã: nhu cầu dự báo `horizon_days` ngày tới, tồn hữu dụng
    FEFO và thiếu hụt = max(0, nhu cầu − tồn). Đi đúng chuỗi
    dss_dashboard.tang1_tang2 → dss_alerts.alert_rows nên không lệch trang
    Cảnh báo. `disease_types`/`requirement_count` giữ để hợp đồng cũ không vỡ.
    """

    try:
        from app.models.medical_supply import MedicalSupply
        from app.services import dss_dashboard, dss_alerts

        _, _, nhu_cau, _ = dss_dashboard.tang1_tang2(db)
        al = dss_alerts.alert_rows(db, demand=nhu_cau, only_focus=False)
        rows = list(al.get("rows") or [])
        if category:
            rows = [r for r in rows if (r.get("danh_muc") or None) == category]

        supply_ids = {
            r.supply_code: r.id
            for r in db.query(MedicalSupply.supply_code, MedicalSupply.id)
            .filter(MedicalSupply.supply_code.in_([r["supply_code"] for r in rows]))
            .all()
        } if rows else {}

        items = []
        supplies_with_shortage = 0
        for r in rows:
            shortage = r.get("delta_need")
            if shortage is not None and shortage > 0:
                supplies_with_shortage += 1
            items.append({
                "supply_id": supply_ids.get(r["supply_code"], 0),
                "supply_name": r["ten"] or r["supply_code"],
                "supply_category": r.get("danh_muc"),
                "supply_unit": r["don_vi"],
                "total_required_quantity": int(round(r["d_forecast"])) if r.get("d_forecast") is not None else 0,
                "current_stock": int(round(r["s_usable"])) if r.get("s_usable") is not None else None,
                "shortage_amount": int(round(shortage)) if shortage is not None else None,
                "disease_types": [],
                "requirement_count": 1 if r.get("d_forecast") is not None else 0,
            })

        return {
            "total_supplies": len(items),
            "supplies_with_shortage": supplies_with_shortage,
            "items": items,
        }

    except Exception as exc:
        logger.exception("Tóm tắt thiếu hụt lỗi")
        raise HTTPException(status_code=500, detail=f"Không lấy được tóm tắt thiếu hụt: {exc}")


