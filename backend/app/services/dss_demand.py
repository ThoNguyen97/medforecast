"""TẦNG 2 — QUY ĐỔI CA BỆNH DỰ BÁO SANG NHU CẦU THUỐC/VTYT.

Đặt tại: backend/app/services/dss_demand.py

    Ŷ_g  (từ topdown.forecast)
      → Ŷ_g,c = Ŷ_g × p̂(g,c)                    phân rã theo rổ chăm sóc
      → D_i   = Σ_g Σ_c Ŷ_g,c × Norm(i,g,c)     quy đổi qua định mức
              + D_i,baseline                     nhu cầu nền không do hô hấp

=============================================================================
BA ĐIỀU PHẢI BIẾT TRƯỚC KHI ĐỌC SỐ CỦA MODULE NÀY

1 · ĐỊNH MỨC HIỆN CHƯA PHÂN BIỆT THEO ĐỘ NẶNG.
    `disease_supply_norms` khoá trên (icd_code, severity, supply_id) — nhìn thì
    đủ ba mức, nhưng đo trên dữ liệu thật thì `quantity_per_case` GIỐNG NHAU ở
    cả ba mức (18/18/18 · 30/30/30 · 20/20/20). Nghĩa là chiều `severity` đang
    là chiều rỗng: công thức ba lớp rút gọn thành D_i = Ŷ_g × Norm(i,g).

    Module vẫn hiện thực đủ công thức, nhưng `chan_doan_dinh_muc()` báo rõ
    chiều nào đang rỗng. Cho tới khi Khoa Dược điền định mức khác nhau theo
    mức nặng, toàn bộ bộ máy p̂(g,c) chỉ là đường dẫn — nó KHÔNG làm dự báo
    chính xác hơn, và không được trình bày như thể có.

2 · TỶ LỆ NHẸ/TB/NẶNG CỦA J09-J18 LÀ SỐ NHÁP.
    `severity_rates` cho J09-J18 mang chú thích "NHÁP — nhóm chưa có dữ liệu
    phân độ". Bảng này chỉ dùng làm phương án lùi cho rổ NT0 (chưa gán).

3 · RỔ → ĐỘ NẶNG là một PHÉP ÁNH XẠ DO NGƯỜI ĐẶT, không phải suy ra từ dữ liệu.
    Quy tắc phân cấp: mã NHỎ = nặng hơn (cấp 1 nặng nhất).

        NGT  ngoại trú        → mild
        NT1  nội trú cấp 1    → severe
        NT2  nội trú cấp 2    → moderate
        NT3  nội trú cấp 3    → mild
        NT0  chưa gán phân cấp → phân bổ theo severity_rates của nhóm

    NT0 KHÔNG được gán mild: rổ này là "hệ thống chưa đánh giá", không phải
    "bệnh nhân nhẹ". Gán mild sẽ dự báo thiếu đúng nhóm thuốc đắt tiền.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

BLOCKS = ("J00-J06", "J09-J18", "J20-J22")
RO_ALL = ("NGT", "NT1", "NT2", "NT3", "NT0")
SEVERITIES = ("mild", "moderate", "severe")

# Ánh xạ rổ → độ nặng. NT0 xử lý riêng (phân bổ theo tỷ lệ nhóm).
RO_SEVERITY: Dict[str, Optional[str]] = {
    "NGT": "mild",
    "NT1": "severe",
    "NT2": "moderate",
    "NT3": "mild",
    "NT0": None,
}

CARE_LEVEL_DEFAULT = {"window_periods": 12, "min_period": "2025-04",
                      "min_cases_per_bucket": 30, "shrink_k0": 6}


def _has(db: Session, name: str) -> bool:
    return bool(db.execute(
        text("SELECT 1 FROM sqlite_master WHERE name = :n LIMIT 1"),
        {"n": name}).first())


def _care_cfg(db: Session) -> Dict[str, Any]:
    out = dict(CARE_LEVEL_DEFAULT)
    r = db.execute(text("SELECT config_value FROM system_config "
                        "WHERE config_key = 'dss.care_level'")).scalar()
    if r:
        try:
            out.update(json.loads(r))
        except Exception:                                 # noqa: BLE001
            logger.warning("dss.care_level không phải JSON hợp lệ — dùng mặc định.")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# p̂(g,c) — tỷ trọng rổ chăm sóc, có co ngót cho rổ mẫu nhỏ
# ─────────────────────────────────────────────────────────────────────────────

def care_level_shares(db: Session) -> Dict[str, Dict[str, float]]:
    """Đọc `v_care_level_share` rồi CO NGÓT những rổ có mẫu quá nhỏ.

    View đã tính tỷ trọng trên cửa sổ 12 kỳ từ 2025-04 và đánh dấu
    `mau_qua_nho = 1` cho rổ dưới ngưỡng (mặc định 30 đợt). Đ11-D đo được có
    rổ chỉ 5-8 đợt — lấy thẳng tỷ trọng của một rổ 5 đợt thì thêm hai ca là
    định mức nhảy 40%.

    Co ngót về phân bố ĐỀU giữa các rổ nội trú của chính nhóm đó:

        p̂ = λ · p_đo  +  (1 − λ) · p_đều       λ = n / (n + K₀)

    với n = số đợt của rổ. Rổ 5 đợt, K₀ = 6 → λ = 0,45: tỷ trọng đo chỉ được
    tin 45%. Rổ 300 đợt → λ = 0,98, gần như tin hoàn toàn.

    Trả {block_code: {ro: tỷ trọng}}, mỗi nhóm tổng bằng 1.
    """
    if not _has(db, "v_care_level_share"):
        return {}
    cfg = _care_cfg(db)
    k0 = float(cfg.get("shrink_k0", 6))

    rows = db.execute(text(
        "SELECT block_code, ro, cases, share_pct, mau_qua_nho, so_ky, tu_ky, den_ky "
        "FROM v_care_level_share")).fetchall()
    if not rows:
        logger.warning("v_care_level_share rỗng — fact_cases_by_care_level chưa "
                       "được nạp. Chạy scripts/run_dss_load.py.")
        return {}

    theo_nhom: Dict[str, List[Any]] = {}
    for r in rows:
        theo_nhom.setdefault(r.block_code, []).append(r)

    out: Dict[str, Dict[str, float]] = {}
    for g, rs in theo_nhom.items():
        tong_ca = sum(float(r.cases or 0) for r in rs)
        if tong_ca <= 0:
            continue
        deu = 1.0 / max(1, len(rs))
        tam: Dict[str, float] = {}
        for r in rs:
            n = float(r.cases or 0)
            p_do = n / tong_ca
            if int(r.mau_qua_nho or 0) == 1:
                lam = n / (n + k0) if (n + k0) > 0 else 0.0
                tam[r.ro] = lam * p_do + (1 - lam) * deu
            else:
                tam[r.ro] = p_do
        s = sum(tam.values())
        out[g] = {k: v / s for k, v in tam.items()} if s > 0 else tam
    return out


def severity_rates(db: Session) -> Dict[str, Dict[str, float]]:
    """Tỷ lệ nhẹ/TB/nặng theo nhóm — CHỈ dùng làm phương án lùi cho rổ NT0."""
    if not _has(db, "severity_rates"):
        return {}
    out: Dict[str, Dict[str, float]] = {}
    for r in db.execute(text("SELECT icd_code, mild_rate, moderate_rate, severe_rate, "
                             "note FROM severity_rates")).fetchall():
        tong = float(r.mild_rate or 0) + float(r.moderate_rate or 0) + float(r.severe_rate or 0)
        if tong <= 0:
            continue
        out[r.icd_code] = {
            "mild":     float(r.mild_rate or 0) / tong,
            "moderate": float(r.moderate_rate or 0) / tong,
            "severe":   float(r.severe_rate or 0) / tong,
            "_nhap":    1.0 if (r.note or "").strip().upper().startswith("NHÁP") else 0.0,
        }
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Định mức
# ─────────────────────────────────────────────────────────────────────────────

def norm_matrix(db: Session) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Norm(i, g, sev) → {block: {severity: {supply_code: lượng mỗi ca}}}."""
    if not (_has(db, "disease_supply_norms") and _has(db, "medical_supplies")):
        return {}
    rows = db.execute(text(
        "SELECT n.icd_code AS g, n.severity AS sev, m.supply_code AS code, "
        "       SUM(n.quantity_per_case) AS q "
        "FROM   disease_supply_norms n "
        "JOIN   medical_supplies     m ON m.id = n.supply_id "
        "GROUP BY n.icd_code, n.severity, m.supply_code")).fetchall()
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for r in rows:
        out.setdefault(r.g, {}).setdefault(r.sev, {})[r.code] = float(r.q or 0)
    return out


