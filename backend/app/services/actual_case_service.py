# -*- coding: utf-8 -*-
"""Số ca THỰC TẾ của một kỳ dự báo, lấy từ disease_cases.

VÌ SAO CẦN
Cột ``disease_forecasts.actual_cases`` chỉ có giá trị khi ai đó nhập tay, nên
hầu như luôn rỗng — báo cáo hiện "—" ở cột Số ca thực tế và Độ lệch dù số ca
thật đã nằm sẵn trong ``disease_cases``. Đây đúng là nguồn mà bảng "Dữ liệu ca
bệnh gần đây" dùng để tính độ lệch, nên dùng chung một hàm để mọi màn hình ra
cùng một con số.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.disease_case import DiseaseCase
from app.utils.icd_groups import dieu_kien_benh


def so_ca_thuc_te(
    db: Session,
    icd_code: str,
    thang: date,
    location: Optional[str],
) -> Optional[int]:
    """Tổng ca thực tế của (nhóm bệnh, tháng, khu vực).

    Trả None khi CHƯA CÓ bản ghi nào cho kỳ đó (chưa tới kỳ, hoặc chưa đồng bộ
    HIS) — khác hẳn "có dữ liệu và bằng 0". Nhờ vậy giao diện hiện "—" thay vì
    số 0 rồi tính ra độ lệch vô nghĩa.
    """
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
    """(dự báo − thực tế)/thực tế × 100. None khi không có số thực tế."""
    if not thuc_te:  # None hoặc 0 → không chia được
        return None
    return round(((predicted or 0) - thuc_te) / thuc_te * 100, 1)
