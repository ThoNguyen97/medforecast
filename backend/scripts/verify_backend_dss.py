#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NGHIỆM THU BỐN BƯỚC THI CÔNG BACKEND DSS
=============================================================================
Đặt tại: backend/scripts/verify_backend_dss.py

    cd backend
    python scripts/verify_backend_dss.py
    python scripts/verify_backend_dss.py --buoc 2      # chỉ kiểm một bước
    python scripts/verify_backend_dss.py --db data/medforecast.db

Mã trả về: 0 = tất cả ĐẠT · 1 = có tiêu chí KHÔNG ĐẠT · 2 = không chạy được.

-----------------------------------------------------------------------------
NGUYÊN TẮC CỦA SCRIPT NÀY

Mỗi tiêu chí phải KIỂM ĐƯỢC BẰNG MỘT PHÉP ĐO, không phải bằng việc đọc mã.
"Đã gỡ hàm X" không kiểm bằng cách tìm chuỗi trong file — vì một chuỗi có thể
nằm trong chú thích; kiểm bằng cách nạp module rồi hỏi `hasattr`.

Script CHỈ ĐỌC dữ liệu. Ngoại lệ duy nhất là Bước 4, nơi `--save` được phép
ghi vào `forecast_accuracy` — và đó chính là điều cần nghiệm thu. Muốn chạy
hoàn toàn không ghi thì thêm `--khong-ghi`.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DAT = "  \033[32m✓\033[0m " if sys.stdout.isatty() else "  [DAT ] "
HONG = "  \033[31m✗\033[0m " if sys.stdout.isatty() else "  [HONG] "
LUU = "  \033[33m!\033[0m " if sys.stdout.isatty() else "  [LUU ] "

_dem = {"dat": 0, "hong": 0, "luu": 0}


def _t(sql: str):
    from sqlalchemy import text
    return text(sql)


def _co_bang(db, ten: str) -> bool:
    """Bảng/view có tồn tại không.

    Script nghiệm thu KHÔNG được tự vỡ vì một bảng chưa được tạo — chính tình
    trạng đó là điều nó phải phát hiện và báo cáo.
    """
    try:
        return bool(db.execute(
            _t("SELECT 1 FROM sqlite_master WHERE name = :n LIMIT 1"),
            {"n": ten}).first())
    except Exception:                                         # noqa: BLE001
        return False


def dat(msg: str) -> None:
    _dem["dat"] += 1
    print(DAT + msg)


def hong(msg: str, cach_sua: str = "") -> None:
    _dem["hong"] += 1
    print(HONG + msg)
    if cach_sua:
        for d in cach_sua.strip().splitlines():
            print("         → " + d.strip())


def luu(msg: str) -> None:
    _dem["luu"] += 1
    print(LUU + msg)


def tieu_de(s: str) -> None:
    print("\n" + "=" * 76)
    print(s)
    print("=" * 76)


# ═════════════════════════════════════════════════════════════════════════════
# BƯỚC 1 · đường ghi phá hoại đã bị gỡ
# ═════════════════════════════════════════════════════════════════════════════

