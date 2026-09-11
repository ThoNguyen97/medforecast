"""DASHBOARD v2 — MỘT PAYLOAD DỰNG ĐỦ MÀN HÌNH TỔNG QUAN (Tuần 3, 11/09/2026).

Đặt tại: backend/app/services/dss_dashboard.py

Hai hàm công khai, ứng với hai endpoint:

    overview_payload(db, ...)   nhanh — số ca, DOI, cảnh báo, phân cấp, chất lượng
    forecast_payload(db, ...)   chậm lần đầu — Ŷ_g cho 3 khối bằng ensemble
                                PRODUCTION_CONFIG, cache trong `dss_forecast_cache`

VÌ SAO TÁCH HAI
Ensemble mức nhóm phải khớp lại ~25 lần cho mỗi khối để dựng khoảng thực
nghiệm (interval_n_back = 24). Có SARIMAX thì mất vài chục giây ở lần đầu.
Nếu gộp vào một endpoint, người dùng nhìn màn hình trắng chừng ấy thời gian.
Tách ra thì thẻ KPI và bảng cảnh báo hiện ngay, riêng thẻ dự báo hiện "đang
tính" — và sau lần đầu, khoá cache theo DẤU VÂN TAY dữ liệu nên các lần sau
là tức thì. Khoá đổi khi chuỗi ca / thời tiết / cấu hình đổi, nên không cần
xoá cache tay sau khi đồng bộ.

Tầng 1 ở đây dùng CÙNG ensemble với trang Kế hoạch (`forecast_group()` của
HierarchicalForecastService), thay cho `topdown.py` (Ridge riêng, chưa từng
có trong bảng so sánh — M11). Hai màn hình không còn hai con số.

HỢP ĐỒNG: không có trường nào thuộc phân hệ mua sắm (PO, ROP, lead time,
safety_stock). Cột "thiếu hụt dự kiến" là Δ_need = max(0, D_forecast − S_usable).
"""
from __future__ import annotations

import csv
import json
import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.forecasting.config import PRODUCTION_CONFIG
from app.services import dss_alerts, dss_demand, dss_runner, period_service as ps
from app.services.hierarchical_forecast_service import HierarchicalForecastService

logger = logging.getLogger(__name__)

BLOCKS = tuple(dss_demand.BLOCKS)
LEVELS = ("red", "amber", "green", "grey")
TOAN_QUOC = "TOAN_QUOC"

# Thư mục kết quả backtest chính thức (run_eval.py --out ketqua_backtest)
KETQUA_BACKTEST_DIR = Path(__file__).resolve().parents[2] / "ketqua_backtest"
PHUONG_AN_CHINH_THUC = "Top-down động"


# ─────────────────────────────────────────────────────────────────────────────
# Cache dự báo mức nhóm
# ─────────────────────────────────────────────────────────────────────────────

_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS dss_forecast_cache (
    block_code    TEXT NOT NULL,
    fingerprint   TEXT NOT NULL,
    target_period TEXT,
    payload       TEXT NOT NULL,
    computed_at   TEXT NOT NULL,
    PRIMARY KEY (block_code, fingerprint)
)
"""


_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS forecast_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    computed_at   TEXT NOT NULL,
    block_code    TEXT NOT NULL,
    anchor_period TEXT,
    target_period TEXT NOT NULL,
    point         REAL, point_raw REAL, lower REAL, upper REAL, level REAL,
    bias_factor   REAL,
    weights       TEXT, members_used TEXT, members_failed TEXT,
    n_history     INTEGER,
    config        TEXT,
    fingerprint   TEXT,
    actual        REAL, abs_err REAL, pct_err REAL, in_interval INTEGER,
    actual_filled_at TEXT
)
"""


def _ensure_cache(db: Session) -> None:
    db.execute(text(_CACHE_DDL))
    db.execute(text(_RUNS_DDL))
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# LƯU VẾT HUẤN LUYỆN (Tuần 4c, 11/09/2026)
#
# Mỗi lần app khớp mô hình cho một khối (cache miss) là một dòng: kỳ đích, điểm,
# khoảng, trọng số, hệ số lệch, thành viên, cấu hình. Khi kỳ đích chốt (sau đồng
# bộ), `fill_actuals` điền thực tế và sai số. Đây là "sổ theo dõi" sống của mô
# hình trong vận hành — khác backtest ở chỗ nó ghi đúng con số màn hình đã hiện
# vào thời điểm đó, không thể chỉnh lại sau.
# ─────────────────────────────────────────────────────────────────────────────

