# -*- coding: utf-8 -*-
"""Backtest ngoài mẫu Tầng 2 (số lượt → nhu cầu thuốc) theo walk-forward, cùng
công thức dss_demand.py; kịch bản A dùng số lượt thực, B dùng ŷ Tầng 1; ghi CSV ra --out.
Chạy: cd backend && python scripts/backtest_tier2.py --db data/medforecast.db --out ketqua_backtest
  --skip-b      bỏ kịch bản B (không chạy Tầng 1)
  --yhat-csv    đọc ŷ Tầng 1 từ CSV thay vì chạy lại walk-forward
"""
from __future__ import annotations
import argparse, json, sqlite3, sys, warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BLOCKS = ("J00-J06", "J09-J18", "J20-J22")
NGT = "NGT"
MIN_N = 30.0      # min_cases_per_bucket
K0 = 6.0          # shrink_k0
WINDOW = 12


def q(con, sql, p=()):
    return pd.read_sql_query(sql, con, params=p)


# ── Tầng 2 ──
def shares(cases_g: dict) -> dict:
    """p̂(g,ro) có co ngót trong khối nội trú (care_level_shares)."""
    tong = sum(cases_g.values())
    if tong <= 0:
        return {}
    p = {ro: n / tong for ro, n in cases_g.items()}
    noi = [ro for ro in cases_g if ro != NGT]
    w = sum(p[ro] for ro in noi)
    tam = {ro: p[ro] for ro in cases_g if ro == NGT}
    if noi and w > 0:
        deu = 1.0 / len(noi)
        qq = {}
        for ro in noi:
            n = cases_g[ro]
            q_do = p[ro] / w
            if n < MIN_N:
                lam = n / (n + K0) if (n + K0) > 0 else 0.0
                qq[ro] = lam * q_do + (1 - lam) * deu
            else:
                qq[ro] = q_do
        sq = sum(qq.values())
        for ro, v in qq.items():
            tam[ro] = (v / sq) * w if sq > 0 else 0.0
    else:
        for ro in noi:
            tam[ro] = p[ro]
    s = sum(tam.values())
    return {k: v / s for k, v in tam.items()} if s > 0 else tam


def norms_on(cases_df, usage_df, periods):
    """Trả (norms{g:{ro:{code:q}}}, shares{g:{ro:p}}) trên tập kỳ cho trước."""
    c = cases_df[cases_df.period.isin(periods)].groupby(["block_code", "ro"])["cases"].sum()
    u = (usage_df[usage_df.period.isin(periods)]
         .groupby(["block_code", "ro", "supply_code"])["quantity"].sum())
    u = u[u > 0]
    norms, sh = {}, {}
    for g in BLOCKS:
        if g not in c.index.get_level_values(0):
            continue
        ro_cases = c.loc[g].to_dict()
        tong = sum(ro_cases.values())
        ug = u.loc[g] if g in u.index.get_level_values(0) else pd.Series(dtype=float)
        gop = ug.groupby(level="supply_code").sum() / tong if tong > 0 else pd.Series(dtype=float)
        norms[g] = {}
        for ro, n in ro_cases.items():
            if n < MIN_N or n <= 0:
                norms[g][ro] = gop.to_dict()
            else:
                s = ug.loc[ro] if ro in ug.index.get_level_values(0) else pd.Series(dtype=float)
                norms[g][ro] = (s / n).to_dict()
        sh[g] = shares(ro_cases)
    return norms, sh


def demand(norms, sh, y_by_block) -> dict:
    """D̂_benh,i = Σ_g Σ_ro Y_g p̂ Norm; rổ thiếu định mức dùng nhánh gộp nội trú."""
    out = defaultdict(float)
    for g, y in y_by_block.items():
        if y is None or y <= 0 or g not in norms or g not in sh:
            continue
        for ro, p in sh[g].items():
            nr = norms[g].get(ro)
            if not nr:
                pooled, nt = defaultdict(float), max(1, sum(1 for r in norms[g] if r != NGT))
                for r2, codes in norms[g].items():
                    if r2 != NGT:
                        for cd, v in codes.items():
                            pooled[cd] += v / nt
                nr = pooled
            for cd, v in nr.items():
                if v > 0:
                    out[cd] += y * p * v
    return out


