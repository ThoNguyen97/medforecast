"""Dựng CSDL HIS_PROD MÔ PHỎNG từ dữ liệu Gia An, để thử nghiệm chuỗi PROD -> STA.

Dùng khi chưa được cấp quyền vào HIS thật. Schema đặt tên giống HIS (KhamBenh,
ChanDoan, BenhNhan, SuDungVatTu, VatTu, TonKho) để câu SQL trong
app/data_pipeline/sql/ chạy được nguyên vẹn — chuyển sang HIS thật chỉ là đổi
chuỗi kết nối.

Điểm khác biệt so với file CSV: CSV đã tổng hợp sẵn số ca theo tháng, còn HIS lưu
TỪNG LƯỢT KHÁM. Script bung ngược: (tháng, mã ICD, tỉnh, cases=N) -> N lượt khám
riêng biệt, rải đều trong tháng. Nhờ vậy câu SQL phải thật sự đếm
COUNT(DISTINCT lượt khám) mới ra đúng số — đúng như với HIS thật.

Bảng BenhNhan cố tình có cột định danh (HoTen, CCCD, DiaChi) mà câu SQL KHÔNG hề
đọc tới, để minh hoạ nguyên tắc chỉ lấy dữ liệu tối thiểu.

Chạy (từ thư mục backend/):
    python scripts/sim_his_build_prod.py --data-dir ../../data --out ../../data/sim/his_prod.db
"""
from __future__ import annotations

import argparse
import os
import random
import sqlite3
import sys
from collections import defaultdict

import pandas as pd

DDL = """
CREATE TABLE BenhNhan (
    Id      INTEGER PRIMARY KEY,
    HoTen   TEXT,          -- KHÔNG được đọc: dữ liệu định danh
    CCCD    TEXT,          -- KHÔNG được đọc: dữ liệu định danh
    DiaChi  TEXT,          -- KHÔNG được đọc: dữ liệu định danh
    Tinh    TEXT           -- chỉ trường này được dùng
);
CREATE TABLE KhamBenh (
    Id          INTEGER PRIMARY KEY,
    BenhNhanId  INTEGER,
    NgayKham    TEXT,
    TrangThai   TEXT,      -- HOAN_TAT | DANG_XU_LY | HUY
    NgayCapNhat TEXT       -- mốc thay đổi, dùng cho job PROD -> STA
);
CREATE TABLE ChanDoan (
    Id          INTEGER PRIMARY KEY,
    KhamBenhId  INTEGER,
    MaICD       TEXT,
    TenICD      TEXT,
    LaChinh     INTEGER    -- 1 = chẩn đoán chính
);
CREATE TABLE VatTu (
    Id        INTEGER PRIMARY KEY,
    MaVatTu   TEXT,
    TenVatTu  TEXT,
    MaThuoc   TEXT,
    HoatChat  TEXT,
    DonVi     TEXT,
    NhomVatTu TEXT,
    LoaiVatTu TEXT,
    MoTa      TEXT,
    TrangThai INTEGER
);
CREATE TABLE SuDungVatTu (
    Id         INTEGER PRIMARY KEY,
    KhamBenhId INTEGER,
    VatTuId    INTEGER,
    SoLuong    REAL
);
CREATE TABLE TonKho (
    Id          INTEGER PRIMARY KEY,
    VatTuId     INTEGER,
    SoLuongTon  INTEGER,
    NgayCapNhat TEXT
);
CREATE INDEX ix_khambenh_ngay    ON KhamBenh(NgayKham);
CREATE INDEX ix_khambenh_capnhat ON KhamBenh(NgayCapNhat);
CREATE INDEX ix_chandoan_kb      ON ChanDoan(KhamBenhId);
CREATE INDEX ix_sudungvt_kb      ON SuDungVatTu(KhamBenhId);
"""

HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Ngô"]
TEN = ["An", "Bình", "Chi", "Dũng", "Hà", "Khang", "Lan", "Minh", "Nam", "Oanh"]


