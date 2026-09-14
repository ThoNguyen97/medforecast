#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G1 — CHUẨN HOÁ API DASHBOARD
=============================================================================
Chạy tại THƯ MỤC GỐC của repo (nơi có backend/ và frontend/).

    python backend/scripts/patch_g1_dashboard.py            # THỬ, không sửa gì
    python backend/scripts/patch_g1_dashboard.py --apply

Cùng nguyên tắc với G0_cat_pham_vi.py: mặc định chỉ thử, định vị bằng MỐC
(decorator của endpoint) thay vì so khớp toàn bộ thân hàm, chạy lại được, và
KHÔNG sửa gì khi không tìm thấy mốc.

-----------------------------------------------------------------------------
BỐN THAY ĐỔI

1. `/summary`, `/overview`, `/case-trend` neo vào KỲ ĐÃ CHỐT
   (`is_complete = 1` trong `mart_monthly_cases_by_block`) thay cho
   `max(DiseaseCase.recorded_at)` — vốn rơi vào kỳ đang mở và sinh ra xu hướng
   6500% (T9/2026 có 3 ca so với T8 có 341 ca).

2. Một nguồn số ca duy nhất: mart. Ba endpoint không còn đọc `disease_cases`.

3. Xoá hàm `_classify_risk`. Quy tắc chuyển sang
   `period_service.assess_overall_risk()` với đầu vào là xu hướng giữa hai kỳ
   ĐÃ CHỐT, và trả kèm `basis` để giao diện nói rõ căn cứ.

4. Tỷ lệ phần trăm lấy mẫu số từ `v_supply_active` (~1.900 mã) thay cho toàn bộ
   5.041 mã danh mục; thêm `v_supply_focus` (~555 mã) làm tập trọng tâm.

-----------------------------------------------------------------------------
GIỮ NGUYÊN TÊN TRƯỜNG CŨ — CÓ CHỦ ĐÍCH