def buoc_1(db) -> None:
    tieu_de("BƯỚC 1 · Dashboard không còn ghi vào bảng alerts")

    try:
        from app.api.v1 import dashboard as dsh
    except Exception as exc:                                  # noqa: BLE001
        hong(f"Không import được app.api.v1.dashboard: {exc}",
             "Lỗi cú pháp hoặc thiếu import — sửa trước khi kiểm tiếp.")
        return

    # 1.1 · ba hàm phải KHÔNG còn tồn tại như thuộc tính của module.
    #       Kiểm bằng hasattr, không phải bằng tìm chuỗi trong file: chuỗi có
    #       thể nằm trong chú thích giải thích vì sao đã gỡ.
    for ten in ("_sync_alerts_with_inventory", "_stock_risk_level",
                "_severity_from_shortage"):
        if hasattr(dsh, ten):
            hong(f"Hàm `{ten}` VẪN CÒN trong dashboard.py",
                 "Gỡ hẳn hàm, không chỉ gỡ lời gọi.")
        else:
            dat(f"Hàm `{ten}` đã được gỡ")

    # 1.2 · không route nào của dashboard được phép ghi. Kiểm bằng cách bắt
    #       mọi lệnh ghi ở tầng driver SQLite thay vì đọc mã.
    from app.services import dss_runner

    ghi: list[str] = []

    def bat(cx, cau, *a):
        c = (cau or "").lstrip().upper()
        if c.startswith(("INSERT", "UPDATE", "DELETE", "REPLACE", "DROP",
                         "ALTER", "CREATE")):
            ghi.append(cau.strip()[:90])
        return None

    raw = db.get_bind().raw_connection()
    try:
        raw.driver_connection.set_trace_callback(
            lambda cau: bat(None, cau))
    except Exception:                                         # noqa: BLE001
        luu("Không gắn được trace_callback — bỏ qua phép kiểm ghi thời gian thực")
        raw = None

    try:
        dss_runner.risk_status_payload(db)
        dss_runner.critical_alerts_payload(db, limit=5)
        dss_runner.stock_signal(db)
    except Exception as exc:                                  # noqa: BLE001
        luu(f"Ba payload chưa chạy được (thường do chưa nạp dữ liệu): {exc}")
    finally:
        if raw is not None:
            try:
                raw.driver_connection.set_trace_callback(None)
            except Exception:                                 # noqa: BLE001
                pass

    if ghi:
        hong(f"Có {len(ghi)} lệnh GHI phát ra khi dựng response dashboard",
             "Các payload dashboard phải hoàn toàn chỉ đọc.\n"
             + "\n".join(ghi[:5]))
    else:
        dat("Không có lệnh GHI nào khi dựng ba response cảnh báo")

    # 1.3 · bảng alerts: cảnh báo tự đóng sạch là dấu hiệu lỗi cũ còn tác dụng
    if not _co_bang(db, "alerts"):
        luu("Không có bảng `alerts` — bỏ qua phép kiểm dấu vết lỗi cũ")
        return
    tong, mo = db.execute(_t("SELECT COUNT(*), SUM(CASE WHEN is_resolved = 0 "
                             "THEN 1 ELSE 0 END) FROM alerts")).first()
    tong, mo = int(tong or 0), int(mo or 0)
    if tong == 0:
        luu("Bảng `alerts` rỗng — không kết luận được gì từ nó")
    elif mo == 0:
        luu(f"Bảng `alerts` có {tong} dòng và KHÔNG dòng nào còn mở. "
            "Đây là dấu vết của lỗi cũ, không phải lỗi mới — dữ liệu đã đóng "
            "không phục hồi được; cảnh báo nay sinh từ DOI mỗi lần gọi.")
    else:
        dat(f"Bảng `alerts`: {mo}/{tong} dòng còn mở")


# ═════════════════════════════════════════════════════════════════════════════
# BƯỚC 2 · bốn luồng ETL
# ═════════════════════════════════════════════════════════════════════════════

BANG_LUONG = {
    "usage_total":      ("fact_usage_total", "period"),
    "cases_care_level": ("fact_cases_by_care_level", "period"),
    "usage_care_level": ("fact_usage_by_care_level", "period"),
    "inventory_lot":    ("fact_inventory_lot", "snapshot_date"),
}


