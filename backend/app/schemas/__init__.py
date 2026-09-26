"""Schema Pydantic cho kiểm tra dữ liệu request/response."""
from app.schemas.base import (
    # Enums
    UserRole,
    # Lớp nền
    ORMBase,
    PaginatedResponse,
    # Auth
    Token,
    # Người dùng
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    # Thuốc/vật tư
    MedicalSupplyBase,
    MedicalSupplyResponse,
    # Tồn kho
    InventoryBase,
    InventoryUpdate,
    InventoryResponse,
    # Dữ liệu môi trường
    EnvironmentalDataBase,
    EnvironmentalDataCreate,
    EnvironmentalDataResponse,
    # Ca bệnh
    DiseaseCaseBase,
    DiseaseCaseCreate,
    DiseaseCaseResponse,
    # Dự báo
    # Dashboard
)

__all__ = [
    "UserRole",
    "ORMBase",
    "PaginatedResponse",
    "Token",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "MedicalSupplyBase",
    "MedicalSupplyResponse",
    "InventoryBase",
    "InventoryUpdate",
    "InventoryResponse",
    "EnvironmentalDataBase",
    "EnvironmentalDataCreate",
    "EnvironmentalDataResponse",
    "DiseaseCaseBase",
    "DiseaseCaseCreate",
    "DiseaseCaseResponse",
]
