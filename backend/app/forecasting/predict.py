"""DỰ BÁO từ artifact đã huấn luyện — không cần DB, không cần khớp lại (3.7).

    python -m app.forecasting.predict --model models/v1/model_v1.pkl
    python -m app.forecasting.predict --model models/v1/model_v1.pkl --block J09-J18 --json

Đọc `model_v1.pkl` (thành viên đã khớp + trọng số + hệ số lệch + phần dư
tương đối) và trả dự báo kỳ kế tiếp của từng khối kèm khoảng 90 %, và chia
xuống mã theo tỷ trọng cố định (top-down) để có số ở mức mã.

Muốn dự báo với dữ liệu MỚI hơn artifact thì huấn luyện lại bằng train.py —
mô hình khớp trong vài chục giây, không có lý do gì để dự báo bằng trạng
thái cũ khi đã có tháng mới.
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np


def predict_from_artifact(pkl_path: str, block: str | None = None) -> dict:
    import joblib
    from .combine import AdaptiveCombiner
    from .evaluate import empirical_interval
    from .hierarchical import split_topdown

    art = joblib.load(pkl_path)
    cfg = art["config"]
    out = {"trained_at": art.get("trained_at"), "level": cfg.get("interval_level", 0.9), "blocks": {}}
    for b, st in art["blocks"].items():
        if block and b != block:
            continue
        ens = st["ensemble"]
        mp = ens.predict_members(int(st["target_month"]))
        w = st["weights"]; bias = float(st["bias_factor"])
        names = [n for n in mp if n in w] or list(mp)
        ws = np.array([w.get(n, 0.0) for n in names], float)
        ws = ws / ws.sum() if ws.sum() > 0 else np.ones(len(names)) / len(names)
        raw = float(sum(wi * mp[n] for wi, n in zip(ws, names)))
        point = max(0.0, raw * bias)
        iv = empirical_interval(point, np.asarray(st["rel_resid"], float), cfg.get("interval_level", 0.9))
        shares = st.get("shares_fixed") or {}
        by_code = split_topdown(point, shares) if shares else {}
        out["blocks"][b] = {
            "anchor_period": st["anchor_period"], "target_period": st["target_period"],
            "point": round(point, 1), "point_raw": round(raw, 1), "bias_factor": round(bias, 3),
            "lower": (int(round(iv[0])) if iv else None), "upper": (int(round(iv[1])) if iv else None),
            "members": {n: round(float(v), 1) for n, v in mp.items()},
            "weights": {n: round(float(wi), 3) for n, wi in zip(names, ws)},
            "by_code_top_down_fixed": {c: int(round(v)) for c, v in by_code.items()},
        }
    return out


def main(argv=None):
    import warnings; warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="models/v1/model_v1.pkl")
    ap.add_argument("--block", default=None)
    ap.add_argument("--json", action="store_true", help="in JSON thay vì bảng")
    args = ap.parse_args(argv)
    res = predict_from_artifact(args.model, args.block)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2)); return
    print(f"Artifact huấn luyện lúc {res['trained_at']} · khoảng {int(res['level']*100)}%")
    for b, r in res["blocks"].items():
        print(f"{b}: kỳ {r['target_period']} → {r['point']} ca [{r['lower']}–{r['upper']}] "
              f"(thô {r['point_raw']} × lệch {r['bias_factor']}) · trọng số {r['weights']}")
        if r["by_code_top_down_fixed"]:
            print("   mức mã:", r["by_code_top_down_fixed"])


if __name__ == "__main__":
    main()