def chan_doan_dinh_muc(db: Session) -> Dict[str, Any]:
    """Định mức có THẬT SỰ khác nhau theo độ nặng không?

    Nếu không, chiều `severity` là chiều rỗng và cả bộ máy p̂(g,c) chỉ là đường
    dẫn. Phải biết điều này TRƯỚC khi trình bày kết quả, không phải sau.
    """
    nm = norm_matrix(db)
    ket = {"co_dinh_muc": bool(nm), "nhom": {}, "phan_biet_theo_do_nang": False,
           "canh_bao": []}
    if not nm:
        ket["canh_bao"].append("Không có định mức nào — mọi mã sẽ ra nhãn Xám.")
        return ket

    co_phan_biet_toan_cuc = False
    for g, theo_sev in nm.items():
        codes = set().union(*[set(d) for d in theo_sev.values()]) if theo_sev else set()
        khac = 0
        for code in codes:
            vals = {theo_sev.get(s, {}).get(code) for s in SEVERITIES}
            vals = {v for v in vals if v is not None}
            if len(vals) > 1:
                khac += 1
        ket["nhom"][g] = {"so_ma": len(codes), "so_ma_phan_biet": khac,
                          "so_muc_do_nang": len(theo_sev)}
        if khac:
            co_phan_biet_toan_cuc = True
        else:
            ket["canh_bao"].append(
                f"{g}: cả {len(codes)} mã có định mức GIỐNG NHAU ở ba mức nặng — "
                f"chiều độ nặng đang rỗng, phân rã phân cấp không thêm thông tin.")

    ket["phan_biet_theo_do_nang"] = co_phan_biet_toan_cuc
    sr = severity_rates(db)
    for g, d in sr.items():
        if d.get("_nhap"):
            ket["canh_bao"].append(
                f"{g}: severity_rates còn là số NHÁP — chỉ dùng cho rổ NT0.")
    return ket


