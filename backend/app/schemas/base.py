"""Base Pydantic schemas shared across the application."""
from datetime import date, datetime
from enum import Enum
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    ADMINISTRATOR = "Administrator"
    PHARMACIST = "Pharmacist"
    INVENTORY_MANAGER = "Inventory_Manager"


class DiseaseType(str, Enum):
    """4 bệnh hô hấp đơn giản dùng để dự báo nhu cầu kho."""
    J20 = "J20"  # Viêm phế quản cấp
    J06 = "J06"  # Nhiễm trùng đường hô hấp trên cấp
    J02 = "J02"  # Viêm họng cấp
    J01 = "J01"  # Viêm xoang cấp


class SeverityLevel(str, Enum):
    """Mức độ nặng của bệnh."""
    MILD = "mild"  # Nhẹ
    MODERATE = "moderate"  # Trung bình
    SEVERE = "severe"  # Nặng


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


class LogLevel(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


# ── Shared config ─────────────────────────────────────────────────────────────

class ORMBase(BaseModel):
    """Base schema that enables ORM mode (from_attributes) for all response models."""
    model_config = ConfigDict(from_attributes=True)


# ── Pagination ────────────────────────────────────────────────────────────────

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    total: int
    page: int
    page_size: int
    items: List[T]


# ── Auth schemas ──────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class TokenData(BaseModel):
    username: Optional[str] = None


# ── User schemas ──────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(ORMBase, UserBase):
    id: int
    is_active: bool
    created_at: datetime


class UserLogin(BaseModel):
    username: str
    password: str


# ── Medical Supply schemas ────────────────────────────────────────────────────

class MedicalSupplyBase(BaseModel):
    supply_code: str = Field(..., description="Mã hệ thống nội bộ (VT001-VT015)")
    drug_code: str = Field(..., description="Mã từ cột DrugCode trong dữ liệu lịch sử")
    ten_hoat_chat: str = Field(..., description="Tên hoạt chất từ cột TenHoatChat")
    unit: str = Field(..., description="Đơn vị tính (Viên, Gói, Lọ, Chai, Cái, Ống)")
    group_name: str = Field(..., description="Nhóm thuốc/vật tư")
    category: Optional[str] = None
    unit_price: Optional[float] = None
    minimum_order_quantity: Optional[int] = None
    lead_time_days: Optional[int] = None
    storage_capacity: Optional[int] = None
    description: Optional[str] = None


class MedicalSupplyCreate(MedicalSupplyBase):
    pass


class MedicalSupplyUpdate(BaseModel):
    supply_code: Optional[str] = None
    drug_code: Optional[str] = None
    ten_hoat_chat: Optional[str] = None
    unit: Optional[str] = None
    group_name: Optional[str] = None
    category: Optional[str] = None
    unit_price: Optional[float] = None
    minimum_order_quantity: Optional[int] = None
    lead_time_days: Optional[int] = None
    storage_capacity: Optional[int] = None
    description: Optional[str] = None


class MedicalSupplyResponse(ORMBase, MedicalSupplyBase):
    id: int
    created_at: datetime


# ── Inventory schemas ─────────────────────────────────────────────────────────

class InventoryBase(BaseModel):
    supply_id: int
    current_stock: int = Field(..., ge=0)
    safety_stock: int = Field(..., ge=0)
    location: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None


class InventoryUpdate(BaseModel):
    current_stock: Optional[int] = Field(None, ge=0)
    safety_stock: Optional[int] = Field(None, ge=0)
    location: Optional[str] = None


class InventoryResponse(ORMBase, InventoryBase):
    id: int
    last_updated: datetime
    supply: Optional[MedicalSupplyResponse] = None


# ── Environmental Data schemas ────────────────────────────────────────────────

class EnvironmentalDataBase(BaseModel):
    recorded_at: datetime
    location: str = Field(..., min_length=1)
    # Spec 4.4 — validate range
    temperature: Optional[float] = Field(None, ge=10, le=45, description="°C, 10-45")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="%, 0-100")
    rainfall: Optional[float] = Field(None, ge=0, description="mm, ≥ 0")
    air_quality_index: Optional[int] = Field(None, ge=0, description="≥ 0")
    pm25: Optional[float] = Field(None, ge=0, description="µg/m³, ≥ 0")
    data_source: Optional[str] = None


