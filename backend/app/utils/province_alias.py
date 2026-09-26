"""Chuẩn hoá tên tỉnh/thành, đồng bộ với normalizeProvinceName ở frontend.

Dữ liệu HIS dùng tên đầy đủ "Thành phố Hồ Chí Minh", còn UI/danh mục dùng
"TP. Hồ Chí Minh"; module cung cấp mọi biến thể để truy vấn khớp bất kể tên đã lưu.
"""
from typing import List, Set, Tuple

# (tên chuẩn, tập biến thể). Mọi thao tác ghi location xuống CSDL phải dùng tên
# chuẩn, nếu không cùng một tỉnh sẽ tách thành hai dòng.
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
    """Danh sách mọi biến thể tên của tỉnh (gồm chính nó).

    Dùng cho query: ``filter(Model.location.in_(province_aliases(p)))``.
    """
    if not name:
        return []
    key = name.strip()
    for _chuan, bien_the in _ALIAS_GROUPS:
        if key in bien_the:
            return list(bien_the)
    return [key]


def ten_chuan(name: str) -> str:
    """Tên chuẩn của tỉnh/thành, dùng khi ghi location xuống CSDL.

    "Thành phố Hồ Chí Minh" → "TP. Hồ Chí Minh". Tên không thuộc nhóm biến thể
    nào thì giữ nguyên (chỉ cắt khoảng trắng thừa).
    """
    if not name:
        return name
    key = name.strip()
    for chuan, bien_the in _ALIAS_GROUPS:
        if key in bien_the:
            return chuan
    return key