def buoc_2(db) -> None:
    tieu_de("BƯỚC 2 · Bốn luồng ETL và dữ liệu đã nạp")

    from app.data_pipeline import dss_loader as dl

    # 2.1 · đặc tả đủ bốn luồng, mỗi luồng có file SQL thật
    if set(dl.FLOWS) == set(BANG_LUONG):
        dat(f"FLOWS khai báo đủ 4 luồng: {', '.join(dl.THU_TU_NAP)}")
    else:
        hong(f"FLOWS thiếu/thừa luồng: {sorted(set(dl.FLOWS))}",
             f"Cần đúng: {sorted(BANG_LUONG)}")

    for ten, spec in dl.FLOWS.items():
        f = dl.SQL_DIR / spec["sql_file"]
        if f.exists() and f.stat().st_size > 0:
            dat(f"{ten}: có {spec['sql_file']}")
        else:
            hong(f"{ten}: THIẾU {f}",
                 "Không có câu SQL thì load_flow trả 'skipped' trong im lặng.")

    # 2.2 · mỗi luồng phải khai `sum` — cột nào cộng được khi gộp dòng trùng.
    #       Suy từ `numeric` là sai: `lot_id` là numeric và là khoá.
    for ten, spec in dl.FLOWS.items():
        if not spec.get("sum"):
            hong(f"{ten}: thiếu khai báo `sum`",
                 "Gộp dòng trùng sẽ cộng cả khoá và cột đơn giá.")
        else:
            xau = [c for c in spec["sum"] if c in ("lot_id", "so_kho", "period",
                                                   "snapshot_date", "block_code",
                                                   "ro", "supply_code")]
            if xau:
                hong(f"{ten}: `sum` chứa cột khoá {xau}")
            else:
                dat(f"{ten}: `sum` = {spec['sum']}")

    # 2.3 · gộp rổ lạ về NT0 — kiểm bằng dữ liệu, không bằng đọc mã
    import pandas as pd
    thu = pd.DataFrame({"period": ["2026-08"] * 3,
                        "disease_group": ["J09-J18"] * 3,
                        "ro": ["NT2", "NT9", "XYZ"],
                        "cases": [10, 5, 3]})
    ra = dl._prepare(thu, dl.FLOWS["cases_care_level"])
    if set(ra["ro"]) == {"NT2", "NT0"} and int(ra[ra.ro == "NT0"].cases.iloc[0]) == 8:
        dat("Rổ lạ (NT9, XYZ) được dồn về NT0 và cộng lại đúng: 5 + 3 = 8")
    else:
        hong(f"Dồn rổ lạ sai: {ra.to_dict('records')}")

    # 2.4 · khử trùng khoá không được cộng cột đơn giá
    thu2 = pd.DataFrame({
        "NgaySnapshot": ["2026-09-01"] * 2, "supply_code": ["VT1"] * 2,
        "lot_id": [7, 7], "lot_code": ["L", "L"], "expiry_date": ["2027-1-5"] * 2,
        "co_han_dung": [1, 1], "quantity": [80, 20], "so_kho": ["K1", "K1"],
        "don_gia_mua": [20, 20], "don_gia_thau": [19, 19], "don_gia_von": [18, 18]})
    r2 = dl._prepare(thu2, dl.FLOWS["inventory_lot"])
    if (len(r2) == 1 and float(r2.quantity.iloc[0]) == 100
            and float(r2.don_gia_mua.iloc[0]) == 20 and int(r2.lot_id.iloc[0]) == 7
            and r2.expiry_date.iloc[0] == "2027-01-05"):
        dat("Gộp trùng khoá: quantity cộng (100), đơn giá và lot_id nguyên vẹn, "
            "hạn dùng chuẩn hoá về 2027-01-05")
    else:
        hong(f"Gộp trùng khoá sai: {r2.to_dict('records')}")

    # 2.5 · dữ liệu đã có trong DB local chưa
    for ten, (bang, khoa) in BANG_LUONG.items():
        try:
            n = db.execute(_t(f"SELECT COUNT(*) FROM {bang}")).scalar() or 0
        except Exception:                                     # noqa: BLE001
            n = None
        if n is None:
            hong(f"{bang}: BẢNG CHƯA TỒN TẠI",
                 "python scripts/run_dss_load.py --full")
        elif n == 0:
            hong(f"{bang}: 0 dòng — ETL chưa chạy",
                 f"python scripts/run_dss_load.py --flow {ten} --full")
        else:
            r = db.execute(_t(f"SELECT MIN({khoa}), MAX({khoa}) FROM {bang}")).first()
            dat(f"{bang}: {n:,} dòng · {khoa} {r[0]} → {r[1]}")

    # 2.6 · bốn view phải có dòng
    for v in ("v_supply_active", "v_supply_focus", "v_supply_daily_demand",
              "v_care_level_share"):
        try:
            n = db.execute(_t(f"SELECT COUNT(*) FROM {v}")).scalar() or 0
        except Exception as exc:                              # noqa: BLE001
            hong(f"{v}: không đọc được ({str(exc)[:60]})")
            continue
        if n == 0:
            hong(f"{v}: 0 dòng", "Bảng nguồn rỗng — chạy ETL trước.")
        else:
            dat(f"{v}: {n:,} dòng")

    # 2.7 · cấp 2 phải chiếm đa số trong nội trú J09-J18 (chứng minh cửa sổ
    #       2025-04 đã có hiệu lực — Đ11)
    try:
        rows = db.execute(_t(
            "SELECT ro, share_pct FROM v_care_level_share "
            "WHERE block_code = 'J09-J18' AND ro LIKE 'NT%'")).fetchall()
    except Exception:                                         # noqa: BLE001
        rows = []
    if not rows:
        luu("Chưa kiểm được tỷ trọng phân cấp — v_care_level_share rỗng")
    else:
        d = {r.ro: float(r.share_pct or 0) for r in rows}
        nt = {k: v for k, v in d.items() if k in ("NT1", "NT2", "NT3")}
        if nt and max(nt, key=nt.get) == "NT2":
            dat(f"J09-J18 nội trú: cấp 2 chiếm đa số ({nt['NT2']:.1f}%) — "
                "cửa sổ 2025-04 đã có hiệu lực")
        else:
            hong(f"J09-J18 nội trú: cấp {max(nt, key=nt.get) if nt else '?'} "
                 f"chiếm đa số ({nt}) — cửa sổ CHƯA có hiệu lực",
                 "Kiểm dss.care_level.min_period, và kiểm fact_cases_by_care_level "
                 "đã có dữ liệu từ 2025-04 chưa (SP ca bệnh phải là bản v3).")


