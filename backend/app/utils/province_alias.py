"""Chuẩn hoá tên tỉnh/thành, đồng bộ với normalizeProvinceName ở frontend.
HIS dùng "Thành phố Hồ Chí Minh", UI dùng "TP. Hồ Chí Minh"; truy vấn khớp mọi biến thể.
"""
from typing import List, Set, Tuple

# (tên chuẩn, tập biến thể); ghi location xuống CSDL phải dùng tên chuẩn
_ALIAS_GROUPS: List[Tuple[str, Set[str]]] = [
    (
        "TP. Hồ Chí Minh",
        {
            "TP. Hồ Chí Minh", "Thành phố Hồ Chí Minh", "Thành Phố Hồ Chí Minh",
            "Hồ Chí Minh", "TP Hồ Chí Minh", "TPHCM",
        },
    ),
    ("Hà Nội", {"Hà Nội", "Thành phố Hà Nội", "Thành Phố Hà Nội"}),
    ("Đà Nẵng", {"Đà Nẵng", "Thành phố Đà Nẵng"}),
    ("Hải Phòng", {"Hải Phòng", "Thành phố Hải Phòng"}),
    ("Cần Thơ", {"Cần Thơ", "Thành phố Cần Thơ"}),
]


def province_aliases(name: str) -> List[str]:
    """Mọi biến thể tên của tỉnh (gồm chính nó), dùng cho filter(location.in_(...))."""
    if not name:
        return []
    key = name.strip()
    for _chuan, bien_the in _ALIAS_GROUPS:
        if key in bien_the:
            return list(bien_the)
    return [key]


def ten_chuan(name: str) -> str:
    """Tên chuẩn của tỉnh/thành khi ghi CSDL; tên lạ giữ nguyên sau khi strip."""
    if not name:
        return name
    key = name.strip()
    for chuan, bien_the in _ALIAS_GROUPS:
        if key in bien_the:
            return chuan
    return key
