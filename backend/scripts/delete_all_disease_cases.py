"""Script to delete all disease case data from database."""
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete
from app.database import SessionLocal, engine
from app.models.disease_case import DiseaseCase


def delete_all_disease_cases():
    """Delete all disease case records from the database."""
    db = SessionLocal()
    try:
        # Count records before deletion
        count_before = db.query(DiseaseCase).count()
        print(f"📊 Tìm thấy {count_before} bản ghi disease cases trong database")
        
        if count_before == 0:
            print("✅ Database đã trống, không có gì để xóa")
            return
        
        # Delete all records
        print("🗑️  Đang xóa tất cả dữ liệu bệnh...")
        stmt = delete(DiseaseCase)
        result = db.execute(stmt)
        db.commit()
        
        # Verify deletion
        count_after = db.query(DiseaseCase).count()
        print(f"✅ Đã xóa thành công {result.rowcount} bản ghi")
        print(f"📊 Số bản ghi còn lại: {count_after}")
        
        if count_after == 0:
            print("✨ Database disease cases đã được làm sạch hoàn toàn!")
        else:
            print(f"⚠️  Cảnh báo: Còn {count_after} bản ghi chưa được xóa")
            
    except Exception as e:
        print(f"❌ Lỗi khi xóa dữ liệu: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("🗑️  XÓA TOÀN BỘ DỮ LIỆU BỆNH")
    print("=" * 60)
    print()
    
    # Confirm before deletion
    confirm = input("⚠️  BẠN CÓ CHẮC CHẮN MUỐN XÓA TẤT CẢ DỮ LIỆU BỆNH? (yes/no): ")
    
    if confirm.lower() in ['yes', 'y']:
        delete_all_disease_cases()
    else:
        print("❌ Hủy bỏ thao tác xóa")
