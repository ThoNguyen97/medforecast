"""Xoá toàn bộ dữ liệu test/mock để có hệ thống sạch trước khi test lại.

GIỮ LẠI (cần để hệ thống hoạt động):
- Tài khoản trong bảng `users` (đặc biệt là admin)
- system_config: danh mục bệnh, khu vực, hệ số dự phòng, ngưỡng cảnh báo

XOÁ TẤT CẢ:
- disease_cases (Module 3)
- environmental_data (Module 4)
- disease_forecasts (Module 5)
- supply_requirements (cầu nối Module 5 ↔ 7)
- medical_supplies + inventory (Module 6)
- conversion_ratios (định mức theo bệnh — sẽ được tạo lại khi seed)
- alerts (Module 7)
- procurement_plans (Module 7)
- audit_logs + system_logs (lịch sử thao tác)

Cách dùng:
    cd backend
    venv/bin/python scripts/clear_test_data.py            # hỏi xác nhận
    venv/bin/python scripts/clear_test_data.py --yes      # bỏ qua xác nhận
    venv/bin/python scripts/clear_test_data.py --keep-users-extra
                                                          # giữ cả user khác ngoài admin
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.database import SessionLocal


# Thứ tự xoá: con → cha (để không vướng FK)
DELETE_ORDER = [
    # Logs trước
    ("audit_logs", "Nhật ký audit"),
    ("system_logs", "Nhật ký hệ thống"),
    # Cảnh báo + kế hoạch
    ("alerts", "Cảnh báo thiếu hụt"),
    ("procurement_plans", "Kế hoạch nhập kho"),
    # Yêu cầu vật tư
    ("supply_requirements", "Yêu cầu vật tư"),
    # Dự báo
    ("disease_forecasts", "Dự báo dịch bệnh"),
    # Inventory + Conversion Ratios (đều có FK → medical_supplies)
    ("inventory", "Tồn kho"),
    ("conversion_ratios", "Định mức vật tư"),
    # Master data vật tư
    ("medical_supplies", "Danh mục vật tư"),
    # Dữ liệu nhập tay
    ("disease_cases", "Dữ liệu ca bệnh"),
    ("environmental_data", "Dữ liệu thời tiết"),
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Xoá toàn bộ dữ liệu test/mock của hệ thống Smart Medical."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Bỏ qua xác nhận tương tác.",
    )
    parser.add_argument(
        "--keep-users-extra",
        action="store_true",
        help="Giữ tất cả user (mặc định: chỉ giữ admin, xoá pharmacist + inventory_manager seed).",
    )
    args = parser.parse_args()

    if not args.yes:
        print("=" * 60)
        print("CẢNH BÁO: Lệnh này sẽ XOÁ HẾT dữ liệu test trong DB.")
        print("=" * 60)
        print("Sẽ xoá các bảng:")
        for tbl, label in DELETE_ORDER:
            print(f"  - {tbl:25s} ({label})")
        print()
        print("Sẽ GIỮ:")
        print("  - users (tài khoản admin)")
        print("  - system_config (danh mục bệnh, khu vực, hệ số dự phòng, ngưỡng)")
        print()
        confirm = input("Gõ 'YES' để xác nhận: ").strip()
        if confirm != "YES":
            print("Đã huỷ.")
            sys.exit(0)

    db = SessionLocal()
    try:
        total_deleted = 0
        print("\nĐang xoá dữ liệu...")
        for tbl, label in DELETE_ORDER:
            try:
                # Đếm trước khi xoá
                count_result = db.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                count = count_result.scalar() or 0
                # Xoá
                db.execute(text(f"DELETE FROM {tbl}"))
                # Reset auto-increment cho SQLite (chỉ thử, không bắt buộc)
                try:
                    db.execute(
                        text(f"DELETE FROM sqlite_sequence WHERE name='{tbl}'")
                    )
                except Exception:
                    # SQLite chưa tạo sqlite_sequence (không có AUTOINCREMENT) — bỏ qua
                    pass
                print(f"  ✓ {tbl:25s} — đã xoá {count:,} dòng ({label})")
                total_deleted += count
            except Exception as exc:
                # Rollback transaction nếu lỗi để các lệnh sau không bị ảnh hưởng
                db.rollback()
                print(f"  ✗ {tbl:25s} — lỗi: {exc}")

        # Xoá user phụ (giữ admin)
        if not args.keep_users_extra:
            extra = db.execute(
                text("DELETE FROM users WHERE username != 'admin'")
            ).rowcount or 0
            print(f"  ✓ users (non-admin)        — đã xoá {extra} dòng")
            total_deleted += extra

        db.commit()
        print(f"\nTổng cộng đã xoá: {total_deleted:,} dòng.")
        print("\nHệ thống đã sạch — sẵn sàng để test lại theo 9 bước.")
        print("Đăng nhập: admin / admin123")
    except Exception as exc:
        db.rollback()
        print(f"\n✗ Lỗi: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
