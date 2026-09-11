#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NGHIỆM THU GIAI ĐOẠN G1
=============================================================================
Đặt tại: backend/scripts/verify_g1.py

    cd backend
    python scripts/verify_g1.py
    python scripts/verify_g1.py --api http://127.0.0.1:8000 --token <JWT>
    python scripts/verify_g1.py --db data/medforecast.db

Kiểm tra sáu tiêu chí đã chốt trong G1_HuongDan.md. Mỗi tiêu chí trả lời được
bằng MỘT CON SỐ, không bằng cảm nhận. Thoát với mã 1 nếu có tiêu chí ĐẠT hụt.

Chỉ đọc — script không ghi gì vào cơ sở dữ liệu.

-----------------------------------------------------------------------------
NGƯỠNG LẤY TỪ ĐÂU

Các con số kỳ vọng bên dưới là kết quả đo thật trên HIS Gia An ngày 06/09/2026
(Đ9, Đ10 và phép đối chiếu DOI), không phải ước lượng:

    danh mục còn hoạt động   ~1.900 mã   (Đ10-A: 1.901 mã có tiêu hao 12 tháng)
    tập trọng tâm            ~555  mã    (Đ10-B: 110 + 179 + 258 = 547; SP: 555)
    tỷ trọng hô hấp chung    7–10%       (Đ10-A: 7,80%; SP 24 tháng: 7,72%)

Sai lệch lớn so với các mốc này thường KHÔNG phải do dữ liệu đổi, mà do một
bước trong chuỗi nạp chưa chạy hoặc chạy nhầm nguồn — thông điệp của từng tiêu
chí nói rõ nghi ngờ đầu tiên nên kiểm tra.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple

# ── ngưỡng kỳ vọng ───────────────────────────────────────────────────────────
ACTIVE_MIN, ACTIVE_MAX = 1_400, 2_600      # quanh 1.900
FOCUS_MIN, FOCUS_MAX = 380, 800            # quanh 555
SHARE_MIN, SHARE_MAX = 5.0, 15.0           # quanh 7,8%
TREND_ABS_MAX = 100.0                      # |xu hướng| giữa hai kỳ đã chốt

TREND_WINDOW = 24                          # số kỳ đã chốt gần nhất đem ra soi

# Màu chỉ bật khi thật sự ra terminal — tránh rác \033[ trong file log và trên
# cmd.exe cũ không hiểu ANSI.
_MAU = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
RESET = BOLD = GREEN = RED = YELLOW = DIM = ""
if _MAU:
    RESET, BOLD = "\033[0m", "\033[1m"
    GREEN, RED, YELLOW, DIM = "\033[32m", "\033[31m", "\033[33m", "\033[2m"


class Result:
    def __init__(self):
        self.rows: List[Tuple[str, str, bool, str]] = []

    def add(self, ma: str, ten: str, dat: bool, chi_tiet: str):
        self.rows.append((ma, ten, dat, chi_tiet))

    @property
    def failed(self) -> int:
        return sum(1 for _, _, d, _ in self.rows if not d)

    def show(self):
        w = max(len(t) for _, t, _, _ in self.rows) + 2
        print("\n" + "=" * 78)
        print(BOLD + "NGHIỆM THU G1" + RESET)
        print("=" * 78)
        for ma, ten, dat, ct in self.rows:
            mark = (GREEN + "ĐẠT   " + RESET) if dat else (RED + "CHƯA  " + RESET)
            print(f"  {ma:<4} {mark} {ten:<{w}} {ct}")
        print("-" * 78)
        if self.failed:
            print(f"  {RED}{self.failed}/{len(self.rows)} tiêu chí chưa đạt.{RESET}"
                  "  Xem gợi ý ở từng dòng trước khi sang G2.")
        else:
            print(f"  {GREEN}Toàn bộ {len(self.rows)} tiêu chí ĐẠT — G1 hoàn thành.{RESET}")
        print("=" * 78)


# ─────────────────────────────────────────────────────────────────────────────