class EnvironmentalDataCreate(EnvironmentalDataBase):
    pass


class EnvironmentalDataUpdate(BaseModel):
    """Cập nhật một phần — tất cả field optional, vẫn validate range."""
    recorded_at: Optional[datetime] = None
    location: Optional[str] = Field(None, min_length=1)
    temperature: Optional[float] = Field(None, ge=10, le=45)
    humidity: Optional[float] = Field(None, ge=0, le=100)
    rainfall: Optional[float] = Field(None, ge=0)
    air_quality_index: Optional[int] = Field(None, ge=0)
    pm25: Optional[float] = Field(None, ge=0)
    data_source: Optional[str] = None


class EnvironmentalDataResponse(ORMBase, EnvironmentalDataBase):
    id: int
    created_at: datetime


# ── Disease Case schemas ──────────────────────────────────────────────────────

class DiseaseCaseBase(BaseModel):
    recorded_at: datetime
    icd_code: str = Field(..., min_length=1, description="Mã ICD: J20, J06, J02, J01")
    disease_name: str = Field(..., min_length=1, description="Tên bệnh")
    disease_type: Optional[str] = Field(None, description="Loại bệnh (respiratory)")
    case_count: int = Field(..., ge=0)
    location: str = Field(..., min_length=1)
    severity: Optional[str] = Field(None, description="mild, moderate, severe")
    length_of_stay: Optional[int] = Field(None, ge=0, description="Số ngày nằm viện")
    sub_icd_count: Optional[int] = Field(None, ge=0, description="Số bệnh kèm theo")
    data_source: Optional[str] = None
    note: Optional[str] = None


class DiseaseCaseCreate(DiseaseCaseBase):
    pass


class DiseaseCaseUpdate(BaseModel):
    recorded_at: Optional[datetime] = None
    icd_code: Optional[str] = None
    disease_name: Optional[str] = None
    disease_type: Optional[str] = None
    case_count: Optional[int] = Field(None, ge=0)
    location: Optional[str] = None
    severity: Optional[str] = None
    length_of_stay: Optional[int] = Field(None, ge=0)
    sub_icd_count: Optional[int] = Field(None, ge=0)
    note: Optional[str] = None


class DiseaseCaseResponse(ORMBase, DiseaseCaseBase):
    id: int
    created_by: Optional[str] = None
    created_at: datetime


# ── Forecast schemas ──────────────────────────────────────────────────────────

class ForecastRequest(BaseModel):
    disease_type: DiseaseType
    forecast_period_days: int = Field(..., ge=7, le=30)
    location: Optional[str] = None


class DiseaseForecastResponse(ORMBase):
    id: int
    forecast_date: date
    disease_type: str
    predicted_cases: int
    confidence_lower: Optional[int] = None
    confidence_upper: Optional[int] = None
    model_used: Optional[str] = None
    model_accuracy_mae: Optional[float] = None
    model_accuracy_rmse: Optional[float] = None
    model_accuracy_mape: Optional[float] = None
    forecast_period_days: Optional[int] = None
    created_at: datetime


# ── Supply Requirement schemas ────────────────────────────────────────────────

class SupplyRequirementResponse(ORMBase):
    id: int
    forecast_id: Optional[int] = None
    supply_id: int
    supply_name: Optional[str] = None
    required_quantity: int
    requirement_date: date
    disease_type: Optional[str] = None
    current_stock: Optional[int] = None
    shortage_amount: Optional[int] = None
    created_at: Optional[datetime] = None


class SupplyRequirementSummaryItem(BaseModel):
    """Summary of requirements aggregated by supply type."""
    supply_id: int
    supply_name: str
    supply_category: Optional[str] = None
    supply_unit: Optional[str] = None
    total_required_quantity: int
    current_stock: Optional[int] = None
    shortage_amount: Optional[int] = None
    disease_types: List[str] = []
    requirement_count: int


class SupplyRequirementSummaryResponse(BaseModel):
    """Response for supply requirement summary endpoint."""
    total_supplies: int
    supplies_with_shortage: int
    items: List[SupplyRequirementSummaryItem]


# ── Alert schemas ─────────────────────────────────────────────────────────────

