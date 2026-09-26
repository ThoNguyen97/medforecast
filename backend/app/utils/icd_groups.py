# -*- coding: utf-8 -*-
"""Danh mục ba nhóm ICD hô hấp, nguồn duy nhất cho backend.

Bộ lọc và combobox theo nhóm vì dự báo ở cấp nhóm rồi phân bổ top-down về mã:
chuỗi nhóm ổn định, còn chuỗi mã lẻ thưa làm mô hình mất ổn định. Mức mã vẫn
có trong dữ liệu để phân bổ và ánh xạ vật tư; chỉ tầng hiển thị/lọc theo nhóm.
"""
from __future__ import annotations

from typing import List, Optional

# Thứ tự cố định, cũng là thứ tự hiển thị trên UI
NHOM_ICD: dict[str, str] = {
    "J00-J06": "Nhiễm khuẩn cấp đường hô hấp trên",
    "J09-J18": "Cúm và viêm phổi",
    "J20-J22": "Nhiễm khuẩn cấp đường hô hấp dưới khác",
}

def ma_thuoc_nhom(nhom: str) -> List[str]:
    """'J09-J18' → ['J09', 'J10', ..., 'J18']."""
    try:
        dau, cuoi = nhom.split("-")
        chu = dau[0]
        return [f"{chu}{n:02d}" for n in range(int(dau[1:]), int(cuoi[1:]) + 1)]
    except (ValueError, IndexError):
        return []


def nhom_cua_ma(icd_code: str) -> Optional[str]:
    """'J13' → 'J09-J18'. None nếu không thuộc nhóm nào."""
    ma = (icd_code or "").strip().upper()[:3]
    for nhom in NHOM_ICD:
        if ma in ma_thuoc_nhom(nhom):
            return nhom
    return None


def dieu_kien_nhom(DiseaseCase, nhom: str):
    """Điều kiện SQLAlchemy lọc DiseaseCase theo nhóm.

    Dùng cột disease_group (do đồng bộ điền), OR thêm dải mã để không bỏ sót
    bản ghi có disease_group NULL.
    """
    from sqlalchemy import or_
    return or_(DiseaseCase.disease_group == nhom,
               DiseaseCase.icd_code.in_(ma_thuoc_nhom(nhom)))


def dieu_kien_benh(DiseaseCase, khoa: str):
    """Bộ lọc 'bệnh' dùng chung: nhận khoá nhóm ('J09-J18') hoặc mã lẻ ('J20') khi drill-down."""
    if khoa in NHOM_ICD:
        return dieu_kien_nhom(DiseaseCase, khoa)
    return DiseaseCase.icd_code == khoa
