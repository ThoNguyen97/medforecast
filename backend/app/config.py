"""Cấu hình ứng dụng, nạp từ biến môi trường và tệp .env."""
from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Tập tham số cấu hình ứng dụng (biến môi trường / .env)."""

    # ── CSDL ──
    DATABASE_URL: str = "sqlite:///./data/medforecast.db"

    # ── Bảo mật ──
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 giờ

    # ── Ứng dụng ──
    APP_NAME: str = "MedForecast AI"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    # SQL_ECHO in toàn bộ câu SQL ra log; tách khỏi DEBUG để bật DEBUG không làm
    # tệp log phình nhanh. Chỉ bật khi cần soi một truy vấn cụ thể.
    SQL_ECHO: bool = False
    LOG_LEVEL: str = "INFO"

    # CORS: chuỗi phân tách bằng dấu phẩy trong .env, tách thành list khi dùng.
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
        """Danh sách origin CORS đã tách và bỏ khoảng trắng."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # extra="ignore": .env còn chứa biến PIPELINE_* (đọc trực tiếp từ os.environ);
    # pydantic-settings >= 2.10 mặc định từ chối biến không khai báo.
    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
