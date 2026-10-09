"""Tạo tài khoản quản trị mặc định (admin / admin123) nếu chưa tồn tại.

Chạy: cd backend && python scripts/create_admin_user.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash


def create_admin() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if existing:
            print(f"Tài khoản 'admin' đã tồn tại (email: {existing.email}, vai trò: {existing.role}).")
            return

        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=get_password_hash("admin123"),
            full_name="System Administrator",
            role="Administrator",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print("Đã tạo tài khoản admin / admin123: đổi mật khẩu sau lần đăng nhập đầu.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
