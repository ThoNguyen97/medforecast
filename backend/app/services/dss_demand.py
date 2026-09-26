"""Tầng 2: quy đổi số ca bệnh dự báo (Tầng 1) sang nhu cầu thuốc theo rổ chăm sóc.
Ŷ_g,ro = Ŷ_g × p̂(g,ro)
D_i = Σ_g Σ_ro Ŷ_g,ro × Norm(i,g,ro) + D_i,baseline
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

BLOCKS = ("J00-J06", "J09-J18", "J20-J22")
RO_ALL = ("NGT", "NT1", "NT2", "NT3", "NT0")
RO_NGOAI_TRU = "NGT"                 # rổ ngoại trú; các rổ còn lại là nội trú
RO_NOI_TRU = ("NT1", "NT2", "NT3", "NT0")
RO_LABEL = {"NGT": "Ngoại trú", "NT1": "Nội trú cấp 1", "NT2": "Nội trú cấp 2",
            "NT3": "Nội trú cấp 3", "NT0": "Nội trú chưa phân cấp"}

CARE_LEVEL_DEFAULT: Dict[str, Any] = {
    "window_periods": 12, "min_period": "2025-04",
    "min_cases_per_bucket": 30, "shrink_k0": 6,
}


def _has(db: Session, name: str) -> bool:
    return bool(db.execute(
        text("SELECT 1 FROM sqlite_master WHERE name = :n LIMIT 1"),
        {"n": name}).first())


def care_cfg(db: Session) -> Dict[str, Any]:
    """`dss.care_level` đã trộn với mặc định; khoá lạ được giữ nguyên."""
    out = dict(CARE_LEVEL_DEFAULT)
    r = db.execute(text("SELECT config_value FROM system_config "
                        "WHERE config_key = 'dss.care_level'")).scalar()
    if r:
        try:
            out.update(json.loads(r))
        except Exception:                                 # noqa: BLE001
            logger.warning("dss.care_level không phải JSON hợp lệ — dùng mặc định.")
    return out


# ── p̂(g,ro): tỷ trọng rổ chăm sóc, co ngót rổ mẫu nhỏ ──

def care_level_shares(db: Session) -> Dict[str, Dict[str, float]]:
    """p̂(g,ro) từ `v_care_level_share`, trả {block_code: {ro: tỷ trọng}} tổng bằng 1.
    Rổ mẫu nhỏ co ngót chỉ trong khối nội trú, giữ nguyên p̂(NGT):
    q̂ = λ·q_đo + (1−λ)/số_rổ_nội_trú với λ = n/(n+K₀), rồi p̂(ro) = q̂·(1−p̂(NGT)).
    """
    if not _has(db, "v_care_level_share"):
        return {}
    cfg = care_cfg(db)
    k0 = float(cfg.get("shrink_k0", 6))

    rows = db.execute(text(
        "SELECT block_code, ro, cases, share_pct, mau_qua_nho, so_ky, tu_ky, den_ky "
        "FROM v_care_level_share")).fetchall()
    if not rows:
        logger.warning("v_care_level_share rỗng — fact_cases_by_care_level chưa "
                       "được nạp. Bấm «Nạp dữ liệu DW» ở trang Dữ liệu bệnh.")
        return {}

    theo_nhom: Dict[str, List[Any]] = {}
    for r in rows:
        theo_nhom.setdefault(r.block_code, []).append(r)

    out: Dict[str, Dict[str, float]] = {}
    for g, rs in theo_nhom.items():
        tong_ca = sum(float(r.cases or 0) for r in rs)
        if tong_ca <= 0:
            continue
        p_do = {r.ro: float(r.cases or 0) / tong_ca for r in rs}
        noi_tru = [r for r in rs if r.ro != RO_NGOAI_TRU]
        w = sum(p_do[r.ro] for r in noi_tru)      # khối lượng nội trú, giữ nguyên
        tam: Dict[str, float] = {r.ro: p_do[r.ro] for r in rs if r.ro == RO_NGOAI_TRU}
        if noi_tru and w > 0:
            deu = 1.0 / len(noi_tru)              # phân bố đều trong khối nội trú
            q: Dict[str, float] = {}
            for r in noi_tru:
                n = float(r.cases or 0)
                q_do = p_do[r.ro] / w
                if int(r.mau_qua_nho or 0) == 1:
                    lam = n / (n + k0) if (n + k0) > 0 else 0.0
                    q[r.ro] = lam * q_do + (1 - lam) * deu
                else:
                    q[r.ro] = q_do
            sq = sum(q.values())
            for ro, v in q.items():
                tam[ro] = (v / sq) * w if sq > 0 else 0.0
        else:
            for r in noi_tru:
                tam[r.ro] = p_do[r.ro]
        s = sum(tam.values())
        out[g] = {k: v / s for k, v in tam.items()} if s > 0 else tam
    return out


# ── Định mức thực nghiệm Norm(i, g, ro) ──

def _cua_so_ky(db: Session, cfg: Dict[str, Any]) -> List[str]:
    """`window_periods` kỳ đã chốt gần nhất kể từ `min_period`, loại tháng hiện tại."""
    if not _has(db, "fact_cases_by_care_level"):
        return []
    rows = db.execute(text(
        "SELECT DISTINCT period FROM fact_cases_by_care_level "
        "WHERE period >= :mp AND period < :thang_nay "
        "ORDER BY period DESC LIMIT :n"),
        {"mp": str(cfg.get("min_period", "2025-04")),
         "thang_nay": date.today().strftime("%Y-%m"),
         "n": int(cfg.get("window_periods", 12))}).fetchall()
    return sorted(r[0] for r in rows)


def empirical_norms(db: Session) -> Dict[str, Any]:
    """Norm(i,g,ro) = Σ tiêu hao / Σ ca theo (nhóm × rổ) trên cửa sổ kỳ đã chốt.
    Rổ dưới `min_cases_per_bucket` ca dùng định mức gộp toàn nhóm (ghi vào `ro_mau_nho`).
    Trả {"norms", "cases", "periods", "ro_mau_nho", "usage", "gop", "cfg"}.
    """
    out: Dict[str, Any] = {"norms": {}, "cases": {}, "periods": [],
                           "ro_mau_nho": {}, "usage": {}, "gop": {}, "cfg": {}}
    if not (_has(db, "fact_usage_by_care_level") and _has(db, "fact_cases_by_care_level")):
        return out
    cfg = care_cfg(db)
    out["cfg"] = cfg
    ky = _cua_so_ky(db, cfg)
    if not ky:
        return out
    out["periods"] = ky
    min_n = float(cfg.get("min_cases_per_bucket", 30))
    ph = ",".join(f":k{i}" for i in range(len(ky)))
    prm = {f"k{i}": k for i, k in enumerate(ky)}

    # mẫu số: ca theo (nhóm × rổ)
    cases: Dict[str, Dict[str, float]] = {}
    for r in db.execute(text(
            f"SELECT block_code, ro, SUM(cases) AS n FROM fact_cases_by_care_level "
            f"WHERE period IN ({ph}) GROUP BY block_code, ro"), prm).fetchall():
        cases.setdefault(r.block_code, {})[r.ro] = float(r.n or 0)
    out["cases"] = cases

    # tử số: tiêu hao theo (nhóm × rổ × mã)
    usage: Dict[str, Dict[str, Dict[str, float]]] = {}       # g → ro → code → q
    for r in db.execute(text(
            f"SELECT block_code, ro, supply_code, SUM(quantity) AS q "
            f"FROM fact_usage_by_care_level WHERE period IN ({ph}) "
            f"GROUP BY block_code, ro, supply_code"), prm).fetchall():
        q = float(r.q or 0)
        if q <= 0:
            continue
        usage.setdefault(r.block_code, {}).setdefault(r.ro, {})[r.supply_code] = q
    out["usage"] = usage

    norms: Dict[str, Dict[str, Dict[str, float]]] = {}
    for g, ro_cases in cases.items():
        tong_ca_g = sum(ro_cases.values())
        # định mức gộp toàn nhóm (dự phòng cho rổ mẫu nhỏ)
        gop: Dict[str, float] = {}
        for ro, codes in usage.get(g, {}).items():
            for code, q in codes.items():
                gop[code] = gop.get(code, 0.0) + q
        gop = {c: q / tong_ca_g for c, q in gop.items()} if tong_ca_g > 0 else {}
        out["gop"][g] = gop

        for ro, n in ro_cases.items():
            if n < min_n or n <= 0:
                out["ro_mau_nho"].setdefault(g, []).append(ro)
                norms.setdefault(g, {})[ro] = dict(gop)
            else:
                norms.setdefault(g, {})[ro] = {c: q / n for c, q in usage.get(g, {}).get(ro, {}).items()}
    out["norms"] = norms
    return out


def chan_doan_dinh_muc(db: Session) -> Dict[str, Any]:
    """Chẩn đoán định mức: có khác nhau theo rổ không và nhóm nào thiếu dữ liệu."""
    emp = empirical_norms(db)
    ket_emp: Dict[str, Any] = {"co": bool(emp["norms"]), "so_ky": len(emp["periods"]),
                               "ky": (emp["periods"][0], emp["periods"][-1]) if emp["periods"] else None,
                               "nhom": {}, "ro_mau_nho": emp["ro_mau_nho"]}
    for g, theo_ro in emp["norms"].items():
        codes = set().union(*[set(d) for d in theo_ro.values()]) if theo_ro else set()
        khac = sum(1 for c in codes
                   if len({round(theo_ro.get(ro, {}).get(c, 0.0), 6) for ro in theo_ro} - {0.0}) > 1)
        ket_emp["nhom"][g] = {"so_ma": len(codes), "so_ro": len(theo_ro),
                              "so_ma_phan_biet_theo_ro": khac,
                              "ca": {ro: int(n) for ro, n in emp["cases"].get(g, {}).items()}}

    ket: Dict[str, Any] = {
        "co_dinh_muc": bool(emp["norms"]),
        "nguon_uu_tien": "thuc_nghiem" if emp["norms"] else None,
        "thuc_nghiem": ket_emp,
        "phan_biet_theo_ro": any(v["so_ma_phan_biet_theo_ro"] > 0 for v in ket_emp["nhom"].values()),
        "canh_bao": [],
    }
    if not emp["norms"]:
        ket["canh_bao"].append(
            "Chưa có định mức thực nghiệm — fact_usage_by_care_level / "
            "fact_cases_by_care_level rỗng. Đồng bộ HIS rồi chạy lại; tới lúc đó mọi mã ra nhãn Xám.")
        return ket
    thieu = [g for g in BLOCKS if g not in emp["norms"]]
    if thieu:
        ket["canh_bao"].append(f"Định mức thực nghiệm thiếu nhóm {thieu} — nhóm này không góp vào nhu cầu.")
    for g, lst in emp["ro_mau_nho"].items():
        ket["canh_bao"].append(f"{g}: rổ {lst} dưới ngưỡng mẫu — dùng định mức gộp toàn nhóm cho rổ đó.")
    return ket


# ── Nhu cầu nền ──

def baseline_demand(db: Session) -> Dict[str, float]:
    """Nhu cầu nền 30 ngày (không do hô hấp) từ tiêu hao trung bình 12 kỳ; thiếu nền thì DOI tiến tới vô cực."""
    if not _has(db, "v_supply_daily_demand"):
        return {}
    rows = db.execute(text(
        "SELECT supply_code, d_daily_baseline, d_daily FROM v_supply_daily_demand")).fetchall()
    out: Dict[str, float] = {}
    for r in rows:
        d = r.d_daily_baseline
        if d is None:
            d = r.d_daily
        out[r.supply_code] = float(d or 0) * 30.0
    return out


# ── Quy đổi ──

def demand_by_supply(db: Session,
                     forecast_by_block: Dict[str, float],
                     horizon_days: int = 30,
                     include_baseline: bool = True) -> Dict[str, Any]:
    """D_i = Σ_g Σ_ro (Ŷ_g × p̂(g,ro) × Norm(i,g,ro)) + D_i,baseline.
    `forecast_by_block` là số ca dự báo một tháng theo nhóm; cả hai phần co giãn theo horizon_days/30.
    Rổ có tỷ trọng nhưng không có định mức dùng trung bình định mức các rổ nội trú còn lại.
    """
    p_gc = care_level_shares(db)
    emp = empirical_norms(db)
    he_so = float(horizon_days) / 30.0

    dong: Dict[str, Dict[str, Any]] = {}
    thieu_p: List[str] = []
    thieu_norm: List[str] = []
    nguon_dinh_muc: Dict[str, str] = {}

    for g, y_g in forecast_by_block.items():
        y_g = float(y_g or 0)
        if y_g <= 0:
            continue
        shares = p_gc.get(g)
        emp_g = emp["norms"].get(g)
        if not emp_g:
            thieu_norm.append(g)
            continue
        if not shares:
            thieu_p.append(g)
            continue
        nguon_dinh_muc[g] = "thuc_nghiem"
        for ro, p in shares.items():
            y_ro = y_g * float(p)
            norm_ro = emp_g.get(ro)
            if not norm_ro:
                pooled: Dict[str, float] = {}
                n_nt = max(1, sum(1 for r2 in emp_g if r2 != "NGT"))
                for r2, codes in emp_g.items():
                    if r2 != "NGT":
                        for c, q in codes.items():
                            pooled[c] = pooled.get(c, 0.0) + q / n_nt
                norm_ro = pooled
            for code, q in norm_ro.items():
                if q <= 0:
                    continue
                rec = dong.setdefault(code, {"supply_code": code, "d_benh": 0.0,
                                             "d_baseline": 0.0, "chi_tiet": {}})
                them = y_ro * float(q) * he_so
                rec["d_benh"] += them
                rec["chi_tiet"][f"{g}|{ro}"] = round(rec["chi_tiet"].get(f"{g}|{ro}", 0.0) + them, 3)

    if include_baseline:
        for code, d30 in baseline_demand(db).items():
            rec = dong.setdefault(code, {"supply_code": code, "d_benh": 0.0,
                                         "d_baseline": 0.0, "chi_tiet": {}})
            rec["d_baseline"] = float(d30) * he_so

    for rec in dong.values():
        rec["d_forecast"] = round(rec["d_benh"] + rec["d_baseline"], 3)
        rec["d_benh"] = round(rec["d_benh"], 3)
        rec["d_baseline"] = round(rec["d_baseline"], 3)
        tong = rec["d_forecast"]
        rec["ty_le_do_hohap_pct"] = (round(100 * rec["d_benh"] / tong, 1)
                                     if tong > 0 else None)

    if thieu_p:
        logger.warning("Không có p̂(g,ro) cho %s — nhóm này không góp vào nhu cầu.",
                       ", ".join(sorted(set(thieu_p))))
    if thieu_norm:
        logger.warning("Không có định mức thực nghiệm cho %s — nhóm này không góp vào nhu cầu.",
                       ", ".join(sorted(set(thieu_norm))))

    return {
        "horizon_days": horizon_days,
        "rows": sorted(dong.values(), key=lambda r: -r["d_forecast"]),
        "so_ma": len(dong),
        "nhom_thieu_p_hat": sorted(set(thieu_p)),
        "nhom_thieu_dinh_muc": sorted(set(thieu_norm)),
        "nguon_dinh_muc": nguon_dinh_muc,
        "dinh_muc_thuc_nghiem": {
            "periods": emp["periods"],
            "so_nhom": len(emp["norms"]),
            "ro_mau_nho": emp["ro_mau_nho"],
        },
        "chan_doan_dinh_muc": chan_doan_dinh_muc(db),
    }


# ── Bảng tra định mức cho màn Quản trị ──

def norms_payload(db: Session, block: str, q: Optional[str] = None,
                  limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Tử số, mẫu số và Norm theo rổ cho từng mã của một nhóm; `q` lọc theo mã hoặc tên hoạt chất."""
    if block not in BLOCKS:
        raise ValueError(f"block phải thuộc {BLOCKS}")
    emp = empirical_norms(db)
    shares = care_level_shares(db).get(block, {})
    cases = emp["cases"].get(block, {})
    norms = emp["norms"].get(block, {})
    ro_list = [ro for ro in RO_ALL if ro in cases]
    mau_nho = set(emp["ro_mau_nho"].get(block, []))

    # tử số thô theo mã × rổ
    tu_so: Dict[str, Dict[str, float]] = {}
    for ro, codes in emp["usage"].get(block, {}).items():
        for code, qty in codes.items():
            tu_so.setdefault(code, {})[ro] = qty

    # tên / đơn vị
    ten: Dict[str, Any] = {}
    if _has(db, "medical_supplies"):
        for r in db.execute(text(
                "SELECT supply_code, ten_hoat_chat, unit, group_name FROM medical_supplies")).fetchall():
            ten[r.supply_code] = r

    rows: List[Dict[str, Any]] = []
    for code, theo_ro in tu_so.items():
        tong = sum(theo_ro.values())
        m = ten.get(code)
        chi_tiet = {}
        for ro in ro_list:
            n = cases.get(ro, 0.0)
            tu, mau = theo_ro.get(ro, 0.0), n
            gop = ro in mau_nho
            chi_tiet[ro] = {
                "tieu_hao": round(tu, 1), "ca": int(mau),
                "norm": round(float(norms.get(ro, {}).get(code, 0.0)), 4),
                "gop": gop,
                "p_hat": round(float(shares.get(ro, 0.0)), 4),
            }
        rows.append({
            "supply_code": code,
            "ten": (m.ten_hoat_chat if m else None) or code,
            "don_vi": m.unit if m else None,
            "nhom": m.group_name if m else None,
            "tieu_hao_tong": round(tong, 1),
            "norm_gop": round(float(emp["gop"].get(block, {}).get(code, 0.0)), 4),
            # Σ_ro p̂ · Norm: lượng cần cho một ca dự báo của nhóm
            "norm_hieu_dung": round(sum(
                float(shares.get(ro, 0.0)) * float(norms.get(ro, {}).get(code, 0.0))
                for ro in ro_list), 4),
            "theo_ro": chi_tiet,
        })

    if q:
        qq = q.strip().lower()
        rows = [r for r in rows if qq in r["supply_code"].lower() or qq in str(r["ten"]).lower()]
    rows.sort(key=lambda r: -r["tieu_hao_tong"])
    total = len(rows)
    return {
        "block": block,
        "periods": emp["periods"],
        "cfg": {k: emp["cfg"].get(k) for k in CARE_LEVEL_DEFAULT},
        "ro": [{"ro": ro, "ten": RO_LABEL.get(ro, ro), "ca": int(cases.get(ro, 0)),
                "p_hat": round(float(shares.get(ro, 0.0)), 4), "mau_nho": ro in mau_nho}
               for ro in ro_list],
        "total": total,
        "offset": offset,
        "limit": limit,
        "rows": rows[offset:offset + limit],
        "cong_thuc": ("Norm(i,g,ro) = Σ tiêu hao(i,g,ro) / Σ ca(g,ro) trên cửa sổ; "
                      "rổ < min_cases_per_bucket ca → dùng định mức gộp nhóm. "
                      "Nhu cầu 30 ngày D_i = Σ_ro Ŷ_g·p̂(g,ro)·Norm(i,g,ro) + nền."),
    }
