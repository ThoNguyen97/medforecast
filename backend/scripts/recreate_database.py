"""Script to recreate database with new schema (without district_ward)."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Base, engine
from app.models import *  # Import all models

def recreate_database():
    """Drop all tables and recreate them."""
    print("🗑️  Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("✨ Creating new schema (without district_ward)...")
    Base.metadata.create_all(bind=engine)
    
    print("✅ Database recreated successfully!")
    print("📝 Note: All data has been deleted. You'll need to re-import your data.")

if __name__ == "__main__":
    recreate_database()
