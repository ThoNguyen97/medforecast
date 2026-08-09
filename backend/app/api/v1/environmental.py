"""Environmental Data API endpoints."""
import logging
from typing import List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.schemas.base import (
    EnvironmentalDataCreate,
    EnvironmentalDataResponse,
    EnvironmentalDataUpdate,
)
from app.services.environmental_service import EnvironmentalDataService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/", response_model=List[EnvironmentalDataResponse])
def list_environmental_data(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),  # Bỏ giới hạn tối đa
    location: Optional[str] = Query(None, description="Filter by location"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    List environmental data records.
    
    Supports filtering by location.
    All authenticated users can access this endpoint.
    """
    service = EnvironmentalDataService(db)
    data = service.get_environmental_data(
        skip=skip,
        limit=limit,
        location=location
    )
    return data


@router.post("/", response_model=EnvironmentalDataResponse, status_code=status.HTTP_201_CREATED)
def create_environmental_data(
    data: EnvironmentalDataCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Create a new environmental data record.
    
    All authenticated users can create environmental data records.
    """
    service = EnvironmentalDataService(db)
    client_ip = get_client_ip(request)
    
    try:
        new_data = service.create_environmental_data(
            data=data,
            created_by_user_id=current_user.id,
            ip_address=client_ip
        )
        return new_data
    except Exception as e:
        logger.error(f"Failed to create environmental data: {str(e)}")
        raise


@router.get("/latest", response_model=EnvironmentalDataResponse)
def get_latest_environmental_data(
    location: Optional[str] = Query(None, description="Filter by location"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get the latest environmental data record.
    
    Optionally filter by location.
    All authenticated users can access this endpoint.
    """
    service = EnvironmentalDataService(db)
    data = service.get_latest_data(location=location)
    return data


@router.get("/range", response_model=List[EnvironmentalDataResponse])
def get_environmental_data_range(
    start_date: datetime = Query(..., description="Start date and time (ISO format)"),
    end_date: datetime = Query(..., description="End date and time (ISO format)"),
    location: Optional[str] = Query(None, description="Filter by location"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get environmental data for a specific date range.
    
    All authenticated users can access this endpoint.
    """
    service = EnvironmentalDataService(db)
    data = service.get_data_by_date_range(
        start_date=start_date,
        end_date=end_date,
        location=location
    )
    return data


# ── New endpoints theo Smart Medical spec ──────────────────────────────────

@router.get("/template")
async def download_template():
    """File mẫu CSV cho dữ liệu thời tiết & môi trường."""
    from fastapi.responses import StreamingResponse

    sample = (
        "month,province_city,district_ward,avg_temp,humidity,rainfall,aqi,pm25\n"
        "06/2024,TP. Hồ Chí Minh,Quận 1,32.5,75,120.5,45,12.4\n"
        "06/2024,TP. Hồ Chí Minh,Quận 7,31.8,78,145.2,85,28.5\n"
        "06/2024,TP. Hồ Chí Minh,Thành phố Thủ Đức,33.2,72,85.0,112,45.2\n"
    )
    return StreamingResponse(
        iter([sample]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=environmental_template.csv"},
    )


@router.get("/distinct-values")
async def env_distinct_values(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Province/city + district/ward duy nhất + cascade map để dropdown filter."""
    from app.models.environmental_data import EnvironmentalData

    provinces = (
        db.query(EnvironmentalData.location).distinct().order_by(EnvironmentalData.location).all()
    )
    districts = (
        db.query(EnvironmentalData.district_ward)
        .distinct()
        .order_by(EnvironmentalData.district_ward)
        .all()
    )
    pairs = (
        db.query(EnvironmentalData.location, EnvironmentalData.district_ward)
        .filter(EnvironmentalData.district_ward.isnot(None))
        .distinct()
        .all()
    )
    province_districts: dict[str, list[str]] = {}
    for prov, dist in pairs:
        if prov and dist:
            province_districts.setdefault(prov, []).append(dist)
    for v in province_districts.values():
        v.sort()
    return {
        "provinces": [p[0] for p in provinces if p[0]],
        "districts": [d[0] for d in districts if d[0]],
        "province_districts": province_districts,
    }


@router.post("/import-csv")
async def import_environmental_csv_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Import environmental CSV. Cột mong đợi:
    month, province_city, district_ward, avg_temp, humidity, rainfall, aqi, pm25

    Validate spec 4.4: nhiệt độ 10-45°C, độ ẩm 0-100%, mưa/AQI/PM2.5 ≥ 0.
    Tự động đăng ký khu vực mới (province_city / district_ward) vào admin.regions.
    """
    import csv as _csv
    import io as _io
    import json as _json
    from datetime import datetime as _dt
    from app.models.environmental_data import EnvironmentalData
    from app.models.system_config import SystemConfig

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")
    reader = list(_csv.DictReader(_io.StringIO(text)))

    imported = 0
    updated = 0
    skipped = 0
    errors: list[dict] = []
    new_regions: set[str] = set()

    for idx, row in enumerate(reader, start=2):
        month = (row.get("month") or "").strip()
        prov = (row.get("province_city") or row.get("location") or "").strip()
        dist = (row.get("district_ward") or "").strip()

        if not month or not prov:
            skipped += 1
            errors.append({
                "row": idx,
                "reason": "Thiếu cột bắt buộc (month / province_city)",
            })
            continue

        parsed = None
        for fmt in ("%m/%Y", "%Y-%m", "%Y-%m-%d"):
            try:
                parsed = _dt.strptime(month, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            skipped += 1
            errors.append({
                "row": idx,
                "reason": f"Không hiểu định dạng tháng: '{month}' (chấp nhận MM/YYYY hoặc YYYY-MM)",
            })
            continue
        recorded_at = _dt(parsed.year, parsed.month, 1)

        def _f(name: str):
            v = (row.get(name) or "").strip()
            try:
                return float(v) if v else None
            except ValueError:
                return None

        def _i(name: str):
            v = (row.get(name) or "").strip()
            try:
                return int(float(v)) if v else None
            except ValueError:
                return None

        temp = _f("avg_temp")
        humidity = _f("humidity")
        rainfall = _f("rainfall")
        aqi = _i("aqi")
        pm25 = _f("pm25")

        # Validate range theo spec 4.4
        row_errors = []
        if temp is not None and (temp < 10 or temp > 45):
            row_errors.append(f"Nhiệt độ {temp} ngoài khoảng 10-45°C")
        if humidity is not None and (humidity < 0 or humidity > 100):
            row_errors.append(f"Độ ẩm {humidity} ngoài khoảng 0-100%")
        if rainfall is not None and rainfall < 0:
            row_errors.append(f"Lượng mưa {rainfall} âm")
        if aqi is not None and aqi < 0:
            row_errors.append(f"AQI {aqi} âm")
        if pm25 is not None and pm25 < 0:
            row_errors.append(f"PM2.5 {pm25} âm")

        if row_errors:
            skipped += 1
            errors.append({"row": idx, "reason": "; ".join(row_errors)})
            continue

        new_regions.add(prov)
        if dist:
            new_regions.add(dist)

        existing = (
            db.query(EnvironmentalData)
            .filter(
                EnvironmentalData.recorded_at == recorded_at,
                EnvironmentalData.location == prov,
                EnvironmentalData.district_ward == (dist or None),
            )
            .first()
        )
        values = dict(
            recorded_at=recorded_at,
            location=prov,
            district_ward=dist or None,
            temperature=temp,
            humidity=humidity,
            rainfall=rainfall,
            air_quality_index=aqi,
            pm25=pm25,
            data_source=file.filename,
        )
        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(EnvironmentalData(**values))
            imported += 1

    # Auto-register new regions vào admin.regions (idempotent)
    if new_regions:
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
            existing_regions = _json.loads(cfg.config_value or "[]")
            if not isinstance(existing_regions, list):
                existing_regions = []
        except Exception:
            existing_regions = []
        existing_names = {
            r.get("name") for r in existing_regions if isinstance(r, dict)
        }
        added = 0
        for name in new_regions:
            if name and name not in existing_names:
                existing_regions.append(
                    {"name": name, "province": None, "description": ""}
                )
                added += 1
        if added:
            cfg.config_value = _json.dumps(existing_regions, ensure_ascii=False)
            cfg.updated_by = current_user.id
            logger.info(
                "Env CSV import: auto-registered %d new region(s): %s",
                added,
                ", ".join(sorted(new_regions)),
            )

    db.commit()
    return {
        "status": "ok",
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:200],
        "errors_truncated": len(errors) > 200,
    }


@router.get("/trend")
async def env_trend(
    target_month: int = Query(..., ge=1, le=12, description="Tháng cần xem xu hướng (1-12)"),
    province: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy giá trị các yếu tố thời tiết cho cùng 1 tháng qua các năm.

    Trả về danh sách points: [{year, temp, humidity, rainfall, aqi, pm25}]
    """
    from app.models.environmental_data import EnvironmentalData
    from sqlalchemy import extract, func as _func

    q = (
        db.query(
            extract('year', EnvironmentalData.recorded_at).label('y'),
            _func.avg(EnvironmentalData.temperature).label('t'),
            _func.avg(EnvironmentalData.humidity).label('h'),
            _func.avg(EnvironmentalData.rainfall).label('r'),
            _func.avg(EnvironmentalData.air_quality_index).label('a'),
            _func.avg(EnvironmentalData.pm25).label('p'),
        )
        .filter(extract('month', EnvironmentalData.recorded_at) == target_month)
    )
    if province:
        from app.utils.province_alias import province_aliases
        q = q.filter(EnvironmentalData.location.in_(province_aliases(province)))
    if district:
        q = q.filter(EnvironmentalData.district_ward == district)
    rows = q.group_by('y').order_by('y').all()

    def _to_float(v):
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return [
        {
            'year': int(r[0]),
            'temp': _to_float(r[1]),
            'humidity': _to_float(r[2]),
            'rainfall': _to_float(r[3]),
            'aqi': _to_float(r[4]),
            'pm25': _to_float(r[5]),
        }
        for r in rows
    ]


@router.put("/{record_id}", response_model=EnvironmentalDataResponse)
def update_environmental_record(
    record_id: int,
    data: EnvironmentalDataUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cập nhật một bản ghi (PATCH-style)."""
    from app.models.environmental_data import EnvironmentalData

    item = db.query(EnvironmentalData).filter(EnvironmentalData.id == record_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")

    update_dict = data.model_dump(exclude_none=True)
    for k, v in update_dict.items():
        setattr(item, k, v)
    try:
        db.commit()
        db.refresh(item)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update: {exc}",
        )
    logger.info(f"Environmental record {record_id} updated by user={current_user.username}")
    return item


@router.delete("/{record_id}")
def delete_environmental_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.environmental_data import EnvironmentalData

    item = db.query(EnvironmentalData).filter(EnvironmentalData.id == record_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(item)
    db.commit()
    return {"message": "deleted"}


# ── Open-Meteo integration ────────────────────────────────────────────────
# Endpoint sync dữ liệu thời tiết + chất lượng không khí từ Open-Meteo public API
# (https://open-meteo.com — free, không cần API key).


@router.post("/sync-openmeteo")
def sync_openmeteo(
    province: str = Query(
        "TP. Hồ Chí Minh",
        description="Tỉnh/thành để sync (mặc định TP. HCM)",
    ),
    months_back: int = Query(
        12, ge=1, le=120,
        description="Số tháng quá khứ cần sync (gộp historical archive)",
    ),
    forecast_days: int = Query(
        16, ge=1, le=16,
        description="Số ngày forecast tương lai cần sync (gộp daily)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đồng bộ dữ liệu thời tiết từ Open-Meteo về bảng environmental_data.

    Logic:
    - Quá khứ (months_back tháng): dùng historical archive API, gộp theo tháng,
      ghi vào environmental_data với recorded_at = đầu tháng.
    - Tương lai (forecast_days ngày): dùng forecast API, gộp theo tháng, ghi
      tháng kế tiếp nếu có overlap.
    - AQI/PM2.5 chỉ có cho ~7 ngày forecast (giới hạn của air-quality API miễn phí),
      sẽ ghi đè vào tháng hiện tại nếu có dữ liệu.

    Tự upsert theo (recorded_at, location).
    """
    from datetime import date as _date, timedelta as _timedelta
    from calendar import monthrange as _monthrange
    from app.services.openmeteo_client import OpenMeteoClient
    from app.models.environmental_data import EnvironmentalData

    coords = OpenMeteoClient.lookup_coords(province)
    if not coords:
        raise HTTPException(
            status_code=400,
            detail=f"Không có toạ độ cho tỉnh/thành '{province}'. "
                   f"Thêm vào PROVINCE_COORDS trong openmeteo_client.py.",
        )
    lat, lon = coords

    client = OpenMeteoClient()

    # Bước 1: Historical — group theo (year, month)
    today = _date.today()
    earliest = (today.replace(day=1) - _timedelta(days=1)).replace(day=1)  # tháng trước
    for _ in range(months_back - 1):
        earliest = (earliest - _timedelta(days=1)).replace(day=1)

    historical_end = today - _timedelta(days=1)
    if historical_end < earliest:
        historical_end = earliest

    try:
        historical_rows = client.get_historical_daily(lat, lon, earliest, historical_end)
    except Exception as exc:
        logger.error("Open-Meteo archive fetch failed: %s", exc)
        historical_rows = []

    # Bước 2: Forecast (16-day daily)
    try:
        forecast_rows = client.get_daily_forecast(lat, lon, forecast_days=forecast_days)
    except Exception as exc:
        logger.error("Open-Meteo forecast fetch failed: %s", exc)
        forecast_rows = []

    # Bước 3: Air quality - dùng historical API để lấy toàn bộ data
    # Lấy AQI/PM2.5 cho cùng khoảng thời gian với weather historical
    try:
        # Historical AQI/PM2.5
        aq_rows = client.get_air_quality_historical(lat, lon, earliest, historical_end)
    except Exception as exc:
        logger.warning("Open-Meteo air-quality historical fetch failed: %s", exc)
        aq_rows = []
    
    # Forecast AQI/PM2.5 (5 ngày)
    try:
        aq_forecast = client.get_air_quality_daily(lat, lon, forecast_days=5, past_days=0)
        aq_rows.extend(aq_forecast)
    except Exception as exc:
        logger.warning("Open-Meteo air-quality forecast fetch failed: %s", exc)

    # Build map ngày → AQI cho merge
    aq_map = {r["date"]: r for r in aq_rows}

    # Merge tất cả rows + augment AQI nếu có
    all_rows = historical_rows + forecast_rows
    monthly: dict[tuple[int, int], dict] = {}
    for r in all_rows:
        d_str = r.get("date")
        if not d_str:
            continue
        try:
            y, m, _ = d_str.split("-")
            year, month = int(y), int(m)
        except Exception:
            continue
        bucket = monthly.setdefault((year, month), {
            "temps": [],
            "hums": [],
            "rains": [],
            "aqis": [],
            "pm25s": [],
        })
        if r.get("temperature") is not None:
            bucket["temps"].append(r["temperature"])
        if r.get("humidity") is not None:
            bucket["hums"].append(r["humidity"])
        if r.get("rainfall") is not None:
            bucket["rains"].append(r["rainfall"])
        # Augment AQI nếu có
        aq = aq_map.get(d_str)
        if aq:
            if aq.get("aqi") is not None:
                bucket["aqis"].append(aq["aqi"])
            if aq.get("pm25") is not None:
                bucket["pm25s"].append(aq["pm25"])

    imported = 0
    updated = 0
    months_summary: list[dict] = []

    for (year, month), b in sorted(monthly.items()):
        recorded_at = datetime(year, month, 1)
        temp = round(sum(b["temps"]) / len(b["temps"]), 2) if b["temps"] else None
        humidity = round(sum(b["hums"]) / len(b["hums"]), 2) if b["hums"] else None
        rainfall = round(sum(b["rains"]), 2) if b["rains"] else None
        aqi = int(round(sum(b["aqis"]) / len(b["aqis"]))) if b["aqis"] else None
        pm25 = round(sum(b["pm25s"]) / len(b["pm25s"]), 2) if b["pm25s"] else None

        existing = (
            db.query(EnvironmentalData)
            .filter(
                EnvironmentalData.recorded_at == recorded_at,
                EnvironmentalData.location == province,
                EnvironmentalData.district_ward.is_(None),
            )
            .first()
        )

        if existing:
            existing.temperature = temp
            existing.humidity = humidity
            existing.rainfall = rainfall
            if aqi is not None:
                existing.air_quality_index = aqi
            if pm25 is not None:
                existing.pm25 = pm25
            existing.data_source = "open-meteo"
            updated += 1
        else:
            db.add(EnvironmentalData(
                recorded_at=recorded_at,
                location=province,
                district_ward=None,
                temperature=temp,
                humidity=humidity,
                rainfall=rainfall,
                air_quality_index=aqi,
                pm25=pm25,
                data_source="open-meteo",
            ))
            imported += 1

        months_summary.append({
            "year": year,
            "month": month,
            "temperature": temp,
            "humidity": humidity,
            "rainfall": rainfall,
            "aqi": aqi,
            "pm25": pm25,
            "days_aggregated": len(b["temps"]),
        })

    db.commit()

    logger.info(
        "Open-Meteo sync by user=%s province=%s: imported=%d updated=%d months=%d",
        current_user.username, province, imported, updated, len(months_summary),
    )

    return {
        "status": "ok",
        "province": province,
        "lat": lat,
        "lon": lon,
        "imported": imported,
        "updated": updated,
        "total_months": len(months_summary),
        "historical_days": len(historical_rows),
        "forecast_days": len(forecast_rows),
        "air_quality_days": len(aq_rows),
        "months": months_summary,
    }


@router.get("/openmeteo/forecast")
def openmeteo_forecast_preview(
    province: str = Query("TP. Hồ Chí Minh"),
    days: int = Query(7, ge=1, le=16),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview forecast Open-Meteo cho N ngày tới — KHÔNG ghi DB."""
    from app.services.openmeteo_client import OpenMeteoClient

    coords = OpenMeteoClient.lookup_coords(province)
    if not coords:
        raise HTTPException(status_code=400, detail=f"Unknown province: {province}")
    lat, lon = coords

    client = OpenMeteoClient()
    try:
        forecast = client.get_daily_forecast(lat, lon, forecast_days=days)
        air = client.get_air_quality_daily(lat, lon, forecast_days=min(days, 5))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Open-Meteo error: {exc}")

    aq_map = {a["date"]: a for a in air}
    enriched = []
    for d in forecast:
        merged = dict(d)
        aq = aq_map.get(d["date"])
        if aq:
            merged["aqi"] = aq.get("aqi")
            merged["pm25"] = aq.get("pm25")
        enriched.append(merged)

    return {
        "province": province,
        "lat": lat,
        "lon": lon,
        "forecast_days": len(forecast),
        "items": enriched,
    }
