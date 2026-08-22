# -*- coding: utf-8 -*-
"""Ba nhóm ICD của đề tài — nguồn danh mục DUY NHẤT cho backend.

Vì sao mọi combobox/bộ lọc phải theo NHÓM chứ không theo mã lẻ:
  - Đề cương chốt phạm vi ba nhóm, dự báo cấp nhóm rồi phân bổ về mã.
  - Backtest 09/08/2026 trên dữ liệu HIS thật: chuỗi nhóm ổn định
    (MASE 0,51–0,65), chuỗi mã lẻ thưa làm mô hình nổ (bottom-up
    MASE 483 ở cửa sổ 2022/J09-J18).
Mức MÃ vẫn tồn tại trong dữ liệu (cần cho phân bổ top-down và ánh xạ
vật tư) — chỉ tầng hiển thị/lọc là theo nhóm.
"""
from __future__ import annotations

from typing import List, Optional

# Thứ tự cố định — cũng là thứ tự hiển thị trên UI
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

    Ưu tiên cột disease_group (do cầu nối đồng bộ điền); OR thêm dải mã để
    không bỏ sót bản ghi cũ nhập trước khi cột tồn tại (giá trị NULL).
    """
    from sqlalchemy import or_
    return or_(DiseaseCase.disease_group == nhom,
               DiseaseCase.icd_code.in_(ma_thuoc_nhom(nhom)))


def dieu_kien_benh(DiseaseCase, khoa: str):
    """Bộ lọc 'bệnh' dùng chung: nhận KHOÁ NHÓM ('J09-J18') là chính,
    vẫn nhận mã lẻ ('J20') để tương thích API cũ / drill-down."""
    if khoa in NHOM_ICD:
        return dieu_kien_nhom(DiseaseCase, khoa)
    return DiseaseCase.icd_code == khoa