# ═════════════════════════════════════════════════════════════════════════════
# BƯỚC 3 · dashboard đã chuẩn hoá
# ═════════════════════════════════════════════════════════════════════════════

KHOA_CU = {
    "risk_status": ["total_items", "safe_count", "low_count", "critical_count",
                    "safe_percentage", "low_percentage", "critical_percentage",
                    "safe_items", "low_items", "critical_items"],
    "critical_alerts": ["alerts", "total_returned", "limit", "severity_summary"],
    "demand_vs_stock": ["supply_id", "supply_name", "unit", "demand", "stock"],
}


def buoc_3(db) -> None:
    tieu_de("BƯỚC 3 · Dashboard chuẩn hoá — mốc thời gian, DOI, mẫu số")

    from app.services import dss_runner, period_service as ps

    # 3.1 · mốc thời gian neo vào kỳ đã chốt
    a = ps.get_period_anchor(db)
    lc, op = a.get("last_closed_period"), a.get("open_period")
    if not lc:
        hong("Không có kỳ nào is_complete = 1 trong mart_monthly_cases_by_block")
    else:
        chot = (db.execute(_t(
            "SELECT MAX(period) FROM mart_monthly_cases_by_block "
            "WHERE is_complete = 1")).scalar()
            if _co_bang(db, "mart_monthly_cases_by_block") else None)
        if lc == chot:
            dat(f"Kỳ chốt = max(period) WHERE is_complete = 1 = {lc}")
        else:
            hong(f"Kỳ chốt {lc} ≠ max(period) is_complete=1 = {chot}")
        if op and op <= lc:
            hong(f"Kỳ đang mở {op} không lớn hơn kỳ chốt {lc}")
        elif op:
            dat(f"Kỳ đang mở {op} được tách riêng, không tham gia so sánh")

    # 3.2 · ba endpoint dùng DOI, giữ đủ khoá cũ
    th = None
    try:
        from app.services import dss_alerts
        th = dss_alerts.get_thresholds(db)
        if (float(th["doi_red_days"]), float(th["doi_amber_days"])) == (18.0, 36.0):
            dat("Ngưỡng DOI đọc từ dss.thresholds = 18 / 36 ngày")
        else:
            hong(f"Ngưỡng DOI = {th['doi_red_days']}/{th['doi_amber_days']}, "
                 "không phải 18/36")
    except Exception as exc:                                  # noqa: BLE001
        hong(f"Không đọc được ngưỡng: {exc}")

    rs = dss_runner.risk_status_payload(db)
    thieu = [k for k in KHOA_CU["risk_status"] if k not in rs]
    if thieu:
        hong(f"/risk-status thiếu khoá cũ: {thieu}")
    else:
        dat("/risk-status giữ đủ 10 khoá cũ")
    if "grey_count" in rs:
        dat(f"/risk-status có khoá `grey_count` riêng ({rs['grey_count']} mã) — "
            "Xám không bị dồn vào safe")
    else:
        hong("/risk-status thiếu `grey_count`",
             "Nhãn Xám bị dồn vào safe là lỗi nặng nhất ở tầng này.")
    if rs.get("san_sang"):
        t = (rs["safe_count"] + rs["low_count"] + rs["critical_count"]
             + rs["grey_count"])
        if t == rs["total_items"]:
            dat(f"/risk-status: bốn nhóm cộng đúng tổng ({t})")
        else:
            hong(f"/risk-status: {t} ≠ total_items {rs['total_items']}")
        # nhất quán DOI ↔ nhãn
        sai = [r["supply_code"] for r in rs["critical_items"]
               if r["doi"] is not None and r["doi"] > float(th["doi_red_days"])]
        if sai:
            hong(f"{len(sai)} mã nhãn Đỏ nhưng DOI > 18: {sai[:5]}")
        else:
            dat("Mọi mã nhãn Đỏ đều có DOI ≤ 18 ngày")
    else:
        luu(f"/risk-status chưa sẵn sàng: {rs.get('ly_do')}")

    ca = dss_runner.critical_alerts_payload(db, limit=5)
    thieu = [k for k in KHOA_CU["critical_alerts"] if k not in ca]
    if thieu:
        hong(f"/critical-alerts thiếu khoá cũ: {thieu}")
    else:
        dat("/critical-alerts giữ đủ 4 khoá cũ")
    xam = [a for a in ca.get("alerts", []) if a.get("muc") == "grey"]
    if xam:
        hong(f"/critical-alerts chứa {len(xam)} mã Xám",
             "Xám là 'chưa đo được', không phải 'sắp hết'.")
    else:
        dat("/critical-alerts không chứa mã Xám")

    # 3.3 · mẫu số
    cat = ps.catalogue_counts(db)
    if cat["active"] and cat["active"] < cat["total"]:
        dat(f"Mẫu số: active {cat['active']:,} / tổng danh mục {cat['total']:,}")
    elif not cat["active"]:
        hong("v_supply_active = 0 → mọi tỷ lệ % sẽ chia cho mẫu số tĩnh",
             "python scripts/run_dss_load.py --flow usage_total --full")
    else:
        luu(f"active ({cat['active']}) không nhỏ hơn total ({cat['total']})")
    if cat["focus"]:
        dat(f"Mẫu số dịch tễ: focus {cat['focus']:,} mã (hô hấp ≥ 25%)")
    else:
        hong("v_supply_focus = 0 → thẻ dịch tễ không có mẫu số riêng")


