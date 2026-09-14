"""
Script sinh dữ liệu giả cho các tháng đầu năm 2023 (01-09/2023 + 11/2023)
Dựa trên pattern từ file HMSG_2023_2026.csv hiện có
"""
import csv
import random
from datetime import datetime

# Đọc dữ liệu mẫu từ file gốc
SOURCE_FILE = "/Users/nguyenminhhieu/Desktop/webyte/test_data/HMSG_2023_2026.csv"
OUTPUT_FILE = "/Users/nguyenminhhieu/Desktop/webyte/test_data/HMSG_2023_EARLY.csv"

def read_sample_data():
    """Đọc dữ liệu mẫu từ tháng 10/2023"""
    samples = []
    with open(SOURCE_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('month') == '10/2023':
                samples.append(row)
    return samples

def generate_month_data(samples, month, year):
    """Sinh dữ liệu cho 1 tháng dựa trên mẫu"""
    month_data = []
    
    # Random chọn ~80% số lượng records từ mẫu
    num_records = int(len(samples) * random.uniform(0.7, 0.9))
    selected_samples = random.sample(samples, num_records)
    
    for sample in selected_samples:
        new_row = sample.copy()
        # Đổi tháng
        new_row['month'] = f"{month:02d}/{year}"
        
        # Random số ca bệnh (±20%)
        try:
            original_cases = int(float(sample['cases']))
            variation = random.uniform(0.8, 1.2)
            new_cases = max(1, int(original_cases * variation))
            new_row['cases'] = str(new_cases)
        except:
            pass
        
        # Random số lượng thuốc (±30%)
        try:
            if sample.get('supply_quantity'):
                original_qty = float(sample['supply_quantity'])
                variation = random.uniform(0.7, 1.3)
                new_qty = max(0.5, original_qty * variation)
                new_row['supply_quantity'] = f"{new_qty:.1f}"
        except:
            pass
        
        month_data.append(new_row)
    
    return month_data

def main():
    print("🔧 Sinh dữ liệu cho các tháng đầu năm 2023...")
    
    # Đọc mẫu
    print("📂 Đọc dữ liệu mẫu từ 10/2023...")
    samples = read_sample_data()
    print(f"✓ Đọc được {len(samples)} records mẫu")
    
    # Sinh dữ liệu cho các tháng thiếu
    missing_months = [
        (1, 2023), (2, 2023), (3, 2023), (4, 2023), (5, 2023),
        (6, 2023), (7, 2023), (8, 2023), (9, 2023), (11, 2023)
    ]
    
    all_data = []
    
    for month, year in missing_months:
        print(f"📅 Sinh dữ liệu cho {month:02d}/{year}...")
        month_data = generate_month_data(samples, month, year)
        all_data.extend(month_data)
        print(f"  → {len(month_data)} records")
    
    # Ghi ra file
    print(f"\n💾 Ghi vào file: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        if all_data:
            fieldnames = all_data[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_data)
    
    print(f"✅ Hoàn tất! Tổng cộng {len(all_data)} records")
    print(f"\n📥 Bạn có thể import file này vào hệ thống:")
    print(f"   {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
