"""Dựng HIS mô phỏng ĐÚNG HÌNH DẠNG eHospital rồi chạy logic của
usp_MedForecast_DayDuLieu để xác nhận cấu trúc join mới không làm sai số."""
import sqlite3, os, warnings, collections
warnings.filterwarnings("ignore")
import pandas as pd

DB="/tmp/work/sim/ehos_prod.db"
os.makedirs("/tmp/work/sim",exist_ok=True)
if os.path.exists(DB): os.remove(DB)
c=sqlite3.connect(DB)
c.executescript("""
CREATE TABLE TM_ICD(ICD_ID INTEGER PRIMARY KEY, MAICD TEXT, TENICD TEXT, PHANNHOM TEXT, BENHVIEN_ID INT);
CREATE TABLE LST_DICTIONARY(DICTIONARY_ID INTEGER PRIMARY KEY, DICTIONARY_TYPE_CODE TEXT, DICTIONARY_NAME TEXT);
CREATE TABLE TT_BENHNHAN(BENHNHAN_ID INTEGER PRIMARY KEY, TENBENHNHAN TEXT, CMND TEXT, DIACHI TEXT, TINHTHANH_ID INT, ACTIVE TEXT, BENHVIEN_ID INT);
CREATE TABLE TT_TIEPNHAN(TIEPNHAN_ID INTEGER PRIMARY KEY, BENHNHAN_ID INT, NGAYTIEPNHAN TEXT, TINHTHANH_ID INT, TRANGTHAI TEXT, BENHVIEN_ID INT);
CREATE TABLE TT_NGOAITRU_KHAMBENH(KHAMBENH_ID INTEGER PRIMARY KEY, BENHNHAN_ID INT, TIEPNHAN_ID INT,
    NGAYKHAM TEXT, CHANDOANICD_ID INT, BENHVIEN_ID INT);
CREATE TABLE TT_NGOAITRU_TOATHUOC(TOATHUOC_ID INTEGER PRIMARY KEY, KHAMBENH_ID INT, TIEPNHAN_ID INT,
    DUOC_ID INT, SOLUONG REAL, HUYTOATHUOC TEXT, TRANGTHAI TEXT, BENHVIEN_ID INT);
CREATE TABLE TM_DUOC(DUOC_ID INTEGER PRIMARY KEY, MADUOC TEXT, MADUOCBV TEXT, MA_BHYT TEXT,
    TENDUOCDAYDU TEXT, TENHOATCHAT TEXT, DONVITINH TEXT, NHOMDUOC_ID INT, LOAIDUOC_ID INT, TAMNGUNG TEXT, BENHVIEN_ID INT);
CREATE TABLE TM_NHOMDUOC(NHOMDUOC_ID INTEGER PRIMARY KEY, TENNHOMDUOC TEXT);
CREATE TABLE TM_LOAIDUOC(LOAIDUOC_ID INTEGER PRIMARY KEY, TENLOAIDUOC TEXT);
CREATE TABLE TT_DUOC_TONKHO(DUOCTONKHO_ID INTEGER PRIMARY KEY, KHODUOC_ID INT, DUOC_ID INT,
    SOLONHAP_ID INT, SOLUONG REAL, BENHVIEN_ID INT);
""")
BV=79428
cases=pd.read_csv("data/data_GIAAN_6_2019_2026.csv",dtype=str)
inv=pd.read_csv("data/data_TonKho_GiaAn_2019-2026.csv",dtype=str)
cases["disease_code"]=cases.disease_code.str.strip().str.upper().str[:3]   # HIS that chi co 1 ICD_ID
cases["cases"]=pd.to_numeric(cases["cases"]).fillna(0).astype(int)
cases["supply_quantity"]=pd.to_numeric(cases["supply_quantity"]).fillna(0.0)
inv["stock_quantity"]=pd.to_numeric(inv["stock_quantity"]).fillna(0).astype(int)

# TM_ICD: mỗi mã 3 ký tự tách thành 2 mã con để ép logic gom 3 ký tự phải hoạt động
icd_id={}; rows=[]; i=1
for code in sorted(cases.disease_code.unique()):
    for suf in ['.0','.9']:
        rows.append((i, code+suf, f"Ten {code}", "J00-J06" if code!="J20" else "J20-J22", BV)); icd_id.setdefault(code,[]).append(i); i+=1
