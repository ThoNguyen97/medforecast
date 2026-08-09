"""Script to create admin user."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

def create_admin():
    """Create admin user with default credentials."""
    db = SessionLocal()
    try:
        # Check if admin already exists
        existing = db.query(User).filter(User.username == "admin").first()
        if existing:
            print("⚠️  User 'admin' already exists!")
            print(f"   Email: {existing.email}")
            print(f"   Role: {existing.role}")
            return
        
        # Create admin user
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=get_password_hash("admin123"),
            full_name="System Administrator",
            role="Administrator",
            is_active=True
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        print("✅ Admin user created successfully!")
        print(f"   Username: admin")
        print(f"   Password: admin123")
        print(f"   Email: {admin.email}")
        print(f"   Role: {admin.role}")
        print()
        print("⚠️  Please change the password after first login!")
        
    except Exception as e:
        print(f"❌ Error creating admin user: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
