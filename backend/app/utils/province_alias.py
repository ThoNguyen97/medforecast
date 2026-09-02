"""Chuẩn hoá tên tỉnh/thành — đồng bộ với frontend normalizeProvinceName.

Data thật (data_HM) dùng tên đầy đủ "Thành phố Hồ Chí Minh", còn UI/master dùng
"TP. Hồ Chí Minh". Helper này trả về tất cả biến thể của 1 tỉnh để query DB
match được bất kể tên nào được lưu.
"""
from typing import List, Set, Tuple

# (TÊN CHUẨN, tập biến thể). Tên chuẩn là tên dùng trên dropdown/master data —
# mọi nơi GHI xuống DB phải dùng tên này, nếu không cùng một tỉnh sẽ nằm ở hai
# dòng khác nhau (đã gặp: "TP. Hồ Chí Minh" do người dùng chọn và "Thành phố
# Hồ Chí Minh" do máy lấy thô từ disease_cases → lịch sử hiện 2 dòng cho 1 nơi).
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
    """Trả về list tất cả biến thể tên của tỉnh (gồm chính nó).

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
    """Tên CHUẨN của tỉnh/thành — dùng mỗi khi GHI location xuống DB.

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
