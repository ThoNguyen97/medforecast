"""
Seed sample disease supply norms for testing.

Creates supply norms for 4 respiratory diseases (J01, J02, J06, J20)
with 3 severity levels (mild, moderate, severe) each.
"""
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.disease_supply_norm import DiseaseSupplyNorm
from app.models.medical_supply import MedicalSupply

def seed_disease_supply_norms():
    """Seed disease supply norms for 4 respiratory diseases."""
    db = SessionLocal()
    
    try:
        # Get some sample supplies from database
        supplies = db.query(MedicalSupply).limit(20).all()
        
        if not supplies:
            print("ERROR: No medical supplies found in database!")
            print("Please import supplies first using: python scripts/import_medical_supplies.py")
            return
        
        print(f"Found {len(supplies)} supplies in database")
        
        # Disease definitions
        diseases = [
            {"icd": "J01", "name": "Viêm xoang cấp"},
            {"icd": "J02", "name": "Viêm họng cấp"},
            {"icd": "J06", "name": "Nhiễm trùng đường hô hấp trên cấp"},
            {"icd": "J20", "name": "Viêm phế quản cấp"},
        ]
        
        severities = ["mild", "moderate", "severe"]
        
        # Clear existing norms
        deleted = db.query(DiseaseSupplyNorm).delete()
        print(f"Deleted {deleted} existing disease supply norms")
        
        created = 0
        
        # Create norms for each disease
        for disease in diseases:
            icd = disease["icd"]
            name = disease["name"]
            
            # Use first 5 supplies for each disease with different quantities
            for i, supply in enumerate(supplies[:5]):
                for severity in severities:
                    # Quantity increases with severity
                    base_qty = (i + 1) * 5
                    if severity == "mild":
                        qty = base_qty
                    elif severity == "moderate":
                        qty = base_qty * 2
                    else:  # severe
                        qty = base_qty * 3
                    
                    norm = DiseaseSupplyNorm(
                        icd_code=icd,
                        disease_name=name,
                        severity=severity,
                        supply_id=supply.id,
                        quantity_per_case=qty,
                        updated_by="system"
                    )
                    db.add(norm)
                    created += 1
        
        db.commit()
        print(f"\n✅ Successfully created {created} disease supply norms")
        print(f"   - {len(diseases)} diseases")
        print(f"   - 3 severity levels each (mild, moderate, severe)")
        print(f"   - 5 supplies per disease-severity combination")
        
        # Show sample
        print("\nSample norms created:")
        samples = db.query(DiseaseSupplyNorm).limit(5).all()
        for norm in samples:
            supply = db.query(MedicalSupply).filter(
                MedicalSupply.id == norm.supply_id
            ).first()
            supply_name = supply.name if supply else "Unknown"
            print(f"  {norm.icd_code} ({norm.disease_name}) - {norm.severity}: "
                  f"{norm.quantity_per_case} units of {supply_name}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_disease_supply_norms()
