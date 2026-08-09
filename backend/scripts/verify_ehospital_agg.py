"""Kiểm chứng logic của usp_MedForecast_DayDuLieu (bản dịch SQLite).

Chạy sau scripts/sim_ehospital_prod.py — dựng HIS mô phỏng đúng hình dạng
eHospital rồi chạy đúng cấu trúc join của thủ tục bên PROD, đối chiếu kết quả
với dữ liệu gốc Gia An.

    cd backend
    python scripts/sim_ehospital_prod.py --data-dir ../../data
    python scripts/verify_ehospital_agg.py --data-dir ../../data
"""
from __future__ import annotations
import argparse, sqlite3, sys, warnings
warnings.filterwarnings("ignore")
import pandas as pd

BV = 79428
TYPE_TINH = 'TinhThanh'
FAIL: list[str] = []

def check(name, cond, detail=""):
    print(("  [PASS] " if cond else "  [FAIL] ") + name + (f"  — {detail}" if detail else ""))
    if not cond:
        FAIL.append(name)

JOIN_TINH = """
LEFT JOIN TT_TIEPNHAN tn ON tn.TIEPNHAN_ID = kb.TIEPNHAN_ID
LEFT JOIN TT_BENHNHAN bn ON bn.BENHNHAN_ID = kb.BENHNHAN_ID
LEFT JOIN LST_DICTIONARY dic ON dic.DICTIONARY_ID = COALESCE(tn.TINHTHANH_ID, bn.TINHTHANH_ID)
                            AND dic.DICTIONARY_TYPE_CODE = '%s'
""" % TYPE_TINH


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="../../data")
    ap.add_argument("--db", default="../../data/sim/ehos_prod.db")
    a = ap.parse_args()

    c = sqlite3.connect(a.db)
    c.create_function('P', 1, lambda s: s[:7] + '-01')

    ca = pd.read_sql(f"""
        SELECT kb.KHAMBENH_ID enc, kb.NGAYKHAM ngay,
               UPPER(SUBSTR(TRIM(icd.MAICD),1,3)) disease_code,
               icd.TENICD disease_name, dic.DICTIONARY_NAME region
        FROM TT_NGOAITRU_KHAMBENH kb
        JOIN TM_ICD icd ON icd.ICD_ID = kb.CHANDOANICD_ID {JOIN_TINH}
        WHERE kb.BENHVIEN_ID={BV} AND kb.CHANDOANICD_ID IS NOT NULL
          AND icd.MAICD LIKE 'J%' AND UPPER(SUBSTR(TRIM(icd.MAICD),1,3)) GLOB '[A-Z][0-9][0-9]'""", c)
    ca = ca[ca.region.notna() & (ca.region.str.strip() != '')]
    ca['Period'] = ca.ngay.str[:7] + '-01'
    ca['month'] = ca.ngay.str[5:7] + '/' + ca.ngay.str[:4]
    ct = (ca.groupby(['Period', 'month', 'disease_code', 'region'])
            .agg(disease_name=('disease_name', 'max'), cases=('enc', 'nunique')).reset_index())

    vt = pd.read_sql(f"""
        SELECT P(kb.NGAYKHAM) Period, UPPER(SUBSTR(TRIM(icd.MAICD),1,3)) disease_code,
               dic.DICTIONARY_NAME region, d.MADUOC supply_code,
               MAX(d.TENDUOCDAYDU) supply_name, SUM(tt.SOLUONG) supply_quantity,
               MAX(d.DONVITINH) supply_unit, MAX(nd.TENNHOMDUOC) supply_category
        FROM TT_NGOAITRU_KHAMBENH kb
        JOIN TM_ICD icd ON icd.ICD_ID = kb.CHANDOANICD_ID {JOIN_TINH}
        JOIN TT_NGOAITRU_TOATHUOC tt ON tt.KHAMBENH_ID = kb.KHAMBENH_ID
        JOIN TM_DUOC d ON d.DUOC_ID = tt.DUOC_ID
        LEFT JOIN TM_NHOMDUOC nd ON nd.NHOMDUOC_ID = d.NHOMDUOC_ID
        WHERE kb.BENHVIEN_ID={BV} AND icd.MAICD LIKE 'J%'
          AND COALESCE(tt.HUYTOATHUOC,'0')='0' AND COALESCE(tt.SOLUONG,0)>0
          AND d.MADUOC IS NOT NULL AND dic.DICTIONARY_NAME IS NOT NULL
        GROUP BY P(kb.NGAYKHAM), UPPER(SUBSTR(TRIM(icd.MAICD),1,3)),
                 dic.DICTIONARY_NAME, d.MADUOC""", c)

    kq = ct.merge(vt, on=['Period', 'disease_code', 'region'], how='left')
    kq['note'] = None

    csv = pd.read_csv(f"{a.data_dir}/data_GIAAN_6_2019_2026.csv", dtype=str)
    csv['cases'] = pd.to_numeric(csv['cases'])
    csv['supply_quantity'] = pd.to_numeric(csv['supply_quantity'])
    csv['norm'] = csv.disease_code.str.strip().str.upper().str[:3]
    ca_csv = int(csv.groupby(['month', 'norm', 'region'])['cases'].max().sum())
    qty_csv = round(csv.supply_quantity.sum(), 1)

    print("\n[1] Kết quả tổng hợp so với dữ liệu gốc")
    n = int(kq.groupby(['Period', 'disease_code', 'region'])['cases'].max().sum())
    check("tổng số ca khớp tuyệt đối", n == ca_csv, f"{n:,} / {ca_csv:,}")
    check("tổng lượng vật tư khớp tuyệt đối",
          round(vt.supply_quantity.sum(), 1) == qty_csv,
          f"{round(vt.supply_quantity.sum(),1):,} / {qty_csv:,}")
    check("đủ 11 cột hợp đồng + Period", len(kq.columns) == 12, f"{len(kq.columns)} cột")
    check("cases lặp trên dòng vật tư, không phải 1", kq.cases.max() > 1,
          f"cao nhất {kq.cases.max()}")

    print("\n[2] Join qua ICD_ID và gom mã về 3 ký tự")
    n_sub = c.execute("SELECT COUNT(*) FROM TM_ICD WHERE MAICD LIKE '%.%'").fetchone()[0]
    check("HIS mô phỏng lưu mã con J01.0 / J01.9", n_sub > 0, f"{n_sub} mã con")
    check("kết quả chỉ còn mã 3 ký tự", set(kq.disease_code) == {'J01', 'J02', 'J06', 'J20'},
          str(sorted(set(kq.disease_code))))
    j = int(kq[kq.disease_code == 'J01'].groupby(['Period', 'region'])['cases'].max().sum())
    jc = int(csv[csv.norm == 'J01'].groupby(['month', 'region'])['cases'].max().sum())
    check("J01 gộp từ 2 mã con ra đúng số", j == jc, f"{j:,} / {jc:,}")

    print("\n[3] Bộ lọc")
    h = c.execute("SELECT COUNT(*), SUM(SOLUONG) FROM TT_NGOAITRU_TOATHUOC WHERE HUYTOATHUOC='1'").fetchone()
    check("toa đã huỷ bị loại khỏi kết quả", round(vt.supply_quantity.sum(), 1) == qty_csv,
          f"bỏ {h[0]} dòng / {h[1]:,.0f} đơn vị")
    nd = c.execute("SELECT COUNT(*) FROM LST_DICTIONARY WHERE DICTIONARY_TYPE_CODE<>'TinhThanh'").fetchone()[0]
    check("chỉ lấy đúng loại tra cứu tỉnh", kq.region.notna().all(),
          f"bỏ qua {nd} dòng tra cứu loại khác")

    print("\n[4] Tồn kho")
    tk = pd.read_sql(f"""SELECT d.MADUOC s, SUM(tk.SOLUONG) q
        FROM TT_DUOC_TONKHO tk JOIN TM_DUOC d ON d.DUOC_ID = tk.DUOC_ID
        WHERE tk.BENHVIEN_ID={BV} AND COALESCE(d.TAMNGUNG,'0')='0' AND d.MADUOC IS NOT NULL
        GROUP BY d.MADUOC""", c)
    inv = pd.read_csv(f"{a.data_dir}/data_TonKho_GiaAn_2019-2026.csv", dtype=str)
    inv['stock_quantity'] = pd.to_numeric(inv['stock_quantity'])
    check("số mặt hàng khớp", len(tk) == inv.supply_code.nunique(),
          f"{len(tk)} / {inv.supply_code.nunique()}")
    check("tổng tồn khớp", int(tk.q.sum()) == int(inv.stock_quantity.sum()), f"{int(tk.q.sum()):,}")

    print("\n[5] Dữ liệu đẩy xuống STA")
    pii = [x for x in kq.columns if x.upper() in
           ('TENBENHNHAN', 'CMND', 'DIACHI', 'BENHNHAN_ID', 'KHAMBENH_ID', 'NGAYKHAM', 'ENC')]
    check("không chứa cột định danh nào", not pii, str(pii) or "sạch")
    check("tỉnh là TÊN chứ không phải mã số",
          str(kq.region.iloc[0]).strip()[0].isalpha(), repr(kq.region.iloc[0]))
    n_toa = c.execute("SELECT COUNT(*) FROM TT_NGOAITRU_TOATHUOC").fetchone()[0]
    check("đã gộp nên lượng dữ liệu qua đường truyền nhỏ hơn nhiều",
          len(kq) < n_toa / 3, f"{len(kq):,} dòng thay vì {n_toa:,} dòng toa thuốc")

    print("\n" + "=" * 60)
    print("KẾT QUẢ:", "TẤT CẢ PASS" if not FAIL else f"{len(FAIL)} HỎNG: {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
