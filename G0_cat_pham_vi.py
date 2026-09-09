#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G0 — CẮT PHẠM VI MUA SẮM KHỎI MEDFORECAST
=============================================================================
Chạy tại THƯ MỤC GỐC của repo (nơi có backend/ và frontend/).

    cd D:\\Personnal\\LienThong\\CDTN\\webyte\\webyte
    python G0_cat_pham_vi.py                    # THỬ, không đụng vào file nào
    python G0_cat_pham_vi.py --apply            # thực hiện
    python G0_cat_pham_vi.py --apply --strip-masterdata   # + gỡ cột MOQ/sức chứa

-----------------------------------------------------------------------------
NGUYÊN TẮC CỦA SCRIPT NÀY

1. MẶC ĐỊNH LÀ THỬ. Không có --apply thì chỉ in ra sẽ làm gì.
2. KHỚP CHÍNH XÁC. Mỗi phép sửa phải tìm thấy đoạn văn bản cũ ĐÚNG TỪNG KÝ TỰ.
   Không tìm thấy thì BÁO và BỎ QUA, không đoán, không sửa gần đúng.
   Nghĩa là chạy script trên một bản mã đã thay đổi sẽ không làm hỏng gì.
3. CHẠY LẠI ĐƯỢC. Đoạn nào đã sửa rồi thì lần sau báo "đã xong", không lỗi.
4. XOÁ QUA GIT khi repo là git, để còn `git checkout` lấy lại được.

-----------------------------------------------------------------------------
KHÔNG LÀM Ở G0 — CÓ LÝ DO, ĐỪNG TỰ THÊM VÀO

• KHÔNG xoá trang frontend SupplyPlanning.
  Trang này là giao diện DUY NHẤT của dự báo phân cấp (useHierForecast) — một
  tính năng thuộc Tầng 1 đang giữ lại. Xoá bây giờ làm mất tính năng đang chạy
  mà không được gì. Phần "mức an toàn + lead time" trong
  services/supply_planning_service.py sẽ được gọt ở G3.

• KHÔNG xoá ~550 dòng trình bày báo cáo mua sắm trong api/v1/reports.py.
  Script chỉ gỡ "procurement" khỏi danh sách loại báo cáo hợp lệ, nên endpoint
  từ chối ngay ở cửa và không còn logic nào chạy. Phần trình bày PDF/Excel giữ
  lại làm khung cho báo cáo DOI ở G5 — xoá bây giờ thì G5 phải viết lại từ đầu.

• KHÔNG đụng ai_engine/supply_demand_calculator.generate_procurement_suggestion.
  Đã kiểm: ai_engine/forecasting_service.py không được bất kỳ endpoint nào gọi
  (chỉ db_forecasting_service, forecasting_pipeline và conversion_module được
  dùng). Đây là mã chết trong nhánh cũ mà G2 sẽ thay toàn bộ.

• KHÔNG drop bảng procurement_plans trong cơ sở dữ liệu.
  Gỡ model là đủ để không còn mã nào đọc/ghi nó. Bảng để lại cho tới khi bảo vệ
  xong, phòng khi cần đối chiếu số cũ.
=============================================================================
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

BACKEND = os.path.join("backend", "app")
FRONTEND = os.path.join("frontend", "src")

ok, warn, fail = [], [], []


# ── tiện ích ────────────────────────────────────────────────────────────────

def _p(path):
    return os.path.normpath(path)


def is_git_repo():
    return os.path.isdir(".git")


def delete(path, apply):
    path = _p(path)
    if not os.path.exists(path):
        ok.append(f"đã xoá trước đó: {path}")
        return
    if not apply:
        warn.append(f"[THỬ] sẽ xoá: {path}")
        return
    if is_git_repo():
        r = subprocess.run(["git", "rm", "-r", "-q", "--", path],
                           capture_output=True, text=True)
        if r.returncode != 0:
            # tệp chưa được git theo dõi
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    else:
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    ok.append(f"đã xoá: {path}")


def edit(path, old, new, label, apply, required=True):
    """Thay `old` bằng `new` trong tệp. Khớp chính xác, đúng một lần."""
    path = _p(path)
    if not os.path.exists(path):
        (fail if required else warn).append(f"không thấy tệp: {path}  ({label})")
        return
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if old not in s:
        if new and new in s:
            ok.append(f"đã sửa trước đó: {label}")
        else:
            (fail if required else warn).append(
                f"KHÔNG KHỚP — bỏ qua: {label}\n"
                f"      tệp {path} không chứa đúng đoạn cần thay.\n"
                f"      Sửa tay theo G0_HuongDan.md rồi chạy lại."
            )
        return
    n = s.count(old)
    if n > 1:
        fail.append(f"KHỚP {n} LẦN — bỏ qua cho an toàn: {label} ({path})")
        return
    if not apply:
        warn.append(f"[THỬ] sẽ sửa: {label}  ({path})")
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(s.replace(old, new, 1))
    ok.append(f"đã sửa: {label}")


