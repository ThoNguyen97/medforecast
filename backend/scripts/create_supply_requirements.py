#!/usr/bin/env python3
"""
Script tạo supply requirements từ SupplyRecommendation
Tạo requirements cho 60 ngày tới để Dashboard có dữ liệu hiển thị
"""

import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import engine
from app.models.supply_recommendation import SupplyRecommendation
from app.models.supply_requirement import SupplyRequirement
from app.models.medical_supply import MedicalSupply

def create_supply_requirements():
    print("=" * 80)
    print("TẠO SUPPLY REQUIREMENTS TỪ DỰ BÁO")
    print("=" * 80)
    
    with Session(engine) as db:
        today = date.today()
        
        # 1. Kiểm tra SupplyRecommendation
        print(f"\n1️⃣ Kiểm tra SupplyRecommendation:")
        total_recommendations = db.scalar(select(func.count()).select_from(SupplyRecommendation))
        print(f"   • Tổng số recommendations: {total_recommendations:,}")
        
        if total_recommendations == 0:
            print(f"\n   ❌ Không có dữ liệu dự báo!")
            print(f"   💡 Vui lòng chạy dự báo trước:")
            print(f"      1. Vào trang 'Đề xuất nhập kho'")
            print(f"      2. Chọn tháng và % dự phòng")
            print(f"      3. Bấm 'Tính lại'")
            print(f"      4. Bấm 'Lưu kết quả vào DB'")
            return
        
        # 2. Lấy recommendations mới nhất (theo tháng)
        latest_month = db.scalar(
            select(func.max(SupplyRecommendation.forecast_month))
        )
        print(f"   • Tháng dự báo mới nhất: {latest_month}")
        
        recommendations = db.execute(
            select(
                SupplyRecommendation.supply_id,
                SupplyRecommendation.drug_code,
                SupplyRecommendation.predicted_need,
                MedicalSupply.ten_hoat_chat,
                MedicalSupply.unit
            )
            .join(MedicalSupply, SupplyRecommendation.supply_id == MedicalSupply.id)
            .where(SupplyRecommendation.forecast_month == latest_month)
            .group_by(
                SupplyRecommendation.supply_id,
                SupplyRecommendation.drug_code,
                MedicalSupply.ten_hoat_chat,
                MedicalSupply.unit
            )
        ).all()
        
        print(f"   • Số vật tư có dự báo: {len(recommendations)}")
        
        if len(recommendations) == 0:
            print(f"\n   ❌ Không tìm thấy recommendations cho tháng {latest_month}!")
            return
        
        # 3. Tính toán phân bổ requirements cho 60 ngày tới
        print(f"\n2️⃣ Tạo supply requirements cho 60 ngày tới:")
        print(f"   • Từ ngày: {today}")
        print(f"   • Đến ngày: {today + timedelta(days=60)}")
        
        # Xóa requirements cũ (nếu có) để tạo mới
        deleted_count = db.execute(
            select(func.count()).select_from(SupplyRequirement)
            .where(SupplyRequirement.requirement_date >= today)
        ).scalar()
        
        if deleted_count > 0:
            print(f"\n   🗑️  Xóa {deleted_count} requirements cũ...")
            db.query(SupplyRequirement).filter(
                SupplyRequirement.requirement_date >= today
            ).delete()
        
        # Tạo requirements mới
        created_count = 0
        total_quantity = 0
        
        # Phân bổ đều nhu cầu trong 60 ngày
        days = 60
        
        print(f"\n   🔄 Đang tạo requirements...")
        
        for supply_id, drug_code, predicted_need, name, unit in recommendations:
            # Phân bổ đều mỗi ngày
            daily_need = int(predicted_need / days) if predicted_need > 0 else 0
            
            if daily_need == 0:
                continue
            
            # Tạo requirement cho mỗi ngày
            for day_offset in range(days):
                req_date = today + timedelta(days=day_offset)
                
                new_req = SupplyRequirement(
                    supply_id=supply_id,
                    requirement_date=req_date,
                    required_quantity=daily_need
                )
                
                db.add(new_req)
                created_count += 1
                total_quantity += daily_need
        
        # Commit
        db.commit()
        
        print(f"\n✅ Đã tạo {created_count:,} supply requirements!")
        print(f"   • Tổng số lượng: {total_quantity:,}")
        print(f"   • Trung bình mỗi ngày: {total_quantity//days:,}")
        
        # 4. Thống kê
        print(f"\n3️⃣ THỐNG KÊ SAU KHI TẠO:")
        
        total_reqs = db.scalar(select(func.count()).select_from(SupplyRequirement))
        print(f"   • Tổng số requirements: {total_reqs:,}")
        
        future_reqs = db.scalar(
            select(func.count()).select_from(SupplyRequirement)
            .where(SupplyRequirement.requirement_date >= today)
        )
        print(f"   • Requirements tương lai (≥ hôm nay): {future_reqs:,}")
        
        # Top 5 vật tư có nhu cầu cao nhất
        end_60d = today + timedelta(days=60)
        top_demand = db.execute(
            select(
                MedicalSupply.ten_hoat_chat,
                MedicalSupply.unit,
                func.sum(SupplyRequirement.required_quantity).label('total_demand')
            )
            .join(MedicalSupply, SupplyRequirement.supply_id == MedicalSupply.id)
            .where(
                SupplyRequirement.requirement_date >= today,
                SupplyRequirement.requirement_date <= end_60d
            )
            .group_by(MedicalSupply.id, MedicalSupply.ten_hoat_chat, MedicalSupply.unit)
            .order_by(func.sum(SupplyRequirement.required_quantity).desc())
            .limit(5)
        ).all()
        
        print(f"\n   📊 Top 5 vật tư có nhu cầu cao nhất (60 ngày tới):")
        for name, unit, demand in top_demand:
            print(f"      • {name[:40]}: {demand:,} {unit}")
    
    print(f"\n" + "=" * 80)
    print("HOÀN THÀNH")
    print("=" * 80)
    print(f"\n💡 BÂY GIỜ:")
    print(f"   1. Vào Dashboard")
    print(f"   2. Bấm nút 'Làm mới'")
    print(f"   3. Biểu đồ 'Nhu cầu vs Tồn kho' sẽ hiển thị dữ liệu!")

if __name__ == "__main__":
    try:
        create_supply_requirements()
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
