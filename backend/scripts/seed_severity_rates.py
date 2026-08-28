#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seed mặc định cho bảng `severity_rates` (Tỷ lệ Nhẹ/TB/Nặng) trên máy mới.

VÌ SAO CẦN SCRIPT NÀY
File DB (backend/data/medforecast.db) bị .gitignore nên máy mới `git clone`
về sẽ có bảng severity_rates HOÀN TOÀN RỖNG — trang Quản trị → "Tỷ lệ
Nhẹ/TB/Nặng" không hiển thị dòng nào, và nút "Phân loại lại toàn bộ" cũng
không chạy được gì (code chỉ lặp qua các dòng ĐÃ CÓ SẴN trong bảng để tính
lại, xem SeverityInferenceService.update_severity_rates_from_history — bảng
rỗng thì không có gì để lặp).

Trước đây 3 dòng tỷ lệ nhóm được tạo bằng 2 script chạy tay một lần
(scripts/chuyen_dinh_muc_sang_nhom.py, scripts/sua_dinh_muc_nhom_v2.py — cần
dữ liệu ca bệnh lịch sử để gộp trọng số), nhưng bản thân 2 script đó cũng
chưa được commit, và đằng nào cũng không chạy được trên máy trắng chưa có
disease_cases. Script này thay vào đó SEED THẲNG 3 dòng bằng đúng giá trị
đang dùng chính thức trên môi trường hiện tại (xem NHOM_ICD trong
app/utils/icd_groups.py — 3 nhóm là danh mục cố định, đã backtest).

Lưu ý: dòng J09-J18 vẫn giữ nguyên ghi chú "NHÁP" như bản gốc — nhóm này
chưa có dữ liệu phân độ thực tế, Khoa Dược cần rà lại tại Quản trị → Tỷ lệ
Nhẹ/TB/Nặng trước khi dùng chính thức cho môi trường mới.

Idempotent: chỉ tạo dòng nào CHƯA có (theo icd_code); dòng đã tồn tại (kể cả
đã được admin sửa tay) được giữ nguyên, không ghi đè.

Chạy:
    cd backend
    venv\\Scripts\\python scripts\\seed_severity_rates.py      (Windows)
    venv/bin/python scripts/seed_severity_rates.py             (macOS/Linux)
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models.severity_rate import SeverityRate  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# Khớp NHOM_ICD trong app/utils/icd_groups.py — không tự đổi thứ tự/khoá ở
# đây; nếu NHOM_ICD đổi thì sửa danh sách này theo.
DEFAULT_SEVERITY_RATES = [
    {
        "icd_code": "J00-J06",
        "disease_name": "Nhiễm khuẩn cấp đường hô hấp trên",
        "mild_rate": 71.49,
        "moderate_rate": 23.51,
        "severe_rate": 5,
        "note": "Gộp có trọng số từ J06, J02, J01 theo số ca thực tế 2019–2026.",
    },
    {
        "icd_code": "J09-J18",
        "disease_name": "Cúm và viêm phổi",
        "mild_rate": 30,
        "moderate_rate": 45,
        "severe_rate": 25,
        "note": (
            "NHÁP — nhóm chưa có dữ liệu phân độ; Khoa Dược hiệu chỉnh tại "
            "Quản trị → Tỷ lệ Nhẹ/TB/Nặng trước khi dùng chính thức."
        ),
    },
    {
        "icd_code": "J20-J22",
        "disease_name": "Nhiễm khuẩn cấp đường hô hấp dưới khác",
        "mild_rate": 60,
        "moderate_rate": 30,
        "severe_rate": 10,
        "note": "Gộp có trọng số từ J20 theo số ca thực tế 2019–2026.",
    },
]


def seed_severity_rates() -> None:
    db = SessionLocal()
    created, skipped = 0, 0
    try:
        for item in DEFAULT_SEVERITY_RATES:
            existing = (
                db.query(SeverityRate)
                .filter(SeverityRate.icd_code == item["icd_code"])
                .first()
            )
            if existing:
                logger.info("Đã có %s — giữ nguyên, bỏ qua.", item["icd_code"])
                skipped += 1
                continue

            db.add(
                SeverityRate(
                    icd_code=item["icd_code"],
                    disease_name=item["disease_name"],
                    mild_rate=item["mild_rate"],
                    moderate_rate=item["moderate_rate"],
                    severe_rate=item["severe_rate"],
                    note=item["note"],
                    updated_by="seed_severity_rates",
                )
            )
            created += 1
            logger.info(
                "Tạo mới %s: %s/%s/%s%% — %s",
                item["icd_code"], item["mild_rate"], item["moderate_rate"],
                item["severe_rate"], item["disease_name"],
            )

        db.commit()
        logger.info("Xong: %s dòng mới, %s dòng đã có sẵn (bỏ qua).", created, skipped)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_severity_rates()