def cut_between(path, start_marker, end_marker, label, apply):
    """Cắt bỏ đoạn từ start_marker tới ngay trước end_marker."""
    path = _p(path)
    if not os.path.exists(path):
        fail.append(f"không thấy tệp: {path}  ({label})")
        return
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if start_marker not in s:
        ok.append(f"đã cắt trước đó: {label}")
        return
    a = s.index(start_marker)
    if end_marker not in s[a:]:
        fail.append(f"không thấy mốc kết thúc: {label} ({path})")
        return
    b = a + s[a:].index(end_marker)
    if not apply:
        warn.append(f"[THỬ] sẽ cắt {b - a} ký tự: {label}  ({path})")
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(s[:a] + s[b:])
    ok.append(f"đã cắt: {label}  ({b - a} ký tự)")


def drop_lines(path, patterns, label, apply):
    """Xoá các dòng khớp regex. Dùng cho --strip-masterdata."""
    path = _p(path)
    if not os.path.exists(path):
        fail.append(f"không thấy tệp: {path}  ({label})")
        return
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    keep, cut = [], 0
    for ln in lines:
        if any(re.match(p, ln) for p in patterns):
            cut += 1
            continue
        keep.append(ln)
    if cut == 0:
        ok.append(f"đã gỡ trước đó: {label}")
        return
    if not apply:
        warn.append(f"[THỬ] sẽ xoá {cut} dòng: {label}  ({path})")
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(keep)
    ok.append(f"đã xoá {cut} dòng: {label}")


# ── các bước ────────────────────────────────────────────────────────────────

def buoc_1_xoa_tep(apply):
    """Xoá phân hệ mua sắm. Gỡ router TRƯỚC (bước 2) rồi mới xoá là an toàn
    nhất, nhưng script chạy tuần tự trong một lượt nên thứ tự không quan trọng
    — miễn là không khởi động app ở giữa chừng."""
    for p in [
        os.path.join(BACKEND, "procurement"),
        os.path.join(BACKEND, "api", "v1", "procurement.py"),
        os.path.join(BACKEND, "api", "v1", "test_procurement_api.py"),
        os.path.join(BACKEND, "models", "procurement_plan.py"),
    ]:
        delete(p, apply)


def buoc_2_main(apply):
    f = os.path.join(BACKEND, "main.py")
    edit(f,
         "supply_requirements, alerts, procurement, dashboard",
         "supply_requirements, alerts, dashboard",
         "main.py — gỡ procurement khỏi dòng import", apply)
    edit(f,
         '\napp.include_router(procurement.router, prefix="/api/v1/procurement", tags=["procurement"])',
         "",
         "main.py — gỡ include_router procurement", apply)


def buoc_3_models(apply):
    f = os.path.join(BACKEND, "models", "__init__.py")
    edit(f, "from app.models.procurement_plan import ProcurementPlan\n", "",
         "models/__init__.py — gỡ import", apply)
    edit(f, '    "ProcurementPlan",\n', "",
         "models/__init__.py — gỡ khỏi __all__", apply)


def buoc_4_schemas(apply):
    f = os.path.join(BACKEND, "schemas", "__init__.py")
    edit(f,
         "    # Procurement\n"
         "    ProcurementPlanBase,\n"
         "    ProcurementPlanCreate,\n"
         "    ProcurementPlanUpdate,\n"
         "    ProcurementPlanResponse,\n"
         "    ProcurementGenerateRequest,\n"
         "    ProcurementGenerateResponse,\n",
         "",
         "schemas/__init__.py — gỡ 6 import", apply)
    edit(f,
         '    "ProcurementPlanBase",\n'
         '    "ProcurementPlanCreate",\n'
         '    "ProcurementPlanUpdate",\n'
         '    "ProcurementPlanResponse",\n'
         '    "ProcurementGenerateRequest",\n'
         '    "ProcurementGenerateResponse",\n',
         "",
         "schemas/__init__.py — gỡ 6 tên khỏi __all__", apply)

    cut_between(os.path.join(BACKEND, "schemas", "base.py"),
                "# ── Procurement Plan schemas ",
                "# ── Dashboard schemas ",
                "schemas/base.py — cắt khối Procurement Plan", apply)


