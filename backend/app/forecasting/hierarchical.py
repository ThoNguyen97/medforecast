"""Các hướng hòa giải phân cấp: bottom-up, top-down (cố định/động), MinT-OLS."""
from __future__ import annotations
from typing import Dict, List
import numpy as np
import pandas as pd


def ewma_shares(hist_group: pd.DataFrame, hist_codes: Dict[str, pd.DataFrame],
                span: int = 6) -> Dict[str, float]:
    """Tỷ trọng ĐỘNG: EWMA của (ca mã / tổng nhóm) theo tháng, chuẩn hóa tổng=1."""
    g = hist_group.set_index("period")["cases"]
    ratios = {}
    for code, cdf in hist_codes.items():
        c = cdf.set_index("period")["cases"].reindex(g.index).fillna(0.0)
        r = np.where(g.values > 0, c.values / np.where(g.values == 0, 1, g.values), 0.0)
        s = pd.Series(r).ewm(span=span, adjust=False).mean()
        ratios[code] = float(s.iloc[-1]) if len(s) else 0.0
    tot = sum(ratios.values())
    if tot <= 0:
        n = len(ratios)
        return {k: 1.0 / n for k in ratios}
    return {k: v / tot for k, v in ratios.items()}


def reconcile_ols(codes: List[str], base_group: float,
                  base_codes: Dict[str, float]) -> Dict[str, float]:
    """Hòa giải MinT-OLS: dùng cả dự báo nhóm lẫn từng mã.

    S (n+1 x n): hàng đầu = tổng, còn lại = ma trận đơn vị.
    bottom = (Sᵀ S)⁻¹ Sᵀ · [base_group, base_codes...]  (W = I).
    """
    n = len(codes)
    if n == 0:
        return {}
    if n == 1:
        # 1 mã: hòa giải = trung bình dự báo nhóm và mã
        v = max(0.0, 0.5 * (base_group + base_codes[codes[0]]))
        return {codes[0]: v}
    S = np.vstack([np.ones(n), np.eye(n)])
    b = np.array([base_group] + [base_codes[c] for c in codes], dtype=float)
    G = np.linalg.inv(S.T @ S) @ S.T
    bottom = np.maximum(G @ b, 0.0)
    return {c: float(bottom[i]) for i, c in enumerate(codes)}


def split_topdown(base_group: float, shares: Dict[str, float]) -> Dict[str, float]:
    return {c: float(max(0.0, base_group * s)) for c, s in shares.items()}
