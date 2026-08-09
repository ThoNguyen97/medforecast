"""Disease Cases API endpoints."""
import csv
import io
import logging
from typing import List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.base import DiseaseCaseCreate, DiseaseCaseResponse, DiseaseCaseUpdate
from app.services.disease_case_service import DiseaseCaseService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/", response_model=List[DiseaseCaseResponse])
def list_disease_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),  # Bỏ giới hạn tối đa
    disease_type: Optional[str] = Query(None, description="Filter by ICD code (J20, J06, J02, J01)"),
    location: Optional[str] = Query(None, description="Filter by location (Tỉnh/Thành)"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD format)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD format)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    List disease case records.

    Supports filtering by ICD code (J20, J06, J02, J01), location (Tỉnh/Thành), and date range.
    """
    from app.models.disease_case import DiseaseCase

    q = db.query(DiseaseCase)
    if disease_type:
        q = q.filter(DiseaseCase.icd_code == disease_type)
    if location:
        q = q.filter(DiseaseCase.location == location)
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            q = q.filter(DiseaseCase.recorded_at >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid start_date format: {start_date}. Expected YYYY-MM-DD."
            )
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            # Add 1 day and subtract 1 second to include the entire end date
            from datetime import timedelta
            end_dt = end_dt + timedelta(days=1) - timedelta(seconds=1)
            q = q.filter(DiseaseCase.recorded_at <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid end_date format: {end_date}. Expected YYYY-MM-DD."
            )
    return (
        q.order_by(DiseaseCase.recorded_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("/", response_model=DiseaseCaseResponse, status_code=status.HTTP_201_CREATED)
def create_disease_case(
    data: DiseaseCaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Create a new disease case record.

    Spec 3.4 — không trùng tháng + bệnh + khu vực:
    nếu đã tồn tại bản ghi cùng (year, month, disease_type, location), trả về 409
    để frontend gợi ý người dùng cập nhật thay vì thêm mới.
    """
    from app.models.disease_case import DiseaseCase
    from sqlalchemy import extract

    service = DiseaseCaseService(db)
    client_ip = get_client_ip(request)

    # Dedupe check: cùng (year, month, disease_type, location) → 409
    existing = (
        db.query(DiseaseCase)
        .filter(
            extract("year", DiseaseCase.recorded_at) == data.recorded_at.year,
            extract("month", DiseaseCase.recorded_at) == data.recorded_at.month,
            DiseaseCase.disease_type == data.disease_type,
            DiseaseCase.location == data.location,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Đã tồn tại bản ghi cho cùng tháng, bệnh và khu vực. "
                           "Vui lòng cập nhật thay vì thêm mới.",
                "existing_id": existing.id,
            },
        )

    try:
        new_case = service.create_disease_case(
            data=data,
            created_by_user_id=current_user.id,
            ip_address=client_ip
        )
        # Gắn note + created_by username
        new_case.note = data.note
        new_case.created_by = current_user.username
        db.commit()
        db.refresh(new_case)
        return new_case
    except Exception as e:
        logger.error(f"Failed to create disease case: {str(e)}")
        raise


