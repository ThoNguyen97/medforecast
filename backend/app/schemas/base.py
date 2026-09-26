"""Schema Pydantic dùng chung cho toàn ứng dụng."""
from datetime import date, datetime
from enum import Enum
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    ADMINISTRATOR = "Administrator"
    PHARMACIST = "Pharmacist"
    INVENTORY_MANAGER = "Inventory_Manager"


# ── Cấu hình chung ─────────────────────────────────────────────────────────────

class ORMBase(BaseModel):
    """Lớp nền bật from_attributes (đọc từ ORM) cho các schema response."""
    model_config = ConfigDict(from_attributes=True)


# ── Pagination ────────────────────────────────────────────────────────────────

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Khung response phân trang tổng quát."""
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
    group_name: str = Field(..., description="Nhóm thuốc")
    category: Optional[str] = None
    unit_price: Optional[float] = None
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
    # Tồn âm có thật trong dữ liệu HIS (xuất trước, nhập bù sau). ge=0 ở
    # InventoryBase chỉ để chặn nhập sai; ở chiều trả ra phải bỏ ràng buộc, nếu
    # không một dòng âm gây ResponseValidationError (500) cho cả danh sách.
    current_stock: int
    safety_stock: int


# ── Environmental Data schemas ────────────────────────────────────────────────

class EnvironmentalDataBase(BaseModel):
    recorded_at: datetime
    location: str = Field(..., min_length=1)
    # Kiểm tra miền giá trị hợp lệ
    temperature: Optional[float] = Field(None, ge=10, le=45, description="°C, 10-45")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="%, 0-100")
    rainfall: Optional[float] = Field(None, ge=0, description="mm, ≥ 0")
    air_quality_index: Optional[int] = Field(None, ge=0, description="≥ 0")
    pm25: Optional[float] = Field(None, ge=0, description="µg/m³, ≥ 0")
    data_source: Optional[str] = None


class EnvironmentalDataCreate(EnvironmentalDataBase):
    pass


class EnvironmentalDataUpdate(BaseModel):
    """Cập nhật một phần: mọi trường tuỳ chọn, vẫn kiểm tra miền giá trị."""
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
    icd_code: str = Field(..., min_length=1, description="Mã ICD 3 ký tự thuộc ba nhóm J00-J06, J09-J18, J20-J22")
    disease_name: str = Field(..., min_length=1, description="Tên bệnh")
    disease_group: Optional[str] = Field(None, description="Nhóm ICD: J00-J06 / J09-J18 / J20-J22")
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


# ── Supply Requirement schemas ────────────────────────────────────────────────

class SupplyRequirementSummaryItem(BaseModel):
    """Tổng hợp nhu cầu theo loại thuốc/vật tư."""
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
    """Response của endpoint tổng hợp nhu cầu thuốc/vật tư."""
    total_supplies: int
    supplies_with_shortage: int
    items: List[SupplyRequirementSummaryItem]


# ── Dashboard schemas ─────────────────────────────────────────────────────────


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


# ── Threshold schemas ─────────────────────────────────────────────────────────


# ── Audit Log schemas ─────────────────────────────────────────────────────────

class AuditLogResponse(ORMBase):
    """Một bản ghi nhật ký kiểm toán."""
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None  # lấy từ quan hệ user
    action: str
    table_name: Optional[str] = None
    record_id: Optional[int] = None
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Danh sách nhật ký kiểm toán có phân trang."""
    total: int
    page: int
    page_size: int
    items: List[AuditLogResponse]


# ── System Log schemas ────────────────────────────────────────────────────────

class SystemLogResponse(ORMBase):
    """Một bản ghi log hệ thống."""
    id: int
    log_level: str
    module_name: Optional[str] = None
    message: str
    stack_trace: Optional[str] = None
    created_at: datetime


class SystemLogListResponse(BaseModel):
    """Danh sách log hệ thống có phân trang."""
    total: int
    page: int
    page_size: int
    items: List[SystemLogResponse]
