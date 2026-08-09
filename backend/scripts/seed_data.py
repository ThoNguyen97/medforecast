"""Seed script for initial data."""
import logging
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.user import User
from app.core.security import get_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_initial_admin():
    """Create initial admin user if it doesn't exist."""
    db: Session = SessionLocal()
    
    try:
        # Check if admin user already exists
        admin_user = db.query(User).filter(User.username == "admin").first()
        
        if admin_user:
            logger.info("Admin user already exists")
            return
        
        # Create admin user
        admin_password = "admin123"  # Default password - should be changed after first login
        password_hash = get_password_hash(admin_password)
        
        admin_user = User(
            username="admin",
            email="admin@medforecast.com",
            password_hash=password_hash,
            full_name="System Administrator",
            role="Administrator",
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        logger.info(f"Created admin user: {admin_user.username} (ID: {admin_user.id})")
        logger.info("Default password: admin123 (Please change after first login)")
        
    except Exception as e:
        logger.error(f"Failed to create admin user: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def create_sample_users():
    """Create sample users for testing."""
    db: Session = SessionLocal()
    
    try:
        # Sample pharmacist
        pharmacist = db.query(User).filter(User.username == "pharmacist").first()
        if not pharmacist:
            pharmacist = User(
                username="pharmacist",
                email="pharmacist@medforecast.com",
                password_hash=get_password_hash("pharmacist123"),
                full_name="Dr. Nguyen Van A",
                role="Pharmacist",
                is_active=True
            )
            db.add(pharmacist)
            logger.info("Created sample pharmacist user")
        
        # Sample inventory manager
        inventory_manager = db.query(User).filter(User.username == "inventory_manager").first()
        if not inventory_manager:
            inventory_manager = User(
                username="inventory_manager",
                email="inventory@medforecast.com",
                password_hash=get_password_hash("inventory123"),
                full_name="Tran Thi B",
                role="Inventory_Manager",
                is_active=True
            )
            db.add(inventory_manager)
            logger.info("Created sample inventory manager user")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Failed to create sample users: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """Main function to run all seed operations."""
    logger.info("Starting seed data creation...")
    
    try:
        # Create initial admin user
        create_initial_admin()
        
        # Create sample users for testing
        create_sample_users()
        
        logger.info("Seed data creation completed successfully!")
        
    except Exception as e:
        logger.error(f"Seed data creation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()