"""
Script import file HMSG_2023_2026.csv vào database qua API
"""
import requests
import os

# Cấu hình
API_URL = "http://localhost:8000/api/v1/disease-cases/import-csv"
CSV_FILE = "/Users/nguyenminhhieu/Desktop/webyte/test_data/HMSG_2023_2026.csv"

# Lấy token từ environment hoặc login
# Bạn cần thay thế bằng token thật từ login
USERNAME = os.getenv("API_USERNAME", "admin")
PASSWORD = os.getenv("API_PASSWORD", "admin123")

def login():
    """Login để lấy token"""
    login_url = "http://localhost:8000/api/v1/auth/login"
    
    try:
        response = requests.post(
            login_url,
            data={
                "username": USERNAME,
                "password": PASSWORD,
            }
        )
        response.raise_for_status()
        data = response.json()
        return data.get("access_token")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        print("\nVui lòng:")
        print("1. Kiểm tra backend đang chạy: http://localhost:8000")
        print("2. Đặt username/password đúng:")
        print("   export API_USERNAME=your_username")
        print("   export API_PASSWORD=your_password")
        return None

def import_csv(token):
    """Import CSV file"""
    print(f"📂 Đang import file: {CSV_FILE}")
    
    if not os.path.exists(CSV_FILE):
        print(f"❌ File không tồn tại: {CSV_FILE}")
        return
    
    # Đọc file
    with open(CSV_FILE, 'rb') as f:
        files = {'file': ('HMSG_2023_2026.csv', f, 'text/csv')}
        headers = {'Authorization': f'Bearer {token}'}
        
        try:
            print("⏳ Đang upload và xử lý... (có thể mất vài phút)")
            response = requests.post(
                API_URL,
                files=files,
                headers=headers,
                timeout=300  # 5 phút timeout
            )
            response.raise_for_status()
            
            result = response.json()
            print("\n✅ Import thành công!")
            print(f"  - Đã import: {result.get('imported', 0)} records")
            print(f"  - Đã cập nhật: {result.get('updated', 0)} records")
            print(f"  - Đã bỏ qua: {result.get('skipped', 0)} records")
            
            errors = result.get('errors', [])
            if errors:
                print(f"\n⚠️  Có {len(errors)} dòng lỗi:")
                for err in errors[:10]:
                    print(f"  Dòng {err.get('row')}: {err.get('reason')}")
                if len(errors) > 10:
                    print(f"  ... và {len(errors) - 10} lỗi khác")
            
            # Auto severity recompute
            auto_severity = result.get('auto_severity_recompute')
            if auto_severity:
                print(f"\n🔄 Auto severity recompute: {auto_severity.get('mode', 'unknown')}")
            
        except requests.exceptions.Timeout:
            print("❌ Timeout! File quá lớn hoặc server quá chậm.")
            print("   Thử tăng timeout hoặc chia nhỏ file.")
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            print(f"   Response: {e.response.text}")
        except Exception as e:
            print(f"❌ Error: {e}")

def main():
    print("🚀 HMSG CSV Import Script")
    print("=" * 50)
    
    # Login
    print("\n1️⃣ Đăng nhập...")
    token = login()
    if not token:
        return
    
    print("✓ Đăng nhập thành công!")
    
    # Import
    print("\n2️⃣ Import CSV...")
    import_csv(token)
    
    print("\n" + "=" * 50)
    print("✅ Hoàn tất!")

if __name__ == "__main__":
    main()