# ── Chỉ số ──
def pooled(rows):
    a = np.array([r[0] for r in rows], float); p = np.array([r[1] for r in rows], float)
    sa = a.sum()
    return dict(n=len(a), WAPE_pct=100 * np.abs(p - a).sum() / sa if sa > 0 else np.nan,
                MPE_pct=100 * (p - a).sum() / sa if sa > 0 else np.nan,
                tong_thuc=sa, tong_du_bao=p.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/medforecast.db")
    ap.add_argument("--out", default="ketqua_backtest")
    ap.add_argument("--skip-b", action="store_true", help="bỏ kịch bản B (không chạy Tầng 1)")
    ap.add_argument("--yhat-csv", default=None,
                    help="đọc ŷ Tầng 1 từ CSV (period,block,y_hat) thay vì chạy lại walk-forward")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(args.db)
    thang_nay = datetime.now().strftime("%Y-%m")

    cases = q(con, "select period, block_code, ro, cases from fact_cases_by_care_level where period < ?", (thang_nay,))
    usage = q(con, "select period, block_code, ro, supply_code, quantity from fact_usage_by_care_level "
                   "where is_vtyt = 0 and period < ?", (thang_nay,))
    mart = q(con, "select period, block_code, cases from mart_monthly_cases_by_block "
                  "where region = 'TOAN_QUOC' and period < ?", (thang_nay,))
    tot = q(con, "select period, supply_code, so_luong_toan_vien, so_luong_hohap, d_baseline_thang "
                 "from fact_usage_total where is_vtyt = 0 and period < ?", (thang_nay,))
    focus = set(q(con, "select supply_code from v_supply_focus").supply_code)
    all_periods = sorted(cases.period.unique())
    tot_periods = sorted(tot.period.unique())
    y_act = mart.pivot_table(index="period", columns="block_code", values="cases", aggfunc="sum")
    resp_act = usage.groupby(["period", "supply_code"])["quantity"].sum()
    tot_act = tot.set_index(["period", "supply_code"])["so_luong_toan_vien"]

    # ── ŷ Tầng 1 ──
    yhat = {}
    if args.yhat_csv:
        for r in pd.read_csv(args.yhat_csv).itertuples():
            yhat[(str(r.period), r.block)] = float(r.y_hat)
        print(f"  ŷ Tầng 1 đọc từ {args.yhat_csv}: {len(yhat)} dòng", file=sys.stderr)
    elif not args.skip_b:
        warnings.filterwarnings("ignore")
        import logging; logging.getLogger("app.forecasting.models").setLevel(logging.ERROR)
        from app.forecasting import data_access as da
        from app.forecasting.config import PRODUCTION_CONFIG
        from app.forecasting.group_forecast import run_group_walk_forward
        weather = da.weather_series(args.db)
        rows_y = []
        for g in BLOCKS:
            gs = da.group_series(args.db, g, from_period=PRODUCTION_CONFIG.from_period)
            gw = da.join_weather(gs, weather)
            r = run_group_walk_forward(gw, PRODUCTION_CONFIG)
            for pr, a, pdt, raw in zip(r.periods, r.actual, r.pred, r.pred_raw):
                yhat[(pr, g)] = float(pdt)
                rows_y.append(dict(period=pr, block=g, thuc=a, y_hat=round(pdt, 3), y_hat_truoc_bias=round(raw, 3)))
            print(f"  Tầng 1 {g}: {len(r.periods)} bước", file=sys.stderr)
        pd.DataFrame(rows_y).to_csv(out / "tang2_yhat.csv", index=False, encoding="utf-8-sig")

    # ── Vòng walk-forward ──
    buoc, per_code, tv_rows = [], defaultdict(list), []
    for bien_the, min_p in (("sanxuat", "2025-04"), ("toanbo", None)):
        for t in all_periods:
            prev = [p for p in all_periods if p < t and (min_p is None or p >= min_p)]
            win = prev[-WINDOW:]
            if len(win) < 1 or (min_p is None and len(win) < WINDOW):
                continue
            norms, sh = norms_on(cases, usage, win)
            if t not in y_act.index:
                continue
            yA = {g: float(y_act.loc[t].get(g, 0) or 0) for g in BLOCKS}
            scen = {"A": yA}
            if yhat and all((t, g) in yhat for g in BLOCKS):
                scen["B"] = {g: yhat[(t, g)] for g in BLOCKS}
            # đối chứng ngây thơ: TB cửa sổ
            naive_resp = usage[usage.period.isin(win)].groupby("supply_code")["quantity"].sum() / len(win)
            a_resp = resp_act.loc[t] if t in resp_act.index.get_level_values(0) else pd.Series(dtype=float)
            # nền: 12 kỳ trước t
            prev_t = [p for p in tot_periods if p < t][-WINDOW:]
            co_nen = len(prev_t) >= WINDOW and t in tot_periods
            if co_nen:
                sub = tot[tot.period.isin(prev_t)].groupby("supply_code")
                base = sub["d_baseline_thang"].sum() / len(prev_t)
                naive_tot = sub["so_luong_toan_vien"].sum() / len(prev_t)
                a_tot = tot_act.loc[t]
            for kb, y in scen.items():
                d = demand(norms, sh, y)
                codes = set(d) | set(a_resp.index)
                rows = [(float(a_resp.get(c, 0.0)), float(d.get(c, 0.0))) for c in codes]
                m = pooled(rows)
                m_f = pooled([(float(a_resp.get(c, 0.0)), float(d.get(c, 0.0))) for c in codes if c in focus])
                nv = pooled([(float(a_resp.get(c, 0.0)), float(naive_resp.get(c, 0.0))) for c in codes])
                rec = dict(bien_the=bien_the, kich_ban=kb, period=t, n_ky_cua_so=len(win),
                           tu_ky=win[0], den_ky=win[-1],
                           luot_thuc=sum(yA.values()), luot_dung=sum(y.values()),
                           resp_n_ma=m["n"], resp_thuc=m["tong_thuc"], resp_du_bao=m["tong_du_bao"],
                           resp_WAPE=m["WAPE_pct"], resp_MPE=m["MPE_pct"],
                           resp_focus_WAPE=m_f["WAPE_pct"], resp_focus_MPE=m_f["MPE_pct"],
                           resp_naive_WAPE=nv["WAPE_pct"], resp_naive_MPE=nv["MPE_pct"])
                if bien_the == "sanxuat":
                    for c in codes:
                        per_code[(kb, c)].append((t, float(a_resp.get(c, 0.0)), float(d.get(c, 0.0)),
                                                  float(naive_resp.get(c, 0.0))))
                if co_nen:
                    codes_t = set(a_tot.index) | set(d) | set(base.index)
                    rows_t = [(float(a_tot.get(c, 0.0)), float(d.get(c, 0.0)) + float(base.get(c, 0.0))) for c in codes_t]
                    if bien_the == "sanxuat":
                        tv_rows += [dict(kich_ban=kb, supply_code=c, period=t, thuc=r[0], du_bao=r[1],
                                         naive=float(naive_tot.get(c, 0.0)), focus=c in focus)
                                    for r, c in zip(rows_t, codes_t)]
                    mt = pooled(rows_t)
                    mtf = pooled([r for r, c in zip(rows_t, codes_t) if c in focus])
                    nvt = pooled([(float(a_tot.get(c, 0.0)), float(naive_tot.get(c, 0.0))) for c in codes_t])
                    nvtf = pooled([(float(a_tot.get(c, 0.0)), float(naive_tot.get(c, 0.0))) for c in codes_t if c in focus])
                    rec.update(tot_n_ma=mt["n"], tot_thuc=mt["tong_thuc"], tot_du_bao=mt["tong_du_bao"],
                               tot_WAPE=mt["WAPE_pct"], tot_MPE=mt["MPE_pct"],
                               tot_focus_WAPE=mtf["WAPE_pct"], tot_focus_MPE=mtf["MPE_pct"],
                               tot_naive_WAPE=nvt["WAPE_pct"], tot_naive_MPE=nvt["MPE_pct"],
                               tot_focus_naive_WAPE=nvtf["WAPE_pct"], tot_focus_naive_MPE=nvtf["MPE_pct"])
                buoc.append(rec)
    df_b = pd.DataFrame(buoc)
    df_b.round(3).to_csv(out / "tang2_buoc.csv", index=False, encoding="utf-8-sig")

    # ── Tóm tắt ──
    tomtat = []
    def _sum(df, tag, cols):
        for kb, s in df.groupby("kich_ban"):
            r = dict(bien_the=tag, kich_ban=kb, n_buoc=len(s), tu=s.period.min(), den=s.period.max())
            for pre, thuc, du in cols:
                r[f"{pre}_WAPE_tb_buoc"] = s[f"{pre}_WAPE"].mean()
                r[f"{pre}_MPE_tb_buoc"] = s[f"{pre}_MPE"].mean()
                r[f"{pre}_WAPE_tong_muc"] = 100 * (s[du] - s[thuc]).abs().sum() / s[thuc].sum()
                r[f"{pre}_MPE_tong_muc"] = 100 * (s[du] - s[thuc]).sum() / s[thuc].sum()
                r[f"{pre}_naive_WAPE_tb_buoc"] = s[f"{pre}_naive_WAPE"].mean()
            tomtat.append(r)
    sx = df_b[df_b.bien_the == "sanxuat"]
    _sum(sx[sx.n_ky_cua_so >= 6], "sanxuat_cua_so>=6", [("resp", "resp_thuc", "resp_du_bao")])
    _sum(sx, "sanxuat_moi_buoc", [("resp", "resp_thuc", "resp_du_bao")])
    tb = df_b[(df_b.bien_the == "toanbo")]
    _sum(tb, "toanbo_12ky", [("resp", "resp_thuc", "resp_du_bao")])
    _sum(tb[tb.period < "2025-01"], "toanbo_truoc_2025", [("resp", "resp_thuc", "resp_du_bao")])
    _sum(tb[(tb.period >= "2025-01") & (tb.period < "2026-01")], "toanbo_2025", [("resp", "resp_thuc", "resp_du_bao")])
    _sum(tb[tb.period >= "2026-01"], "toanbo_2026", [("resp", "resp_thuc", "resp_du_bao")])
    sxn = sx[sx.tot_WAPE.notna()] if "tot_WAPE" in sx else sx.iloc[0:0]
    if len(sxn):
        _sum(sxn, "sanxuat_toanvien", [("tot", "tot_thuc", "tot_du_bao")])
        for kb, s in sxn.groupby("kich_ban"):
            tomtat.append(dict(bien_the="sanxuat_toanvien_focus", kich_ban=kb, n_buoc=len(s),
                               tu=s.period.min(), den=s.period.max(),
                               tot_WAPE_tb_buoc=s.tot_focus_WAPE.mean(), tot_MPE_tb_buoc=s.tot_focus_MPE.mean(),
                               tot_naive_WAPE_tb_buoc=s.tot_focus_naive_WAPE.mean()))
    pd.DataFrame(tomtat).round(3).to_csv(out / "tang2_tomtat.csv", index=False, encoding="utf-8-sig")

    # ── Theo mã ──
    rows_c = []
    for (kb, c), lst in per_code.items():
        lst = [r for r in lst if r[0] >= "2025-10"]
        if not lst:
            continue
        a = np.array([r[1] for r in lst]); p = np.array([r[2] for r in lst]); nv = np.array([r[3] for r in lst])
        sa = a.sum()
        rows_c.append(dict(kich_ban=kb, supply_code=c, n_buoc=len(lst), focus=c in focus,
                           tong_thuc=sa, tb_thuc=a.mean(),
                           WAPE=100 * np.abs(p - a).sum() / sa if sa > 0 else np.nan,
                           MPE=100 * (p - a).sum() / sa if sa > 0 else np.nan,
                           naive_WAPE=100 * np.abs(nv - a).sum() / sa if sa > 0 else np.nan))
    pd.DataFrame([dict(kich_ban=kb, supply_code=c, period=r[0], thuc=r[1], du_bao=r[2], naive=r[3], focus=c in focus)
                  for (kb, c), lst in per_code.items() for r in lst]).round(3).to_csv(
        out / "tang2_ma_buoc.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(tv_rows).round(3).to_csv(out / "tang2_toanvien_ma_buoc.csv", index=False, encoding="utf-8-sig")
    df_c = pd.DataFrame(rows_c).sort_values(["kich_ban", "tong_thuc"], ascending=[True, False])
    df_c.round(3).to_csv(out / "tang2_ma.csv", index=False, encoding="utf-8-sig")

    # ── Ổn định định mức ──
    win = [p for p in all_periods if p >= "2025-04"][-WINDOW:]
    h1, h2 = win[:6], win[6:]
    n1, s1 = norms_on(cases, usage, h1); n2, s2 = norms_on(cases, usage, h2)
    def hieu_dung(n, s):
        o = {}
        for g in n:
            for ro, p in s[g].items():
                for cd, v in n[g].get(ro, {}).items():
                    o[(g, cd)] = o.get((g, cd), 0.0) + p * v
        return o
    e1, e2 = hieu_dung(n1, s1), hieu_dung(n2, s2)
    vol = usage[usage.period.isin(win)].groupby(["block_code", "supply_code"])["quantity"].sum()
    rows_s = []
    for k in set(e1) | set(e2):
        rows_s.append(dict(block=k[0], supply_code=k[1], focus=k[1] in focus,
                           tieu_hao_12ky=float(vol.get(k, 0.0)),
                           norm_nua1=e1.get(k, 0.0), norm_nua2=e2.get(k, 0.0)))
    df_s = pd.DataFrame(rows_s)
    df_s["ty_so"] = np.where((df_s.norm_nua1 > 0) & (df_s.norm_nua2 > 0), df_s.norm_nua2 / df_s.norm_nua1, np.nan)
    df_s.sort_values("tieu_hao_12ky", ascending=False).round(5).to_csv(out / "tang2_ondinh.csv", index=False, encoding="utf-8-sig")
    # ── Chẩn đoán ──
    uq = usage.groupby("period")["quantity"].sum()
    cq = cases.groupby("period")["cases"].sum()
    ngt = cases[cases.ro == NGT].groupby("period")["cases"].sum()
    pd.DataFrame(dict(tieu_hao_hohap=uq, luot=cq, ty_trong_ngt_pct=100 * ngt / cq,
                      tieu_hao_moi_luot=uq / cq)).dropna().round(2).to_csv(
        out / "tang2_tieuhao_moi_luot.csv", encoding="utf-8-sig")
    (out / "tang2_cau_hinh.json").write_text(json.dumps(dict(
        chay_luc=datetime.now().isoformat(timespec="seconds"), db=args.db, window=WINDOW,
        min_cases_per_bucket=MIN_N, shrink_k0=K0, nua1=h1, nua2=h2, kich_ban_B=bool(yhat)),
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(pd.DataFrame(tomtat).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
