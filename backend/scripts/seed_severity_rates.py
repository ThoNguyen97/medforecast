#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seed mặc định cho bảng `severity_rates` (Tỷ lệ Nhẹ/TB/Nặng) trên máy mới.

VÌ SAO CẦN SCRIPT NÀY
File DB (backend/data/medforecast.db) bị .gitignore nên máy mới `git clone`
về sẽ có bảng severity_rates HOÀN TOÀN RỖNG.

Từ khi có SeverityInferenceService.ensure_default_severity_rates(), nút
"Phân loại lại toàn bộ" trên Quản trị → Tỷ lệ Nhẹ/TB/Nặng đã tự "insert bù"
3 dòng nhóm còn thiếu mỗi lần bấm (xem update_severity_rates_from_history) —
nên bình thường KHÔNG BẮT BUỘC phải chạy script này nữa, chỉ cần mở app rồi
bấm nút đó.

Script này chỉ còn hữu ích khi muốn insert bù mà KHÔNG qua giao diện/API —
ví dụ chạy trong bước provisioning/CI, hoặc khi disease_cases chưa có gì
(chưa đồng bộ HIS) và chỉ muốn có sẵn 3 dòng mặc định để trang admin không
trống trơn trước khi đồng bộ dữ liệu thật.

Idempotent: chỉ tạo dòng nào CHƯA có (theo icd_code); dòng đã tồn tại (kể cả
đã được admin sửa tay) được giữ nguyên, không ghi đè. Giá trị mặc định lấy
từ app/utils/icd_groups.py::DEFAULT_SEVERITY_RATES (nguồn duy nhất, dùng
chung với logic auto-heal trong SeverityInferenceService).

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
from app.services.severity_inference_service import SeverityInferenceService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    db = SessionLocal()
    try:
        created = SeverityInferenceService(db).ensure_default_severity_rates(
            updated_by="seed_severity_rates",
        )
        if created:
            logger.info("Đã insert bù %d dòng severity_rate mặc định.", created)
        else:
            logger.info("Đã đủ severity_rate cho 3 nhóm ICD — không cần tạo thêm.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