def _log_run(db: Session, block: str, fp: str, payload: Dict[str, Any]) -> None:
    m = payload.get("model") or {}
    try:
        db.execute(text(
            "INSERT INTO forecast_runs (computed_at, block_code, anchor_period, target_period, "
            "point, point_raw, lower, upper, level, bias_factor, weights, members_used, "
            "members_failed, n_history, config, fingerprint) VALUES "
            "(:c, :b, :a, :t, :p, :pr, :lo, :hi, :lv, :bf, :w, :mu, :mf, :nh, :cfg, :fp)"),
            {"c": datetime.now().isoformat(timespec="seconds"), "b": block,
             "a": payload.get("anchor_period"), "t": payload.get("target_period"),
             "p": payload.get("point"), "pr": m.get("point_raw"),
             "lo": payload.get("lower"), "hi": payload.get("upper"), "lv": payload.get("level"),
             "bf": m.get("bias_factor"),
             "w": json.dumps(m.get("weights") or {}, ensure_ascii=False),
             "mu": json.dumps(m.get("members_used") or [], ensure_ascii=False),
             "mf": json.dumps(m.get("members_failed") or {}, ensure_ascii=False),
             "nh": payload.get("n_history_months"),
             "cfg": json.dumps(m.get("config") or {}, ensure_ascii=False), "fp": fp})
        db.commit()
    except Exception as exc:                                  # noqa: BLE001
        db.rollback()
        logger.warning("Không ghi được forecast_runs: %s", exc)


def fill_actuals(db: Session) -> int:
    """Điền thực tế cho các dòng có kỳ đích ĐÃ CHỐT. Trả số dòng vừa điền."""
    try:
        _ensure_cache(db)
        rows = db.execute(text(
            "SELECT r.id, r.block_code, r.target_period, r.point, r.lower, r.upper, m.cases "
            "FROM forecast_runs r JOIN mart_monthly_cases_by_block m "
            "  ON m.block_code = r.block_code AND m.period = r.target_period "
            " AND m.region = :reg AND m.is_complete = 1 "
            "WHERE r.actual IS NULL"), {"reg": TOAN_QUOC}).fetchall()
        n = 0
        now = datetime.now().isoformat(timespec="seconds")
        for r in rows:
            actual = float(r[6] or 0); point = float(r[3] or 0)
            in_iv = (int(r[4] <= actual <= r[5]) if (r[4] is not None and r[5] is not None) else None)
            db.execute(text(
                "UPDATE forecast_runs SET actual = :a, abs_err = :e, pct_err = :pe, "
                "in_interval = :ii, actual_filled_at = :now WHERE id = :id"),
                {"a": actual, "e": abs(point - actual),
                 "pe": ((point - actual) / actual * 100.0) if actual > 0 else None,
                 "ii": in_iv, "now": now, "id": r[0]})
            n += 1
        db.commit()
        return n
    except Exception as exc:                                  # noqa: BLE001
        db.rollback()
        logger.warning("fill_actuals lỗi: %s", exc)
        return 0


