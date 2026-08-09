"""Resolve all alerts whose supply has no inventory record."""
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.alert import Alert
from app.models.inventory import Inventory


def main() -> None:
    db = SessionLocal()
    try:
        tracked_ids = {row[0] for row in db.query(Inventory.supply_id).distinct().all()}
        open_alerts = db.query(Alert).filter(Alert.is_resolved == False).all()  # noqa: E712
        now = datetime.now(timezone.utc)
        cleaned = 0
        for alert in open_alerts:
            if alert.supply_id not in tracked_ids:
                alert.is_resolved = True
                alert.resolved_at = now
                cleaned += 1
        db.commit()
        print(f"Cleaned {cleaned} orphan alerts (tracked supplies: {len(tracked_ids)})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
