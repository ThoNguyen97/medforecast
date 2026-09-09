"""Script để seed dữ liệu 4 bệnh hô hấp và 15 thuốc/vật tư vào database."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import MedicalSupply, SeverityRate, DiseaseSupplyNorm
from app.seed_data import DISEASES, SEVERITY_RATES, MEDICAL_SUPPLIES, DISEASE_SUPPLY_NORMS


def create_tables():
    """Tạo tất cả các bảng trong database."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Tables created successfully")


def seed_severity_rates(db: Session):
    """Seed tỷ lệ mức độ cho 4 bệnh."""
    print("\nSeeding severity rates...")
    
    for rate_data in SEVERITY_RATES:
        existing = db.query(SeverityRate).filter(
            SeverityRate.icd_code == rate_data["icd_code"]
        ).first()
        
        if existing:
            print(f"  - Updating {rate_data['icd_code']}: {rate_data['disease_name']}")
            for key, value in rate_data.items():
                setattr(existing, key, value)
        else:
            print(f"  - Creating {rate_data['icd_code']}: {rate_data['disease_name']}")
            severity_rate = SeverityRate(**rate_data)
            db.add(severity_rate)
    
    db.commit()
    print("✓ Severity rates seeded successfully")


def seed_medical_supplies(db: Session):
    """Seed 15 thuốc/vật tư."""
    print("\nSeeding medical supplies...")
    
    for supply_data in MEDICAL_SUPPLIES:
        existing = db.query(MedicalSupply).filter(
            MedicalSupply.supply_code == supply_data["supply_code"]
        ).first()
        
        if existing:
            print(f"  - Updating {supply_data['supply_code']}: {supply_data['ten_hoat_chat']}")
            for key, value in supply_data.items():
                setattr(existing, key, value)
        else:
            print(f"  - Creating {supply_data['supply_code']}: {supply_data['ten_hoat_chat']}")
            supply = MedicalSupply(**supply_data)
            db.add(supply)
    
    db.commit()
    print("✓ Medical supplies seeded successfully")


def seed_disease_supply_norms(db: Session):
    """Seed định mức thuốc/vật tư theo bệnh và mức độ."""
    print("\nSeeding disease supply norms...")
    
    # Get supply_id mapping
    supplies = db.query(MedicalSupply).all()
    supply_map = {s.supply_code: s.id for s in supplies}
    
    # Get disease names
    severity_rates = db.query(SeverityRate).all()
    disease_map = {sr.icd_code: sr.disease_name for sr in severity_rates}
    
    count = 0
    for icd_code, severity, supply_code, quantity in DISEASE_SUPPLY_NORMS:
        supply_id = supply_map.get(supply_code)
        disease_name = disease_map.get(icd_code)
        
        if not supply_id or not disease_name:
            print(f"  ! Skipping {icd_code}/{severity}/{supply_code}: supply or disease not found")
            continue
        
        existing = db.query(DiseaseSupplyNorm).filter(
            DiseaseSupplyNorm.icd_code == icd_code,
            DiseaseSupplyNorm.severity == severity,
            DiseaseSupplyNorm.supply_id == supply_id
        ).first()
        
        if existing:
            existing.quantity_per_case = quantity
            existing.disease_name = disease_name
        else:
            norm = DiseaseSupplyNorm(
                icd_code=icd_code,
                disease_name=disease_name,
                severity=severity,
                supply_id=supply_id,
                quantity_per_case=quantity
            )
            db.add(norm)
        count += 1
    
    db.commit()
    print(f"✓ {count} disease supply norms seeded successfully")


def main():
    """Main function."""
    print("=" * 60)
    print("SEED DATA: 4 Bệnh Hô Hấp + 15 Thuốc/Vật Tư")
    print("=" * 60)
    
    # Create tables
    create_tables()
    
    # Seed data
    db = SessionLocal()
    try:
        seed_severity_rates(db)
        seed_medical_supplies(db)
        seed_disease_supply_norms(db)
        
        print("\n" + "=" * 60)
        print("✓ ALL DATA SEEDED SUCCESSFULLY!")
        print("=" * 60)
        
        # Print summary
        print("\nSummary:")
        print(f"  - Diseases: {db.query(SeverityRate).count()}")
        print(f"  - Medical Supplies: {db.query(MedicalSupply).count()}")
        print(f"  - Disease Supply Norms: {db.query(DiseaseSupplyNorm).count()}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