def forecast_history(db: Session, limit: int = 60) -> Dict[str, Any]:
    """Sổ theo dõi: các lần khớp gần nhất + tổng kết trên các kỳ đã đối chiếu."""
    _ensure_cache(db)
    fill_actuals(db)
    rows = db.execute(text(
        "SELECT id, computed_at, block_code, anchor_period, target_period, point, point_raw, "
        "lower, upper, level, bias_factor, weights, members_used, n_history, actual, abs_err, "
        "pct_err, in_interval, actual_filled_at FROM forecast_runs ORDER BY id DESC LIMIT :n"),
        {"n": int(limit)}).fetchall()
    cols = ["id", "computed_at", "block_code", "anchor_period", "target_period", "point", "point_raw",
            "lower", "upper", "level", "bias_factor", "weights", "members_used", "n_history",
            "actual", "abs_err", "pct_err", "in_interval", "actual_filled_at"]
    items = []
    for r in rows:
        d = dict(zip(cols, r))
        for k in ("weights", "members_used"):
            try:
                d[k] = json.loads(d[k]) if d[k] else None
            except Exception:                                 # noqa: BLE001
                pass
        items.append(d)

    # Tổng kết: mỗi (khối, kỳ đích) chỉ tính lần khớp CUỐI trước khi kỳ chốt
    ver = db.execute(text(
        "SELECT block_code, target_period, point, actual, abs_err, pct_err, in_interval "
        "FROM forecast_runs WHERE actual IS NOT NULL AND id IN ("
        "  SELECT MAX(id) FROM forecast_runs WHERE actual IS NOT NULL GROUP BY block_code, target_period)")).fetchall()
    tong = {"n_verified": len(ver)}
    if ver:
        ae = [float(v[4]) for v in ver]; act = [float(v[3]) for v in ver]; pt = [float(v[2]) for v in ver]
        tong.update({
            "mae": round(sum(ae) / len(ae), 2),
            "wape_pct": (round(sum(ae) / sum(act) * 100, 1) if sum(act) > 0 else None),
            "mpe_pct": (round((sum(pt) - sum(act)) / sum(act) * 100, 1) if sum(act) > 0 else None),
            "coverage_pct": (round(sum(1 for v in ver if v[6]) / sum(1 for v in ver if v[6] is not None) * 100, 1)
                             if any(v[6] is not None for v in ver) else None),
            "by_block": {b: sum(1 for v in ver if v[0] == b) for b in BLOCKS},
        })
    n_runs = db.execute(text("SELECT COUNT(*) FROM forecast_runs")).scalar() or 0
    return {"items": items, "summary": {**tong, "n_runs": int(n_runs)},
            "ghi_chu": ("Mỗi dòng là một lần app khớp mô hình (cache miss). Tổng kết chỉ tính lần khớp "
                        "cuối của mỗi (khối, kỳ) sau khi kỳ đó chốt — số màn hình đã hiện, không chỉnh lại.")}


def _read_cache(db: Session, block: str, fp: str) -> Optional[Dict[str, Any]]:
    row = db.execute(text(
        "SELECT payload, computed_at FROM dss_forecast_cache "
        "WHERE block_code = :b AND fingerprint = :f"), {"b": block, "f": fp}).first()
    if not row:
        return None
    d = json.loads(row[0])
    d["computed_at"] = row[1]
    d["from_cache"] = True
    return d


def _write_cache(db: Session, block: str, fp: str, payload: Dict[str, Any]) -> None:
    # Mỗi khối chỉ giữ bản mới nhất — bảng không phình theo số lần đồng bộ.
    db.execute(text("DELETE FROM dss_forecast_cache WHERE block_code = :b"), {"b": block})
    db.execute(text(
        "INSERT INTO dss_forecast_cache (block_code, fingerprint, target_period, payload, computed_at) "
        "VALUES (:b, :f, :t, :p, :c)"),
        {"b": block, "f": fp, "t": payload.get("target_period"),
         "p": json.dumps(payload, ensure_ascii=False, default=str),
         "c": datetime.now().isoformat(timespec="seconds")})
    db.commit()


