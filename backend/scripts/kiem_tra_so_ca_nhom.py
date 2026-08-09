# -*- coding: utf-8 -*-
"""Chung minh: cong don so ca cac ma con len NHOM la sai, va ban va da sua.

Chay:  python backend/scripts/kiem_tra_so_ca_nhom.py
Khong can DB, khong can HIS — dung du lieu dung san.
"""
import sys, pathlib, logging
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pandas as pd
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from app.data_pipeline.pipeline import DataPipeline

# --- Tinh huong: 3 luot kham trong thang 01/2024, tinh TP.HCM -----------------
#   luot 1: J01 (chinh) + J06 (phu)   <- ca hai deu thuoc J00-J06
#   luot 2: J02
#   luot 3: J06
# => so ca theo MA : J01=1, J02=1, J06=2  -> cong don = 4
# => so ca THAT cua nhom J00-J06        -> 3 luot kham
CONG_DON = pd.DataFrame([
    dict(period="2024-01", year=2024, month=1, block_code="J00-J06",
         region="TP. Ho Chi Minh", cases=4, is_covid=False, is_complete=True),
    dict(period="2024-01", year=2024, month=1, block_code="J00-J06",
         region="TOAN_QUOC", cases=4, is_covid=False, is_complete=True),
])
NGUON = pd.DataFrame([
    dict(month="01/2024", disease_group="J00-J06",
         disease_group_name="Nhiem khuan cap duong ho hap tren",
         region="TP. Ho Chi Minh", cases=3),
    dict(month="01/2024", disease_group="J00-J06",
         disease_group_name="Nhiem khuan cap duong ho hap tren",
         region="TOAN_QUOC", cases=3),
])

def so_ca(df, region):
    return int(df.loc[df["region"] == region, "cases"].iloc[0])

print("\n=== 1. Nguon KHONG cap so ca nhom (file export cu) ===")
cu = DataPipeline._ap_so_ca_nhom(CONG_DON.copy(), None)
print(f"  TOAN_QUOC = {so_ca(cu,'TOAN_QUOC')}  (that = 3)  -> {'SAI' if so_ca(cu,'TOAN_QUOC')!=3 else 'dung'}")

print("\n=== 2. Nguon CO cap so ca nhom (qua thu tuc PROD) ===")
moi = DataPipeline._ap_so_ca_nhom(CONG_DON.copy(), NGUON)
ok = True
for r in ("TP. Ho Chi Minh", "TOAN_QUOC"):
    v = so_ca(moi, r); ok &= (v == 3)
    print(f"  {r:<18} = {v}  (that = 3)  -> {'dung' if v==3 else 'SAI'}")

print("\n=== 3. Nguon cap thieu mot vung -> giu nguyen dong do, khong vo ===")
thieu = DataPipeline._ap_so_ca_nhom(CONG_DON.copy(), NGUON.iloc[[0]])
print(f"  TP.HCM    = {so_ca(thieu,'TP. Ho Chi Minh')} (lay tu nguon)")
print(f"  TOAN_QUOC = {so_ca(thieu,'TOAN_QUOC')} (giu phep cong don)")
ok &= so_ca(thieu, "TP. Ho Chi Minh") == 3 and so_ca(thieu, "TOAN_QUOC") == 4

print("\n=== 4. Kieu du lieu sau khi thay phai la int ===")
ok &= str(moi["cases"].dtype).startswith("int")
print(f"  dtype = {moi['cases'].dtype}")

print("\nKET LUAN:", "DAT" if ok else "KHONG DAT")
sys.exit(0 if ok else 1)