def find_db(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    for p in ("data/medforecast.db", "backend/data/medforecast.db",
              "../data/medforecast.db"):
        if os.path.exists(p):
            return p
    return "data/medforecast.db"


def q1(cx: sqlite3.Connection, sql: str, params: tuple = ()) -> Any:
    try:
        r = cx.execute(sql, params).fetchone()
        return r[0] if r else None
    except sqlite3.Error:
        return None


def has(cx: sqlite3.Connection, name: str) -> bool:
    return q1(cx, "SELECT 1 FROM sqlite_master WHERE name=? AND type IN ('table','view')",
              (name,)) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Sáu tiêu chí
# ─────────────────────────────────────────────────────────────────────────────

def t1_usage_total(cx, R: Result):
    """fact_usage_total có dữ liệu và LỚN HƠN RÕ RỆT fact_supply_usage.

    Đây là tiêu chí quan trọng nhất của G1. Hai bảng bằng nhau nghĩa là bộ lọc
    ICD vẫn còn trong stored procedure — mẫu số của DOI vẫn chỉ là phần hô hấp
    (7,8% thực tế), và mọi con số tồn kho sau đó bị thổi lên khoảng bảy lần.
    """
    if not has(cx, "fact_usage_total"):
        R.add("T1", "fact_usage_total có dữ liệu", False,
              "chưa có bảng — chạy G1_03_LOCAL_cau_hinh.sql")
        return
    n = q1(cx, "SELECT COUNT(*) FROM fact_usage_total") or 0
    if n == 0:
        R.add("T1", "fact_usage_total có dữ liệu", False,
              "0 dòng — chưa chạy nạp dữ liệu (scripts/run_dss_load.py)")
        return
    tong_moi = q1(cx, "SELECT COALESCE(SUM(so_luong_toan_vien),0) FROM fact_usage_total") or 0
    tong_cu = q1(cx, "SELECT COALESCE(SUM(quantity),0) FROM fact_supply_usage") or 0
    ty = (tong_moi / tong_cu) if tong_cu else 0
    dat = n > 0 and tong_moi > tong_cu * 1.5
    R.add("T1", "fact_usage_total > fact_supply_usage", dat,
          f"{n:,} dòng · tổng {tong_moi:,.0f} so với {tong_cu:,.0f} "
          f"(gấp {ty:.1f}×)" +
          ("" if dat else "  → nghi bộ lọc ICD vẫn còn trong SP"))


def t2_active(cx, R: Result):
    if not has(cx, "v_supply_active"):
        R.add("T2", "danh mục còn hoạt động ~1.900", False,
              "chưa có view — chạy G1_03_LOCAL_cau_hinh.sql")
        return
    n = q1(cx, "SELECT COUNT(*) FROM v_supply_active") or 0
    dat = ACTIVE_MIN <= n <= ACTIVE_MAX
    goi_y = ""
    if n and n < ACTIVE_MIN:
        goi_y = "  → nghi pipeline vẫn nạp bảng tiêu hao cũ (chỉ hô hấp)"
    R.add("T2", "danh mục còn hoạt động ~1.900", dat,
          f"{n:,} mã (kỳ vọng {ACTIVE_MIN:,}–{ACTIVE_MAX:,}){goi_y}")


def t3_focus(cx, R: Result):
    if not has(cx, "v_supply_focus"):
        R.add("T3", "tập trọng tâm ~555", False, "chưa có view")
        return
    n = q1(cx, "SELECT COUNT(*) FROM v_supply_focus") or 0
    dat = FOCUS_MIN <= n <= FOCUS_MAX
    R.add("T3", "tập trọng tâm ~555", dat,
          f"{n:,} mã có tỷ trọng hô hấp ≥ 25% (kỳ vọng {FOCUS_MIN}–{FOCUS_MAX})")


def t4_share(cx, R: Result):
    """Tỷ trọng hô hấp trung bình phải quanh 7–10%.

    Ra ~100% nghĩa là cột so_luong_hohap đang được nạp bằng chính
    so_luong_toan_vien — tức nguồn vẫn là bảng cũ, mẫu số chưa sửa.
    Ra ~0% nghĩa là bộ lọc ICD bên SP không khớp mã nào.
    """
    if not has(cx, "v_supply_daily_demand"):
        R.add("T4", "tỷ trọng hô hấp 5–15%", False, "chưa có view")
        return
    tb = q1(cx, "SELECT ROUND(AVG(ty_trong_hohap),2) FROM v_supply_daily_demand")
    if tb is None:
        R.add("T4", "tỷ trọng hô hấp 5–15%", False, "không tính được — view rỗng")
        return
    dat = SHARE_MIN <= float(tb) <= SHARE_MAX
    goi_y = ""
    if float(tb) > 60:
        goi_y = "  → so_luong_hohap đang bằng so_luong_toan_vien, mẫu số chưa sửa"
    elif float(tb) < 1:
        goi_y = "  → bộ lọc ICD bên SP không khớp mã nào"
    R.add("T4", "tỷ trọng hô hấp 5–15%", dat,
          f"trung bình {tb}% (Đ10 đo được 7,80%){goi_y}")


def t5_anchor(cx, R: Result, api: Optional[str], token: Optional[str]):
    """Mốc kỳ đã chốt. Kiểm tra ở DB; nếu có --api thì kiểm tra thêm response thật."""
    if not has(cx, "mart_monthly_cases_by_block"):
        R.add("T5", "mốc kỳ đã chốt", False, "chưa có mart_monthly_cases_by_block")
        return
    closed = q1(cx, "SELECT MAX(period) FROM mart_monthly_cases_by_block WHERE is_complete=1")
    open_p = q1(cx, "SELECT MAX(period) FROM mart_monthly_cases_by_block WHERE is_complete=0")
    ct = f"kỳ đã chốt = {closed} · kỳ đang mở = {open_p or '—'}"
    dat = bool(closed) and (open_p is None or open_p > closed)

    if api:
        try:
            import urllib.request
            req = urllib.request.Request(api.rstrip("/") + "/api/v1/dashboard/summary")
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            api_closed = body.get("last_closed_period")
            ct += f" · API trả {api_closed}"
            dat = dat and api_closed == closed
            if body.get("open_period") and body.get("open_period") == api_closed:
                ct += "  → API vẫn neo vào kỳ đang mở"
                dat = False
        except Exception as exc:                     # noqa: BLE001
            ct += f" · API không gọi được ({type(exc).__name__}) — bỏ qua"

    R.add("T5", "KPI neo vào kỳ đã chốt", dat, ct)


def t6_trend(cx, R: Result, window: int = TREND_WINDOW):
    """|xu hướng| giữa hai kỳ ĐÃ CHỐT liên tiếp phải < 100%, xét 24 kỳ gần nhất.

    Bản cũ so kỳ đang mở với kỳ đã chốt và cho ra 6500%. Lỗi đó theo cấu tạo
    luôn xuất hiện ở CUỐI chuỗi, nên soi 24 kỳ gần nhất là đủ bắt.

    Cố ý KHÔNG soi toàn bộ 92 kỳ: giai đoạn 2019 là lúc bệnh viện mới bắt đầu
    ghi nhận, số ca tăng vọt từ nền rất thấp (2019-03 tăng +154%) — đó là dữ
    liệu đang hình thành, không phải lỗi mốc thời gian. Bắt lỗi ở đó chỉ tạo
    báo động giả và làm cổng nghiệm thu mất tác dụng.
    """
    if not has(cx, "mart_monthly_cases_by_block"):
        R.add("T6", f"|xu hướng| < 100% ({window} kỳ gần nhất)", False, "chưa có mart")
        return
    rows = cx.execute(
        "SELECT period, SUM(cases) FROM mart_monthly_cases_by_block "
        "WHERE region='TOAN_QUOC' AND is_complete=1 GROUP BY period ORDER BY period"
    ).fetchall()
    tong_so_ky = len(rows)
    rows = rows[-(window + 1):]                 # +1 để có kỳ gốc so sánh
    if len(rows) < 2:
        R.add("T6", f"|xu hướng| < 100% ({window} kỳ gần nhất)", False,
              f"chỉ có {tong_so_ky} kỳ đã chốt — chưa đủ để so")
        return
    vi_pham = []
    for (p0, c0), (p1, c1) in zip(rows, rows[1:]):
        if c0 and c0 > 0:
            t = 100.0 * (c1 - c0) / c0
            if abs(t) >= TREND_ABS_MAX:
                vi_pham.append((p1, round(t, 1)))
    dat = not vi_pham
    ct = (f"soi {len(rows) - 1}/{tong_so_ky} kỳ gần nhất · "
          f"{len(vi_pham)} kỳ vượt ngưỡng")
    if vi_pham:
        ct += "  → " + ", ".join(f"{p} {t:+.0f}%" for p, t in vi_pham[:5])
        if len(vi_pham) > 5:
            ct += f" … (+{len(vi_pham) - 5})"
    R.add("T6", f"|xu hướng| < 100% ({window} kỳ gần nhất)", dat, ct)


# ── kiểm tra bổ sung (không tính vào 6 tiêu chí) ─────────────────────────────

def phu_luc(cx):
    print("\n" + DIM + "── Thông tin bổ sung " + "─" * 52 + RESET)

    for t in ("fact_cases_by_care_level", "fact_usage_by_care_level"):
        n = q1(cx, f"SELECT COUNT(*) FROM {t}") if has(cx, t) else None
        print(f"  {t:<28} {n if n is not None else 'chưa có bảng'}")

    if has(cx, "fact_cases_by_care_level"):
        rows = cx.execute(
            "SELECT block_code, ro, SUM(cases) c FROM fact_cases_by_care_level "
            "GROUP BY block_code, ro ORDER BY block_code, ro").fetchall()
        if rows:
            print(DIM + "\n  Tỷ trọng phân cấp chăm sóc (cổng chặn N1 — J09-J18 phải "
                  "nặng hơn J00-J06):" + RESET)
            tong: Dict[str, int] = {}
            for b, _, c in rows:
                tong[b] = tong.get(b, 0) + (c or 0)
            for b, ro, c in rows:
                pct = 100.0 * (c or 0) / tong[b] if tong.get(b) else 0
                print(f"    {b:<10} {ro:<4} {c or 0:>8,}  {pct:5.1f}%")

    if has(cx, "fact_usage_total") and has(cx, "dim_supply"):
        thieu = q1(cx, "SELECT COUNT(DISTINCT supply_code) FROM fact_usage_total "
                       "WHERE supply_code NOT IN (SELECT supply_code FROM dim_supply)")
        print(f"\n  Mã có tiêu hao nhưng KHÔNG có trong dim_supply: {thieu}")
        print(DIM + "    (đo trước đó: 311 mã — mã mới hoặc danh mục chưa đồng bộ)" + RESET)

    if has(cx, "system_config"):
        raw = q1(cx, "SELECT config_value FROM system_config WHERE config_key='dss.thresholds'")
        if raw:
            try:
                cfg = json.loads(raw)
                print(f"\n  Ngưỡng DOI: đỏ ≤ {cfg.get('doi_red_days')} ngày · "
                      f"vàng ≤ {cfg.get('doi_amber_days')} ngày")
            except ValueError:
                print("\n  Ngưỡng DOI: config_value không phải JSON hợp lệ")
        else:
            print("\n  Ngưỡng DOI: CHƯA GHI — chạy G1_03_LOCAL_cau_hinh.sql")


def main():
    ap = argparse.ArgumentParser(description="Nghiệm thu G1")
    ap.add_argument("--db", help="đường dẫn medforecast.db")
    ap.add_argument("--api", help="ví dụ http://127.0.0.1:8000 — kiểm tra thêm /summary")
    ap.add_argument("--token", help="JWT nếu endpoint yêu cầu đăng nhập")
    ap.add_argument("--trend-periods", type=int, default=TREND_WINDOW,
                    help=f"số kỳ gần nhất soi ở T6 (mặc định {TREND_WINDOW})")
    a = ap.parse_args()

    path = find_db(a.db)
    if not os.path.exists(path):
        print(f"LỖI: không thấy CSDL {path}. Dùng --db để chỉ đường dẫn.")
        sys.exit(2)
    print(f"CSDL: {os.path.abspath(path)}")

    cx = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    cx.row_factory = None
    R = Result()
    t1_usage_total(cx, R)
    t2_active(cx, R)
    t3_focus(cx, R)
    t4_share(cx, R)
    t5_anchor(cx, R, a.api, a.token)
    t6_trend(cx, R, a.trend_periods)
    R.show()
    phu_luc(cx)
    cx.close()
    sys.exit(1 if R.failed else 0)


if __name__ == "__main__":
    main()