def buoc_5_vong_lap_safety_stock(apply):
    """Chốt chặn quan trọng nhất của G0.

    Vòng lặp cũ: safety_stock = nhu cầu × 1,15 rồi ghi ngược vào inventory;
    lần chạy sau đọc chính nó ra làm đầu vào. Mỗi lần bấm "phân tích" nhân
    thêm 1,15 lần. Cột này vì vậy không còn là tồn an toàn mà là dấu vết số
    lần bấm nút.

    Phạm vi DSS không dùng safety_stock ở bất kỳ vế nào — cảnh báo tính bằng
    DOI = tồn hữu dụng / nhu cầu trung bình ngày. Vì vậy đây là XOÁ, không
    phải sửa công thức."""
    edit(os.path.join(BACKEND, "api", "v1", "inventory.py"),
         "        # LUÔN cập nhật (ghi đè) - không bỏ qua giá trị cũ\n"
         "        calculated_safety = round(need_before_buffer * (1 + buffer_rate / 100))\n"
         "        if need_before_buffer > 0 and calculated_safety < 1:\n"
         "            calculated_safety = 1\n"
         "\n"
         "        inv.safety_stock = calculated_safety\n"
         "        updated += 1\n",

         "        # ── G0 · DSS — ĐÃ CẮT VÒNG LẶP TỰ THAM CHIẾU ───────────────\n"
         "        # Trước đây:  safety_stock = nhu cầu × (1 + 15%)  rồi ghi\n"
         "        # ngược vào inventory, và lần chạy sau lại đọc chính nó ra\n"
         "        # làm đầu vào. Mỗi lần bấm \"phân tích\" nhân thêm 1,15 lần.\n"
         "        #\n"
         "        # Phạm vi DSS không dùng safety_stock. Cảnh báo tính bằng\n"
         "        #     DOI = tồn hữu dụng (FEFO) / nhu cầu trung bình ngày\n"
         "        # và được sinh ở tầng cảnh báo (xem G4 trong lộ trình).\n"
         "        #\n"
         "        # KHÔNG khôi phục dòng ghi ngược ở đây.\n"
         "        skipped += 1\n"
         "        continue\n",
         "inventory.py — cắt vòng lặp ghi ngược safety_stock", apply)


def buoc_6_reports(apply):
    """Gỡ 'procurement' khỏi danh sách loại báo cáo hợp lệ → endpoint từ chối
    ngay ở cửa, không còn nhánh nào gọi tới logic mua sắm."""
    edit(os.path.join(BACKEND, "api", "v1", "reports.py"),
         '        "shortage",\n        "procurement",\n',
         '        "shortage",\n'
         '        # "procurement" — gỡ ở G0 (phạm vi DSS). Khung trình bày\n'
         '        # PDF/Excel bên dưới giữ lại làm nền cho báo cáo DOI ở G5.\n',
         "reports.py — gỡ loại báo cáo procurement", apply)


def buoc_7_sidebar(apply):
    f = os.path.join(FRONTEND, "components", "layout", "Sidebar.tsx")
    edit(f, "  ShoppingCart,\n", "  ShieldAlert,\n",
         "Sidebar.tsx — đổi icon giỏ hàng sang khiên cảnh báo", apply)
    edit(f,
         "  { label: 'Đề xuất nhập kho', path: ROUTES.ALERTS, icon: ShoppingCart },",
         "  { label: 'Cảnh báo tồn kho', path: ROUTES.ALERTS, icon: ShieldAlert },",
         "Sidebar.tsx — đổi nhãn mục menu", apply)


def buoc_8_masterdata(apply):
    """Chỉ chạy với --strip-masterdata.

    MOQ và sức chứa kho là hai trong bốn cột master data rỗng 0/5.041 dòng và
    chỉ phục vụ đơn hàng. HIS không có và sẽ không bao giờ có dữ liệu sức chứa
    kho (kho dược quản lý theo giá trị và số lượng, không theo thể tích).

    Ở backend: xoá khỏi model và schema.
    Ở frontend: chỉ chuyển sang tuỳ chọn, KHÔNG xoá — vài component đang đọc
    hai trường này và xoá kiểu sẽ làm hỏng build. G5 dọn nốt cùng lúc viết lại
    giao diện."""
    drop_lines(os.path.join(BACKEND, "models", "medical_supply.py"),
               [r"^\s*minimum_order_quantity\s*=\s*Column",
                r"^\s*storage_capacity\s*=\s*Column"],
               "medical_supply.py — gỡ 2 cột khỏi model", apply)
    drop_lines(os.path.join(BACKEND, "schemas", "base.py"),
               [r"^\s*minimum_order_quantity:\s*Optional\[int\]",
                r"^\s*storage_capacity:\s*Optional\[int\]"],
               "schemas/base.py — gỡ 2 trường khỏi schema", apply)
    edit(os.path.join(FRONTEND, "types", "inventory.ts"),
         "  minimum_order_quantity: number;",
         "  minimum_order_quantity?: number | null;   // G0: không dùng trong phạm vi DSS",
         "types/inventory.ts — MOQ thành tuỳ chọn", apply, required=False)
    edit(os.path.join(FRONTEND, "types", "inventory.ts"),
         "  storage_capacity: number;",
         "  storage_capacity?: number | null;         // G0: HIS không có dữ liệu này",
         "types/inventory.ts — sức chứa thành tuỳ chọn", apply, required=False)


