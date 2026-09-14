"""
Import disease supply norms from HMSG_2023_2026.csv

Tính định mức thuốc cho mỗi bệnh dựa trên lịch sử sử dụng:
- Đọc file HMSG_2023_2026.csv
- Tính trung bình thuốc/ca bệnh cho mỗi loại bệnh
- Cập nhật bảng disease_supply_norm
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db
from app.models.disease_supply_norm import DiseaseSupplyNorm
from app.models.medical_supply import MedicalSupply


def main():
    csv_file = Path(__file__).parent.parent.parent / "test_data" / "HMSG_2023_2026.csv"
    
    if not csv_file.exists():
        print(f"❌ File không tồn tại: {csv_file}")
        return
    
    print(f"📖 Đọc file: {csv_file}")
    
    # Đọc CSV và group theo (disease_code, supply_code)
    # Key: (disease_code, supply_code)
    # Value: [list of quantities]
    usage_data = defaultdict(lambda: {
        'disease_name': '',
        'supply_name': '',
        'supply_unit': '',
        'quantities': [],
        'cases': []
    })
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            disease_code = row['disease_code'].strip()
            disease_name = row['disease_name'].strip()
            supply_code = row['supply_code'].strip()
            supply_name = row['supply_name'].strip()
            supply_unit = row.get('supply_unit', '').strip()
            
            try:
                quantity = int(float(row['supply_quantity']))
                cases = int(float(row['cases']))
            except (ValueError, KeyError):
                continue
            
            if quantity <= 0 or cases <= 0:
                continue
            
            key = (disease_code, supply_code)
            usage_data[key]['disease_name'] = disease_name
            usage_data[key]['supply_name'] = supply_name
            usage_data[key]['supply_unit'] = supply_unit
            usage_data[key]['quantities'].append(quantity)
            usage_data[key]['cases'].append(cases)
    
    print(f"✓ Đọc được {len(usage_data)} cặp (bệnh, thuốc) từ lịch sử")
    
    # Tính định mức trung bình
    norms = []
    for (disease_code, supply_code), data in usage_data.items():
        # Tính trung bình quantity per case
        total_quantity = sum(data['quantities'])
        total_cases = sum(data['cases'])
        
        if total_cases > 0:
            avg_per_case = round(total_quantity / total_cases, 2)
            
            norms.append({
                'disease_code': disease_code,
                'disease_name': data['disease_name'],
                'supply_code': supply_code,
                'supply_name': data['supply_name'],
                'supply_unit': data['supply_unit'],
                'quantity_per_case': avg_per_case
            })
    
    print(f"✓ Tính được {len(norms)} định mức thuốc")
    
    # Xem phân bố theo bệnh
    by_disease = defaultdict(list)
    for norm in norms:
        by_disease[norm['disease_code']].append(norm)
    
    print("\n📊 Phân bố định mức theo bệnh:")
    for disease_code, disease_norms in sorted(by_disease.items()):
        disease_name = disease_norms[0]['disease_name']
        print(f"  {disease_code} ({disease_name}): {len(disease_norms)} thuốc")
    
    # Confirm
    print(f"\n⚠️  Sẽ XÓA tất cả định mức cũ và tạo {len(norms)} định mức mới")
    confirm = input("Tiếp tục? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("❌ Đã hủy")
        return
    
    # Import vào database
    db = next(get_db())
    
    try:
        # 1. Xóa định mức cũ
        deleted = db.query(DiseaseSupplyNorm).delete()
        print(f"✓ Xóa {deleted} định mức cũ")
        
        # 2. Tạo định mức mới
        imported = 0
        skipped = 0
        
        for norm in norms:
            # Tìm supply trong medical_supplies
            supply = db.query(MedicalSupply).filter(
                MedicalSupply.supply_code == norm['supply_code']
            ).first()
            
            if not supply:
                # Tạo medical_supply mới nếu chưa có
                supply = MedicalSupply(
                    supply_code=norm['supply_code'],
                    drug_code=norm['supply_code'],
                    ten_hoat_chat=norm['supply_name'],
                    unit=norm['supply_unit'] or 'Cái',
                    group_name='Thuốc điều trị',
                    category='medicine'
                )
                db.add(supply)
                db.flush()
            
            # Tạo norm cho severity=mild (đơn giản hóa)
            db.add(DiseaseSupplyNorm(
                icd_code=norm['disease_code'],
                disease_name=norm['disease_name'],
                severity='mild',
                supply_id=supply.id,
                quantity_per_case=int(norm['quantity_per_case'])
            ))
            imported += 1
        
        db.commit()
        print(f"✓ Import {imported} định mức mới")
        print("✅ Hoàn tất!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Lỗi: {e}")
        raise


if __name__ == '__main__':
    main()