# ─────────────────────────────────────────────────────────────────────────────
# Nhu cầu nền
# ─────────────────────────────────────────────────────────────────────────────

def baseline_demand(db: Session) -> Dict[str, float]:
    """`d_baseline_thang` trung bình 12 kỳ — nhu cầu KHÔNG do hô hấp.

    Đây là phần quan trọng nhất và dễ bị bỏ quên nhất. Đo được ở Đ10: trung vị
    tỷ trọng hô hấp toàn danh mục chỉ 3,23%. Nếu chỉ cộng phần quy đổi từ ca hô
    hấp thì với đại đa số mã, nhu cầu dự báo sẽ gần bằng 0 — và DOI sẽ ra vô
    cực, tức toàn bộ kho hiện màu Xanh một cách vô nghĩa.
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# Quy đổi
# ─────────────────────────────────────────────────────────────────────────────

def demand_by_supply(db: Session,
                     forecast_by_block: Dict[str, float],
                     horizon_days: int = 30,
                     include_baseline: bool = True) -> Dict[str, Any]:
    """D_i = Σ_g Σ_c (Ŷ_g × p̂(g,c) × Norm(i, g, sev(c))) + D_i,baseline.

    `forecast_by_block` là số ca dự báo của MỘT kỳ (tháng) cho từng nhóm — lấy
    từ `topdown.forecast()`, phần `muc == 'NHOM'`.

    `horizon_days` cho phép quy về cửa sổ khác 30 ngày; phần quy đổi từ ca bệnh
    và phần nền được co giãn CÙNG một hệ số.
    """
    p_gc = care_level_shares(db)
    nm = norm_matrix(db)
    sr = severity_rates(db)
    he_so = float(horizon_days) / 30.0

    dong: Dict[str, Dict[str, Any]] = {}
    thieu_p: List[str] = []
    thieu_norm: List[str] = []

    for g, y_g in forecast_by_block.items():
        y_g = float(y_g or 0)
        if y_g <= 0:
            continue
        norm_g = nm.get(g)
        if not norm_g:
            thieu_norm.append(g)
            continue
        shares = p_gc.get(g)
        if not shares:
            # Không có p̂(g,c): lùi về severity_rates của nhóm. Ghi nhận rõ
            # thay vì im lặng coi như toàn bộ là mild.
            thieu_p.append(g)
            sev_mix = {s: sr.get(g, {}).get(s, 0.0) for s in SEVERITIES}
            if sum(sev_mix.values()) <= 0:
                sev_mix = {"mild": 1.0, "moderate": 0.0, "severe": 0.0}
            phan_bo = [(sev, y_g * w) for sev, w in sev_mix.items() if w > 0]
        else:
            phan_bo = []
            for ro, p in shares.items():
                y_gc = y_g * float(p)
                sev = RO_SEVERITY.get(ro)
                if sev is None:                      # NT0 — chưa gán phân cấp
                    mix = sr.get(g) or {"mild": 1.0}
                    for s in SEVERITIES:
                        w = float(mix.get(s, 0.0))
                        if w > 0:
                            phan_bo.append((s, y_gc * w))
                else:
                    phan_bo.append((sev, y_gc))

        for sev, y_sev in phan_bo:
            for code, q in (norm_g.get(sev) or {}).items():
                if q <= 0:
                    continue
                rec = dong.setdefault(code, {"supply_code": code, "d_benh": 0.0,
                                             "d_baseline": 0.0, "chi_tiet": {}})
                them = y_sev * float(q) * he_so
                rec["d_benh"] += them
                rec["chi_tiet"][f"{g}|{sev}"] = round(
                    rec["chi_tiet"].get(f"{g}|{sev}", 0.0) + them, 3)

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
        logger.warning("Không có p̂(g,c) cho %s — đã lùi về severity_rates.",
                       ", ".join(sorted(set(thieu_p))))
    if thieu_norm:
        logger.warning("Không có định mức cho %s — nhóm này không góp vào nhu cầu.",
                       ", ".join(sorted(set(thieu_norm))))

    return {
        "horizon_days": horizon_days,
        "rows": sorted(dong.values(), key=lambda r: -r["d_forecast"]),
        "so_ma": len(dong),
        "nhom_thieu_p_hat": sorted(set(thieu_p)),
        "nhom_thieu_dinh_muc": sorted(set(thieu_norm)),
        "chan_doan_dinh_muc": chan_doan_dinh_muc(db),
    }
