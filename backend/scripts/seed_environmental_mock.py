"""Seed mock environmental data đúng theo Smart Medical design.

Bao gồm:
- 24 bản ghi đa khu vực (Quận 1, Quận 7, Thành phố Thủ Đức) qua nhiều tháng
- Nhiều năm cho cùng 1 tháng (để biểu đồ trend hiển thị đẹp)
"""
from datetime import datetime
from app.database import SessionLocal
from app.models.environmental_data import EnvironmentalData

PROVINCE = "TP. Hồ Chí Minh"

# (year, month, district, temp, humidity, rainfall, aqi, pm25)
ROWS = [
    # Tháng 6 qua các năm — dùng cho biểu đồ trend
    (2023, 6, "Quận 1", 31.5, 72, 78.0, 45, 14.0),
    (2023, 6, "Quận 7", 30.8, 75, 95.0, 60, 20.0),
    (2024, 6, "Quận 1", 32.8, 75, 120.0, 65, 22.0),
    (2024, 6, "Quận 7", 31.5, 78, 145.0, 80, 28.0),
    (2024, 6, "Thành phố Thủ Đức", 33.0, 73, 90.0, 105, 40.0),
    (2025, 6, "Quận 1", 32.5, 78, 80.0, 80, 25.0),
    (2025, 6, "Quận 7", 31.7, 76, 110.0, 90, 30.0),
    (2025, 6, "Thành phố Thủ Đức", 33.4, 72, 75.0, 130, 45.0),
    (2026, 6, "Quận 1", 33.0, 80, 60.0, 95, 32.0),
    (2026, 6, "Quận 7", 32.0, 79, 90.0, 100, 35.0),
    (2026, 6, "Thành phố Thủ Đức", 33.8, 74, 70.0, 155, 48.0),
    # Tháng 5/2026 (theo screenshot)
    (2026, 5, "Quận 1", 32.5, 75, 120.5, 45, 12.4),
    (2026, 5, "Quận 7", 31.8, 78, 145.2, 85, 28.5),
    (2026, 5, "Thành phố Thủ Đức", 33.2, 72, 85.0, 112, 45.2),
    # Tháng 4/2026
    (2026, 4, "Quận 1", 34.1, 68, 45.5, 65, 22.1),
    (2026, 4, "Quận 7", 33.5, 70, 60.2, 48, 14.5),
    (2026, 4, "Thành phố Thủ Đức", 34.5, 65, 38.0, 90, 35.0),
    # Tháng 3/2026
    (2026, 3, "Quận 1", 32.8, 60, 12.0, 70, 26.0),
    (2026, 3, "Quận 7", 32.4, 62, 18.0, 55, 18.0),
    # Tháng 2/2026
    (2026, 2, "Quận 1", 30.0, 55, 8.0, 50, 15.0),
    (2026, 2, "Thành phố Thủ Đức", 30.8, 58, 5.0, 85, 30.0),
    # Tháng 1/2026
    (2026, 1, "Quận 1", 28.5, 58, 6.0, 40, 12.0),
    (2026, 1, "Quận 7", 28.8, 60, 10.0, 45, 14.0),
    (2026, 1, "Thành phố Thủ Đức", 29.2, 56, 4.0, 75, 28.0),
]


def main() -> None:
    db = SessionLocal()
    try:
        added = 0
        updated = 0
        for y, m, dist, temp, hum, rain, aqi, pm25 in ROWS:
            recorded_at = datetime(y, m, 1)
            existing = (
                db.query(EnvironmentalData)
                .filter(
                    EnvironmentalData.recorded_at == recorded_at,
                    EnvironmentalData.location == PROVINCE,
                    EnvironmentalData.district_ward == dist,
                )
                .first()
            )
            values = dict(
                recorded_at=recorded_at,
                location=PROVINCE,
                district_ward=dist,
                temperature=temp,
                humidity=hum,
                rainfall=rain,
                air_quality_index=aqi,
                pm25=pm25,
                data_source="mock_seed",
            )
            if existing:
                for k, v in values.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(EnvironmentalData(**values))
                added += 1
        db.commit()
        print(f"Mock environmental data: added={added} updated={updated}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
