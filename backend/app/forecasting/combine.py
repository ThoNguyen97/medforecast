"""KẾT HỢP THÍCH ỨNG các thành viên ensemble + HIỆU CHỈNH LỆCH HỆ THỐNG (M12, 11/09/2026).

Vì sao cần
----------
`Ensemble.predict()` lấy TRUNG BÌNH ĐỀU. Walk-forward 11/09/2026 (bench cloud,
đủ SARIMAX) cho thấy chỉ cần bỏ một thành viên yếu (poisson_trend) là RelMAE
mức mã đi từ 0,659 xuống 0,617 — tức trung bình đều đang để một mô hình tồi
kéo cả tổ hợp. Nhưng "bỏ hẳn" là quyết định cứng của người, đúng hôm nay sai
ngày mai. Cách đúng: để DỮ LIỆU quyết định trọng số, và quyết định lại mỗi
bước theo sai số gần đây của từng thành viên — Bates & Granger (1969),
Timmermann (2006): trọng số nghịch đảo sai số trên cửa sổ trượt.

Thứ hai, ba khối có LỆCH HỆ THỐNG một chiều: J09-J18 hụt ~−15 %, J20-J22 thừa
~+13 %, kỳ này qua kỳ khác. Trung bình đều không tự sửa. Một hệ số nhân ước
lượng từ tỷ số thực tế/dự báo của các bước gần đây (co về 1 để không chạy
theo nhiễu) sửa được phần đó — và vì ước lượng CHỈ từ quá khứ nên vẫn là
walk-forward trung thực.

Cả hai đều là "lớp trên" của ensemble như docstring cũ của `Ensemble` đã hẹn:
"Nếu cần trọng số nghịch đảo MSE thì làm ở lớp trên với kết quả backtest,
không giấu vào đây."

Trạng thái được cập nhật TUẦN TỰ: gọi `combine()` cho bước t bằng lịch sử
tới t−1, rồi `update()` với thực tế của t. Không bao giờ nhìn thấy tương lai.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np


class AdaptiveCombiner:
    """Trọng số nghịch đảo MAE trên cửa sổ trượt + hệ số lệch có co rút.

    Tham số
    -------
    mode          'mean' (trung bình đều, hành vi cũ) | 'inv_mae'
    window        số bước gần nhất để tính MAE từng thành viên (12 = 1 mùa)
    power         w_i ∝ MAE_i^(−power); 1 = nghịch đảo, 2 = nghịch đảo bình phương
    min_hist      dưới ngưỡng này (chưa đủ lịch sử) → trung bình đều
    bias_correct  bật hệ số lệch
    bias_window   số bước gần nhất để lấy trung vị tỷ số thực tế/dự báo
    bias_shrink   0..1 — mức tin vào hệ số đo được (1 = dùng nguyên, 0 = tắt)
    bias_clip     chặn hệ số trong [1/clip, clip] để một mùa dịch lạ không kéo
                  dự báo đi gấp đôi
    """

    def __init__(self, mode: str = "mean", window: int = 12, power: float = 1.0,
                 min_hist: int = 6, bias_correct: bool = False,
                 bias_window: int = 12, bias_shrink: float = 0.5,
                 bias_clip: float = 1.5):
        if mode not in ("mean", "inv_mae"):
            raise ValueError(f"mode phải là 'mean' hoặc 'inv_mae', nhận {mode!r}")
        self.mode = mode
        self.window = int(window)
        self.power = float(power)
        self.min_hist = int(min_hist)
        self.bias_correct = bool(bias_correct)
        self.bias_window = int(bias_window)
        self.bias_shrink = float(bias_shrink)
        self.bias_clip = float(bias_clip)
        # lịch sử sai số tuyệt đối theo thành viên (chỉ các bước thành viên có mặt)
        self._abs_err: Dict[str, List[float]] = {}
        # tỷ số thực tế / dự báo-đã-kết-hợp (TRƯỚC hiệu chỉnh lệch)
        self._ratio: List[float] = []
        self.last_weights: Dict[str, float] = {}
        self.last_bias: float = 1.0

    # ── trọng số ────────────────────────────────────────────────────────
    def weights(self, names: List[str]) -> Dict[str, float]:
        if not names:
            return {}
        if self.mode == "mean":
            return {n: 1.0 / len(names) for n in names}
        raw: Dict[str, float] = {}
        for n in names:
            h = self._abs_err.get(n, [])
            if len(h) < self.min_hist:
                raw[n] = None                       # chưa đủ lịch sử
            else:
                mae = float(np.mean(h[-self.window:]))
                raw[n] = 1.0 / max(mae, 1e-6) ** self.power
        known = {n: v for n, v in raw.items() if v is not None}
        if not known:
            return {n: 1.0 / len(names) for n in names}
        # thành viên chưa có lịch sử nhận trọng số bằng TRUNG BÌNH của các
        # thành viên đã có — không bị loại, cũng không được ưu ái
        fill = float(np.mean(list(known.values())))
        full = {n: (v if v is not None else fill) for n, v in raw.items()}
        s = sum(full.values())
        return {n: v / s for n, v in full.items()}

    # ── hệ số lệch ──────────────────────────────────────────────────────
    def bias(self) -> float:
        if not self.bias_correct or len(self._ratio) < self.min_hist:
            return 1.0
        r = np.asarray(self._ratio[-self.bias_window:], float)
        r = r[np.isfinite(r) & (r > 0)]
        if len(r) < self.min_hist:
            return 1.0
        med = float(np.median(r))
        f = 1.0 + self.bias_shrink * (med - 1.0)
        return float(np.clip(f, 1.0 / self.bias_clip, self.bias_clip))

    # ── kết hợp ─────────────────────────────────────────────────────────
    def combine(self, member_preds: Dict[str, float]) -> Tuple[float, float, Dict[str, float], float]:
        """Trả (dự báo cuối, dự báo trước hiệu chỉnh, trọng số, hệ số lệch)."""
        names = list(member_preds.keys())
        if not names:
            self.last_weights, self.last_bias = {}, 1.0
            return 0.0, 0.0, {}, 1.0
        w = self.weights(names)
        raw = float(sum(w[n] * float(member_preds[n]) for n in names))
        b = self.bias()
        self.last_weights, self.last_bias = w, b
        return max(0.0, raw * b), raw, w, b

    def update(self, member_preds: Dict[str, float], actual: float, raw_combined: float) -> None:
        """Ghi nhận thực tế của bước vừa dự báo. `raw_combined` là dự báo TRƯỚC
        hiệu chỉnh lệch — hệ số lệch phải đo trên phần chưa hiệu chỉnh, nếu
        không nó tự "học" chính mình."""
        for n, p in member_preds.items():
            self._abs_err.setdefault(n, []).append(abs(float(actual) - float(p)))
        if raw_combined > 0:
            self._ratio.append(float(actual) / float(raw_combined))

    def describe(self) -> dict:
        return {
            "mode": self.mode, "window": self.window, "power": self.power,
            "bias_correct": self.bias_correct, "bias_window": self.bias_window,
            "bias_shrink": self.bias_shrink, "bias_clip": self.bias_clip,
            "weights": {k: round(v, 3) for k, v in self.last_weights.items()},
            "bias_factor": round(self.last_bias, 3),
            "n_hist": {k: len(v) for k, v in self._abs_err.items()},
        }


def combiner_from_config(cfg) -> AdaptiveCombiner:
    """Dựng combiner từ ForecastConfig — một chỗ đọc tham số, mọi nơi dùng."""
    return AdaptiveCombiner(
        mode=getattr(cfg, "combine", "mean"),
        window=getattr(cfg, "combine_window", 12),
        power=getattr(cfg, "combine_power", 1.0),
        min_hist=getattr(cfg, "combine_min_hist", 6),
        bias_correct=getattr(cfg, "bias_correct", False),
        bias_window=getattr(cfg, "bias_window", 12),
        bias_shrink=getattr(cfg, "bias_shrink", 0.5),
        bias_clip=getattr(cfg, "bias_clip", 1.5),
    )
