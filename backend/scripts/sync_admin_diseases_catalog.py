"""Đồng bộ lại danh mục 'admin.diseases' (Danh mục bệnh) trong system_config
với danh sách 20 mã ICD thực tế đang phân tích.

Vì sao cần script này: app/api/v1/admin_catalog.py::_seed_diseases() chỉ
được dùng để KHỞI TẠO dòng system_config khi nó chưa tồn tại (_get_or_init).
Dòng admin.diseases trên DB hiện tại đã được tạo từ trước (với 4 mã cũ
J20/J06/J02/J01) nên sửa _seed_diseases() không tự cập nhật dữ liệu đã có —
cần patch trực tiếp dòng đã tồn tại.

Dùng sqlite3 chuẩn (không import FastAPI app) để không phụ thuộc venv của
backend — chỉ cần python3 có sẵn. Danh sách DISEASES bên dưới PHẢI khớp với
_seed_diseases() trong admin_catalog.py — nếu sau này sửa 1 bên, nhớ sửa bên kia.

Chạy 1 lần: python3 scripts/sync_admin_diseases_catalog.py
An toàn để chạy lại nhiều lần (idempotent — luôn ghi đè bằng danh sách này).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "medforecast.db"
DISEASES_KEY = "admin.diseases"

DISEASES = [
    {"key": "J00", "label": "Viêm mũi họng cấp tính [cảm thường]", "description": ""},
    {"key": "J01", "label": "Viêm xoang cấp tính", "description": "Acute sinusitis"},
    {"key": "J02", "label": "Viêm họng cấp tính", "description": "Acute pharyngitis"},
    {"key": "J03", "label": "Viêm amydan cấp tính", "description": ""},
    {"key": "J04", "label": "Viêm thanh quản và/hoặc khí quản cấp tính", "description": ""},
    {"key": "J05", "label": "Viêm thanh quản tắc nghẽn cấp tính [croup] và viêm nắp thanh quản", "description": ""},
    {"key": "J06", "label": "Nhiễm trùng đường hô hấp trên cấp tính ở nhiều vị trí và/hoặc vị trí không xác định", "description": "Acute upper respiratory infection"},
    {"key": "J09", "label": "Cúm do virus cúm động vật hoặc đại dịch đã xác định", "description": ""},
    {"key": "J10", "label": "Cảm cúm do virus cúm mùa đã xác định", "description": ""},
    {"key": "J11", "label": "Cúm, virus không được định danh", "description": ""},
    {"key": "J12", "label": "Viêm phổi do virus, không phân loại mục khác", "description": ""},
    {"key": "J13", "label": "Viêm phổi do vi khuẩn phế cầu khuẩn [Streptococcus pneumoniae]", "description": ""},
    {"key": "J14", "label": "Viêm phổi do Haemophilus influenzae", "description": ""},
    {"key": "J15", "label": "Viêm phổi do vi khuẩn, không phân loại mục khác", "description": ""},
    {"key": "J16", "label": "Viêm phổi do vi sinh vật truyền nhiễm khác, không phân loại mục khác", "description": ""},
    {"key": "J17", "label": "Viêm phổi do nhiễm nấm", "description": ""},
    {"key": "J18", "label": "Viêm phổi, tác nhân không xác định", "description": ""},
    {"key": "J20", "label": "Viêm phế quản cấp tính", "description": "Acute bronchitis"},
    {"key": "J21", "label": "Viêm tiểu phế quản cấp tính", "description": ""},
    {"key": "J22", "label": "Nhiễm khuẩn cấp đường hô hấp dưới không xác định", "description": ""},
]


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Không tìm thấy DB: {DB_PATH}")

    con = sqlite3.connect(str(DB_PATH))
    try:
        cur = con.cursor()
        new_value = json.dumps(DISEASES, ensure_ascii=False)
        cur.execute("SELECT config_value FROM system_config WHERE config_key = ?", (DISEASES_KEY,))
        row = cur.fetchone()
        if row:
            old_count = len(json.loads(row[0] or "[]"))
            cur.execute(
                "UPDATE system_config SET config_value = ? WHERE config_key = ?",
                (new_value, DISEASES_KEY),
            )
            print(f"Đã cập nhật '{DISEASES_KEY}': {old_count} -> {len(DISEASES)} bệnh.")
        else:
            cur.execute(
                "INSERT INTO system_config (config_key, config_value, description) VALUES (?, ?, ?)",
                (DISEASES_KEY, new_value, "Auto-created admin.diseases"),
            )
            print(f"Đã tạo mới '{DISEASES_KEY}' với {len(DISEASES)} bệnh.")
        con.commit()
    finally:
        con.close()


if __name__ == "__main__":
    main()
