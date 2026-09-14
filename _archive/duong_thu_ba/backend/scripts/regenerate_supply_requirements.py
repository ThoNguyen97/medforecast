"""
Regenerate supply requirements for existing forecasts.

This script re-creates SupplyRequirement records for all existing DiseaseForecast
records using the current disease_supply_norms configuration.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.disease_forecast import DiseaseForecast
from app.services.supply_requirement_service import SupplyRequirementService

def regenerate_all_requirements():
    """Regenerate supply requirements for all existing forecasts."""
    db = SessionLocal()
    
    try:
        # Get all forecasts
        forecasts = db.query(DiseaseForecast).order_by(
            DiseaseForecast.created_at.desc()
        ).all()
        
        if not forecasts:
            print("No forecasts found in database!")
            print("Please run forecast analysis first.")
            return
        
        print(f"Found {len(forecasts)} forecast records")
        
        service = SupplyRequirementService(db)
        
        total_created = 0
        for forecast in forecasts:
            print(f"\nProcessing forecast id={forecast.id}:")
            print(f"  Disease: {forecast.icd_code} ({forecast.disease_name})")
            print(f"  Location: {forecast.location or 'All regions'}")
            print(f"  Predicted cases: {forecast.predicted_cases}")
            print(f"  Forecast date: {forecast.forecast_date}")
            
            try:
                requirements = service.generate_requirements_for_forecast(forecast.id)
                print(f"  ✅ Created {len(requirements)} supply requirements")
                total_created += len(requirements)
            except Exception as e:
                print(f"  ❌ Error: {e}")
                continue
        
        print(f"\n{'='*60}")
        print(f"✅ Total supply requirements created: {total_created}")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    regenerate_all_requirements()
