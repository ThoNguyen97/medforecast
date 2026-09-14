# -*- coding: utf-8 -*-
"""Số ca THỰC TẾ của một kỳ dự báo — một hàm dùng chung cho mọi màn hình.

`disease_forecasts.actual_cases` chỉ có khi nhập tay nên hầu như rỗng; số thật
đã nằm sẵn trong dữ liệu ca bệnh. Bản Toàn quốc (location IS NULL) đọc
`mart_monthly_cases_by_block` (đếm DISTINCT lượt, cùng nguồn Tổng quan/Cảnh
báo); bản theo tỉnh đọc `disease_cases` theo tỉnh.

Kỳ chưa chốt (tháng lịch hiện tại) trả None — vài ngày dữ liệu không phải
"thực tế" và không được đem tính độ lệch.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import extract, func, text
from sqlalchemy.orm import Session

from app.models.disease_case import DiseaseCase
from app.utils.icd_groups import NHOM_ICD, dieu_kien_benh


def thang_da_chot(thang: date) -> bool:
    """Cùng quy tắc với pipeline (`is_complete`): tháng lịch hiện tại chưa chốt."""
    h = date.today()
    return (thang.year, thang.month) < (h.year, h.month)


def so_ca_thuc_te(
    db: Session,
    icd_code: str,
    thang: date,
    location: Optional[str],
) -> Optional[int]:
    """Tổng ca thực tế của (nhóm bệnh, tháng, khu vực).

    None khi kỳ chưa chốt hoặc chưa có bản ghi nào cho kỳ đó — khác hẳn "có
    dữ liệu và bằng 0", để giao diện hiện "—" thay vì độ lệch vô nghĩa.
    """
    if not thang_da_chot(thang):
        return None
    ky = f"{thang.year:04d}-{thang.month:02d}"

    # Toàn quốc + mã là một khối → số chính thức từ mart (kỳ đã chốt).
    if not location and icd_code in NHOM_ICD:
        try:
            r = db.execute(text(
                "SELECT cases FROM mart_monthly_cases_by_block "
                "WHERE region = 'TOAN_QUOC' AND block_code = :b AND period = :p "
                "AND is_complete = 1"), {"b": icd_code, "p": ky}).first()
            if r is not None:
                return int(r[0] or 0)
        except Exception:                                     # noqa: BLE001
            db.rollback()                                     # mart chưa có → rơi xuống disease_cases

    q = db.query(
        func.count(DiseaseCase.id),
        func.coalesce(func.sum(DiseaseCase.case_count), 0),
    ).filter(
        dieu_kien_benh(DiseaseCase, icd_code),
        extract("year", DiseaseCase.recorded_at) == thang.year,
        extract("month", DiseaseCase.recorded_at) == thang.month,
    )
    if location:
        from app.utils.province_alias import province_aliases
        q = q.filter(DiseaseCase.location.in_(province_aliases(location)))

    so_dong, tong = q.first()
    if not so_dong:
        return None
    return int(tong or 0)


def do_lech_pct(predicted: Optional[int], thuc_te: Optional[int]) -> Optional[float]:
    """(dự báo − thực tế)/thực tế × 100. None khi không có số thực tế hoặc = 0."""
    if not thuc_te:
        return None
    return round(((predicted or 0) - thuc_te) / thuc_te * 100, 1)
