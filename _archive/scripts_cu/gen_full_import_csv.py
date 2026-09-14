"""Tạo file CSV ĐẦY ĐỦ để test import: có cột chi tiết thuốc/vật tư.

Format khớp endpoint /disease-cases/import-csv (nhánh có supply_name):
    month, disease_name, region, district_ward, cases,
    supply_name, supply_quantity, supply_unit, supply_category, note

Logic import: các dòng cùng (month, disease, region, district) được GỘP thành
1 ca bệnh; case_count = max(cases); mỗi dòng có supply_name → 1 dòng chi tiết
thuốc (case_supply_usage).

File sinh ra: 4 bệnh × 6 tháng (01-06/2026) × nhiều thuốc/bệnh, ở TP.HCM/Quận 1.
Số lượng thuốc = round(cases × định mức trung bình mỗi ca) để giống thực tế.
"""
import csv
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "test_data",
                   "disease_cases_full_import.csv")

# (disease_name, base_cases theo tháng 1..6)
DISEASES = {
    "Viêm phế quản cấp": [180, 165, 145, 200, 220, 240],
    "Nhiễm trùng đường hô hấp trên cấp": [420, 380, 340, 360, 400, 450],
    "Viêm họng cấp": [320, 290, 260, 280, 300, 340],
    "Viêm xoang cấp": [150, 140, 130, 145, 160, 175],
}

# Thuốc dùng cho mỗi bệnh: (supply_name, unit, category, qty_per_case_avg)
SUPPLIES_BY_DISEASE = {
    "Viêm phế quản cấp": [
        ("Paracetamol", "Viên", "Thuốc hạ sốt giảm đau", 8),
        ("N-acetylcysteine", "Gói", "Thuốc long đờm", 6),
        ("Salbutamol + ipratropium", "Lọ", "Thuốc khí dung/giãn phế quản", 2),
        ("Budesonid", "Ống", "Corticoid khí dung", 2),
        ("Amoxicilin + acid clavulanic", "Viên", "Kháng sinh uống", 4),
        ("Natri clorid", "Chai", "Dung dịch/dịch truyền", 1),
        ("Bơm tiêm (syringe) dùng một lần các loại, các cỡ", "Cái", "Vật tư y tế", 1),
        ("Kim tiêm", "Cái", "Vật tư y tế", 1),
    ],
    "Nhiễm trùng đường hô hấp trên cấp": [
        ("Paracetamol", "Viên", "Thuốc hạ sốt giảm đau", 8),
        ("Fexofenadin", "Viên", "Kháng histamin", 6),
        ("N-acetylcysteine", "Gói", "Thuốc long đờm", 4),
        ("Vitamin C", "Viên", "Thuốc hỗ trợ", 7),
        ("Amoxicilin + acid clavulanic", "Viên", "Kháng sinh uống", 4),
        ("Methylprednisolon", "Lọ", "Kháng viêm corticosteroid", 1),
        ("Kim tiêm", "Cái", "Vật tư y tế", 1),
    ],
    "Viêm họng cấp": [
        ("Paracetamol", "Viên", "Thuốc hạ sốt giảm đau", 8),
        ("Fexofenadin", "Viên", "Kháng histamin", 5),
        ("Vitamin C", "Viên", "Thuốc hỗ trợ", 7),
        ("Amoxicilin + acid clavulanic", "Viên", "Kháng sinh uống", 4),
        ("Methylprednisolon", "Lọ", "Kháng viêm corticosteroid", 1),
        ("Kim tiêm", "Cái", "Vật tư y tế", 1),
    ],
    "Viêm xoang cấp": [
        ("Paracetamol", "Viên", "Thuốc hạ sốt giảm đau", 8),
        ("Fexofenadin", "Viên", "Kháng histamin", 6),
        ("N-acetylcysteine", "Gói", "Thuốc long đờm", 4),
        ("Amoxicilin + acid clavulanic", "Viên", "Kháng sinh uống", 5),
        ("Methylprednisolon", "Lọ", "Kháng viêm corticosteroid", 1),
        ("Natri clorid", "Chai", "Dung dịch/dịch truyền", 1),
    ],
}

REGION = "TP. Hồ Chí Minh"
DISTRICT = "Quận 1"
YEAR = 2026


def main():
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    rows = []
    for disease, monthly_cases in DISEASES.items():
        supplies = SUPPLIES_BY_DISEASE[disease]
        for m_idx, cases in enumerate(monthly_cases, start=1):
            month = f"{m_idx:02d}/{YEAR}"
            # Mỗi thuốc = 1 dòng; cùng (month, disease, region, district) sẽ gộp
            for (name, unit, category, qpc) in supplies:
                rows.append({
                    "month": month,
                    "disease_name": disease,
                    "region": REGION,
                    "district_ward": DISTRICT,
                    "cases": cases,
                    "supply_name": name,
                    "supply_quantity": cases * qpc,  # tổng dùng = số ca × định mức
                    "supply_unit": unit,
                    "supply_category": category,
                    "note": "",
                })

    fieldnames = ["month", "disease_name", "region", "district_ward", "cases",
                  "supply_name", "supply_quantity", "supply_unit",
                  "supply_category", "note"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"[done] wrote {len(rows)} rows to {os.path.abspath(OUT)}")
    cases_groups = len(DISEASES) * 6
    print(f"  = {len(DISEASES)} bệnh × 6 tháng = {cases_groups} ca bệnh")
    print(f"  + chi tiết thuốc trên mỗi ca")


if __name__ == "__main__":
    main()