class AlertResponse(ORMBase):
    id: int
    supply_id: int
    supply_name: Optional[str] = None
    alert_type: str
    severity: AlertSeverity
    current_stock: Optional[int] = None
    required_stock: Optional[int] = None
    shortage_date: Optional[date] = None
    message: Optional[str] = None
    is_resolved: bool
    resolved_at: Optional[datetime] = None
    created_at: datetime


# ── Procurement Plan schemas ──────────────────────────────────────────────────

class ProcurementPlanBase(BaseModel):
    supply_id: int
    order_quantity: int = Field(..., gt=0)
    order_date: date
    expected_delivery_date: Optional[date] = None
    estimated_cost: Optional[float] = None
    priority: Optional[str] = None
    notes: Optional[str] = None


class ProcurementPlanCreate(ProcurementPlanBase):
    pass


class ProcurementPlanUpdate(BaseModel):
    order_quantity: Optional[int] = Field(None, gt=0)
    order_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None
    estimated_cost: Optional[float] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class ProcurementPlanResponse(ORMBase, ProcurementPlanBase):
    id: int
    supply_name: Optional[str] = None
    status: str
    created_at: datetime


class ProcurementGenerateRequest(BaseModel):
    forecast_days: int = Field(30, ge=7, le=90, description="Days ahead to plan for")


class ProcurementGenerateResponse(BaseModel):
    message: str
    plans_generated: int
    critical_plans: int
    high_plans: int
    normal_plans: int
    plans: List["ProcurementPlanResponse"]


# ── Dashboard schemas ─────────────────────────────────────────────────────────

class DashboardOverview(BaseModel):
    total_supplies: int
    total_value: float
    high_risk_shortages: int
    predicted_demand_30d: int
    disease_outbreaks: int
    supply_risk_percentage: float
    safe_stock_items: int
    low_stock_items: int
    critical_risk_items: int


class SupplyDemandPoint(BaseModel):
    date: date
    actual: Optional[int] = None
    forecast: Optional[int] = None


class SupplyDemandForecast(BaseModel):
    supply_id: int
    supply_name: str
    data_points: List[SupplyDemandPoint]


# ── System Config schemas ─────────────────────────────────────────────────────

class SystemConfigResponse(ORMBase):
    id: int
    config_key: str
    config_value: str
    description: Optional[str] = None
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None


class SystemConfigUpdate(BaseModel):
    config_value: str = Field(..., min_length=1)
    description: Optional[str] = None


# ── Conversion Ratio schemas ──────────────────────────────────────────────────

class ConversionRatioResponse(ORMBase):
    id: int
    disease_type: str
    supply_id: int
    supply_name: Optional[str] = None
    ratio: float
    unit: Optional[str] = None
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None


class ConversionRatioUpdate(BaseModel):
    disease_type: str = Field(..., description="Mã ICD bệnh (J20, J06, J02, J01)")
    supply_id: int = Field(..., gt=0, description="ID of the medical supply")
    ratio: float = Field(..., gt=0, description="Conversion ratio (units per case)")
    unit: Optional[str] = None


class ConversionRatiosBulkUpdate(BaseModel):
    ratios: List[ConversionRatioUpdate]


# ── Threshold schemas ─────────────────────────────────────────────────────────

class ThresholdConfig(BaseModel):
    """Shortage threshold configuration (days until projected shortage)."""
    critical_days: int = Field(..., ge=1, description="Days threshold for critical severity")
    high_days: int = Field(..., ge=1, description="Days threshold for high severity")
    medium_days: int = Field(..., ge=1, description="Days threshold for medium severity")


class ThresholdResponse(BaseModel):
    critical_days: int
    high_days: int
    medium_days: int


# ── Audit Log schemas ─────────────────────────────────────────────────────────

class AuditLogResponse(ORMBase):
    """Schema for a single audit log entry."""
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None  # enriched from user relationship
    action: str
    table_name: Optional[str] = None
    record_id: Optional[int] = None
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""
    total: int
    page: int
    page_size: int
    items: List[AuditLogResponse]


# ── System Log schemas ────────────────────────────────────────────────────────

class SystemLogResponse(ORMBase):
    """Schema for a single system log entry."""
    id: int
    log_level: str
    module_name: Optional[str] = None
    message: str
    stack_trace: Optional[str] = None
    created_at: datetime


class SystemLogListResponse(BaseModel):
    """Paginated list of system log entries."""
    total: int
    page: int
    page_size: int
    items: List[SystemLogResponse]
