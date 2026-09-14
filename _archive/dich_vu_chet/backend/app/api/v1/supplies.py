"""Medical Supplies API endpoints."""
import logging
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.schemas.base import MedicalSupplyCreate, MedicalSupplyUpdate, MedicalSupplyResponse
from app.services.medical_supply_service import MedicalSupplyService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/", response_model=List[MedicalSupplyResponse])
def list_supplies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    List all medical supplies.
    
    Supports filtering by category and searching by name.
    All authenticated users can access this endpoint.
    """
    supply_service = MedicalSupplyService(db)
    supplies = supply_service.get_supplies(
        skip=skip,
        limit=limit,
        category=category,
        search=search
    )
    return supplies


@router.post("/", response_model=MedicalSupplyResponse, status_code=status.HTTP_201_CREATED)
def create_supply(
    supply_data: MedicalSupplyCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
) -> Any:
    """
    Create a new medical supply.
    
    Only administrators can create medical supplies.
    """
    supply_service = MedicalSupplyService(db)
    client_ip = get_client_ip(request)
    
    try:
        new_supply = supply_service.create_supply(
            supply_data=supply_data,
            created_by_user_id=current_user.id,
            ip_address=client_ip
        )
        return new_supply
    except Exception as e:
        logger.error(f"Failed to create medical supply: {str(e)}")
        raise


@router.get("/categories", response_model=List[str])
def get_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get list of unique supply categories.
    
    All authenticated users can access this endpoint.
    """
    supply_service = MedicalSupplyService(db)
    categories = supply_service.get_categories()
    return categories


@router.get("/{supply_id}", response_model=MedicalSupplyResponse)
def get_supply(
    supply_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get medical supply by ID.
    
    All authenticated users can access this endpoint.
    """
    supply_service = MedicalSupplyService(db)
    supply = supply_service.get_supply_by_id(supply_id)
    return supply


@router.put("/{supply_id}", response_model=MedicalSupplyResponse)
def update_supply(
    supply_id: int,
    supply_data: MedicalSupplyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
) -> Any:
    """
    Update medical supply information.
    
    Only administrators can update medical supplies.
    """
    supply_service = MedicalSupplyService(db)
    client_ip = get_client_ip(request)
    
    try:
        updated_supply = supply_service.update_supply(
            supply_id=supply_id,
            supply_data=supply_data,
            updated_by_user_id=current_user.id,
            ip_address=client_ip
        )
        return updated_supply
    except Exception as e:
        logger.error(f"Failed to update medical supply {supply_id}: {str(e)}")
        raise


@router.delete("/{supply_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supply(
    supply_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Delete medical supply.
    
    Only administrators can delete medical supplies.
    """
    supply_service = MedicalSupplyService(db)
    client_ip = get_client_ip(request)
    
    try:
        supply_service.delete_supply(
            supply_id=supply_id,
            deleted_by_user_id=current_user.id,
            ip_address=client_ip
        )
    except Exception as e:
        logger.error(f"Failed to delete medical supply {supply_id}: {str(e)}")
        raise