Toàn bộ khoá cũ trong response được giữ lại (`total_cases_current`,
`shortage_supplies_count`, `overall_risk`, `total_inventory_value`…) để frontend
hiện tại không vỡ. Các khoá mới được THÊM vào bên cạnh. Việc dọn kiểu TypeScript
và bỏ các trường không còn nghĩa thuộc G5, làm cùng lúc với dashboard v2.
"""

import argparse
import os
import re
import subprocess
import sys

DASH = os.path.join("backend", "app", "api", "v1", "dashboard.py")
SENTINEL = "# ── G1·DSS ─"

ok, warn, fail = [], [], []


# ─────────────────────────────────────────────────────────────────────────────
# Thân hàm mới
# ─────────────────────────────────────────────────────────────────────────────

NEW_OVERVIEW = '''@router.get("/overview")
async def get_dashboard_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """KPI tổng quan.

    ── G1·DSS ─────────────────────────────────────────────────────────────
    Ba thay đổi so với bản trước:

    • MẪU SỐ. `total_supplies` nay là DANH MỤC CÒN HOẠT ĐỘNG (~1.900 mã, có
      xuất trong 3 kỳ gần nhất), không phải toàn bộ 5.041 mã — trong đó gần
      4/5 là mã đã ngừng dùng. Mọi tỷ lệ phần trăm chia cho mẫu số này.

    • PHÂN MỨC TỒN KHO. Trước đây dựa trên `safety_stock`, cột đã bị vô hiệu
      hoá ở G0 (nó là dấu vết số lần bấm nút, không phải tồn an toàn), nên
      phép đếm cũ nay luôn trả 0. Thay bằng đếm theo DOI.
      Mã không có mẫu số nhu cầu → 'grey', KHÔNG phải 'safe'.

    • Ổ DỊCH. Trước đây đếm `disease_type` có ca trong 7 ngày gần nhất từ
      `disease_cases` — luôn ra 0 vì dữ liệu bệnh viện trễ 1-2 tháng. Nay là
      số nhóm ICD có số ca kỳ đã chốt CAO HƠN kỳ liền trước.
    ─────────────────────────────────────────────────────────────────────── """
    cache_key = "dashboard:overview"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    anchor = ps.get_period_anchor(db)
    last_closed = anchor["last_closed_period"]
    cat = ps.catalogue_counts(db)
    signal = ps.stock_signal_counts(db)
    blocks = ps.cases_by_block(db, last_closed)

    # Giá trị tồn kho — giữ lại cho tương thích giao diện hiện tại.
    # KHÔNG phải chỉ số y tế và sẽ bỏ ở G5 (xem hợp đồng dashboard v2).
    value_rows = (
        db.query(Inventory.current_stock, MedicalSupply.unit_price)
        .join(MedicalSupply, Inventory.supply_id == MedicalSupply.id)
        .all()
    )
    total_inventory_value = sum(
        float(r.current_stock or 0) * float(r.unit_price)
        for r in value_rows if r.unit_price is not None
    )

    predicted_demand_30d = int(
        db.query(func.coalesce(func.sum(DiseaseForecast.predicted_cases), 0))
        .filter(
            DiseaseForecast.forecast_date >= date.today(),
            DiseaseForecast.forecast_date <= date.today() + timedelta(days=30),
        )
        .scalar() or 0
    )

    outbreaks = sum(1 for b in blocks
                    if (b.get("trend_pct") or 0) > 0 and b["cases_last_closed"] > 0)

    mau_so = cat["active"] or cat["total"] or 1
    canh_bao = signal["red"] + signal["amber"] + signal["zero_stock"]

    result = {
        # ── khoá cũ, giữ nguyên tên để giao diện hiện tại không vỡ ──
        "total_supplies": cat["active"],
        "total_inventory_value": round(total_inventory_value, 2),
        "high_risk_shortages": signal["red"],
        "predicted_demand_30d": predicted_demand_30d,
        "disease_outbreaks": outbreaks,
        "safe_stock_items": signal["green"],
        "low_stock_items": signal["amber"],
        "critical_risk_items": signal["red"] + signal["zero_stock"],
        "supply_risk_percentage": round(100.0 * canh_bao / mau_so, 2),
        # ── khoá mới ──
        "last_closed_period": last_closed,
        "open_period": anchor["open_period"],
        "catalogue": cat,
        "stock_signal": signal,
        "assumptions_note": "Tồn kho tính trên hàng hiện có, chưa trừ hàng đang về.",
    }
    _cache_set(cache_key, result)
    return result


'''

NEW_SUMMARY = '''@router.get("/summary")
async def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """KPI tổng hợp cho Dashboard.

    ── G1·DSS ─────────────────────────────────────────────────────────────
    Bản cũ neo "tháng hiện tại" vào `max(DiseaseCase.recorded_at)`, tức KỲ
    ĐANG MỞ. Tháng 9/2026 mới có 3 ca trong khi tháng 8 có 341 ca, nên

        predicted_trend_pct = (198 − 3) / 3 = 6500%

    và con số đó đi thẳng vào `_classify_risk(6500, 17)` → luôn trả "Cao".

    Bản này neo vào KỲ ĐÃ CHỐT gần nhất (`is_complete = 1`) lấy từ
    `mart_monthly_cases_by_block`, và mọi số ca đều đọc từ mart đó — không
    còn chạm vào bảng `disease_cases`.

    Kỳ đang mở vẫn trả về, nhưng ở trường riêng `open_period_cases` kèm nhãn
    "chưa chốt", và KHÔNG tham gia bất kỳ phép so sánh nào.
    ─────────────────────────────────────────────────────────────────────── """
    anchor = ps.get_period_anchor(db)
    last_closed = anchor["last_closed_period"]
    prev_closed = anchor["prev_closed_period"]
    open_period = anchor["open_period"]

    total_current = ps.cases_in_period(db, last_closed)
    total_prev = ps.cases_in_period(db, prev_closed)
    cases_trend = ps.trend_pct(db, last_closed, prev_closed)

    # Dự báo cho kỳ kế tiếp kỳ đã chốt.
    # Chỉ cộng các dòng CÓ location: dòng location = NULL chính là tổng các
    # tỉnh, gộp vào sẽ đếm gấp đôi.
    next_period = ps.shift_period(last_closed, 1)
    predicted_next = 0
    if next_period:
        y, mo = int(next_period[:4]), int(next_period[5:7])
        predicted_next = int(
            db.query(func.coalesce(func.sum(DiseaseForecast.predicted_cases), 0))
            .filter(
                extract("year", DiseaseForecast.forecast_date) == y,
                extract("month", DiseaseForecast.forecast_date) == mo,
                DiseaseForecast.location.isnot(None),
            )
            .scalar() or 0
        )
    predicted_trend = (
        round(100.0 * (predicted_next - total_current) / total_current, 1)
        if total_current > 0 else 0.0
    )

    signal = ps.stock_signal_counts(db)
    cat = ps.catalogue_counts(db)
    risk = ps.assess_overall_risk(cases_trend, signal["red"], signal["amber"])

    return {
        # ── khoá cũ, giữ nguyên tên ──
        "total_cases_current": total_current,
        "cases_trend_pct": cases_trend,
        "predicted_cases_next_month": predicted_next,
        "predicted_trend_pct": predicted_trend,
        "shortage_supplies_count": signal["red"],
        "overall_risk": risk["level"],
        "as_of": last_closed,
        # ── khoá mới ──
        "last_closed_period": last_closed,
        "prev_closed_period": prev_closed,
        "open_period": open_period,
        "open_period_cases": ps.cases_in_period(db, open_period),
        "open_period_note": "Kỳ chưa chốt — không tính vào xu hướng.",
        "total_cases_prev": total_prev,
        "forecast_period": next_period,
        "blocks": ps.cases_by_block(db, last_closed),
        "catalogue": cat,
        "stock_signal": signal,
        "overall_risk_basis": risk["basis"],
        "overall_risk_is_provisional": risk["is_provisional"],
    }


'''

NEW_CASE_TREND = '''@router.get("/case-trend")
async def get_case_trend(
    months: int = Query(6, ge=3, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """Xu hướng ca bệnh theo tháng, năm nay so với năm trước.

    ── G1·DSS ─────────────────────────────────────────────────────────────
    Đọc từ `mart_monthly_cases_by_block` (region = 'TOAN_QUOC'), kết thúc ở
    KỲ ĐÃ CHỐT gần nhất. Bản cũ đọc `disease_cases` và neo vào
    `max(recorded_at)`, nên cột cuối biểu đồ luôn tụt gần 0 vì đó là kỳ đang
    thu thập dở.

    Số ca ở mức NHÓM đã được đếm DISTINCT bên HIS. Không cộng từ mã con: một
    lượt mang J01 và J06 (cùng thuộc J00-J06) sẽ bị đếm hai lần.
    ─────────────────────────────────────────────────────────────────────── """
    anchor = ps.get_period_anchor(db)
    last_closed = anchor["last_closed_period"]
    if not last_closed:
        return {"this_year": [], "last_year": [], "last_closed_period": None}

    series = ps.case_series(db, n_periods=months, end_period=last_closed)
    this_year, last_year = [], []
    for row in series:
        period = row["period"]
        label = f"T{int(period[5:7])}"
        this_year.append({"month": label, "period": period,
                          "value": row["cases"], "is_complete": row["is_complete"]})
        last_year.append({"month": label,
                          "period": ps.shift_period(period, -12),
                          "value": ps.cases_in_period(db, ps.shift_period(period, -12))})

    return {
        "this_year": this_year,
        "last_year": last_year,
        "last_closed_period": last_closed,
        "open_period": anchor["open_period"],
        "source": "mart_monthly_cases_by_block",
    }


'''


# ─────────────────────────────────────────────────────────────────────────────
# Tiện ích sửa file
# ─────────────────────────────────────────────────────────────────────────────

def _read():
    with open(DASH, encoding="utf-8") as f:
        return f.read()


def _write(s, apply):
    if not apply:
        return
    with open(DASH, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def them_import(apply):
    s = _read()
    if "period_service as ps" in s:
        ok.append("đã thêm trước đó: import period_service")
        return
    moc = "from app.models.user import User\n"
    if moc not in s:
        fail.append("không thấy mốc import User trong dashboard.py")
        return
    moi = moc + "from app.services import period_service as ps\n"
    if not apply:
        warn.append("[THỬ] sẽ thêm: import period_service")
        return
    _write(s.replace(moc, moi, 1), apply)
    ok.append("đã thêm: import period_service")


def thay_khoi(moc_dau, moc_cuoi, than_moi, nhan, apply):
    """Thay toàn bộ đoạn từ `moc_dau` tới ngay trước `moc_cuoi`."""
    s = _read()
    if moc_dau not in s:
        fail.append(f"không thấy mốc đầu: {nhan}  ({moc_dau!r})")
        return
    a = s.index(moc_dau)
    if moc_cuoi not in s[a + len(moc_dau):]:
        fail.append(f"không thấy mốc cuối: {nhan}  ({moc_cuoi!r})")
        return
    b = a + len(moc_dau) + s[a + len(moc_dau):].index(moc_cuoi)
    cu = s[a:b]
    if SENTINEL in cu and cu == than_moi:
        ok.append(f"đã thay trước đó: {nhan}")
        return
    if not apply:
        warn.append(f"[THỬ] sẽ thay {len(cu)} ký tự bằng {len(than_moi)} ký tự: {nhan}")
        return
    _write(s[:a] + than_moi + s[b:], apply)
    ok.append(f"đã thay: {nhan}")


def xoa_classify_risk(apply):
    s = _read()
    moc = "def _classify_risk("
    if moc not in s:
        ok.append("đã xoá trước đó: _classify_risk")
        return
    a = s.index(moc)
    # lùi lên để nuốt cả dòng chú thích đứng ngay trên nếu có
    dau_dong = s.rfind("\n\n", 0, a)
    a = dau_dong + 1 if dau_dong != -1 else a
    sau = s.index('@router.get("/summary")', a)
    if not apply:
        warn.append(f"[THỬ] sẽ xoá {sau - a} ký tự: hàm _classify_risk")
        return
    _write(s[:a] + s[sau:], apply)
    ok.append("đã xoá: hàm _classify_risk")


def kiem_tra_con_sot():
    s = _read()
    con = []
    for i, ln in enumerate(s.splitlines(), 1):
        if re.search(r"DiseaseCase\.recorded_at|_classify_risk", ln):
            con.append(f"{DASH}:{i}: {ln.strip()[:110]}")
    return con


def main():
    ap = argparse.ArgumentParser(description="G1 — chuẩn hoá API dashboard")
    ap.add_argument("--apply", action="store_true", help="thực hiện thật")
    a = ap.parse_args()

    if not os.path.exists(DASH):
        print(f"LỖI: không thấy {DASH}. Chạy script tại thư mục gốc của repo.")
        sys.exit(1)
    if not os.path.exists(os.path.join("backend", "app", "services", "period_service.py")):
        print("LỖI: chưa có backend/app/services/period_service.py — chép file đó vào trước.")
        sys.exit(1)

    if a.apply and os.path.isdir(".git"):
        r = subprocess.run(["git", "status", "--porcelain", "--", DASH],
                           capture_output=True, text=True)
        if r.stdout.strip():
            print(f"CẢNH BÁO: {DASH} đang có thay đổi chưa commit.")
            if input("Vẫn tiếp tục? [y/N] ").strip().lower() != "y":
                sys.exit(0)

    print("=" * 74)
    print("G1 — CHUẨN HOÁ API DASHBOARD" +
          ("  [THỰC HIỆN]" if a.apply else "  [THỬ — không sửa file]"))
    print("=" * 74)

    them_import(a.apply)
    xoa_classify_risk(a.apply)
    thay_khoi('@router.get("/overview")', '@router.get("/supply-demand")',
              NEW_OVERVIEW, "/overview", a.apply)
    thay_khoi('@router.get("/summary")', '@router.get("/case-trend")',
              NEW_SUMMARY, "/summary", a.apply)
    thay_khoi('@router.get("/case-trend")', '@router.get("/demand-vs-stock")',
              NEW_CASE_TREND, "/case-trend", a.apply)

    for td, ds in (("ĐÃ LÀM", ok), ("CẦN CHÚ Ý", warn), ("KHÔNG LÀM ĐƯỢC", fail)):
        if ds:
            print(f"\n── {td} " + "─" * (70 - len(td)))
            for x in ds:
                print("  • " + x)

    if a.apply:
        print("\n── QUÉT LẠI DẤU VẾT CÒN SÓT " + "─" * 46)
        con = kiem_tra_con_sot()
        if con:
            print("  Còn tham chiếu tới mốc thời gian cũ — xem lại từng dòng:")
            for c in con:
                print("    " + c)
        else:
            print("  Sạch: không còn DiseaseCase.recorded_at hay _classify_risk.")
        print("\n  Kiểm tra cú pháp:")
        r = subprocess.run([sys.executable, "-m", "py_compile", DASH],
                           capture_output=True, text=True)
        print("    " + ("OK" if r.returncode == 0 else "LỖI:\n" + r.stderr))

    print("\n── BƯỚC TIẾP THEO " + "─" * 56)
    if not a.apply:
        print("  Chạy lại với --apply để thực hiện.")
    else:
        print("  1) cd backend && uvicorn app.main:app --reload")
        print("  2) python backend/scripts/verify_g1.py")
    if fail:
        sys.exit(2)


if __name__ == "__main__":
    main()
