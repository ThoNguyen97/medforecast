"""BỘ HUẤN LUYỆN đóng gói — xuất từ DB ra file và nạp lại từ file (3.7, 11/09/2026).

Vì sao
------
Mô hình học từ ba bảng mart trong SQLite; người ngoài (hội đồng, bệnh viện
khác) không thấy "dataset" ở đâu. Gói này biến đúng đầu vào mà mô hình đang
đọc thành file phẳng có phiên bản, kèm manifest (số dòng, sha256, cột), để:

    python -m app.forecasting.train   --data dataset/v1     # huấn luyện + backtest từ FILE
    python -m app.forecasting.predict --model ...           # dự báo từ artifact đã huấn luyện

chạy được ở bất kỳ máy nào KHÔNG có DB — và cho ra đúng bảng số của
KetQua_Backtest_ChonCauHinh.md (kiểm chứng ở dataset/v1/manifest.json).

Ba file dữ liệu (CSV UTF-8, có BOM để Excel mở đúng dấu; Parquet nếu có pyarrow):

    nhom_thang.csv     period × block_code: cases, is_covid, is_complete, thời tiết
                       cùng kỳ và trễ 1–2 tháng — đúng đầu vào của Tầng 1 mức nhóm
    ma_thang.csv       period × block_code × icd_code: cases (đã gộp toàn quốc)
    ty_trong_co_dinh.csv  block_code × icd_code × share — cho top-down cố định

Khử định danh: toàn bộ là SỐ ĐẾM theo tháng, không có mã bệnh nhân, không có
ngày khám, không có địa chỉ dưới cấp tỉnh (và bản phát hành gộp toàn quốc).
Ô nhỏ: xem DATASHEET.md — cases < 5 ở mức mã được giữ nguyên vì là đếm theo
tháng trên toàn viện, không truy ngược được cá nhân.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from . import data_access as da

DATASET_VERSION = "1.0"
WCOLS = ["temp", "humidity", "rainfall"]
LAGS = (1, 2)
FILES = {"nhom": "nhom_thang.csv", "ma": "ma_thang.csv", "ty_trong": "ty_trong_co_dinh.csv"}


# ─────────────────────────────────────────────────────────────────────────────
# Xuất
# ─────────────────────────────────────────────────────────────────────────────

def _add_lags(df: pd.DataFrame) -> pd.DataFrame:
    """Cột thời tiết trễ 1–2 tháng, tính TRÊN CHUỖI ĐÃ SẮP THEO THÁNG của từng
    khối. Đây chính là đặc trưng HarmonicPoisson dùng (weather_lags=(1,2)) và
    SARIMAX dùng (lag 1) — ghi thẳng vào file để người đọc thấy mô hình nhìn
    thấy gì, không phải suy ra từ mã."""
    out = df.sort_values("period").reset_index(drop=True).copy()
    for c in WCOLS:
        if c in out:
            for L in LAGS:
                out[f"{c}_lag{L}"] = out[c].shift(L)
    return out


def build_frames(db_path: str, region: str = "TOAN_QUOC") -> Dict[str, pd.DataFrame]:
    """Dựng ba bảng từ DB — CÙNG hàm đọc mà backtest/service dùng (data_access)."""
    weather = da.weather_series(db_path, region)
    nhom_parts, ma_parts, tt_parts = [], [], []
    for b in da.list_blocks(db_path, region):
        g = da.group_series(db_path, b, region, complete_only=False)
        g = da.join_weather(g, weather)
        g.insert(1, "block_code", b)
        nhom_parts.append(_add_lags(g))

        codes = da.code_series(db_path, b, complete_only=False)
        for code, d in codes.items():
            d = d.copy(); d.insert(1, "block_code", b); d.insert(2, "icd_code", code)
            ma_parts.append(d)
        for code, sh in da.fixed_shares(db_path, b).items():
            tt_parts.append({"block_code": b, "icd_code": code, "share": sh})

    nhom = pd.concat(nhom_parts, ignore_index=True)
    ma = pd.concat(ma_parts, ignore_index=True) if ma_parts else pd.DataFrame()
    # is_complete cho mức mã: lấy theo kỳ của nhóm (cùng mốc chốt)
    if not ma.empty:
        flag = nhom[["period", "block_code", "is_complete"]].drop_duplicates()
        ma = ma.merge(flag, on=["period", "block_code"], how="left")
    ty_trong = pd.DataFrame(tt_parts)
    return {"nhom": nhom, "ma": ma, "ty_trong": ty_trong}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export(db_path: str, out_dir: str | Path, region: str = "TOAN_QUOC",
           parquet: bool = True) -> dict:
    """Ghi ba file + manifest.json vào `out_dir`. Trả manifest."""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    frames = build_frames(db_path, region)
    files = {}
    for key, df in frames.items():
        p = out / FILES[key]
        df.to_csv(p, index=False, encoding="utf-8-sig", float_format="%.6g")
        entry = {"csv": p.name, "rows": int(len(df)), "cols": list(df.columns),
                 "sha256": _sha256(p)}
        if parquet:
            try:
                pq = p.with_suffix(".parquet"); df.to_parquet(pq, index=False)
                entry["parquet"] = pq.name
            except Exception:                                 # noqa: BLE001 — pyarrow tuỳ chọn
                pass
        files[key] = entry

    nhom = frames["nhom"]
    closed = nhom[nhom["is_complete"] == 1]
    manifest = {
        "dataset": "MedForecast — bộ huấn luyện dự báo ca bệnh hô hấp theo tháng",
        "version": DATASET_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "source_db": str(db_path),
        "region": region,
        "blocks": sorted(nhom["block_code"].unique().tolist()),
        "period_min": str(nhom["period"].min()), "period_max": str(nhom["period"].max()),
        "period_max_closed": str(closed["period"].max()) if not closed.empty else None,
        "n_periods_closed_per_block": int(closed.groupby("block_code").size().min()) if not closed.empty else 0,
        "n_icd_codes": int(frames["ma"]["icd_code"].nunique()) if not frames["ma"].empty else 0,
        "weather_months": int(nhom.dropna(subset=["temp"])["period"].nunique()) if "temp" in nhom else 0,
        "files": files,
        "split_protocol": {
            "kind": "walk-forward, expanding window, 1-step-ahead",
            "min_train_months": 24,
            "test_steps_per_block": int(max(0, (closed.groupby("block_code").size().min() if not closed.empty else 0) - 24)),
            "open_period_excluded": True,
            "note": "Không chia 80/20 một lần: với chuỗi thời gian, mỗi bước kiểm định là một lần huấn luyện lại trên toàn bộ quá khứ trước bước đó.",
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


# ─────────────────────────────────────────────────────────────────────────────
# Nạp lại — trả về đúng cấu trúc mà walk_forward_frames / forecast_group_next cần
# ─────────────────────────────────────────────────────────────────────────────

def load(data_dir: str | Path, complete_only: bool = True,
         from_period: Optional[str] = None) -> Dict[str, object]:
    """Đọc dataset/vX → {blocks, group[b], codes[b], shares[b], weather, manifest}.

    `complete_only=True` bỏ kỳ chưa chốt (giống service). Thời tiết trả bảng
    riêng [period, temp, humidity, rainfall] để `join_weather` ghép đúng như
    khi đọc DB — cột *_lag trong CSV là để người đọc, mô hình tự tính lại.
    """
    d = Path(data_dir)
    nhom = pd.read_csv(d / FILES["nhom"], encoding="utf-8-sig", dtype={"period": str})
    ma = pd.read_csv(d / FILES["ma"], encoding="utf-8-sig", dtype={"period": str})
    tt = pd.read_csv(d / FILES["ty_trong"], encoding="utf-8-sig")
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8")) if (d / "manifest.json").exists() else {}

    weather = (nhom[["period"] + WCOLS].drop_duplicates("period").sort_values("period").reset_index(drop=True)
               if all(c in nhom for c in WCOLS) else pd.DataFrame())

    def _clean(df: pd.DataFrame) -> pd.DataFrame:
        df = df.sort_values("period").reset_index(drop=True)
        if complete_only and "is_complete" in df:
            df = df[df["is_complete"] == 1].reset_index(drop=True)
        if from_period:
            df = df[df["period"] >= from_period].reset_index(drop=True)
        df["cases"] = df["cases"].astype(float)
        df["is_covid"] = df["is_covid"].astype(bool)
        return df

    blocks = sorted(nhom["block_code"].unique().tolist())
    group = {b: _clean(nhom[nhom["block_code"] == b][["period", "year", "month", "cases", "is_covid", "is_complete"]])
             for b in blocks}
    codes: Dict[str, Dict[str, pd.DataFrame]] = {}
    for b in blocks:
        sub = ma[ma["block_code"] == b]
        codes[b] = {c: _clean(g[["period", "year", "month", "cases", "is_covid", "is_complete"]])[
                        ["period", "year", "month", "cases", "is_covid"]]
                    for c, g in sub.groupby("icd_code")}
    shares = {b: {r.icd_code: float(r.share) for r in tt[tt["block_code"] == b].itertuples()} for b in blocks}
    return {"blocks": blocks, "group": group, "codes": codes, "shares": shares,
            "weather": weather, "manifest": manifest}


def main(argv=None):
    """CLI: python -m app.forecasting.dataset --db data/medforecast.db --out ../dataset/v1"""
    import argparse
    ap = argparse.ArgumentParser(description="Xuất bộ huấn luyện đóng gói từ DB SQLite")
    ap.add_argument("--db", default="data/medforecast.db")
    ap.add_argument("--out", default="../dataset/v1")
    ap.add_argument("--region", default="TOAN_QUOC")
    ap.add_argument("--no-parquet", action="store_true")
    a = ap.parse_args(argv)
    m = export(a.db, a.out, a.region, parquet=not a.no_parquet)
    print(json.dumps({k: v for k, v in m.items() if k != "files"}, ensure_ascii=False, indent=2))
    for k, f in m["files"].items():
        print(f"  {k:9s} {f['csv']:24s} {f['rows']:5d} dòng  sha256 {f['sha256'][:12]}…")


if __name__ == "__main__":
    main()
