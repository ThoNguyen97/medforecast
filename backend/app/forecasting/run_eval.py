"""CLI: backtest walk-forward chính thức — sinh bảng số cho chương 4.

Chạy từ thư mục backend/ (Windows, venv đã cài statsmodels):

    python -m app.forecasting.run_eval --db data/medforecast.db --out ketqua/

Sinh ra trong --out:
    phancap.csv        4 hướng phân cấp × 3 nhóm, đủ chỉ số (M3/M5/M7)
    nhom.csv           mức nhóm + độ phủ khoảng dự báo (M9)
    thoitiet.csv       ensemble CÓ vs KHÔNG thời tiết — cùng cấu hình sản xuất
    smearing.csv       ensemble CÓ vs KHÔNG smearing (M8, đối chứng)
    ket_hop.csv        M12: cách kết hợp thành viên (mean / inv_mae / +bias, có/không ETS)
    thanhvien.csv      thành viên nào đóng góp bao nhiêu % bước, rớt bao nhiêu (M6)
    cau_hinh.json      PRODUCTION_CONFIG đã dùng + ngày chạy + có statsmodels không

MỌI tham số mô hình đến từ config.PRODUCTION_CONFIG (M1). Cờ --no-weather /
--smearing / --lam / --from-period chỉ để ĐỐI CHỨNG — kết quả ghi rõ là biến
thể, không được đưa vào bảng chính thức.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import warnings
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import PRODUCTION_CONFIG
from .evaluate import walk_forward_block, weather_effect, smearing_effect, combine_effect, METHODS
from . import data_access as da

LABELS = {"bottom_up": "Bottom-up", "top_down_fixed": "Top-down cố định",
          "top_down_dynamic": "Top-down động (EWMA)",
          "ols_reconcile": "Hoà giải OLS (trước gọi nhầm là MinT)"}
CHI_SO = ["MAE", "RMSE", "RelMAE", "ME", "MPE_pct", "sMAPE_pct", "WAPE_pct"]


def _tat_canh_bao():
    # Từng lần một thành viên rớt đã được ĐẾM vào thanhvien.csv — không cần
    # in hàng chục dòng warning giống nhau ra màn hình nữa.
    import logging
    logging.getLogger("app.forecasting.models").setLevel(logging.ERROR)
    """Chỉ lọc trong CLI cho dễ đọc — KHÔNG lọc trong app. ConvergenceWarning là
    SARIMAX báo không hội tụ trên chuỗi thưa; giờ nó đã được ghi vào cột
    members_failed nên không cần đọc từng dòng cảnh báo nữa."""
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    warnings.filterwarnings("ignore", category=UserWarning)
    try:
        from statsmodels.tools.sm_exceptions import ConvergenceWarning
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        return True
    except ImportError:
        return False


def main():
    co_statsmodels = _tat_canh_bao()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("PIPELINE_DB_URL", "").replace("sqlite:///", "") or "data/medforecast.db")
    ap.add_argument("--out", default="ketqua_backtest", help="thư mục ghi CSV")
    ap.add_argument("--no-weather", action="store_true", help="ĐỐI CHỨNG: tắt thời tiết")
    ap.add_argument("--smearing", action="store_true", help="ĐỐI CHỨNG: bật smearing")
    ap.add_argument("--lam", type=float, default=None, help="ĐỐI CHỨNG: hình phạt Ridge")
    ap.add_argument("--from-period", default=None, help="ĐỐI CHỨNG: cắt lịch sử YYYY-MM")
    ap.add_argument("--min-train", type=int, default=None)
    args = ap.parse_args()

    cfg = PRODUCTION_CONFIG
    bien_the = {}
    if args.no_weather:   cfg = replace(cfg, use_weather=False);      bien_the["use_weather"] = False
    if args.smearing:     cfg = replace(cfg, smearing=True);          bien_the["smearing"] = True
    if args.lam is not None: cfg = replace(cfg, ridge_lam=args.lam);  bien_the["ridge_lam"] = args.lam
    if args.from_period:  cfg = replace(cfg, from_period=args.from_period); bien_the["from_period"] = args.from_period
    if args.min_train:    cfg = replace(cfg, min_train=args.min_train); bien_the["min_train"] = args.min_train

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    db = args.db
    if not co_statsmodels:
        print("⚠ KHÔNG có statsmodels → ensemble KHÔNG có SARIMAX. Số này KHÔNG phải số "
              "chính thức; chỉ dùng để kiểm tra mã.", file=sys.stderr)
    if bien_the:
        print(f"⚠ BIẾN THỂ đối chứng, không phải cấu hình sản xuất: {bien_the}", file=sys.stderr)

    blocks = da.list_blocks(db)
    rows_pc, rows_nhom, rows_tv, per_block = [], [], [], {}
    for b in blocks:
        r = walk_forward_block(db, b, cfg)
        per_block[b] = r
        meta = r["_meta"]
        for m in METHODS:
            rows_pc.append({"nhom": b, "n_ma": len(meta["codes"]), "n_buoc": meta["n_steps"],
                            "phuong_an": LABELS[m], **{k: r[m].get(k) for k in CHI_SO}})
        g = r["_group"]
        rows_nhom.append({"nhom": b, "n_buoc": meta["n_steps"], "thoi_tiet": meta["weather_active"],
                          **{k: g.get(k) for k in CHI_SO},
                          "do_phu_pct": g.get("coverage_pct"), "do_phu_n": g.get("coverage_n"),
                          "be_rong_tuong_doi": g.get("interval_width_rel")})
        for nm, pct in meta["members_used_pct"].items():
            rows_tv.append({"nhom": b, "thanh_vien": nm, "muc": "nhóm", "dong_gop_pct_buoc": pct,
                            "so_lan_rot": meta["members_failed_count"].get(nm, 0),
                            "vi_du_ly_do": meta["members_failed_example"].get(nm, "")})
        for nm, cnt in meta["members_failed_count"].items():
            if nm.endswith("(mức mã)"):
                rows_tv.append({"nhom": b, "thanh_vien": nm.replace(" (mức mã)", ""), "muc": "mã",
                                "dong_gop_pct_buoc": round(100 - cnt / meta["n_code_fits"] * 100, 1),
                                "so_lan_rot": cnt, "vi_du_ly_do": meta["members_failed_example"].get(nm, "")})

    df_pc = pd.DataFrame(rows_pc)
    tong = (df_pc.groupby("phuong_an")[CHI_SO].mean()
            .reindex([LABELS[m] for m in METHODS]).reset_index())
    tong.insert(0, "nhom", "TỔNG HỢP"); tong.insert(1, "n_ma", ""); tong.insert(2, "n_buoc", "")
    df_pc = pd.concat([df_pc, tong], ignore_index=True)
    df_pc.round(3).to_csv(out / "phancap.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(rows_nhom).round(3).to_csv(out / "nhom.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(rows_tv).to_csv(out / "thanhvien.csv", index=False, encoding="utf-8-sig")

    rows_tt, rows_sm = [], []
    for b in blocks:
        we = weather_effect(db, b, cfg)
        if we.get("with_weather"):
            rows_tt.append({"nhom": b, **{f"khong_{k}": we["without_weather"][k] for k in CHI_SO},
                            **{f"co_{k}": we["with_weather"][k] for k in CHI_SO},
                            "giam_MAE_pct": we["mae_improve_pct"]})
        se = smearing_effect(db, b, cfg)
        rows_sm.append({"nhom": b, **{f"khong_{k}": se["without_smearing"][k] for k in ("MAE", "RelMAE", "ME", "MPE_pct")},
                        **{f"co_{k}": se["with_smearing"][k] for k in ("MAE", "RelMAE", "ME", "MPE_pct")}})
    pd.DataFrame(rows_tt).round(3).to_csv(out / "thoitiet.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(rows_sm).round(3).to_csv(out / "smearing.csv", index=False, encoding="utf-8-sig")

    # M12: cách kết hợp — thành viên ghi một lần, combiner chạy lại
    rows_kh = []
    for b in blocks:
        ce = combine_effect(db, b, cfg)
        for name, m in ce.items():
            if not isinstance(m, dict):
                continue
            rows_kh.append({"nhom": b, "bien_the": name, "n_buoc": ce["n_steps"],
                            **{k: m[k] for k in ("MAE", "RelMAE", "ME", "MPE_pct", "sMAPE_pct", "WAPE_pct")},
                            "do_phu_pct": m["coverage_pct"], "he_so_lech_tb": m["bias_mean"],
                            "trong_so_cuoi": json.dumps(m["weights_last"], ensure_ascii=False)})
    df_kh = pd.DataFrame(rows_kh)
    if not df_kh.empty:
        tb = df_kh.groupby("bien_the")[["RelMAE", "MPE_pct", "do_phu_pct"]].mean().reset_index()
        tb.insert(0, "nhom", "TỔNG HỢP")
        df_kh = pd.concat([df_kh, tb], ignore_index=True)
    df_kh.round(3).to_csv(out / "ket_hop.csv", index=False, encoding="utf-8-sig")

    (out / "cau_hinh.json").write_text(json.dumps({
        "chay_luc": datetime.now().isoformat(timespec="seconds"),
        "db": db, "co_statsmodels": co_statsmodels, "bien_the_doi_chung": bien_the,
        "config": cfg.as_record(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── in ra màn hình ─────────────────────────────────────────────────
    pd.set_option("display.width", 160)
    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    pd.set_option("display.max_colwidth", 60)
    print("\n=== PHÂN CẤP — mức MÃ, walk-forward 1 bước ===")
    print(df_pc.round(3).to_string(index=False))
    print("\n=== MỨC NHÓM + độ phủ khoảng dự báo ===")
    print(pd.DataFrame(rows_nhom).round(3).to_string(index=False))
    print("\n=== THÀNH VIÊN ensemble ===")
    print(pd.DataFrame(rows_tv).to_string(index=False))
    if rows_tt:
        print("\n=== THỜI TIẾT (ensemble sản xuất, có vs không) ===")
        print(pd.DataFrame(rows_tt)[["nhom", "khong_RelMAE", "co_RelMAE", "khong_MPE_pct", "co_MPE_pct", "giam_MAE_pct"]].round(3).to_string(index=False))
    print("\n=== SMEARING (đối chứng M8) ===")
    print(pd.DataFrame(rows_sm).round(3).to_string(index=False))
    if not df_kh.empty:
        print("\n=== KẾT HỢP THÀNH VIÊN (M12) — RelMAE nhóm theo biến thể ===")
        print(df_kh.pivot_table(index="bien_the", columns="nhom", values="RelMAE").round(3).to_string())
    best = tong.loc[tong["RelMAE"].idxmin(), "phuong_an"]
    print(f"\n>> RelMAE thấp nhất: {best}")
    print(f">> Đã ghi: {out}/  (phancap, nhom, thanhvien, thoitiet, smearing, ket_hop, cau_hinh)")


if __name__ == "__main__":
    main()