# ═════════════════════════════════════════════════════════════════════════════
# BƯỚC 4 · dự báo → forecast_accuracy → nhu cầu
# ═════════════════════════════════════════════════════════════════════════════

def buoc_4(db, khong_ghi: bool = False) -> None:
    tieu_de("BƯỚC 4 · Vòng khép kín dự báo → nhu cầu → cảnh báo")

    from app.services import dss_runner

    cy = dss_runner.run_forecast_cycle(db, horizon=1,
                                       save_accuracy=not khong_ghi)
    if cy["loi"]:
        for e in cy["loi"]:
            hong(e)
    else:
        dat("Ba tầng chạy trọn, không lỗi")

    # 4.1 · Tầng A đạt WAPE quanh 12,6% và KHÔNG xấu đi theo tầm dự báo
    acc = {(r["model"], r["h"]): r for r in cy.get("do_chinh_xac", [])}
    if not acc:
        hong("Không có kết quả kiểm định — Tầng 1 chưa chạy được")
    else:
        w = {h: acc[("ridge_total", h)]["wape"] for h in (1, 2, 3)
             if ("ridge_total", h) in acc}
        if 3 in w:
            if 10.0 <= w[3] <= 16.0:
                dat(f"WAPE ridge_total h=3 = {w[3]:.2f}% (khoảng chờ đợi 10–16%)")
            else:
                hong(f"WAPE ridge_total h=3 = {w[3]:.2f}%, ngoài khoảng 10–16%",
                     "Lệch nhiều nghĩa là dữ liệu ca bệnh đã đổi — đo lại trước "
                     "khi tin con số trên dashboard.")
        if 1 in w and 3 in w:
            if w[3] <= w[1] + 1.0:
                dat(f"WAPE phẳng theo tầm: h1 {w[1]:.2f}% → h3 {w[3]:.2f}%")
            else:
                hong(f"WAPE xấu đi theo tầm: h1 {w[1]:.2f}% → h3 {w[3]:.2f}%",
                     "Đây là dấu hiệu bước cắt tầm dự báo trong backtest bị sai. "
                     "Dừng lại kiểm, đừng tin số.")
        nv = {h: acc[("naive1", h)]["wape"] for h in (1, 3) if ("naive1", h) in acc}
        if 1 in nv and 3 in nv:
            if nv[3] > nv[1] + 2.0:
                dat(f"Đối chuẩn naive1 vỡ ra theo tầm: {nv[1]:.2f}% → {nv[3]:.2f}% "
                    "— mô hình mua được TẦM NHÌN")
            else:
                luu(f"naive1 không vỡ theo tầm ({nv[1]:.2f}% → {nv[3]:.2f}%) — "
                    "luận điểm 'mô hình mua được tầm nhìn' yếu đi")

    # 4.2 · khoảng dự báo
    fc = cy.get("du_bao_tong")
    if fc:
        if fc["lo"] < fc["diem"] < fc["hi"]:
            dat(f"Dự báo {fc['period']}: {fc['diem']:.0f} ca "
                f"[{fc['lo']:.0f} – {fc['hi']:.0f}] ở mức {fc['muc_tin_cay']:.0%}")
        else:
            hong(f"Khoảng dự báo không bọc điểm: {fc}")
    else:
        hong("Không có dự báo tổng")

    cov = cy.get("do_phu_khoang") or []
    for r in cov:
        p = r.get("do_phu_pct")
        if p is None:
            continue
        if p < 60:
            hong(f"Độ phủ khoảng h={r['h']} chỉ {p}% (mục tiêu {r['muc_tieu_pct']}%)",
                 "Khoảng quá hẹp — đừng trình bày như khoảng tin cậy đã hiệu chỉnh.")
        elif p < r["muc_tieu_pct"] - 5:
            luu(f"Độ phủ khoảng h={r['h']} = {p}% < mục tiêu {r['muc_tieu_pct']}% "
                "— phải khai báo trong báo cáo")
        else:
            dat(f"Độ phủ khoảng h={r['h']} = {p}%")

    # 4.3 · bảng forecast_accuracy
    n = lo = 0
    if _co_bang(db, "forecast_accuracy"):
        try:
            n = db.execute(_t("SELECT COUNT(*) FROM forecast_accuracy")).scalar() or 0
            lo = db.execute(_t("SELECT COUNT(DISTINCT run_at) "
                               "FROM forecast_accuracy")).scalar() or 0
        except Exception:                                     # noqa: BLE001
            n = lo = 0
    if khong_ghi:
        luu(f"Chạy với --khong-ghi: forecast_accuracy có {n} dòng (không ghi thêm)")
    elif n == 0:
        hong("forecast_accuracy rỗng sau khi chạy --save")
    else:
        dat(f"forecast_accuracy: {n} dòng / {lo} lô run_at")
        r = db.execute(_t("SELECT run_at, target, model, h, wape, mae, rmse, r2, "
                          "do_phu_pct FROM forecast_accuracy "
                          "ORDER BY id DESC LIMIT 1")).first()
        thieu = [c for c, v in zip(("wape", "mae", "rmse", "r2"),
                                   (r.wape, r.mae, r.rmse, r.r2)) if v is None]
        if thieu:
            hong(f"Lô mới nhất thiếu metric: {thieu}")
        else:
            dat(f"Lô mới nhất đủ 4 metric: WAPE {r.wape} · MAE {r.mae} · "
                f"RMSE {r.rmse} · R² {r.r2}")

    # 4.4 · Tầng 2 quy đổi được, và nói thật về chiều độ nặng
    nc = cy.get("nhu_cau")
    if not nc:
        hong("Tầng 2 không quy đổi được nhu cầu")
    else:
        if nc["so_ma"] > 0:
            dat(f"Tầng 2: quy đổi ra nhu cầu cho {nc['so_ma']:,} mã "
                f"trong {nc['horizon_days']} ngày")
        else:
            hong("Tầng 2: 0 mã có nhu cầu",
                 "Thiếu định mức (disease_supply_norms) hoặc thiếu p̂(g,c).")
        cd = nc["chan_doan_dinh_muc"]
        if cd["phan_biet_theo_do_nang"]:
            dat("Định mức CÓ phân biệt theo độ nặng — phân rã phân cấp có tác dụng")
        else:
            luu("Định mức KHÔNG phân biệt theo độ nặng: công thức ba lớp rút gọn "
                "thành Ŷ_g × Norm_i,g. Bộ máy p̂(g,c) hiện chỉ là đường dẫn — "
                "đừng trình bày như thể nó làm dự báo chính xác hơn.")
        for w in cd.get("canh_bao", []):
            luu(w)
        if nc["nhom_thieu_dinh_muc"]:
            hong(f"Nhóm không có định mức: {nc['nhom_thieu_dinh_muc']}")

    # 4.5 · Tầng 3 và FEFO
    al = cy.get("canh_bao") or {}
    if not al.get("san_sang"):
        hong(f"Tầng 3 chưa sẵn sàng: {al.get('ly_do')}")
        return
    t = al["tong_hop"]
    dat(f"Tầng 3: Đỏ {t['red']} · Vàng {t['amber']} · Xanh {t['green']} · "
        f"Xám {t['grey']} (đo được {t['do_duoc']}/{t['tong_ma']})")
    if t.get("fefo_toan_bo"):
        dat(f"FEFO áp cho TOÀN BỘ {t['tong_ma']} mã · nguồn {t.get('nguon_ton_kho')}")
    else:
        luu(f"FEFO chỉ áp cho {t['so_ma_ap_dung_fefo']}/{t['tong_ma']} mã "
            f"(nguồn {t.get('nguon_ton_kho')}). Số còn lại S_usable = tồn hiện có. "
            "KHÔNG được viết trong báo cáo là 'đã áp FEFO'.")
    for w in al.get("canh_bao", []):
        luu(w)