@router.get("/stats")
def get_disease_case_statistics(
    location: Optional[str] = Query(None, description="Filter by location"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get disease case statistics grouped by disease type.
    
    Returns total case counts, record counts, and latest record date for each disease type.
    All authenticated users can access this endpoint.
    """
    service = DiseaseCaseService(db)
    statistics = service.get_statistics(
        location=location,
        start_date=start_date,
        end_date=end_date
    )
    return {
        "statistics": statistics,
        "filters": {
            "location": location,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
    }


@router.get("/trends")
def get_disease_case_trends(
    disease_type: Optional[str] = Query(None, description="Filter by disease type"),
    location: Optional[str] = Query(None, description="Filter by location"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of data points"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get disease case trend data (time series).
    
    Returns daily aggregated case counts over time.
    All authenticated users can access this endpoint.
    """
    service = DiseaseCaseService(db)
    trends = service.get_trends(
        disease_type=disease_type,
        location=location,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    return {
        "trends": trends,
        "filters": {
            "disease_type": disease_type,
            "location": location,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
    }


# Mapping tên bệnh tiếng Việt → mã ICD (chỉ 4 bệnh hô hấp)
NHOM_BENH_MAPPING = {
    "Viêm phế quản cấp": "J20",
    "Nhiễm trùng đường hô hấp trên cấp": "J06",
    "Nhiễm trùng hô hấp trên cấp": "J06",
    "Viêm họng cấp": "J02",
    "Viêm xoang cấp": "J01",
    # Hỗ trợ nhập trực tiếp mã ICD
    "J20": "J20",
    "J06": "J06",
    "J02": "J02",
    "J01": "J01",
}

# Map ICD code → tên bệnh chuẩn
ICD_TO_NAME = {
    "J20": "Viêm phế quản cấp",
    "J06": "Nhiễm trùng đường hô hấp trên cấp",
    "J02": "Viêm họng cấp",
    "J01": "Viêm xoang cấp",
}


@router.post("/import-csv", status_code=status.HTTP_200_OK)
async def import_disease_cases_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Import disease cases from CSV.

    Hỗ trợ 2 định dạng:
    1. **Template đơn giản** (file mẫu): cột ``month``, ``disease_name``, ``region``, ``cases``
       - month dạng MM/YYYY hoặc YYYY-MM
       - disease_name có thể tiếng Việt (Sốt xuất huyết, Cúm A, ...) hoặc key (dengue_fever)
    2. **Hospital CSV**: cột ``AdmissionDate``, ``NhomBenh``, ``SoTiepNhan``, ``District``
       - Records aggregated by (date, disease_type, location), counted by distinct ``SoTiepNhan``.
    """
    from app.models.disease_case import DiseaseCase

    if not file.filename or not file.filename.lower().endswith((".csv",)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV",
        )

    try:
        raw = await file.read()
        # Decode và loại bỏ BOM (Byte Order Mark) nếu có
        text = raw.decode("utf-8-sig", errors="replace")
        reader = list(csv.DictReader(io.StringIO(text)))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot parse CSV: {exc}",
        )

    if not reader:
        return {"status": "ok", "imported": 0, "updated": 0, "skipped": 0, "message": "Empty CSV"}

    headers = {h.strip() for h in (reader[0].keys() if reader else [])}

    imported = 0
    updated = 0
    skipped = 0
    errors: list[dict] = []  # spec 3.5: liệt kê dòng lỗi để user sửa

    # Cache các khu vực đã đăng ký ở module Quản trị (admin.regions) — tránh query lại nhiều lần.
    # Khu vực mới gặp trong CSV sẽ được tự động đăng ký vào danh mục này.
    new_regions_to_register: set[str] = set()

    def _register_pending_regions() -> None:
        """Thêm các khu vực mới từ CSV vào admin.regions (idempotent)."""
        if not new_regions_to_register:
            return
        from app.models.system_config import SystemConfig
        import json as _json

        cfg = (
            db.query(SystemConfig)
            .filter(SystemConfig.config_key == "admin.regions")
            .first()
        )
        if cfg is None:
            cfg = SystemConfig(
                config_key="admin.regions",
                config_value="[]",
                description="Danh mục khu vực",
            )
            db.add(cfg)
            db.flush()

        try:
            existing = _json.loads(cfg.config_value or "[]")
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []

        existing_names = {r.get("name") for r in existing if isinstance(r, dict)}
        added_count = 0
        for name in new_regions_to_register:
            if name in existing_names:
                continue
            existing.append({"name": name, "province": None, "description": ""})
            added_count += 1

        if added_count:
            cfg.config_value = _json.dumps(existing, ensure_ascii=False)
            cfg.updated_by = current_user.id
            logger.info(
                "CSV import: auto-registered %d new region(s): %s",
                added_count,
                ", ".join(sorted(new_regions_to_register)),
            )

    # Check if this is simple template format (supports both disease_name and disease_code)
    has_simple_format = (
        "month" in headers and 
        "region" in headers and 
        "cases" in headers and 
        ("disease_name" in headers or "disease_code" in headers)
    )
    
    if has_simple_format:
        # Simple template format → 1 row = 1 record
        # Cột supply_name / supply_quantity / supply_unit / supply_category là tuỳ chọn:
        #   khi xuất hiện, các dòng cùng (month+disease+region) được gộp thành 1 ca
        #   bệnh kèm nhiều dòng chi tiết thuốc đã dùng.
        from app.models.medical_supply import MedicalSupply
        from app.models.case_supply_usage import CaseSupplyUsage

        has_supply_col = (
            "supply_name" in headers
            or "supply_code" in headers
            or "drug_code" in headers
        )

        # Bước 1: gom theo key (month, disease_key, region) để gộp các dòng
        # supply chi tiết về cùng 1 ca bệnh.
        grouped: dict[tuple, dict] = {}
        for idx, row in enumerate(reader, start=2):
            month_str = (row.get("month") or "").strip()
            # Ưu tiên disease_code, fallback về disease_name
            disease_code = (row.get("disease_code") or "").strip().upper()  # Chuẩn hóa thành chữ hoa
            disease_name = (row.get("disease_name") or "").strip()
            disease = disease_code if disease_code else disease_name
            
            region = (row.get("region") or "").strip()
            cases_raw = (row.get("cases") or "").strip()
            note = (row.get("note") or "").strip() or None
            supply_name = (row.get("supply_name") or "").strip() if has_supply_col else ""
            supply_code = (row.get("supply_code") or "").strip() if has_supply_col else ""
            drug_code = (row.get("drug_code") or "").strip() if has_supply_col else ""
            supply_qty_raw = (row.get("supply_quantity") or "").strip() if has_supply_col else ""
            supply_unit = (row.get("supply_unit") or "").strip() if has_supply_col else ""
            supply_category = (row.get("supply_category") or "").strip() if has_supply_col else ""

            if not month_str or not disease or not region or not cases_raw:
                skipped += 1
                errors.append({
                    "row": idx,
                    "reason": "Thiếu cột bắt buộc (month / disease_code hoặc disease_name / region / cases)",
                    "data": {"month": month_str, "disease": disease, "region": region, "cases": cases_raw},
                })
                continue

            parsed: Optional[datetime] = None
            for fmt in ("%m/%Y", "%Y-%m", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
                try:
                    parsed = datetime.strptime(month_str, fmt)
                    break
                except ValueError:
                    continue
            if parsed is None:
                skipped += 1
                errors.append({
                    "row": idx,
                    "reason": f"Không hiểu định dạng tháng: '{month_str}' (chấp nhận MM/YYYY, YYYY-MM)",
                })
                continue
            recorded_at = datetime(parsed.year, parsed.month, 1)

            try:
                cases_int = int(float(cases_raw))
            except ValueError:
                skipped += 1
                errors.append({"row": idx, "reason": f"Số ca không hợp lệ: '{cases_raw}'"})
                continue
            if cases_int < 0:
                skipped += 1
                errors.append({"row": idx, "reason": f"Số ca phải >= 0, nhận được {cases_int}"})
                continue

            # Nếu disease đã là mã ICD hợp lệ (J01, J02, J06, J20) thì dùng trực tiếp
            # Nếu không thì tra mapping từ tên tiếng Việt
            if disease in ICD_TO_NAME:
                disease_key = disease
            else:
                disease_key = NHOM_BENH_MAPPING.get(disease, disease)
            
            # Validate mã ICD
            if disease_key not in ICD_TO_NAME:
                skipped += 1
                errors.append({
                    "row": idx,
                    "reason": f"Bệnh không hợp lệ: '{disease}'. Chỉ hỗ trợ 4 bệnh: {', '.join(ICD_TO_NAME.values())} hoặc mã ICD: {', '.join(ICD_TO_NAME.keys())}",
                })
                continue
            disease_name_std = ICD_TO_NAME[disease_key]
            key = (recorded_at, disease_key, region)

            entry = grouped.get(key)
            if entry is None:
                entry = {
                    "recorded_at": recorded_at,
                    "disease_key": disease_key,
                    "disease_name": disease_name_std,
                    "region": region,
                    "case_count": cases_int,
                    "note": note,
                    "supplies": [],  # list of dicts
                    "first_row": idx,
                }
                grouped[key] = entry
            else:
                # Cùng ca bệnh — giữ giá trị cases lớn nhất (an toàn nếu user lặp ở nhiều dòng).
                if cases_int > entry["case_count"]:
                    entry["case_count"] = cases_int
                if note and not entry["note"]:
                    entry["note"] = note

            # Nếu dòng có supply (theo code hoặc name) + quantity, gộp vào supplies
            if supply_name or supply_code or drug_code:
                try:
                    supply_qty_int = int(float(supply_qty_raw)) if supply_qty_raw else 0
                except ValueError:
                    skipped += 1
                    errors.append({
                        "row": idx,
                        "reason": f"Số lượng thuốc không hợp lệ: '{supply_qty_raw}'",
                    })
                    continue
                if supply_qty_int < 0:
                    skipped += 1
                    errors.append({
                        "row": idx,
                        "reason": f"Số lượng thuốc phải >= 0, nhận được {supply_qty_int}",
                    })
                    continue
                entry["supplies"].append({
                    "name": supply_name,
                    "supply_code": supply_code,
                    "drug_code": drug_code,
                    "qty": supply_qty_int,
                    "unit": supply_unit or "đơn vị",
                    "category": supply_category or "Khác",
                })

        # Bước 2: persist từng group thành DiseaseCase + CaseSupplyUsage
        # Cache supply lookup để tránh query lại nhiều lần
        supply_cache: dict[str, MedicalSupply] = {}

        def _get_or_create_supply(
            name: str, unit: str, category: str,
            supply_code: str = "", drug_code: str = "",
        ) -> MedicalSupply:
            # Ưu tiên match theo mã (supply_code → drug_code) vì chính xác hơn tên.
            cache_key = (supply_code or drug_code or name).lower().strip()
            if cache_key in supply_cache:
                return supply_cache[cache_key]

            existing_sup = None
            if supply_code:
                existing_sup = (
                    db.query(MedicalSupply)
                    .filter(func.lower(MedicalSupply.supply_code) == supply_code.lower())
                    .first()
                )
            if existing_sup is None and drug_code:
                existing_sup = (
                    db.query(MedicalSupply)
                    .filter(func.lower(MedicalSupply.drug_code) == drug_code.lower())
                    .first()
                )
            if existing_sup is None and name:
                key = name.lower().strip()
                existing_sup = (
                    db.query(MedicalSupply)
                    .filter(
                        (func.lower(MedicalSupply.ten_hoat_chat) == key)
                        | (func.lower(MedicalSupply.supply_code) == key)
                    )
                    .first()
                )
            if existing_sup is None:
                # Không tìm thấy → tạo placeholder (chỉ điền tối thiểu)
                logger.warning(
                    "Supply code=%s name='%s' không khớp 15 thuốc/vật tư, tạo placeholder.",
                    supply_code or drug_code, name,
                )
                next_code = supply_code or f"VT_AUTO_{int(datetime.now().timestamp())}"
                existing_sup = MedicalSupply(
                    supply_code=next_code,
                    drug_code=drug_code or next_code,
                    ten_hoat_chat=name or next_code,
                    unit=unit,
                    group_name=category or "Khác",
                    category=category,
                )
                db.add(existing_sup)
                db.flush()
            supply_cache[cache_key] = existing_sup
            return existing_sup

        for entry in grouped.values():
            recorded_at = entry["recorded_at"]
            disease_key = entry["disease_key"]
            disease_name_std = entry["disease_name"]
            region = entry["region"]
            cases_int = entry["case_count"]
            note = entry["note"]

            existing = (
                db.query(DiseaseCase)
                .filter(
                    DiseaseCase.recorded_at == recorded_at,
                    DiseaseCase.icd_code == disease_key,
                    DiseaseCase.location == region,
                )
                .first()
            )
            if existing:
                existing.case_count = cases_int
                existing.disease_name = disease_name_std
                existing.disease_type = "respiratory"
                existing.data_source = file.filename
                if note:
                    existing.note = note
                case_obj = existing
                updated += 1
            else:
                case_obj = DiseaseCase(
                    recorded_at=recorded_at,
                    icd_code=disease_key,
                    disease_name=disease_name_std,
                    disease_type="respiratory",
                    case_count=cases_int,
                    location=region,
                    data_source=file.filename,
                    note=note,
                    created_by=current_user.username,
                )
                db.add(case_obj)
                db.flush()  # cần case_obj.id ngay
                imported += 1

            new_regions_to_register.add(region)

            # Persist supply usage details (nếu CSV có)
            if entry["supplies"]:
                # Xoá usage cũ của ca này để cập nhật lại từ CSV mới
                db.query(CaseSupplyUsage).filter(
                    CaseSupplyUsage.case_id == case_obj.id
                ).delete(synchronize_session=False)
                db.flush()
                # Gom số lượng theo supply_id TRƯỚC (cộng dồn nếu 1 thuốc xuất
                # hiện nhiều dòng trong cùng ca) rồi mới insert 1 lần/thuốc —
                # tránh vi phạm UNIQUE(case_id, supply_id).
                qty_by_supply: dict[int, int] = {}
                for sup in entry["supplies"]:
                    supply_obj = _get_or_create_supply(
                        sup["name"], sup["unit"], sup["category"],
                        supply_code=sup.get("supply_code", ""),
                        drug_code=sup.get("drug_code", ""),
                    )
                    qty_by_supply[supply_obj.id] = (
                        qty_by_supply.get(supply_obj.id, 0) + sup["qty"]
                    )
                for supply_id, qty in qty_by_supply.items():
                    db.add(CaseSupplyUsage(
                        case_id=case_obj.id,
                        supply_id=supply_id,
                        quantity=qty,
                    ))
    else:
        # Hospital CSV format
        aggregate: dict[tuple, set[str]] = {}
        for row in reader:
            admit = (row.get("AdmissionDate") or "").strip()
            nhom = (row.get("NhomBenh") or "").strip()
            so_tiep_nhan = (row.get("SoTiepNhan") or "").strip()
            location = (row.get("District") or "Thành phố Hồ Chí Minh").strip()

            if not admit or not nhom or not so_tiep_nhan:
                skipped += 1
                continue

            disease_type = NHOM_BENH_MAPPING.get(nhom)
            if not disease_type:
                skipped += 1
                continue

            parsed = None
            for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    parsed = datetime.strptime(admit, fmt)
                    break
                except ValueError:
                    continue
            if parsed is None:
                skipped += 1
                continue

            key = (parsed.date(), disease_type, location)
            aggregate.setdefault(key, set()).add(so_tiep_nhan)
            new_regions_to_register.add(location)

        for (rec_date, disease_type, location), ids in aggregate.items():
            recorded_at = datetime(rec_date.year, rec_date.month, rec_date.day)
            disease_name_std = ICD_TO_NAME.get(disease_type, disease_type)
            existing = (
                db.query(DiseaseCase)
                .filter(
                    DiseaseCase.recorded_at == recorded_at,
                    DiseaseCase.icd_code == disease_type,
                    DiseaseCase.location == location,
                )
                .first()
            )
            if existing:
                existing.case_count = len(ids)
                existing.disease_name = disease_name_std
                existing.data_source = file.filename
                updated += 1
            else:
                db.add(
                    DiseaseCase(
                        recorded_at=recorded_at,
                        icd_code=disease_type,
                        disease_name=disease_name_std,
                        disease_type="respiratory",
                        case_count=len(ids),
                        location=location,
                        data_source=file.filename,
                    )
                )
                imported += 1

    # Register các khu vực mới gặp trong CSV vào admin.regions
    try:
        _register_pending_regions()
    except Exception as exc:
        logger.warning("Không thể tự đăng ký khu vực mới: %s", exc)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save: {exc}",
        )

    logger.info(
        f"Disease cases import by user={current_user.username}: "
        f"imported={imported} updated={updated} skipped={skipped}"
    )

    # Sau khi import xong → tự động phân loại lại severity & cập nhật severity_rate
    # (mục 5.2). Dispatch async qua Celery; nếu broker không có thì chạy sync.
    auto_severity: dict | None = None
    if imported > 0 or updated > 0:
        try:
            from app.tasks.severity_inference_task import dispatch_recompute

            auto_severity = dispatch_recompute(
                force=False,
                trigger="csv_import",
                updated_by=current_user.username,
            )
        except Exception as exc:
            logger.warning("Auto severity recompute after CSV import failed: %s", exc)
            auto_severity = {"mode": "failed", "error": str(exc)}

    return {
        "status": "ok",
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:200],  # giới hạn 200 dòng lỗi đầu để response không quá lớn
        "errors_truncated": len(errors) > 200,
        "auto_severity_recompute": auto_severity,
    }


@router.put("/{case_id}", response_model=DiseaseCaseResponse)
def update_disease_case(
    case_id: int,
    data: DiseaseCaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update an existing disease case (PATCH-style: chỉ cập nhật field có giá trị)."""
    from app.models.disease_case import DiseaseCase
    from sqlalchemy import extract

    case = db.query(DiseaseCase).filter(DiseaseCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disease case {case_id} not found",
        )

    # Nếu đổi (recorded_at + icd_code + location) → check trùng với bản ghi khác
    new_recorded_at = data.recorded_at or case.recorded_at
    new_icd = data.icd_code or case.icd_code
    new_location = data.location or case.location

    duplicate = (
        db.query(DiseaseCase)
        .filter(
            DiseaseCase.id != case_id,
            extract("year", DiseaseCase.recorded_at) == new_recorded_at.year,
            extract("month", DiseaseCase.recorded_at) == new_recorded_at.month,
            DiseaseCase.icd_code == new_icd,
            DiseaseCase.location == new_location,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Đã có bản ghi khác cho cùng tháng/bệnh/khu vực này.",
                "existing_id": duplicate.id,
            },
        )

    update_dict = data.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(case, k, v)

    try:
        db.commit()
        db.refresh(case)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update: {exc}",
        )
    logger.info(f"Disease case {case_id} updated by user={current_user.username}")
    return case


@router.delete("/{case_id}", status_code=status.HTTP_200_OK)
def delete_disease_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Delete a single disease case record."""
    from app.models.disease_case import DiseaseCase

    case = db.query(DiseaseCase).filter(DiseaseCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disease case {case_id} not found",
        )

    db.delete(case)
    db.commit()
    logger.info(f"Disease case {case_id} deleted by user={current_user.username}")
    return {"message": "Disease case deleted", "id": case_id}


@router.get("/{case_id}/supply-usage")
def get_case_supply_usage(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Chi tiết sử dụng thuốc cho 1 ca bệnh.

    Logic mới (theo yêu cầu mục 4-6):
    - Phân bổ tổng số ca theo severity_rate (Nhẹ/Trung bình/Nặng)
    - Với mỗi thuốc: số lượng = Σ(số ca theo mức × định mức theo mức) từ disease_supply_norm
    - Fallback: nếu chưa có severity_rate / norm → dùng case_supply_usage thực tế hoặc conversion_ratios
    """
    from app.models.disease_case import DiseaseCase
    from app.models.medical_supply import MedicalSupply
    from app.models.conversion_ratio import ConversionRatio
    from app.models.case_supply_usage import CaseSupplyUsage
    from app.models.severity_rate import SeverityRate
    from app.models.disease_supply_norm import DiseaseSupplyNorm
    from sqlalchemy import extract

    case = db.query(DiseaseCase).filter(DiseaseCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disease case {case_id} not found",
        )

    supplies: list[dict] = []
    severity_breakdown: dict | None = None

    # Bước 1: Tính theo severity_rate × disease_supply_norm (logic chuẩn)
    severity = (
        db.query(SeverityRate)
        .filter(SeverityRate.icd_code == case.icd_code)
        .first()
    )
    norms = (
        db.query(DiseaseSupplyNorm, MedicalSupply)
        .join(MedicalSupply, MedicalSupply.id == DiseaseSupplyNorm.supply_id)
        .filter(DiseaseSupplyNorm.icd_code == case.icd_code)
        .all()
    )

    if severity and norms:
        # Phân bổ số ca theo mức độ
        mild_cases = round(case.case_count * float(severity.mild_rate) / 100)
        moderate_cases = round(case.case_count * float(severity.moderate_rate) / 100)
        severe_cases = case.case_count - mild_cases - moderate_cases  # đảm bảo tổng = case_count
        if severe_cases < 0:
            severe_cases = 0

        severity_breakdown = {
            "mild_rate": float(severity.mild_rate),
            "moderate_rate": float(severity.moderate_rate),
            "severe_rate": float(severity.severe_rate),
            "mild_cases": mild_cases,
            "moderate_cases": moderate_cases,
            "severe_cases": severe_cases,
        }

        # Gộp định mức theo (supply_id)
        supply_norms: dict[int, dict] = {}
        for norm, supply in norms:
            sid = supply.id
            if sid not in supply_norms:
                supply_norms[sid] = {
                    "supply": supply,
                    "mild": 0,
                    "moderate": 0,
                    "severe": 0,
                }
            if norm.severity == "mild":
                supply_norms[sid]["mild"] = norm.quantity_per_case
            elif norm.severity == "moderate":
                supply_norms[sid]["moderate"] = norm.quantity_per_case
            elif norm.severity == "severe":
                supply_norms[sid]["severe"] = norm.quantity_per_case

        # Tính tổng nhu cầu cho từng thuốc
        for sid, data in supply_norms.items():
            supply = data["supply"]
            total = (
                mild_cases * data["mild"]
                + moderate_cases * data["moderate"]
                + severe_cases * data["severe"]
            )
            if total <= 0:
                # Bỏ qua thuốc không dùng cho bệnh này
                continue
            ratio = round(total / case.case_count, 4) if case.case_count > 0 else 0.0
            supplies.append({
                "supply_id": supply.id,
                "code": supply.supply_code or f"VT{supply.id:03d}",
                "drug_code": supply.drug_code,
                "name": supply.ten_hoat_chat,
                "category": supply.group_name or supply.category or "Khác",
                "unit": supply.unit,
                "description": supply.description,
                "ratio": ratio,
                "used_quantity": int(total),
                "norm_mild": data["mild"],
                "norm_moderate": data["moderate"],
                "norm_severe": data["severe"],
                "disease_label": case.disease_name,
                "source": "norm",
            })

    # Bước 2: Fallback — actual data từ case_supply_usage (nếu đã import chi tiết)
    if not supplies:
        actual_usages = (
            db.query(CaseSupplyUsage, MedicalSupply)
            .join(MedicalSupply, MedicalSupply.id == CaseSupplyUsage.supply_id)
            .filter(CaseSupplyUsage.case_id == case_id)
            .all()
        )
        if actual_usages:
            for usage, supply in actual_usages:
                supplies.append({
                    "supply_id": supply.id,
                    "code": supply.supply_code or f"VT{supply.id:03d}",
                    "drug_code": supply.drug_code,
                    "name": supply.ten_hoat_chat,
                    "category": supply.group_name or supply.category or "Khác",
                    "unit": supply.unit,
                    "description": supply.description,
                    "ratio": (
                        round(float(usage.quantity) / case.case_count, 4)
                        if case.case_count > 0 else 0.0
                    ),
                    "used_quantity": int(usage.quantity),
                    "disease_label": case.disease_name,
                    "source": "actual",
                })

    # Bước 3: Fallback cuối — conversion_ratios cũ
    if not supplies:
        ratios = (
            db.query(ConversionRatio, MedicalSupply)
            .join(MedicalSupply, MedicalSupply.id == ConversionRatio.supply_id)
            .filter(ConversionRatio.disease_type == case.icd_code)
            .all()
        )
        for ratio, supply in ratios:
            ratio_val = float(ratio.ratio) if ratio.ratio is not None else 0.0
            used_qty = int(round(case.case_count * ratio_val))
            if used_qty <= 0:
                continue
            supplies.append({
                "supply_id": supply.id,
                "code": supply.supply_code or f"VT{supply.id:03d}",
                "drug_code": supply.drug_code,
                "name": supply.ten_hoat_chat,
                "category": supply.group_name or supply.category or "Khác",
                "unit": supply.unit,
                "description": supply.description,
                "ratio": ratio_val,
                "used_quantity": used_qty,
                "disease_label": case.disease_name,
                "source": "estimated",
            })

    # Sort theo used_quantity giảm dần
    supplies.sort(key=lambda s: s["used_quantity"], reverse=True)

    # Compare tháng trước
    prev_year = case.recorded_at.year
    prev_month = case.recorded_at.month - 1
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    prev_q = (
        db.query(func.coalesce(func.sum(DiseaseCase.case_count), 0))
        .filter(
            DiseaseCase.icd_code == case.icd_code,
            DiseaseCase.location == case.location,
            extract("year", DiseaseCase.recorded_at) == prev_year,
            extract("month", DiseaseCase.recorded_at) == prev_month,
        )
    )
    prev_total = int(prev_q.scalar() or 0)
    prev_supply_types = len(supplies)
    delta_cases = (
        round(((case.case_count - prev_total) / prev_total) * 100, 1)
        if prev_total > 0
        else None
    )

    return {
        "case": {
            "id": case.id,
            "recorded_at": case.recorded_at.isoformat(),
            "month": case.recorded_at.month,
            "year": case.recorded_at.year,
            "icd_code": case.icd_code,
            "disease_name": case.disease_name,
            # giữ disease_type cho frontend cũ
            "disease_type": case.icd_code,
            "location": case.location,
            "case_count": case.case_count,
            "note": case.note,
        },
        "severity_breakdown": severity_breakdown,
        "summary": {
            "total_supply_types": len(supplies),
            "total_cases": case.case_count,
            "prev_total_cases": prev_total,
            "delta_cases_pct": delta_cases,
            "prev_total_supply_types": prev_supply_types,
        },
        "supplies": supplies,
    }


@router.get("/template")
async def download_template():
    """Trả về file CSV mẫu để người dùng tải về điền (4 bệnh hô hấp)."""
    from fastapi.responses import StreamingResponse

    sample = (
        "month,disease_name,region,cases,supply_name,supply_quantity,supply_unit,supply_category,note\n"
        "10/2024,Viêm phế quản cấp,TP. Hồ Chí Minh,145,Paracetamol,1450,Viên,Thuốc hạ sốt giảm đau,\n"
        "10/2024,Viêm phế quản cấp,TP. Hồ Chí Minh,145,N-acetylcysteine,1015,Gói,Thuốc long đờm,\n"
        "10/2024,Nhiễm trùng đường hô hấp trên cấp,TP. Hồ Chí Minh,89,Paracetamol,890,Viên,Thuốc hạ sốt giảm đau,\n"
        "09/2024,Viêm họng cấp,Hà Nội,67,Fexofenadin,335,Viên,Kháng histamin,\n"
        "09/2024,Viêm xoang cấp,Hà Nội,42,,,,,Có thể bỏ trống supply để chỉ ghi số ca\n"
    )
    return StreamingResponse(
        iter([sample]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=disease_cases_template.csv"},
    )


@router.get("/distinct-values")
async def distinct_values(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Lấy danh sách icd_code + location duy nhất để dropdown filter."""
    from app.models.disease_case import DiseaseCase

    # Lấy distinct (icd_code, disease_name) để hiển thị nhãn rõ ràng
    diseases_rows = (
        db.query(DiseaseCase.icd_code, DiseaseCase.disease_name)
        .distinct()
        .order_by(DiseaseCase.icd_code)
        .all()
    )
    regions = (
        db.query(DiseaseCase.location)
        .distinct()
        .order_by(DiseaseCase.location)
        .all()
    )

    # icd_codes: list mã ICD; diseases: list {icd_code, name} cho UI hiển thị nhãn
    icd_codes = [d[0] for d in diseases_rows if d[0]]
    diseases_list = [
        {"icd_code": icd, "disease_name": name or ICD_TO_NAME.get(icd, icd)}
        for icd, name in diseases_rows
        if icd
    ]
    return {
        # Trường mới
        "icd_codes": icd_codes,
        "diseases": diseases_list,
        # Tương thích frontend cũ — disease_types là list ICD code
        "disease_types": icd_codes,
        "regions": [r[0] for r in regions if r[0]],
    }
