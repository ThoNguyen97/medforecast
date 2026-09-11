"""HUẤN LUYỆN từ bộ dữ liệu đóng gói → backtest + artifact mô hình (3.7, 11/09/2026).

    python -m app.forecasting.train --data dataset/v1 --out models/v1

Không đụng DB. Đọc dataset/v1/*.csv (xem dataset.py), với mỗi khối ICD:

  1. Walk-forward mở rộng cửa sổ, 1 bước (đúng giao thức của run_eval) →
     RelMAE / MPE / độ phủ ở mức nhóm và 4 hướng phân cấp mức mã. Đây là
     "đánh giá trên tập kiểm định" — mỗi bước là một lần huấn luyện lại thật.
  2. Huấn luyện LẦN CUỐI trên toàn bộ kỳ đã chốt, kết hợp bằng trọng số +
     hệ số lệch vừa học ở bước 1 → dự báo kỳ kế tiếp + khoảng 90 %.
  3. Ghi artifact:
        model_v1.json   cấu hình, thành viên, trọng số, hệ số lệch, dự báo,
                        chỉ số backtest, sha256 của dataset — đọc được bằng mắt
        model_v1.pkl    các thành viên ĐÃ KHỚP + combiner, để predict.py dự báo
                        mà không cần khớp lại (joblib)

Kết quả bảng số phải TRÙNG KetQua_Backtest_ChonCauHinh.md khi dataset xuất từ
cùng DB — đó là cách chứng minh file dữ liệu này đúng là thứ mô hình đã học.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import dataset as ds
from .config import PRODUCTION_CONFIG
from .evaluate import walk_forward_frames, METHODS
from .group_forecast import forecast_group_next, make_ensemble
from .data_access import join_weather

CHI_SO = ["MAE", "RMSE", "RelMAE", "ME", "MPE_pct", "sMAPE_pct", "WAPE_pct"]


def _next_month(period: str) -> tuple[str, int]:
    y, m = int(period[:4]), int(period[5:7])
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}", m


def train(data_dir: str, out_dir: str, cfg=PRODUCTION_CONFIG, quiet: bool = False) -> dict:
    d = ds.load(data_dir, complete_only=True, from_period=cfg.from_period)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    manifest = d["manifest"]
    fitted = {}                       # để pickle
    record = {
        "model": "MedForecast ensemble M12 — top-down động",
        "version": "1",
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": {"dir": str(data_dir), "version": manifest.get("version"),
                    "exported_at": manifest.get("exported_at"),
                    "sha256": {k: v.get("sha256") for k, v in (manifest.get("files") or {}).items()}},
        "config": cfg.as_record(),
        "blocks": {},
    }
    rows_pc, rows_nhom = [], []
    for b in d["blocks"]:
        group, codes, shares = d["group"][b], d["codes"][b], d["shares"][b]
        if not quiet:
            print(f"[{b}] walk-forward {len(group) - cfg.min_train} bước, {len(codes)} mã …", file=sys.stderr, flush=True)
        r = walk_forward_frames(b, group, codes, shares, d["weather"], cfg)
        meta, g = r["_meta"], r["_group"]
        for m in METHODS:
            rows_pc.append({"nhom": b, "phuong_an": m, **{k: r[m].get(k) for k in CHI_SO}})
        rows_nhom.append({"nhom": b, **{k: g.get(k) for k in CHI_SO},
                          "do_phu_pct": g.get("coverage_pct"), "do_phu_n": g.get("coverage_n")})

        # Huấn luyện lần cuối + dự báo kỳ kế tiếp
        gw = join_weather(group, d["weather"]) if cfg.use_weather else group
        target, tm = _next_month(str(group["period"].iloc[-1]))
        gf = forecast_group_next(gw, tm, cfg)
        ens = make_ensemble(gw, cfg).fit(gw)          # thành viên đã khớp, để pickle
        fitted[b] = {"ensemble": ens, "combiner_state": gf["combiner"],
                     "weights": gf["weights"], "bias_factor": gf["bias_factor"],
                     "rel_resid": list(map(float, np.asarray(gf["walk_forward"]["actual"]) /
                                           np.maximum(np.asarray(gf["walk_forward"]["pred"]), 1e-9))),
                     "anchor_period": str(group["period"].iloc[-1]), "target_period": target,
                     "target_month": tm, "shares_fixed": shares}
        record["blocks"][b] = {
            "n_history_months": int(len(group)),
            "anchor_period": str(group["period"].iloc[-1]),
            "target_period": target,
            "forecast": {"point": round(gf["point"], 1), "point_raw": round(gf["point_raw"], 1),
                         "lower": (int(round(gf["lower"])) if gf["lower"] is not None else None),
                         "upper": (int(round(gf["upper"])) if gf["upper"] is not None else None),
                         "level": gf["level"]},
            "members_used": gf["members_used"], "members_failed": gf["members_failed"],
            "member_forecasts": gf["members"], "weights": gf["weights"], "bias_factor": gf["bias_factor"],
            "backtest": {"n_steps": meta["n_steps"], "group": {k: round(float(g[k]), 3) for k in CHI_SO},
                         "coverage_pct": g.get("coverage_pct"),
                         "codes_top_down_dynamic": {k: round(float(r["top_down_dynamic"][k]), 3) for k in CHI_SO},
                         "members_used_pct": meta["members_used_pct"]},
            "codes": sorted(codes.keys()),
        }

    df_pc = pd.DataFrame(rows_pc); df_nhom = pd.DataFrame(rows_nhom)
    tong = df_pc.groupby("phuong_an")[CHI_SO].mean()
    record["summary"] = {
        "code_level_top_down_dynamic": {k: round(float(tong.loc["top_down_dynamic", k]), 3) for k in CHI_SO},
        "code_level_by_method": {m: round(float(tong.loc[m, "RelMAE"]), 3) for m in METHODS},
        "group_level": {r["nhom"]: {"RelMAE": round(float(r["RelMAE"]), 3), "MPE_pct": round(float(r["MPE_pct"]), 1),
                                    "coverage_pct": (round(float(r["do_phu_pct"]), 1) if r["do_phu_pct"] is not None else None)}
                        for r in rows_nhom},
    }
    (out / "model_v1.json").write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    try:
        import joblib
        joblib.dump({"blocks": fitted, "config": cfg.as_record(), "trained_at": record["trained_at"]},
                    out / "model_v1.pkl")
        record["pkl"] = str(out / "model_v1.pkl")
    except Exception as exc:                                  # noqa: BLE001
        record["pkl_error"] = str(exc)
    df_pc.round(3).to_csv(out / "backtest_phancap.csv", index=False, encoding="utf-8-sig")
    df_nhom.round(3).to_csv(out / "backtest_nhom.csv", index=False, encoding="utf-8-sig")
    return record


def main(argv=None):
    warnings.filterwarnings("ignore")
    import logging; logging.getLogger("app.forecasting.models").setLevel(logging.ERROR)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="dataset/v1", help="thư mục dataset (nhom_thang.csv, ma_thang.csv, ty_trong_co_dinh.csv)")
    ap.add_argument("--out", default="models/v1", help="thư mục ghi model_v1.json / .pkl")
    args = ap.parse_args(argv)
    rec = train(args.data, args.out)
    s = rec["summary"]
    print("\n=== KẾT QUẢ HUẤN LUYỆN (walk-forward trên dataset) ===")
    print("Mức mã, top-down động:", s["code_level_top_down_dynamic"])
    print("RelMAE theo hướng:", s["code_level_by_method"])
    for b, v in s["group_level"].items():
        fc = rec["blocks"][b]["forecast"]
        print(f"{b}: RelMAE nhóm {v['RelMAE']} · MPE {v['MPE_pct']}% · phủ {v['coverage_pct']}% · "
              f"dự báo {rec['blocks'][b]['target_period']}: {fc['point']} [{fc['lower']}–{fc['upper']}] · "
              f"trọng số {rec['blocks'][b]['weights']}")
    print(f">> Đã ghi {args.out}/model_v1.json, model_v1.pkl, backtest_*.csv")


if __name__ == "__main__":
    main()
