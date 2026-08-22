"""CLI: chạy so sánh 4 hướng phân cấp trên toàn bộ nhóm trong MART, xuất bảng + CSV.

Ví dụ:
  PIPELINE_DB_URL=sqlite:////tmp/mart.db python -m app.forecasting.run_eval \
      --db /tmp/mart.db --min-train 24 --out /tmp/ketqua_phancap.csv
"""
from __future__ import annotations
import argparse
import os
import numpy as np
import pandas as pd

from .evaluate import walk_forward_block, weather_effect, METHODS
from . import data_access as da

LABELS = {"bottom_up": "Bottom-up", "top_down_fixed": "Top-down cố định",
          "top_down_dynamic": "Top-down động (EWMA)", "mint": "Hòa giải MinT"}


def main():
    # Chỉ lọc cảnh báo trong CLI backtest cho dễ đọc — không lọc trong app.
    # ConvergenceWarning là SARIMAX báo không hội tụ trên chuỗi thưa: vô hại
    # với kết quả (ensemble tự hạ trọng số mô hình tồi) nhưng in hàng trăm
    # dòng che mất bảng kết quả.
    import warnings
    from statsmodels.tools.sm_exceptions import ConvergenceWarning
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    warnings.filterwarnings("ignore", category=UserWarning, module="statsmodels")
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("PIPELINE_DB_URL", "").replace("sqlite:///", "") or "/tmp/mart.db")
    ap.add_argument("--min-train", type=int, default=24)
    ap.add_argument("--out", default="/tmp/ketqua_phancap.csv")
    ap.add_argument("--from-period", default=None,
                    help="Cắt lịch sử, dạng YYYY-MM (vd 2022-01). Bỏ trống = dùng toàn "
                         "bộ. Dùng khi chuỗi có dịch chuyển mức nền — đo bằng mục 7 của "
                         "sql_his/06_danh_gia_du_lieu.sql. Chạy vài mốc rồi so MASE, "
                         "đừng chọn bằng cảm tính.")
    args = ap.parse_args()
    db = args.db

    blocks = da.list_blocks(db)
    rows = []
    per_block = {}
    if args.from_period:
        print(f"[Chỉ dùng dữ liệu từ {args.from_period} trở đi]")
    for b in blocks:
        r = walk_forward_block(db, b, min_train=args.min_train,
                               from_period=args.from_period)
        per_block[b] = r
        for m in METHODS:
            rows.append({"block": b, "n_ma": len(r["_meta"]["codes"]),
                         "phuong_an": LABELS[m], **r[m]})

    df = pd.DataFrame(rows)
    # trung bình toàn cục theo phương án (gộp các nhóm)
    overall = (df.groupby("phuong_an")[["MAE", "RMSE", "MASE"]].mean()
               .reindex([LABELS[m] for m in METHODS]).reset_index())
    overall.insert(0, "block", "TỔNG HỢP")
    overall.insert(2, "n_ma", "")

    full = pd.concat([df, overall], ignore_index=True)
    full[["MAE", "RMSE", "MASE"]] = full[["MAE", "RMSE", "MASE"]].round(3)
    full.to_csv(args.out, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 120)
    print("\n=== SO SÁNH CÁC HƯỚNG DỰ BÁO PHÂN CẤP (mức MÃ, walk-forward 1 bước) ===\n")
    for b in blocks:
        meta = per_block[b]["_meta"]
        print(f"# Nhóm {b}  ({len(meta['codes'])} mã: {', '.join(meta['codes'])}; "
              f"{meta['n_steps']} bước kiểm định)")
        sub = df[df["block"] == b][["phuong_an", "MAE", "RMSE", "MASE"]]
        print(sub.round(3).to_string(index=False))
        g = per_block[b]["_group"]
        print(f"  (tham chiếu — dự báo TỔNG nhóm: MAE={g['MAE']:.1f} "
              f"RMSE={g['RMSE']:.1f} MASE={g['MASE']:.2f})\n")

    print("=== TRUNG BÌNH TOÀN CỤC ===")
    print(overall[["phuong_an", "MAE", "RMSE", "MASE"]].round(3).to_string(index=False))
    best = overall.loc[overall["MASE"].idxmin(), "phuong_an"]
    print("\n=== HIỆU QUẢ THỜI TIẾT (mức nhóm, thời tiết có độ trễ) ===")
    for b in blocks:
        we = weather_effect(db, b, from_period=args.from_period)
        if we.get("with_weather"):
            wo, ww = we["without_weather"], we["with_weather"]
            print(f"# {b}: KHÔNG TT MASE={wo['MASE']:.3f} (MAE {wo['MAE']:.1f}) | "
                  f"CÓ TT MASE={ww['MASE']:.3f} (MAE {ww['MAE']:.1f}) | "
                  f"giảm {we['mae_improve_pct']:+.1f}% MAE")
        else:
            print(f"# {b}: chưa có dữ liệu thời tiết")
    print(f"\n>> Phương án MASE thấp nhất: {best}")
    print(f">> Đã lưu bảng chi tiết: {args.out}")


if __name__ == "__main__":
    main()
