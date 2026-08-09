"""Chuẩn hoá tên tỉnh/thành — đồng bộ với frontend normalizeProvinceName.

Data thật (data_HM) dùng tên đầy đủ "Thành phố Hồ Chí Minh", còn UI/master dùng
"TP. Hồ Chí Minh". Helper này trả về tất cả biến thể của 1 tỉnh để query DB
match được bất kể tên nào được lưu.
"""
from typing import List

# Nhóm các biến thể cùng 1 tỉnh/thành
_ALIAS_GROUPS = [
    {
        "TP. Hồ Chí Minh", "Thành phố Hồ Chí Minh", "Thành Phố Hồ Chí Minh",
        "Hồ Chí Minh", "TP Hồ Chí Minh", "TPHCM",
    },
    {"Hà Nội", "Thành phố Hà Nội", "Thành Phố Hà Nội"},
    {"Đà Nẵng", "Thành phố Đà Nẵng"},
    {"Hải Phòng", "Thành phố Hải Phòng"},
    {"Cần Thơ", "Thành phố Cần Thơ"},
]


def province_aliases(name: str) -> List[str]:
    """Trả về list tất cả biến thể tên của tỉnh (gồm chính nó).

    Dùng cho query: ``filter(Model.location.in_(province_aliases(p)))``.
    """
    if not name:
        return []
    key = name.strip()
    for group in _ALIAS_GROUPS:
        if key in group:
            return list(group)
    return [key]