def forecast_payload(db: Session, compute: bool = True,
                     force: bool = False) -> Dict[str, Any]:
    """Ŷ_g + khoảng tin cậy cho từng khối, và tổng.

    `compute=False`: chỉ đọc cache, không khớp mô hình — dùng cho endpoint
    nhanh để biết dự báo đã sẵn chưa. `force=True`: bỏ cache, tính lại.
    """
    _ensure_cache(db)
    svc = HierarchicalForecastService(db)
    blocks: List[Dict[str, Any]] = []
    missing: List[str] = []
    errors: List[str] = []

    for b in BLOCKS:
        try:
            fp = svc.group_series_fingerprint(b)
        except Exception as exc:                              # noqa: BLE001
            errors.append(f"{b}: {exc}")
            missing.append(b)
            continue
        hit = None if force else _read_cache(db, b, fp)
        if hit is None:
            if not compute:
                missing.append(b)
                continue
            try:
                hit = svc.forecast_group(b)
                _write_cache(db, b, fp, hit)
                _log_run(db, b, fp, hit)                   # Tuần 4c: sổ theo dõi
                hit["computed_at"] = datetime.now().isoformat(timespec="seconds")
                hit["from_cache"] = False
            except Exception as exc:                          # noqa: BLE001
                logger.exception("Dự báo khối %s lỗi", b)
                errors.append(f"{b}: {exc}")
                missing.append(b)
                continue
        blocks.append(hit)

    ready = len(blocks) == len(BLOCKS)
    tong: Dict[str, Any] = {"point": None, "lower": None, "upper": None}
    if blocks:
        tong["point"] = int(round(sum(float(x["point"]) for x in blocks)))
        if all(x.get("lower") is not None for x in blocks):
            tong["lower"] = int(sum(int(x["lower"]) for x in blocks))
            tong["upper"] = int(sum(int(x["upper"]) for x in blocks))
    target = blocks[0]["target_period"] if blocks else None
    anchor = blocks[0]["anchor_period"] if blocks else None

    ghi_chu: List[str] = []
    if ready and tong["lower"] is not None:
        ghi_chu.append("Khoảng của tổng = cộng khoảng ba khối — bảo thủ (rộng hơn "
                       "khoảng thật vì bỏ qua bù trừ giữa các khối).")
    for x in blocks:
        if x.get("lower") is not None and x["lower"] > x["point"]:
            ghi_chu.append(f"{x['block']}: cận dưới ({x['lower']}) nằm trên điểm dự báo "
                           f"({x['point']:.0f}) — mô hình dự báo THẤP có hệ thống cho "
                           "khối này trong các bước walk-forward gần đây; đọc khoảng, "
                           "đừng đọc điểm.")
        if x.get("upper") is not None and x["upper"] < x["point"]:
            ghi_chu.append(f"{x['block']}: cận trên ({x['upper']}) nằm dưới điểm dự báo "
                           f"({x['point']:.0f}) — mô hình dự báo CAO có hệ thống cho "
                           "khối này gần đây; đọc khoảng, đừng đọc điểm.")

    return {
        "ready": ready,
        "blocks": blocks,
        "missing": missing,
        "errors": errors,
        "total": tong,
        "target_period": target,
        "anchor_period": anchor,
        "level": PRODUCTION_CONFIG.interval_level,
        "config": PRODUCTION_CONFIG.as_record(),
        "computed_at": max((x.get("computed_at") or "" for x in blocks), default=None),
        "ghi_chu": ghi_chu,
    }


def _forecast_by_block_from_cache(db: Session) -> Dict[str, float]:
    fc = forecast_payload(db, compute=False)
    if not fc["ready"]:
        return {}
    return {x["block"]: float(x["point"]) for x in fc["blocks"]}


# ─────────────────────────────────────────────────────────────────────────────
# Chuỗi xu hướng: 12 kỳ gần nhất, tổng + từng khối, kèm cùng kỳ năm trước
# ─────────────────────────────────────────────────────────────────────────────

def _trend_series(db: Session, end_period: Optional[str], n: int = 12) -> Dict[str, Any]:
    if not end_period or not ps._has(db, "mart_monthly_cases_by_block"):
        return {"periods": [], "total": [], "by_block": {}, "last_year": {}}
    start = ps.shift_period(end_period, -(n - 1))
    start_ly = ps.shift_period(start, -12)
    rows = db.execute(text(
        "SELECT period, block_code, cases, is_complete "
        "FROM mart_monthly_cases_by_block "
        "WHERE region = :r AND period >= :s AND period <= :e "
        "ORDER BY period, block_code"),
        {"r": TOAN_QUOC, "s": start_ly, "e": end_period}).fetchall()

    cases: Dict[str, Dict[str, int]] = {}
    complete: Dict[str, bool] = {}
    for r in rows:
        cases.setdefault(r.period, {})[r.block_code] = int(r.cases or 0)
        complete[r.period] = complete.get(r.period, True) and bool(r.is_complete)

    periods = [ps.shift_period(start, i) for i in range(n)]
    periods = [p for p in periods if p and p in cases]

    def _tot(p: Optional[str]) -> Optional[int]:
        return sum(cases[p].values()) if p and p in cases else None

    out_total, by_block, last_year = [], {b: [] for b in BLOCKS}, {"total": [], "by_block": {b: [] for b in BLOCKS}}
    for p in periods:
        ly = ps.shift_period(p, -12)
        out_total.append({"period": p, "month": f"T{int(p[5:7])}",
                          "cases": _tot(p), "is_complete": complete.get(p, False)})
        last_year["total"].append({"period": ly, "cases": _tot(ly)})
        for b in BLOCKS:
            by_block[b].append({"period": p, "cases": cases[p].get(b, 0),
                                "is_complete": complete.get(p, False)})
            last_year["by_block"][b].append(
                {"period": ly, "cases": (cases[ly].get(b) if ly in cases else None)})
    return {"periods": periods, "total": out_total, "by_block": by_block,
            "last_year": last_year}


# ─────────────────────────────────────────────────────────────────────────────
# Chất lượng dự báo — đọc kết quả backtest chính thức (run_eval.py)
# ─────────────────────────────────────────────────────────────────────────────

