#!/usr/bin/env python3
"""
Script tự động tạo alerts cho các vật tư thiếu hụt
"""

import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import engine
from app.models.alert import Alert
from app.models.inventory import Inventory
from app.models.medical_supply import MedicalSupply

def create_missing_alerts():
    print("=" * 80)
    print("TẠO ALERTS CHO VẬT TƯ THIẾU HỤT")
    print("=" * 80)
    
    with Session(engine) as db:
        # 1. Tìm tất cả vật tư thiếu hụt chưa có alert
        missing_alerts = db.execute(
            select(
                Inventory.id,
                Inventory.current_stock,
                Inventory.safety_stock,
                MedicalSupply.id.label('supply_id'),
                MedicalSupply.ten_hoat_chat,
                MedicalSupply.unit
            )
            .join(MedicalSupply, Inventory.supply_id == MedicalSupply.id)
            .outerjoin(
                Alert,
                (Alert.supply_id == MedicalSupply.id) & (Alert.is_resolved == False)
            )
            .where(
                Inventory.current_stock < Inventory.safety_stock,
                Alert.id.is_(None)
            )
        ).all()
        
        print(f"\n📊 Tìm thấy {len(missing_alerts)} vật tư thiếu hụt chưa có alert")
        
        if not missing_alerts:
            print(f"\n✅ Tất cả vật tư thiếu hụt đều đã có alerts!")
            return
        
        # 2. Tạo alerts
        print(f"\n🔄 Đang tạo alerts...")
        created_count = 0
        
        for inv_id, curr, safety, sid, name, unit in missing_alerts:
            shortage = safety - curr
            
            # Xác định severity
            if curr <= 0:
                severity = "critical"
            elif shortage > safety * 0.5:
                severity = "high"
            elif shortage > safety * 0.2:
                severity = "medium"
            else:
                severity = "low"
            
            # Tạo alert
            new_alert = Alert(
                supply_id=sid,
                alert_type="shortage",
                severity=severity,
                current_stock=curr,
                required_stock=safety,
                shortage_date=date.today(),
                message=f"Vật tư {name} ({unit}) thiếu hụt: còn {curr}/{safety}. Cần nhập thêm {shortage} {unit}.",
                is_resolved=False
            )
            
            db.add(new_alert)
            created_count += 1
            
            print(f"   {created_count}. [{severity.upper():8s}] {name[:40]}")
            print(f"      Tồn: {curr:,} / AT: {safety:,} / Thiếu: {shortage:,} {unit}")
        
        # 3. Commit
        db.commit()
        
        print(f"\n✅ Đã tạo {created_count} alerts mới!")
        
        # 4. Thống kê
        print(f"\n📈 THỐNG KÊ ALERTS SAU KHI TẠO:")
        total_alerts = db.scalar(select(func.count()).select_from(Alert))
        unresolved = db.scalar(
            select(func.count()).select_from(Alert).where(Alert.is_resolved == False)
        )
        
        print(f"   • Tổng số alerts: {total_alerts:,}")
        print(f"   • Chưa giải quyết: {unresolved:,}")
        
        by_severity = db.execute(
            select(Alert.severity, func.count(Alert.id))
            .where(Alert.is_resolved == False)
            .group_by(Alert.severity)
        ).all()
        
        print(f"\n   📊 Phân loại:")
        for sev, count in by_severity:
            print(f"      • {sev}: {count:,}")
    
    print(f"\n" + "=" * 80)
    print("HOÀN THÀNH")
    print("=" * 80)

# Import func
from sqlalchemy import func

if __name__ == "__main__":
    try:
        create_missing_alerts()
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
