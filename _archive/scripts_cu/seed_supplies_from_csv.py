"""Bulk import all unique supplies from CSV files into medical_supplies + inventory.

- Tạo record MedicalSupply cho mỗi DrugName chưa có trong DB.
- Tạo record Inventory với current_stock=0 cho mỗi supply chưa có inventory.
- Idempotent: chạy lại nhiều lần không tạo trùng.
"""

from pathlib import Path
import pandas as pd

from app.database import SessionLocal
from app.models.inventory import Inventory
from app.models.medical_supply import MedicalSupply

CSV_DIR = Path("/Users/nguyenminhhieu/Desktop/webyte")
CSV_FILES = [
    "data.csv",
    "data_HM_2025_1.csv",
    "data_HM_2025_2.csv",
    "data_HM_2026_1.csv",
    "data_test.csv",
]


def _category_from_drug_category(value: str) -> str:
    """Map DrugCategory tiếng Việt → category tiếng Anh ngắn."""
    if not value:
        return "general"
    low = value.lower()
    if "vật tư" in low or "vtyt" in low or low.startswith("vt"):
        return "consumable"
    if "thuốc" in low:
        return "drug"
    return "general"


def main() -> None:
    rows: list[dict] = []
    for fname in CSV_FILES:
        path = CSV_DIR / fname
        if not path.exists():
            continue
        try:
            df = pd.read_csv(
                path,
                usecols=["DrugName", "UnitOfMeasure", "DrugCategory"],
                dtype=str,
                low_memory=False,
            )
        except ValueError:
            df = pd.read_csv(path, low_memory=False)
            if "DrugName" not in df.columns:
                continue

        df = df.dropna(subset=["DrugName"])
        df["DrugName"] = df["DrugName"].str.strip()
        df = df.drop_duplicates(subset=["DrugName"])
        for _, r in df.iterrows():
            rows.append(
                {
                    "name": r["DrugName"],
                    "unit": (r.get("UnitOfMeasure") or "").strip(),
                    "category": _category_from_drug_category(
                        str(r.get("DrugCategory") or "")
                    ),
                }
            )

    # Dedupe by name
    seen: dict[str, dict] = {}
    for row in rows:
        seen.setdefault(row["name"], row)

    print(f"Tổng số vật tư duy nhất từ CSV: {len(seen):,}")

    db = SessionLocal()
    try:
        existing_names = {row[0] for row in db.query(MedicalSupply.name).all()}
        new_supplies = 0
        new_inventory = 0
        for name, info in seen.items():
            if name in existing_names:
                supply = (
                    db.query(MedicalSupply)
                    .filter(MedicalSupply.name == name)
                    .first()
                )
            else:
                supply = MedicalSupply(
                    name=name,
                    category=info["category"],
                    unit=info["unit"] or "Cái",
                    description="Auto-imported from CSV bulk seed",
                )
                db.add(supply)
                db.flush()
                new_supplies += 1

            # Ensure inventory row exists
            has_inv = (
                db.query(Inventory.id)
                .filter(Inventory.supply_id == supply.id)
                .first()
                is not None
            )
            if not has_inv:
                db.add(
                    Inventory(
                        supply_id=supply.id,
                        current_stock=0,
                        safety_stock=0,
                    )
                )
                new_inventory += 1

        db.commit()
        print(f"Đã thêm mới {new_supplies} medical_supplies")
        print(f"Đã thêm mới {new_inventory} inventory rows (stock=0)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
