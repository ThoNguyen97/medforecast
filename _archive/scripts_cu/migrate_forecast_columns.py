"""Add columns to disease_forecasts to support analysis & history."""
from sqlalchemy import text
from app.database import engine


COLS = [
    ("location", "VARCHAR(100)"),
    ("risk_level", "VARCHAR(20)"),
    ("baseline_cases", "INTEGER"),
    ("weather_factor", "NUMERIC(5,3)"),
    ("trend_factor", "NUMERIC(5,3)"),
    ("explanation", "VARCHAR(1000)"),
    ("actual_cases", "INTEGER"),
    ("deviation_pct", "NUMERIC(7,2)"),
    ("created_by", "VARCHAR(100)"),
]


def main() -> None:
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info('disease_forecasts')")).all()
        existing = {r[1] for r in rows}
        for name, type_ in COLS:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE disease_forecasts ADD COLUMN {name} {type_}"))
                print(f"Added column: {name}")
        print("Migration done.")


if __name__ == "__main__":
    main()