def _read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _f(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def backtest_quality(dir_: Path = KETQUA_BACKTEST_DIR) -> Dict[str, Any]:
    """Đọc `phancap.csv`, `nhom.csv`, `cau_hinh.json` do run_eval.py ghi.

    Không có thư mục → `available = False`, giao diện phải nói "chưa chạy
    backtest", không bịa số. RelMAE gộp = Σ MAE / Σ MAE_naive (trọng số theo
    số bước), không phải trung bình cộng ba RelMAE.
    """
    out: Dict[str, Any] = {"available": False, "source": str(dir_),
                           "phuong_an": PHUONG_AN_CHINH_THUC}
    p_phancap, p_nhom, p_cfg = dir_ / "phancap.csv", dir_ / "nhom.csv", dir_ / "cau_hinh.json"
    if not (p_phancap.exists() and p_nhom.exists()):
        return out
    try:
        phancap = [r for r in _read_csv(p_phancap)
                   if (r.get("phuong_an") or "").startswith(PHUONG_AN_CHINH_THUC)]
        nhom = _read_csv(p_nhom)
    except Exception as exc:                                  # noqa: BLE001
        out["error"] = str(exc)
        return out

    by_block: Dict[str, Dict[str, Any]] = {}
    sum_mae = sum_naive = 0.0
    for r in phancap:
        b = r["nhom"]
        mae, rel, n = _f(r.get("MAE")), _f(r.get("RelMAE")), _f(r.get("n_buoc")) or 0
        by_block.setdefault(b, {"block": b})
        by_block[b].update({"rel_mae_codes": rel, "mae_codes": mae,
                            "mpe_codes_pct": _f(r.get("MPE_pct")),
                            "n_codes": int(_f(r.get("n_ma")) or 0), "n_steps": int(n)})
        if mae is not None and rel and rel > 0:
            sum_mae += mae * n
            sum_naive += (mae / rel) * n
    for r in nhom:
        b = r["nhom"]
        by_block.setdefault(b, {"block": b})
        by_block[b].update({"rel_mae_group": _f(r.get("RelMAE")),
                            "mpe_group_pct": _f(r.get("MPE_pct")),
                            "coverage_pct": _f(r.get("do_phu_pct")),
                            "coverage_n": int(_f(r.get("do_phu_n")) or 0),
                            "weather": (r.get("thoi_tiet") or "").lower() == "true"})

    rel_pooled = (sum_mae / sum_naive) if sum_naive > 0 else None
    # Con số tiêu đề = trung bình ba khối (khớp KetQua_Backtest_ChonCauHinh.md);
    # bản gộp theo trọng số MAE trả kèm để đối chiếu.
    rels = [v["rel_mae_codes"] for v in by_block.values() if v.get("rel_mae_codes") is not None]
    rel_mean = (sum(rels) / len(rels)) if rels else None
    run_at, co_sm = None, None
    if p_cfg.exists():
        try:
            cfg = json.loads(p_cfg.read_text(encoding="utf-8"))
            run_at, co_sm = cfg.get("chay_luc"), cfg.get("co_statsmodels")
        except Exception:                                     # noqa: BLE001
            pass
    cov = [v["coverage_pct"] for v in by_block.values() if v.get("coverage_pct") is not None]
    out.update({
        "available": True,
        "run_at": run_at,
        "co_statsmodels": co_sm,
        "rel_mae_codes": (round(rel_mean, 3) if rel_mean is not None else None),
        "rel_mae_codes_pooled": (round(rel_pooled, 3) if rel_pooled is not None else None),
        "improvement_vs_naive_pct": (round((1 - rel_mean) * 100, 1)
                                     if rel_mean is not None else None),
        "coverage_mean_pct": (round(sum(cov) / len(cov), 1) if cov else None),
        "coverage_target_pct": round(PRODUCTION_CONFIG.interval_level * 100),
        "by_block": [by_block[b] for b in BLOCKS if b in by_block],
        "ghi_chu": ("Walk-forward mở rộng, min_train 24, cửa sổ kiểm 24 bước. RelMAE = "
                    "MAE / MAE(seasonal naive) trên cùng tập kiểm; < 1 là tốt hơn naive."),
    })
    if co_sm is False:
        out["canh_bao"] = "Backtest chạy KHÔNG có statsmodels (thiếu SARIMAX) — không phải số chính thức."
    return out


# ─────────────────────────────────────────────────────────────────────────────
# DOI theo danh mục
# ─────────────────────────────────────────────────────────────────────────────

def _doi_by_category(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    gom: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        c = r.get("danh_muc") or "Khác"
        g = gom.setdefault(c, {"category": c, "n": 0, "red": 0, "amber": 0,
                               "green": 0, "grey": 0, "_doi": []})
        g["n"] += 1
        g[r["muc"]] += 1
        if r["doi"] is not None:
            g["_doi"].append(float(r["doi"]))
    out = []
    for g in gom.values():
        d = g.pop("_doi")
        g["median_doi"] = round(statistics.median(d), 1) if d else None
        g["n_measured"] = len(d)
        out.append(g)
    # Danh mục nguy hiểm nhất lên đầu; chưa đo được xuống cuối.
    out.sort(key=lambda g: (g["median_doi"] is None, g["median_doi"] or 0, -g["n"]))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Diễn giải nhanh — quy tắc đơn giản, nói đúng những gì dữ liệu nói
# ─────────────────────────────────────────────────────────────────────────────

def _insights(anchor, cases_last, cases_prev, trend, fc, sig, tap, doi_cat,
              grey_reasons: Dict[str, int]) -> List[Dict[str, str]]:
    ins: List[Dict[str, str]] = []
    lc, pv = anchor.get("last_closed_period"), anchor.get("prev_closed_period")
    if lc and pv and cases_prev:
        chieu = "tăng" if trend > 0 else ("giảm" if trend < 0 else "đi ngang")
        ins.append({"tone": "info", "text":
                    f"Kỳ đã chốt {lc}: {cases_last:,} ca, {chieu} {abs(trend):.1f}% so với {pv} "
                    f"({cases_prev:,} ca)."})
    if fc.get("ready"):
        t = fc["total"]
        khoang = (f", khoảng {t['lower']:,}–{t['upper']:,} (mức {int(fc['level']*100)}%)"
                  if t.get("lower") is not None else "")
        ins.append({"tone": "info", "text":
                    f"Dự báo kỳ {fc['target_period']}: {t['point']:,} ca{khoang}."})
        for g in fc.get("ghi_chu", []):
            if "cận" in g:
                ins.append({"tone": "warn", "text": g})
    else:
        ins.append({"tone": "warn", "text":
                    "Chưa có dự báo cho kỳ tới — thẻ dự báo đang tính; cột \"Thiếu hụt dự kiến\" "
                    "để trống. DOI vẫn đúng vì mẫu số lấy từ tiêu hao 12 kỳ."})
    if sig.get("measured"):
        ins.append({"tone": "critical" if sig["red"] else "info", "text":
                    f"{sig['red']} mã Đỏ (DOI ≤ {sig['nguong']['red_days']:.0f} ngày) và "
                    f"{sig['amber']} mã Vàng trên {tap} mã; {sig['zero_stock']} mã đã hết hàng thật."})
    if doi_cat:
        worst = doi_cat[0]
        if worst.get("median_doi") is not None:
            ins.append({"tone": "warn" if worst["median_doi"] <= 36 else "info", "text":
                        f"Danh mục có DOI trung vị thấp nhất: {worst['category']} "
                        f"({worst['median_doi']} ngày, {worst['red']} mã Đỏ / {worst['n']} mã)."})
    if sig.get("grey"):
        ly = ", ".join(f"{_ly_do_xam_ten(k)} {v}" for k, v in
                       sorted(grey_reasons.items(), key=lambda kv: -kv[1]))
        ins.append({"tone": "muted", "text":
                    f"{sig['grey']} mã Xám (chưa đo được): {ly}."})
    return ins


def _ly_do_xam_ten(key: str) -> str:
    return {
        "no_norm": "không có định mức",
        "no_forecast": "không có dự báo",
        "no_stock_data": "không có dữ liệu tồn",
        "period_not_closed": "kỳ chưa chốt",
    }.get(key, key)


# ─────────────────────────────────────────────────────────────────────────────
# Payload chính
# ─────────────────────────────────────────────────────────────────────────────

def overview_payload(db: Session, focus: bool = True,
                     level: Optional[str] = None, limit: int = 8) -> Dict[str, Any]:
    """Mọi thứ Dashboard cần, TRỪ việc khớp mô hình dự báo.

    `focus`  True → tập trọng tâm (tỷ trọng hô hấp ≥ 25 %); False → toàn danh mục
    `level`  lọc bảng cảnh báo theo một mức (red/amber/green/grey); None → Đỏ + Vàng
    """
    if level is not None and level not in LEVELS:
        raise ValueError(f"level phải thuộc {LEVELS}")

    anchor = ps.get_period_anchor(db)
    last_closed, prev_closed, open_p = (anchor["last_closed_period"],
                                        anchor["prev_closed_period"], anchor["open_period"])
    cases_last = ps.cases_in_period(db, last_closed)
    cases_prev = ps.cases_in_period(db, prev_closed)
    cases_open = ps.cases_in_period(db, open_p)
    trend = ps.trend_pct(db, last_closed, prev_closed)
    blocks_closed = ps.cases_by_block(db, last_closed)

    # Tầng 1 (chỉ đọc cache) → Tầng 2
    fc = forecast_payload(db, compute=False)
    du_bao_nhom = {x["block"]: float(x["point"]) for x in fc["blocks"]} if fc["ready"] else {}
    th = dss_alerts.get_thresholds(db)
    nhu_cau: Dict[str, float] = {}
    nhu_cau_meta: Dict[str, Any] = {"ready": False}
    if du_bao_nhom:
        try:
            dm = dss_demand.demand_by_supply(db, du_bao_nhom,
                                             horizon_days=int(th.get("horizon_days", 30)))
            nhu_cau = {r["supply_code"]: r["d_forecast"] for r in dm["rows"]}
            nhu_cau_meta = {"ready": True, "so_ma": dm["so_ma"],
                            "horizon_days": dm["horizon_days"],
                            "nguon_dinh_muc": dm.get("nguon_dinh_muc"),
                            "nhom_thieu_p_hat": dm["nhom_thieu_p_hat"],
                            "nhom_thieu_dinh_muc": dm["nhom_thieu_dinh_muc"]}
        except Exception as exc:                              # noqa: BLE001
            logger.exception("Tầng 2 lỗi")
            nhu_cau_meta = {"ready": False, "error": str(exc)}

    # Tầng 3 — hai tập, đếm cả hai để bộ lọc đổi tức thì
    al_focus = dss_alerts.alert_rows(db, demand=nhu_cau, only_focus=True)
    al_all = dss_alerts.alert_rows(db, demand=nhu_cau, only_focus=False)
    chon = al_focus if focus else al_all

    def _counts(al: Dict[str, Any]) -> Dict[str, Any]:
        if not al.get("san_sang"):
            return {"red": 0, "amber": 0, "green": 0, "grey": 0, "total": 0,
                    "zero_stock": 0, "measured": 0, "san_sang": False}
        t = al["tong_hop"]
        return {"red": t["red"], "amber": t["amber"], "green": t["green"],
                "grey": t["grey"], "total": t["tong_ma"], "measured": t["do_duoc"],
                "zero_stock": sum(1 for r in al["rows"] if r["doi"] == 0.0),
                "fefo_codes": t.get("so_ma_ap_dung_fefo", 0),
                "ly_do_xam": t.get("ly_do_xam", {}), "san_sang": True}

    dem_focus, dem_all = _counts(al_focus), _counts(al_all)
    dem = dem_focus if focus else dem_all
    sig = {**dem, "nguong": {"red_days": float(th["doi_red_days"]),
                             "amber_days": float(th["doi_amber_days"])}}

    rows = chon.get("rows") or []
    if level is None:
        rows_tbl = [r for r in rows if r["muc"] in ("red", "amber")]
    else:
        rows_tbl = [r for r in rows if r["muc"] == level]
    thu_tu = {"red": 0, "amber": 1, "green": 2, "grey": 3}
    rows_tbl.sort(key=lambda r: (thu_tu[r["muc"]],
                                 r["doi"] if r["doi"] is not None else 10 ** 9,
                                 -(r["delta_need"] or 0)))
    alerts = [{
        "supply_code": r["supply_code"], "ten": r["ten"], "don_vi": r["don_vi"],
        "nhom": r["nhom"], "danh_muc": r["danh_muc"],
        "s_total": r["s_total"], "s_usable": r["s_usable"], "s_expiring": r["s_expiring"],
        "d_daily": r["d_daily"], "d_forecast": r["d_forecast"], "delta_need": r["delta_need"],
        "doi": r["doi"], "muc": r["muc"], "ly_do_xam": r["ly_do_xam"],
        "fefo_ap_dung": r["fefo_ap_dung"], "ty_trong_hohap": r["ty_trong_hohap"],
    } for r in rows_tbl[:limit]]

    risk = ps.assess_overall_risk(trend, dem_focus["red"], dem_focus["amber"])
    cat = ps.catalogue_counts(db)

    # Tình trạng dữ liệu (phần rẻ; STA lấy qua /sync/status)
    dss_tables: Dict[str, Any] = {}
    for t, k in (("fact_usage_total", "period"), ("fact_cases_by_care_level", "period"),
                 ("fact_usage_by_care_level", "period"), ("fact_inventory_lot", "snapshot_date")):
        try:
            r = db.execute(text(f"SELECT COUNT(*), MAX({k}) FROM {t}")).first()
            dss_tables[t] = {"rows": int(r[0] or 0), "latest": r[1]}
        except Exception:                                     # noqa: BLE001
            db.rollback()
            dss_tables[t] = None
    last_sync = None
    try:
        r = db.execute(text("SELECT source, last_period, rows_ingested, status, run_at "
                            "FROM sync_state ORDER BY id DESC LIMIT 1")).first()
        if r:
            last_sync = {"source": r[0], "last_period": r[1], "rows_ingested": r[2],
                         "status": r[3], "run_at": str(r[4])}
    except Exception:                                         # noqa: BLE001
        db.rollback()

    quality = backtest_quality()
    try:
        _ensure_cache(db)
        fill_actuals(db)
        quality["track_record"] = forecast_history(db, limit=1)["summary"]
    except Exception as exc:                                  # noqa: BLE001
        quality["track_record"] = {"n_runs": 0, "n_verified": 0, "error": str(exc)[:120]}
    doi_cat = _doi_by_category(rows)
    tap_ten = "tập trọng tâm" if focus else "toàn danh mục"

    return {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "last_closed_period": last_closed,
            "prev_closed_period": prev_closed,
            "open_period": open_p,
            "forecast_period": fc.get("target_period") or ps.shift_period(last_closed, 1),
            "focus": focus, "level": level, "limit": limit,
            "thresholds": sig["nguong"],
            "horizon_days": int(th.get("horizon_days", 30)),
            "fefo_window_days": int(th.get("fefo_window_days", 30)),
            "assumptions_note": "Tồn kho tính trên hàng hiện có, chưa trừ hàng đang về.",
        },
        "cases": {
            "last_closed": {"period": last_closed, "cases": cases_last, "trend_pct": trend,
                            "prev_period": prev_closed, "prev_cases": cases_prev},
            "open": {"period": open_p, "cases": cases_open,
                     "note": "Kỳ chưa chốt — không tính vào xu hướng."},
            "by_block": blocks_closed,
        },
        "forecast": {  # bản tóm tắt; bản đầy đủ ở /dashboard/v2/forecast
            "ready": fc["ready"], "target_period": fc.get("target_period"),
            "total": fc["total"], "level": fc["level"],
            "blocks": [{"block": x["block"], "point": x["point"], "lower": x.get("lower"),
                        "upper": x.get("upper")} for x in fc["blocks"]],
            "computed_at": fc.get("computed_at"), "ghi_chu": fc.get("ghi_chu", []),
        },
        "demand": nhu_cau_meta,
        "risk": {
            "selected": tap_ten, "counts": sig,
            "focus": dem_focus, "all": dem_all,
            "overall": risk,
            "basis": "DOI = S_usable(FEFO) / d_daily · Đỏ ≤ %.0f · Vàng ≤ %.0f · Xanh > %.0f ngày"
                     % (sig["nguong"]["red_days"], sig["nguong"]["amber_days"], sig["nguong"]["amber_days"]),
            "canh_bao": chon.get("canh_bao", []),
        },
        "catalogue": cat,
        "alerts": alerts,
        "alerts_total_matched": len(rows_tbl),
        "doi_by_category": doi_cat,
        "trend": _trend_series(db, open_p or last_closed, 12),
        "care_level": dss_runner.care_level_payload(db),
        "quality": quality,
        "data_status": {"dss_tables": dss_tables, "last_sync": last_sync,
                        "fefo": {"codes": dem_all.get("fefo_codes", 0), "total": dem_all["total"]},
                        "nguon_ton_kho": (al_all.get("tong_hop") or {}).get("nguon_ton_kho")},
        "insights": _insights(anchor, cases_last, cases_prev, trend, fc, sig,
                              dem["total"], doi_cat, dem.get("ly_do_xam", {})),
    }