def split_quantity(total: float, parts: int) -> list[float]:
    """Chia `total` thành `parts` phần, giữ nguyên tổng (phần dư dồn vào phần đầu)."""
    if parts <= 1:
        return [total]
    base = round(total / parts, 3)
    out = [base] * parts
    out[0] = round(total - base * (parts - 1), 3)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Dựng HIS_PROD mô phỏng")
    ap.add_argument("--data-dir", default="../../data")
    ap.add_argument("--out", default="../../data/sim/his_prod.db")
    ap.add_argument("--case-file", default="data_GIAAN_6_2019_2026.csv")
    ap.add_argument("--inv-file", default="data_TonKho_GiaAn_2019-2026.csv")
    ap.add_argument("--seed", type=int, default=20260801)
    args = ap.parse_args()

    rnd = random.Random(args.seed)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    if os.path.exists(args.out):
        os.remove(args.out)

    print(f"Đọc nguồn: {args.data_dir}")
    cases = pd.read_csv(f"{args.data_dir}/{args.case_file}", dtype=str)
    inv = pd.read_csv(f"{args.data_dir}/{args.inv_file}", dtype=str)
    cases["cases"] = pd.to_numeric(cases["cases"], errors="coerce").fillna(0).astype(int)
    cases["supply_quantity"] = pd.to_numeric(cases["supply_quantity"], errors="coerce").fillna(0.0)
    inv["stock_quantity"] = pd.to_numeric(inv["stock_quantity"], errors="coerce").fillna(0).astype(int)

    con = sqlite3.connect(args.out)
    con.executescript(DDL)

    # ── Danh mục vật tư ──────────────────────────────────────────────────────
    vt_rows, vt_id = [], {}
    for i, r in enumerate(inv.itertuples(index=False), start=1):
        code = str(getattr(r, "supply_code") or "").strip()
        if not code or code in vt_id:
            continue
        vt_id[code] = i
        vt_rows.append((i, code, getattr(r, "ten_hoat_chat"), getattr(r, "drug_code"),
                        getattr(r, "ten_hoat_chat"), getattr(r, "unit"),
                        getattr(r, "group_name"), getattr(r, "category"),
                        getattr(r, "description"), 1))
    con.executemany("INSERT INTO VatTu VALUES (?,?,?,?,?,?,?,?,?,?)", vt_rows)

    # vật tư chỉ xuất hiện ở bảng ca bệnh (chưa có trong danh mục tồn kho)
    extra = []
    nxt = len(vt_rows) + 1
    for code in cases["supply_code"].dropna().unique():
        code = str(code).strip()
        if code and code not in vt_id:
            vt_id[code] = nxt
            extra.append((nxt, code, None, None, None, None, None, None, None, 1))
            nxt += 1
    if extra:
        con.executemany("INSERT INTO VatTu VALUES (?,?,?,?,?,?,?,?,?,?)", extra)

    # tên/đơn vị/nhóm lấy từ chính dữ liệu ca bệnh (nguồn đầy đủ hơn)
    seen = set()
    for r in cases.itertuples(index=False):
        code = str(getattr(r, "supply_code") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        con.execute("UPDATE VatTu SET TenVatTu=COALESCE(TenVatTu,?), DonVi=COALESCE(DonVi,?),"
                    " NhomVatTu=COALESCE(NhomVatTu,?) WHERE MaVatTu=?",
                    (getattr(r, "supply_name"), getattr(r, "supply_unit"),
                     getattr(r, "supply_category"), code))

    # ── Tồn kho ──────────────────────────────────────────────────────────────
    tk = []
    for i, r in enumerate(inv.itertuples(index=False), start=1):
        code = str(getattr(r, "supply_code") or "").strip()
        if code in vt_id:
            tk.append((i, vt_id[code], int(getattr(r, "stock_quantity")), "2026-06-01"))
    con.executemany("INSERT INTO TonKho VALUES (?,?,?,?)", tk)

    # ── Bệnh nhân: một nhóm cố định cho mỗi tỉnh ─────────────────────────────
    tinhs = sorted({str(x).strip() for x in cases["region"].dropna().unique() if str(x).strip()})
    bn_rows, bn_by_tinh, bn_id = [], defaultdict(list), 1
    for tinh in tinhs:
        for _ in range(40):
            bn_rows.append((bn_id, f"{rnd.choice(HO)} Văn {rnd.choice(TEN)}",
                            f"{rnd.randrange(10**11, 10**12)}", f"Số {rnd.randint(1, 300)}, {tinh}",
                            tinh))
            bn_by_tinh[tinh].append(bn_id)
            bn_id += 1
    con.executemany("INSERT INTO BenhNhan VALUES (?,?,?,?,?)", bn_rows)

    # ── Lượt khám: bung số ca tháng thành từng lượt ──────────────────────────
    # gom vật tư theo (month, icd, region) để rải vào các lượt khám của nhóm đó
    supplies = defaultdict(list)
    for r in cases.itertuples(index=False):
        code = str(getattr(r, "supply_code") or "").strip()
        if code:
            supplies[(r.month, r.disease_code, str(r.region).strip())].append(
                (code, float(getattr(r, "supply_quantity"))))

    # Gom theo ĐÚNG khoá tự nhiên (tháng, mã ICD, tỉnh) — không gộp disease_name vào
    # khoá, nếu không một biến thể cách viết tên bệnh sẽ nhân đôi số lượt khám.
    groups = (cases.groupby(["month", "disease_code", "region"], dropna=False)
              .agg(disease_name=("disease_name", "first"), cases=("cases", "max"))
              .reset_index())

    kb_rows, cd_rows, sd_rows = [], [], []
    kb_id = cd_id = sd_id = 1
    for g in groups.itertuples(index=False):
        tinh = str(g.region).strip()
        n = int(g.cases)
        if n <= 0 or not tinh:
            continue
        mm, yyyy = str(g.month).split("/")
        ids = []
        for i in range(n):
            day = 1 + (i * 29 // max(n, 1)) % 28          # rải đều trong tháng
            ngay = f"{int(yyyy):04d}-{int(mm):02d}-{day + 1:02d}"
            pid = bn_by_tinh[tinh][i % len(bn_by_tinh[tinh])]
            kb_rows.append((kb_id, pid, ngay, "HOAN_TAT", ngay))
            cd_rows.append((cd_id, kb_id, g.disease_code, g.disease_name, 1))
            ids.append(kb_id)
            kb_id += 1
            cd_id += 1
        # Rải lượng vật tư của nhóm vào một số lượt khám (không phải ai cũng dùng
        # mọi loại thuốc), nhưng TỔNG lượng giữ nguyên để đối chiếu được.
        for code, qty in supplies.get((g.month, g.disease_code, tinh), []):
            take = ids[:min(len(ids), 8)]
            for kid, part in zip(take, split_quantity(qty, len(take))):
                if part:
                    sd_rows.append((sd_id, kid, vt_id[code], part))
                    sd_id += 1

    # thêm nhiễu thực tế: một ít lượt khám bị huỷ / đang xử lý (SQL phải lọc ra)
    noise = 0
    for i in range(0, len(kb_rows), 500):
        r = list(kb_rows[i])
        r[3] = "HUY" if i % 1000 == 0 else "DANG_XU_LY"
        kb_rows.append((kb_id, r[1], r[2], r[3], r[2]))
        cd_rows.append((cd_id, kb_id, "J01", "Viêm xoang cấp", 1))
        kb_id += 1
        cd_id += 1
        noise += 1

    con.executemany("INSERT INTO KhamBenh VALUES (?,?,?,?,?)", kb_rows)
    con.executemany("INSERT INTO ChanDoan VALUES (?,?,?,?,?)", cd_rows)
    con.executemany("INSERT INTO SuDungVatTu VALUES (?,?,?,?)", sd_rows)
    con.commit()

    print(f"Đã dựng {args.out}")
    for t in ["BenhNhan", "KhamBenh", "ChanDoan", "VatTu", "SuDungVatTu", "TonKho"]:
        print(f"  {t:14s} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>7,}")
    print(f"  (trong đó {noise} lượt khám HUY/DANG_XU_LY để kiểm tra bộ lọc TrangThai)")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