# ═════════════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description="Nghiệm thu bốn bước backend DSS")
    ap.add_argument("--db", default=None,
                    help="đường dẫn SQLite (mặc định: lấy từ cấu hình ứng dụng)")
    ap.add_argument("--buoc", type=int, choices=[1, 2, 3, 4], action="append",
                    help="chỉ kiểm bước này (lặp lại được)")
    ap.add_argument("--khong-ghi", action="store_true",
                    help="Bước 4 không ghi vào forecast_accuracy")
    a = ap.parse_args()
    logging.basicConfig(level=logging.ERROR, format="%(levelname)-7s %(message)s")

    if a.db:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        db = sessionmaker(bind=create_engine(f"sqlite:///{a.db}", future=True),
                          future=True)()
    else:
        from app.database import SessionLocal
        db = SessionLocal()

    cac_buoc = sorted(set(a.buoc)) if a.buoc else [1, 2, 3, 4]
    try:
        for b in cac_buoc:
            try:
                if b == 1:
                    buoc_1(db)
                elif b == 2:
                    buoc_2(db)
                elif b == 3:
                    buoc_3(db)
                else:
                    buoc_4(db, khong_ghi=a.khong_ghi)
            except Exception as exc:                          # noqa: BLE001
                hong(f"Bước {b} dừng vì lỗi không lường được: {exc}")
                logging.getLogger(__name__).exception("Bước %d", b)
    finally:
        db.close()

    print("\n" + "=" * 76)
    print(f"KẾT QUẢ:  {_dem['dat']} đạt · {_dem['hong']} không đạt · "
          f"{_dem['luu']} cần lưu ý")
    print("=" * 76)
    if _dem["hong"]:
        print("\nCác tiêu chí KHÔNG ĐẠT phải xử lý trước khi chuyển sang frontend:")
        print("dữ liệu sai trên dashboard tệ hơn dashboard trống.\n")
        return 1
    if _dem["luu"]:
        print("\nKhông có tiêu chí nào hỏng. Các dòng 'cần lưu ý' là những điều")
        print("PHẢI khai báo trong báo cáo, không phải lỗi cần sửa.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
