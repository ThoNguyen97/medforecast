"""Add new columns (pm25, district_ward) to environmental_data if missing."""
from sqlalchemy import text
from app.database import engine


def main() -> None:
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info('environmental_data')")).all()
        existing = {row[1] for row in rows}
        if "pm25" not in existing:
            conn.execute(text("ALTER TABLE environmental_data ADD COLUMN pm25 NUMERIC(7,2)"))
            print("Added column: pm25")
        if "district_ward" not in existing:
            conn.execute(text("ALTER TABLE environmental_data ADD COLUMN district_ward VARCHAR(100)"))
            print("Added column: district_ward")
        print("Migration done.")


if __name__ == "__main__":
    main()