def kiem_tra_con_sot():
    """Quét lại xem còn dấu vết mua sắm nào không."""
    pat = re.compile(r"procurement|ProcurementPlan", re.I)
    bo_qua = ("__pycache__", "node_modules", ".git", "ai_engine")
    con = []
    for root in (BACKEND, FRONTEND):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in bo_qua]
            for fn in filenames:
                if not fn.endswith((".py", ".ts", ".tsx")):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, encoding="utf-8") as f:
                        for i, ln in enumerate(f, 1):
                            if pat.search(ln):
                                con.append(f"{fp}:{i}: {ln.strip()[:110]}")
                except Exception:
                    pass
    return con


# ── chạy ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="G0 — cắt phạm vi mua sắm")
    ap.add_argument("--apply", action="store_true",
                    help="thực hiện thật (mặc định chỉ thử)")
    ap.add_argument("--strip-masterdata", action="store_true",
                    help="gỡ thêm cột MOQ và sức chứa kho")
    a = ap.parse_args()

    if not (os.path.isdir("backend") and os.path.isdir("frontend")):
        print("LỖI: chạy script này tại thư mục gốc của repo (nơi có backend/ và frontend/).")
        sys.exit(1)

    if a.apply and is_git_repo():
        r = subprocess.run(["git", "status", "--porcelain"],
                           capture_output=True, text=True)
        if r.stdout.strip():
            print("CẢNH BÁO: repo đang có thay đổi chưa commit.")
            print("Nên commit hoặc stash trước để diff của G0 đọc được rõ ràng.")
            if input("Vẫn tiếp tục? [y/N] ").strip().lower() != "y":
                sys.exit(0)

    print("=" * 74)
    print("G0 — CẮT PHẠM VI MUA SẮM" + ("  [THỰC HIỆN]" if a.apply else "  [THỬ — không đụng file nào]"))
    print("=" * 74)

    buoc_1_xoa_tep(a.apply)
    buoc_2_main(a.apply)
    buoc_3_models(a.apply)
    buoc_4_schemas(a.apply)
    buoc_5_vong_lap_safety_stock(a.apply)
    buoc_6_reports(a.apply)
    buoc_7_sidebar(a.apply)
    if a.strip_masterdata:
        buoc_8_masterdata(a.apply)

    for tieu_de, ds in (("ĐÃ LÀM", ok), ("CẦN CHÚ Ý", warn), ("KHÔNG LÀM ĐƯỢC", fail)):
        if ds:
            print(f"\n── {tieu_de} " + "─" * (70 - len(tieu_de)))
            for x in ds:
                print("  • " + x)

    if a.apply:
        print("\n── QUÉT LẠI DẤU VẾT CÒN SÓT " + "─" * 46)
        con = kiem_tra_con_sot()
        if con:
            print(f"  Còn {len(con)} dòng nhắc tới mua sắm (đã bỏ qua ai_engine — mã chết,")
            print("  G2 sẽ thay toàn bộ). Xem lại từng dòng:")
            for c in con[:40]:
                print("    " + c)
        else:
            print("  Sạch. Không còn dòng nào ngoài ai_engine.")

    print("\n── BƯỚC TIẾP THEO " + "─" * 56)
    if not a.apply:
        print("  Chạy lại với --apply để thực hiện.")
    else:
        print("  1) cd backend && uvicorn app.main:app --reload     → app phải khởi động sạch")
        print("  2) mở http://127.0.0.1:8000/docs                   → không còn nhóm 'procurement'")
        print("  3) cd frontend && npm run build                    → build phải xanh")
        print("  4) pytest backend/app -q                           → chạy được (test procurement đã xoá)")
        print("  5) git diff --stat                                 → xem lại trước khi commit")
    if fail:
        print("\n  Có mục KHÔNG LÀM ĐƯỢC — xem G0_HuongDan.md, mục 'Sửa tay'.")
        sys.exit(2)


if __name__ == "__main__":
    main()