c.executemany("INSERT INTO TM_ICD VALUES(?,?,?,?,?)",rows)
# tỉnh trong LST_DICTIONARY + vài dòng nhiễu loại khác
tinhs=sorted({str(x).strip() for x in cases.region.dropna().unique() if str(x).strip()})
d=[]; tinh_id={}; i=1000
for t in tinhs: d.append((i,'TinhThanh',t)); tinh_id[t]=i; i+=1
for n in ['Kinh','Tay','Nung']: d.append((i,'DanToc',n)); i+=1
c.executemany("INSERT INTO LST_DICTIONARY VALUES(?,?,?)",d)
# dược
vt_id={}; vt=[]; i=1
for r in inv.itertuples(index=False):
    code=str(r.supply_code or '').strip()
    if code and code not in vt_id:
        vt_id[code]=i; vt.append((i,code,'BV'+code,'BH'+code,r.ten_hoat_chat,r.ten_hoat_chat,r.unit,1,1,'0',BV)); i+=1
for code in cases.supply_code.dropna().unique():
    code=str(code).strip()
    if code and code not in vt_id:
        vt_id[code]=i; vt.append((i,code,'BV'+code,'BH'+code,None,None,None,1,1,'0',BV)); i+=1
c.executemany("INSERT INTO TM_DUOC VALUES(?,?,?,?,?,?,?,?,?,?,?)",vt)
c.execute("INSERT INTO TM_NHOMDUOC VALUES(1,'Nhom test')"); c.execute("INSERT INTO TM_LOAIDUOC VALUES(1,'Loai test')")
c.executemany("INSERT INTO TT_DUOC_TONKHO VALUES(?,?,?,?,?,?)",
    [(j+1,1,vt_id[str(r.supply_code).strip()],1,int(r.stock_quantity),BV)
     for j,r in enumerate(inv.itertuples(index=False)) if str(r.supply_code or '').strip() in vt_id])
# bệnh nhân + tiếp nhận + khám
bn=[]; bn_by=collections.defaultdict(list); k=1
for t in tinhs:
    for _ in range(30): bn.append((k,'Ho Ten '+str(k),'0123456789','So 1',tinh_id[t],'1',BV)); bn_by[t].append(k); k+=1
c.executemany("INSERT INTO TT_BENHNHAN VALUES(?,?,?,?,?,?,?)",bn)
sup=collections.defaultdict(list)
for r in cases.itertuples(index=False):
    code=str(r.supply_code or '').strip()
    if code: sup[(r.month,r.disease_code,str(r.region).strip())].append((code,float(r.supply_quantity)))
grp=(cases.groupby(["month","disease_code","region"],dropna=False)
       .agg(cases=("cases","max")).reset_index())
tn=[]; kb=[]; tt=[]; tid=kid=sid=1
for g in grp.itertuples(index=False):
    t=str(g.region).strip(); n=int(g.cases)
    if n<=0 or not t: continue
    mm,yyyy=str(g.month).split("/"); ids=[]
    for j in range(n):
        day=1+(j*29//max(n,1))%28
        ngay=f"{int(yyyy):04d}-{int(mm):02d}-{day+1:02d}"
        pid=bn_by[t][j%len(bn_by[t])]
        tn.append((tid,pid,ngay,tinh_id[t],'HOANTAT',BV))
        kb.append((kid,pid,tid,ngay,icd_id[g.disease_code][j%2],BV))   # luân phiên 2 mã con
        ids.append(kid); tid+=1; kid+=1
    for code,q in sup.get((g.month,g.disease_code,t),[]):
        take=ids[:min(len(ids),8)]; base=round(q/len(take),3)
        parts=[base]*len(take); parts[0]=round(q-base*(len(take)-1),3)
        for kk,p in zip(take,parts):
            if p: tt.append((sid,kk,None,vt_id[code],p,'0','DAPHAT',BV)); sid+=1
# nhiễu: toa đã huỷ (phải bị loại)
for j in range(0,len(tt),400):
    r=tt[j]; tt.append((sid,r[1],None,r[3],999.0,'1','HUY',BV)); sid+=1
c.executemany("INSERT INTO TT_TIEPNHAN VALUES(?,?,?,?,?,?)",tn)
c.executemany("INSERT INTO TT_NGOAITRU_KHAMBENH VALUES(?,?,?,?,?,?)",kb)
c.executemany("INSERT INTO TT_NGOAITRU_TOATHUOC VALUES(?,?,?,?,?,?,?,?)",tt)
c.commit()
print(f"Da dung HIS mo phong hinh dang eHospital: {len(kb):,} luot kham, {len(tt):,} dong toa thuoc, {len(vt):,} duoc")
