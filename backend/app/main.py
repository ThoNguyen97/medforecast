"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Nạp .env vào os.environ để các biến PIPELINE_* (nguồn đồng bộ HIS) dùng được.
load_dotenv()

from app.config import settings
from app.core.logging import setup_logging
from app.database import Base, engine

# ── Logging ──────────────────────────────────────────────────────────────────
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# ── Database ──────────────────────────────────────────────────────────────────
# Import all models so SQLAlchemy registers them before create_all
import app.models  # noqa: F401, E402

Base.metadata.create_all(bind=engine)
logger.info("Database tables verified / created.")

# DATABASE_URL là đường dẫn TƯƠNG ĐỐI theo thư mục làm việc, và _ensure_db_dir()
# còn tự mkdir — chạy uvicorn từ thư mục khác backend/ là âm thầm dùng một file DB
# khác mà không có lỗi nào. In đường dẫn tuyệt đối để không bao giờ phải đoán nữa.
if settings.DATABASE_URL.startswith("sqlite:///"):
    from pathlib import Path as _Path
    _db = _Path(settings.DATABASE_URL[len("sqlite:///"):]).resolve()
    logger.info("SQLite đang dùng: %s (tồn tại=%s, %s bytes) — CWD=%s",
                _db, _db.exists(), _db.stat().st_size if _db.exists() else 0,
                _Path.cwd())

# Hợp nhất nguồn dữ liệu: tạo luôn bảng tầng dữ liệu (mart/fact) trong CÙNG DB app.
try:
    from app.data_pipeline.db import init_db as _pipeline_init_db
    _pipeline_init_db()
    logger.info("Data-pipeline (mart) tables verified / created.")
except Exception as _e:  # noqa: BLE001
    logger.warning("Pipeline table init skipped (non-fatal): %s", _e)

# Lược đồ ngoài ORM (6 bảng tự quản, 2 dòng cấu hình DSS, 4 view): create_all
# không biết tới chúng; thiếu view thì Tầng 2/3 mù mà không ném lỗi. Idempotent.
try:
    from app.data_pipeline.views import dam_bao_luoc_do as _dam_bao
    _kq = _dam_bao()
    _xong = ("đã tạo", "đã gieo", "đã có")
    _da = [k for k, v in _kq.items() if v in _xong]
    _bo = {k: v for k, v in _kq.items() if v not in _xong}
    logger.info("Lược đồ ngoài ORM: %d/%d mục sẵn sàng %s", len(_da), len(_kq),
                ("— chờ dữ liệu: %s" % _bo) if _bo else "")
except Exception as _e:  # noqa: BLE001
    logger.warning("Bỏ qua dựng lược đồ ngoài ORM (non-fatal): %s", _e)

# ── Application ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: run startup logic then yield."""
    # Startup: run log retention cleanup once (non-fatal if it fails)
    try:
        from app.database import SessionLocal
        from app.services.audit_log_service import AuditLogService

        db = SessionLocal()
        try:
            service = AuditLogService(db)
            result = service.delete_old_logs()
            logger.info(
                "Startup log cleanup: audit_deleted=%d system_deleted=%d",
                result["audit_logs_deleted"],
                result["system_logs_deleted"],
            )
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Startup log cleanup failed (non-fatal): %s", exc)

    yield
    # Shutdown: nothing to do


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="AI-powered medical supply forecasting system for hospitals",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("CORS configured for origins: %s", settings.cors_origins_list)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["root"])
async def root():
    """Root endpoint — basic service info."""
    return {
        "message": "MedForecast AI - Medical Supply Forecasting System",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "medforecast-api",
        "version": settings.VERSION,
    }


# ── API Routes ────────────────────────────────────────────────────────────────
# Router đã archive (xem _archive/README.md): alerts, supply_recommendations,
# admin_severity, supply_plan, forecast_hier, supplies.
from app.api.v1 import (auth, users, inventory, environmental, disease_cases,
                        supply_requirements, dashboard, reports, config, audit_logs,
                        forecast_analysis, admin_catalog, sync, dss_config)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["inventory"])
app.include_router(environmental.router, prefix="/api/v1/environmental", tags=["environmental-data"])
app.include_router(disease_cases.router, prefix="/api/v1/disease-cases", tags=["disease-cases"])
app.include_router(supply_requirements.router, prefix="/api/v1/supply-requirements", tags=["supply-requirements"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(config.router, prefix="/api/v1/config", tags=["configuration"])
app.include_router(audit_logs.router, prefix="/api/v1", tags=["audit-logs"])
app.include_router(forecast_analysis.router, prefix="/api/v1/forecast", tags=["forecast-analysis"])
app.include_router(admin_catalog.router, prefix="/api/v1/admin", tags=["admin-catalog"])
app.include_router(sync.router, prefix="/api/v1/sync", tags=["data-sync"])
app.include_router(dss_config.router, prefix="/api/v1/dss", tags=["dss-config"])
