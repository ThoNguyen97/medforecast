"""GỘP DÒNG THỜI TIẾT TRÙNG + KHOÁ CHỐNG TÁI PHÁT (13/09/2026).

    cd backend
    python scripts/gop_thoi_tiet_trung.py            # xem trước, không ghi
    python scripts/gop_thoi_tiet_trung.py --ghi      # thực hiện

Vì sao cần: `environmental_data.location` là chuỗi tự do và trước đây không có
ràng buộc nào, nên cùng một nơi lưu dưới hai tên ("TP. Hồ Chí Minh" do UI/Open-
Meteo ghi, "Thành phố Hồ Chí Minh" do bộ dữ liệu đóng gói ghi) nằm ở hai dòng
khác nhau. Màn hình Dữ liệu thời tiết chuẩn hoá tên lúc LỌC nên hiển thị cả hai
→ người dùng thấy một tháng có hai dòng.

Script làm 3 việc:
  1. Đưa mọi `location` về tên CHUẨN (app/utils/province_alias.ten_chuan).
  2. Gộp các dòng trùng (cùng tháng × cùng địa bàn): giữ dòng đầy đủ nhất, lấp
     các trường còn thiếu từ những dòng kia rồi xoá chúng — không mất số liệu.
  3. Tạo UNIQUE INDEX để DB tự chặn về sau.

Lưu ý SQLite: trong UNIQUE, các giá trị NULL được coi là KHÁC nhau, mà
`district_ward` của dữ liệu cấp tỉnh đều NULL — nên ràng buộc phải đặt trên
biểu thức IFNULL(district_ward, ''), không thể dùng UNIQUE cột trần.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.utils.province_alias import ten_chuan  # noqa: E402

TEN_INDEX = "uq_env_thang_diaban"
# Thứ tự ưu tiên khi chọn dòng "đầy đủ nhất": nhiều trường có dữ liệu hơn thì thắng.
COT_DU_LIEU = ["temperature", "humidity", "rainfall", "air_quality_index", "pm25"]


def _khoa(row: sqlite3.Row) -> tuple:
    return (row["recorded_at"], row["location"], row["district_ward"] or "")


def _do_day(row: sqlite3.Row) -> int:
    return sum(1 for c in COT_DU_LIEU if row[c] is not None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="data/medforecast.db",
                    help="đường dẫn file SQLite của app (chạy từ thư mục backend/)")
    ap.add_argument("--ghi", action="store_true",
                    help="thực sự ghi thay đổi (mặc định chỉ xem trước)")
    args = ap.parse_args()

    duong_dan = Path(args.db)
    if not duong_dan.exists():
        print(f"DỪNG: không thấy {duong_dan}. Chạy từ thư mục backend/.")
        return 1

    if args.ghi:
        ban_sao = duong_dan.with_name(
            f"saoluu_{datetime.now():%Y%m%d_%H%M%S}_{duong_dan.name}")
        shutil.copy2(duong_dan, ban_sao)
        print(f"Đã sao lưu → {ban_sao.name}")

    con = sqlite3.connect(duong_dan)
    con.row_factory = sqlite3.Row

    # ── 0. chuẩn hoá recorded_at ──────────────────────────────────────────────
    # SQLite lưu DATETIME dưới dạng TEXT, và hai đường ghi dùng hai định dạng
    # khác nhau: SQLAlchemy ghi '2026-09-01 00:00:00.000000', còn INSERT thô
    # trong khoi_tao_moi.py ghi '2026-09-01 00:00:00'. Là hai CHUỖI khác nhau
    # nên vừa lọt khỏi câu gộp bên dưới, vừa lọt khỏi UNIQUE INDEX — cùng một
    # tháng vẫn nằm được ở hai dòng dù tên tỉnh đã giống hệt.
    doi_ngay = 0
    for r in con.execute("SELECT DISTINCT recorded_at FROM environmental_data").fetchall():
        cu = r["recorded_at"]
        if not cu:
            continue
        moi = None
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                moi = datetime.strptime(cu, fmt).strftime("%Y-%m-%d %H:%M:%S.%f")
                break
            except ValueError:
                continue
        if moi and moi != cu:
            n = con.execute(
                "UPDATE environmental_data SET recorded_at = ? WHERE recorded_at = ?",
                (moi, cu)).rowcount
            print(f"  chuẩn ngày: {cu!r} → {moi!r}  ({n} dòng)")
            doi_ngay += n
    if not doi_ngay:
        print("  không có recorded_at nào phải chuẩn hoá")

    # ── 1. chuẩn hoá tên ──────────────────────────────────────────────────────
    doi_ten = 0
    for r in con.execute("SELECT DISTINCT location FROM environmental_data").fetchall():
        cu = r["location"]
        moi = ten_chuan(cu or "")
        if moi and moi != cu:
            n = con.execute(
                "UPDATE environmental_data SET location = ? WHERE location = ?",
                (moi, cu)).rowcount
            print(f"  đổi tên: {cu!r} → {moi!r}  ({n} dòng)")
            doi_ten += n
    if not doi_ten:
        print("  không có tên nào phải chuẩn hoá")

    # ── 2. gộp dòng trùng ─────────────────────────────────────────────────────
    nhom: dict[tuple, list[sqlite3.Row]] = {}
    for r in con.execute(
            "SELECT id, recorded_at, location, district_ward, "
            + ", ".join(COT_DU_LIEU) + ", data_source FROM environmental_data"):
        nhom.setdefault(_khoa(r), []).append(r)

    xoa_ids: list[int] = []
    gop = 0
    for khoa, rows in sorted(nhom.items()):
        if len(rows) < 2:
            continue
        rows.sort(key=lambda r: (_do_day(r), r["id"]), reverse=True)
        giu, bo = rows[0], rows[1:]
        lap = {}
        for c in COT_DU_LIEU:
            if giu[c] is None:
                for r in bo:
                    if r[c] is not None:
                        lap[c] = r[c]
                        break
        print(f"  gộp {khoa[0][:7]} {khoa[1]}: giữ id={giu['id']} "
              f"({giu['data_source']}), xoá {[r['id'] for r in bo]}"
              + (f", lấp {lap}" if lap else ""))
        if lap:
            con.execute(
                f"UPDATE environmental_data SET {', '.join(f'{c} = ?' for c in lap)} "
                "WHERE id = ?", (*lap.values(), giu["id"]))
        xoa_ids += [r["id"] for r in bo]
        gop += 1
    if not gop:
        print("  không có dòng trùng")
    if xoa_ids:
        con.executemany("DELETE FROM environmental_data WHERE id = ?",
                        [(i,) for i in xoa_ids])

    # ── 3. khoá chống tái phát ────────────────────────────────────────────────
    con.execute(f"DROP INDEX IF EXISTS {TEN_INDEX}")
    con.execute(
        f"CREATE UNIQUE INDEX {TEN_INDEX} ON environmental_data "
        "(recorded_at, location, IFNULL(district_ward, ''))")
    print(f"  đã tạo UNIQUE INDEX {TEN_INDEX}")

    if args.ghi:
        con.commit()
        print(f"XONG: chuẩn ngày {doi_ngay} dòng, chuẩn tên {doi_ten} dòng, "
              f"gộp {gop} nhóm, xoá {len(xoa_ids)} dòng thừa.")
    else:
        con.rollback()
        print("XEM TRƯỚC — chưa ghi gì. Thêm --ghi để thực hiện.")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
