"""Ánh xạ phân cấp ICD: Mã → Nhóm (block) → Chương.

Nguồn: TM_ICD.xlsx (cột MAICD, TENICD, PHANNHOM) + TM_ICD_CHUONG.xlsx
(cột MACHUONGICD, TENCHUONGICD). PHANNHOM chính là mã NHÓM, vd 'J00-J06'.

3 nhóm hô hấp dùng để dự báo (đã chốt):
  J00-J06  Nhiễm khuẩn hô hấp trên cấp
  J20-J22  Nhiễm khuẩn hô hấp dưới cấp khác
  J09-J18  Cúm và viêm phổi
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

TARGET_BLOCKS = {
    "J00-J06": "Nhiễm khuẩn hô hấp trên cấp",
    "J20-J22": "Nhiễm khuẩn hô hấp dưới cấp khác",
    "J09-J18": "Cúm và viêm phổi",
}


def normalize_icd(code: str) -> str:
    """Chuẩn hóa mã ICD: bỏ khoảng trắng, viết HOA, bỏ phần sau dấu chấm nếu cần.

    'j01' → 'J01'; ' J20.0 ' → 'J20' (gốc 3 ký tự để gộp nhóm).
    """
    if code is None:
        return ""
    c = str(code).strip().upper().replace(" ", "")
    m = re.match(r"^([A-Z]\d{2})", c)
    return m.group(1) if m else c


@dataclass
class IcdHierarchy:
    """Tra cứu nhóm/chương từ mã ICD."""
    code_to_block: Dict[str, str] = field(default_factory=dict)       # 'J20' -> 'J20-J22'
    block_name: Dict[str, str] = field(default_factory=dict)          # 'J20-J22' -> tên
    block_to_chapter: Dict[str, str] = field(default_factory=dict)    # 'J20-J22' -> 'J00-J99'
    chapter_name: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dir_optional(cls, icd_dir: str | Path) -> "IcdHierarchy":
        """Đọc TM_ICD*.xlsx nếu có; thiếu file thì trả bảng tra RỖNG, không ném lỗi.

        Vì sao không bắt buộc: khi nguồn là DB trung chuyển STA, mỗi dòng dữ liệu
        đã kèm sẵn cột `disease_group` (thủ tục bên PROD lấy từ TM_ICD.PHANNHOM),
        nên không cần tra Excel nữa. Bắt buộc có file sẽ làm máy chủ triển khai
        chết ngay lúc khởi động chỉ vì thiếu hai file không còn dùng tới.

        Khi nguồn là file CSV export thì vẫn cần — lúc đó thiếu file sẽ lộ ra ở
        chỗ khác: mọi dòng không tra được nhóm và bị loại, log báo rõ.
        """
        icd = Path(icd_dir) / "TM_ICD.xlsx"
        chapter = Path(icd_dir) / "TM_ICD_CHUONG.xlsx"
        if not (icd.exists() and chapter.exists()):
            logger.info(
                "Không thấy %s / %s — bỏ qua bảng tra ICD. Không sao nếu nguồn là "
                "STA (dữ liệu đã kèm cột disease_group).", icd, chapter)
            return cls()
        try:
            return cls.from_files(icd, chapter)
        except Exception as exc:                                    # file hỏng, sai cột
            logger.warning("Đọc bảng tra ICD thất bại (%s) — dùng bảng rỗng.", exc)
            return cls()

    @classmethod
    def from_files(cls, icd_path: str | Path, chapter_path: str | Path) -> "IcdHierarchy":
        h = cls()
        chapters = pd.read_excel(chapter_path)
        # Chương: MACHUONGICD = 'A00-B99', TENCHUONGICD
        chap_ranges = []
        for _, r in chapters.iterrows():
            rng = str(r.get("MACHUONGICD", "")).strip()
            name = str(r.get("TENCHUONGICD", "")).strip()
            if rng:
                h.chapter_name[rng] = name
                chap_ranges.append(rng)

        icd = pd.read_excel(icd_path)
        for _, r in icd.iterrows():
            code = normalize_icd(r.get("MAICD"))
            block = str(r.get("PHANNHOM", "")).strip()
            if not code or not block:
                continue
            h.code_to_block.setdefault(code, block)
            if block not in h.block_name:
                h.block_name[block] = ""  # tên nhóm điền sau nếu có
            # Map nhóm → chương theo khoảng chữ-số
            if block not in h.block_to_chapter:
                ch = _find_chapter(block, chap_ranges)
                if ch:
                    h.block_to_chapter[block] = ch

        # Tên nhóm cho 3 nhóm đích (đảm bảo có nhãn đẹp)
        for b, name in TARGET_BLOCKS.items():
            h.block_name[b] = name
        return h

    # ── Tra cứu ──
    def block_of(self, icd_code: str) -> Optional[str]:
        return self.code_to_block.get(normalize_icd(icd_code))

    def chapter_of(self, icd_code: str) -> Optional[str]:
        b = self.block_of(icd_code)
        return self.block_to_chapter.get(b) if b else None

    def is_target(self, icd_code: str) -> bool:
        return self.block_of(icd_code) in TARGET_BLOCKS

    def block_label(self, block_code: str) -> str:
        return self.block_name.get(block_code) or block_code


def _letter_num(token: str):
    m = re.match(r"^([A-Z])(\d{2})$", token.strip().upper())
    return (m.group(1), int(m.group(2))) if m else None


def _find_chapter(block: str, chapter_ranges: list[str]) -> Optional[str]:
    """Tìm chương chứa nhóm dựa trên khoảng (vd 'J20-J22' ⊂ 'J00-J99')."""
    bparts = block.split("-")
    start = _letter_num(bparts[0])
    if not start:
        return None
    for rng in chapter_ranges:
        cparts = rng.split("-")
        if len(cparts) != 2:
            continue
        lo, hi = _letter_num(cparts[0]), _letter_num(cparts[1])
        if not lo or not hi:
            continue
        if lo[0] == start[0] == hi[0] and lo[1] <= start[1] <= hi[1]:
            return rng
        # Chương bắc cầu nhiều chữ cái (hiếm với hô hấp) — bỏ qua cho đơn giản
    return None
