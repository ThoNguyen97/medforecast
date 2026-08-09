"""Application configuration."""
from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # Database
    DATABASE_URL: str = "sqlite:///./data/medforecast.db"

    # Security
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Application
    APP_NAME: str = "MedForecast AI"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # CORS — stored as a plain string in .env; parsed into a list at runtime.
    # Use a comma-separated string in .env:
    #   CORS_ORIGINS=http://localhost:3000,http://localhost:5173
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @model_validator(mode="after")
    def _check_production_secret(self):
        """Chặn khởi động production nếu còn dùng SECRET_KEY mặc định."""
        default = "your-secret-key-change-this-in-production"
        if self.ENVIRONMENT.lower() == "production" and self.SECRET_KEY == default:
            raise ValueError(
                "SECRET_KEY phải được đặt riêng (khác giá trị mặc định) ở môi trường production."
            )
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS_ORIGINS as a list of stripped origin strings."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Redis — used for caching (dashboard) and as Celery broker/backend
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_URL: str = "redis://localhost:6379/1"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Cache TTL values (seconds)
    CACHE_TTL_DASHBOARD: int = 300   # 5 minutes for dashboard metrics
    CACHE_TTL_SHORT: int = 60        # 1 minute for frequently changing data

    # External APIs (Optional)
    OPENWEATHER_API_KEY: str = ""
    HEALTH_DEPT_API_URL: str = ""
    HEALTH_DEPT_API_KEY: str = ""

    # Email/SMS (Optional)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # Backup
    BACKUP_DIR: str = "/var/backups/medforecast"
    BACKUP_RETAIN_DAYS: int = 30

    # extra="ignore": .env còn chứa các biến PIPELINE_* (đọc trực tiếp từ os.environ,
    # không qua Settings) — pydantic-settings >=2.10 mặc định cấm biến lạ nên phải nới.
    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
