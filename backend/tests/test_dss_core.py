# -*- coding: utf-8 -*-
"""Kiểm thử lõi DSS ba tầng trên SQLite trong bộ nhớ.

Bao phủ: FEFO + nhãn bốn màu (dss_alerts), kết hợp Bates–Granger (combine),
quy đổi định mức (dss_demand), bốn view loại kỳ dở dang (views), xoá-rồi-chèn
có rollback (dss_loader), đồng bộ danh mục vật tư (sync_service), và KPI
báo cáo neo vào kỳ đã chốt (reports).
Không cần dữ liệu HIS; mọi bảng được dựng tại chỗ.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.data_pipeline import dss_loader, views
from app.forecasting.combine import AdaptiveCombiner
from app.services import dss_alerts, dss_demand, sync_service


THANG_NAY = date.today().strftime("%Y-%m")


def _ky(luui: int) -> str:
    """Kỳ 'YYYY-MM' lùi `luui` tháng so với tháng hiện tại."""
    y, m = date.today().year, date.today().month
    t = y * 12 + (m - 1) - luui
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    with engine.begin() as c:
        c.execute(text("CREATE TABLE system_config (id INTEGER PRIMARY KEY, config_key TEXT, "
                       "config_value TEXT, description TEXT, updated_by INTEGER)"))
        c.execute(text("CREATE TABLE medical_supplies (id INTEGER PRIMARY KEY, supply_code TEXT, "
                       "ten_hoat_chat TEXT, unit TEXT, group_name TEXT, category TEXT)"))
        c.execute(text("CREATE TABLE inventory (id INTEGER PRIMARY KEY, supply_id INTEGER, "
                       "current_stock INTEGER, safety_stock INTEGER, expiry_date TEXT)"))
    Session = sessionmaker(bind=engine)
    s = Session()
    dss_loader.ensure_tables(s)
    views.dam_bao_cau_hinh(engine)
    yield s, engine
    s.close()
    engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# Tầng 3 — FEFO và nhãn
# ─────────────────────────────────────────────────────────────────────────────

def test_fefo_lo_het_han_khong_huu_dung():
    hom = date(2026, 9, 13)
    lots = [(100.0, hom + timedelta(days=10)),     # kịp dùng 10 ngày × 5 = 50
            (100.0, hom + timedelta(days=200))]    # hữu dụng toàn bộ
    st = dss_alerts.usable_stock_fefo(lots, d_daily=5.0, hom_nay=hom, fefo_window_days=30)
    assert st["fefo_ap_dung"] is True
    assert st["s_usable"] == pytest.approx(150.0)
    assert st["s_expiring"] == pytest.approx(50.0)
    assert st["s_total"] == pytest.approx(200.0)


def test_fefo_da_het_han_bo_hoan_toan():
    hom = date(2026, 9, 13)
    st = dss_alerts.usable_stock_fefo([(40.0, hom - timedelta(days=1)), (10.0, None)],
                                      d_daily=1.0, hom_nay=hom)
    assert st["s_usable"] == pytest.approx(10.0)
    assert st["s_expiring"] == pytest.approx(40.0)


def test_fefo_khong_han_dung_fallback_ton_so_sach():
    st = dss_alerts.usable_stock_fefo([(30.0, None), (20.0, None)], d_daily=2.0)
    assert st["fefo_ap_dung"] is False
    assert st["s_usable"] == 50.0


def test_fefo_d_daily_bang_0_khong_chia():
    st = dss_alerts.usable_stock_fefo([(30.0, date(2030, 1, 1))], d_daily=0.0)
    assert st["fefo_ap_dung"] is False and st["s_usable"] == 30.0


@pytest.mark.parametrize("doi,muc", [(None, "grey"), (0.0, "red"), (18.0, "red"),
                                     (18.1, "amber"), (36.0, "amber"), (36.1, "green")])
def test_classify_bon_mau(doi, muc):
    assert dss_alerts.classify(doi, 18, 36) == muc


def test_alert_rows_tren_db_rong_khong_no(db):
    s, _ = db
    out = dss_alerts.alert_rows(s)
    # chưa có view → báo rõ, không ném ngoại lệ
    assert out["san_sang"] in (True, False)


def test_alert_rows_gan_nhan_dung(db):
    s, engine = db
    # 3 kỳ đã chốt, 1 kỳ dở dang bị loại khỏi mẫu số
    rows = []
    for i in (1, 2, 3):
        rows.append((_ky(i), "A", 0, 300.0, 100.0, 200.0))     # d_daily = 10/ngày
        rows.append((_ky(i), "B", 0, 300.0, 300.0, 0.0))
    rows.append((THANG_NAY, "A", 0, 5.0, 1.0, 4.0))            # kỳ dở
    s.execute(text("INSERT INTO fact_usage_total (period, supply_code, is_vtyt, "
                   "so_luong_toan_vien, so_luong_hohap, d_baseline_thang) VALUES (:p,:c,:v,:t,:h,:b)"),
              [dict(p=p, c=c, v=v, t=t, h=h, b=b) for p, c, v, t, h, b in rows])
    s.execute(text("INSERT INTO medical_supplies VALUES (1,'A','Thuốc A','viên','G','Khác'),"
                   "(2,'B','Thuốc B','viên','G','Khác'),(3,'C','Thuốc C','viên','G','Khác')"))
    hom = date.today().isoformat()
    s.execute(text("INSERT INTO fact_inventory_lot (snapshot_date, supply_code, lot_id, expiry_date, "
                   "co_han_dung, quantity, so_kho) VALUES "
                   "(:h,'A',1,'2030-01-01',1,100,'K1'), (:h,'B',1,'2030-01-01',1,1000,'K1')"), {"h": hom})
    s.commit()
    views.tao_views(engine)

    d = {r.supply_code: r for r in s.execute(text("SELECT * FROM v_supply_daily_demand"))}
    assert d["A"].so_ky == 3 and d["A"].d_daily == pytest.approx(10.0, rel=1e-3)

    out = dss_alerts.alert_rows(s, demand={"A": 600.0})
    theo_ma = {r["supply_code"]: r for r in out["rows"]}
    assert theo_ma["A"]["doi"] == pytest.approx(10.0) and theo_ma["A"]["muc"] == "red"
    assert theo_ma["A"]["delta_need"] == pytest.approx(500.0)
    assert theo_ma["B"]["doi"] == pytest.approx(100.0) and theo_ma["B"]["muc"] == "green"
    assert out["tong_hop"]["red"] == 1 and out["tong_hop"]["green"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Bốn view — loại kỳ dở dang, chỉ thuốc
# ─────────────────────────────────────────────────────────────────────────────

def test_views_loai_ky_do_va_vtyt(db):
    s, engine = db
    s.execute(text("INSERT INTO fact_usage_total (period, supply_code, is_vtyt, so_luong_toan_vien, "
                   "so_luong_hohap, d_baseline_thang) VALUES "
                   "(:k1,'A',0,300,100,200), (:k2,'A',0,300,100,200), (:k3,'A',0,300,100,200), "
                   "(:now,'A',0,3,1,2), (:k1,'V',1,999,999,0)"),
              {"k1": _ky(1), "k2": _ky(2), "k3": _ky(3), "now": THANG_NAY})
    s.execute(text("INSERT INTO fact_cases_by_care_level VALUES (:k1,'J00-J06','NGT',100), "
                   "(:now,'J00-J06','NGT',2)"), {"k1": _ky(1), "now": THANG_NAY})
    s.commit()
    kq = views.tao_views(engine)
    assert all(v == "đã tạo" for v in kq.values()), kq

    assert [r[0] for r in s.execute(text("SELECT supply_code FROM v_supply_active"))] == ["A"]
    focus = s.execute(text("SELECT supply_code, so_ky FROM v_supply_focus")).fetchall()
    assert focus == [("A", 3)]                       # kỳ dở không đếm, VTYT không vào
    share = s.execute(text("SELECT cases, so_ky FROM v_care_level_share")).fetchall()
    assert share == [(100, 1)]


def test_focus_loai_ma_da_ngung_dung(db):
    """Mã tỷ trọng hô hấp cao nhưng ngừng xuất 3 kỳ gần nhất không vào tập trọng tâm."""
    s, engine = db
    rows = []
    for i in (1, 2, 3):                      # A: còn dùng
        rows.append((_ky(i), "A", 0, 300.0, 100.0, 200.0))
    for i in (4, 5, 6):                      # B: hô hấp 100% nhưng đã ngừng
        rows.append((_ky(i), "B", 0, 300.0, 300.0, 0.0))
    s.execute(text("INSERT INTO fact_usage_total (period, supply_code, is_vtyt, "
                   "so_luong_toan_vien, so_luong_hohap, d_baseline_thang) VALUES (:p,:c,:v,:t,:h,:b)"),
              [dict(p=p, c=c, v=v, t=t, h=h, b=b) for p, c, v, t, h, b in rows])
    s.commit()
    views.tao_views(engine)

    assert [r[0] for r in s.execute(text("SELECT supply_code FROM v_supply_active"))] == ["A"]
    # B đủ tỷ trọng (100 %) và đủ 3 kỳ trong cửa sổ 12, nhưng không còn hoạt động
    assert [r[0] for r in s.execute(text("SELECT supply_code FROM v_supply_focus"))] == ["A"]


# ─────────────────────────────────────────────────────────────────────────────
# Tầng 2 — định mức và quy đổi
# ─────────────────────────────────────────────────────────────────────────────

def test_demand_by_supply_cong_thuc(db):
    s, engine = db
    k = _ky(1)
    s.execute(text("INSERT INTO fact_cases_by_care_level VALUES (:k,'J00-J06','NGT',100), "
                   "(:k,'J00-J06','NT1',50)"), {"k": k})
    s.execute(text("INSERT INTO fact_usage_by_care_level (period, block_code, ro, supply_code, "
                   "is_vtyt, quantity) VALUES (:k,'J00-J06','NGT','A',0,200), (:k,'J00-J06','NT1','A',0,150)"),
              {"k": k})
    s.commit()
    views.tao_views(engine)

    emp = dss_demand.empirical_norms(s)
    assert emp["periods"] == [k]
    assert emp["norms"]["J00-J06"]["NGT"]["A"] == pytest.approx(2.0)   # 200/100
    assert emp["norms"]["J00-J06"]["NT1"]["A"] == pytest.approx(3.0)   # 150/50

    p = dss_demand.care_level_shares(s)["J00-J06"]
    assert p["NGT"] == pytest.approx(100 / 150) and p["NT1"] == pytest.approx(50 / 150)

    dm = dss_demand.demand_by_supply(s, {"J00-J06": 150.0}, horizon_days=30, include_baseline=False)
    a = {r["supply_code"]: r for r in dm["rows"]}["A"]
    # 150 × (2/3 × 2 + 1/3 × 3) = 150 × 2,3333 = 350
    assert a["d_forecast"] == pytest.approx(350.0, rel=1e-3)
    assert a["ty_le_do_hohap_pct"] == 100.0


def test_demand_khong_chia_0_khi_ca_bang_0(db):
    s, engine = db
    s.execute(text("INSERT INTO fact_cases_by_care_level VALUES (:k,'J09-J18','NGT',0)"), {"k": _ky(1)})
    s.commit()
    views.tao_views(engine)
    emp = dss_demand.empirical_norms(s)
    assert emp["gop"].get("J09-J18") == {}
    dm = dss_demand.demand_by_supply(s, {"J09-J18": 100.0}, include_baseline=False)
    assert dm["so_ma"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Đồng bộ danh mục vật tư từ mart
# ─────────────────────────────────────────────────────────────────────────────

class _Gia:
    """Đối tượng giả cho một dòng MartInventory / MedicalSupply."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_dong_bo_cap_nhat_category():
    """Phân loại tính lại bên PROD phải tới được mã ĐÃ TỒN TẠI.

    13/09/2026: nhánh cập nhật thiếu `category` nên sau khi sửa #DrugMeta trên
    PROD và đồng bộ, 3.001 mã vẫn giữ nhãn 'Dịch truyền' cũ.
    """
    s = _Gia(drug_code="D1", ten_hoat_chat="Paracetamol", unit="Viên",
             group_name="2. GIẢM ĐAU", category="Dịch truyền")
    t = _Gia(drug_code="D1", name="Paracetamol", unit="Viên",
             group_name="2. GIẢM ĐAU", category="Thuốc hạ sốt giảm đau")
    assert sync_service.cap_nhat_thuoc_tinh_vat_tu(s, t) == ["category"]
    assert s.category == "Thuốc hạ sốt giảm đau"


def test_dong_bo_khong_ghi_de_bang_gia_tri_rong():
    """'nan'/rỗng bên nguồn không được xoá giá trị đang có."""
    s = _Gia(drug_code="D1", ten_hoat_chat="Paracetamol", unit="Viên",
             group_name="2. GIẢM ĐAU", category="Thuốc hạ sốt giảm đau")
    t = _Gia(drug_code="nan", name=None, unit="", group_name="NaT", category="none")
    assert sync_service.cap_nhat_thuoc_tinh_vat_tu(s, t) == []
    assert s.category == "Thuốc hạ sốt giảm đau" and s.drug_code == "D1"


def test_dong_bo_khong_doi_thi_khong_ghi():
    s = _Gia(drug_code="D1", ten_hoat_chat="A", unit="Viên", group_name="G", category="Khác")
    t = _Gia(drug_code="D1", name="A", unit="Viên", group_name="G", category="Khác")
    assert sync_service.cap_nhat_thuoc_tinh_vat_tu(s, t) == []


# ─────────────────────────────────────────────────────────────────────────────
# Tầng 1 — kết hợp thích ứng
# ─────────────────────────────────────────────────────────────────────────────

def test_combiner_trong_so_nghich_dao_mae():
    c = AdaptiveCombiner("inv_mae", window=12, power=1, min_hist=2)
    for a in (100.0, 100.0):
        mp = {"tot": a + 1, "te": a + 10}
        _, raw, _, _ = c.combine(mp)
        c.update(mp, a, raw)
    w = c.weights(["tot", "te"])
    assert w["tot"] > w["te"] and abs(sum(w.values()) - 1) < 1e-9


def test_combiner_thanh_vien_chua_du_lich_su_lay_trung_binh():
    c = AdaptiveCombiner("inv_mae", min_hist=2)
    for a in (10.0, 10.0):
        mp = {"x": 11.0, "y": 15.0}
        _, raw, _, _ = c.combine(mp)
        c.update(mp, a, raw)
    w = c.weights(["x", "y", "moi"])
    raw = {"x": 1.0, "y": 1 / 5}
    fill = sum(raw.values()) / 2
    tong = sum(raw.values()) + fill
    assert w["moi"] == pytest.approx(fill / tong)


def test_combiner_khong_lich_su_la_trung_binh_deu():
    c = AdaptiveCombiner("inv_mae")
    final, raw, w, b = c.combine({"a": 10.0, "b": 20.0})
    assert final == 15.0 and w == {"a": 0.5, "b": 0.5} and b == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Nạp dữ liệu — xoá-rồi-chèn
# ─────────────────────────────────────────────────────────────────────────────

def test_replace_periods_idempotent_va_giu_ky_khac(db):
    s, _ = db
    cols = ["period", "block_code", "ro", "cases"]
    df1 = pd.DataFrame([("2026-07", "J00-J06", "NGT", 5), ("2026-08", "J00-J06", "NGT", 7)], columns=cols)
    dss_loader._replace_periods(s, "fact_cases_by_care_level", df1, cols)
    s.commit()
    df2 = pd.DataFrame([("2026-08", "J00-J06", "NGT", 9)], columns=cols)
    dss_loader._replace_periods(s, "fact_cases_by_care_level", df2, cols)
    dss_loader._replace_periods(s, "fact_cases_by_care_level", df2, cols)
    s.commit()
    rows = s.execute(text("SELECT period, cases FROM fact_cases_by_care_level ORDER BY period")).fetchall()
    assert rows == [("2026-07", 5), ("2026-08", 9)]


def test_load_flow_rollback_khi_insert_vo(db, monkeypatch):
    s, _ = db
    cols = ["period", "block_code", "ro", "cases"]
    dss_loader._replace_periods(s, "fact_cases_by_care_level", pd.DataFrame(
        [("2026-08", "J00-J06", "NGT", 7)], columns=cols), cols)
    s.commit()

    class _Conn:
        def _read(self, sql, params):
            # cases = None vi phạm NOT NULL → INSERT vỡ sau khi DELETE đã chạy
            return pd.DataFrame([{"period": "2026-08-01", "disease_group": "J00-J06",
                                  "ro": "NGT", "cases": None}])

    monkeypatch.setattr(dss_loader, "_load_sql", lambda f: "select 1")
    monkeypatch.setattr(dss_loader, "_prepare", lambda df, spec: pd.DataFrame(
        [{"period": "2026-08", "block_code": "J00-J06", "ro": "NGT", "cases": None}]))
    with pytest.raises(Exception):
        dss_loader.load_flow(s, _Conn(), "cases_care_level", full=True)
    rows = s.execute(text("SELECT period, cases FROM fact_cases_by_care_level")).fetchall()
    assert rows == [("2026-08", 7)]                 # dữ liệu cũ còn nguyên


def test_prepare_don_ro_la_va_gop_trung_khoa():
    spec = dss_loader.FLOWS["cases_care_level"]
    raw = pd.DataFrame([
        {"Period": "2026-08-01", "disease_group": "J00-J06", "ro": "NGT", "cases": 3},
        {"Period": "2026-08-01", "disease_group": "J00-J06", "ro": "NGT", "cases": 4},
        {"Period": "2026-08-01", "disease_group": "J00-J06", "ro": "XYZ", "cases": 1},
    ])
    out = dss_loader._prepare(raw, spec)
    assert set(out["ro"]) == {"NGT", "NT0"}
    assert int(out.loc[out["ro"] == "NGT", "cases"].iloc[0]) == 7


# ─────────────────────────────────────────────────────────────────────────────
# Khoá hai lỗi sửa ngày 18/09/2026
# ─────────────────────────────────────────────────────────────────────────────

def test_d_daily_chia_so_ky_cua_so_khong_phai_so_ky_co_dong(db):
    """d_daily lấy mẫu số là SỐ KỲ CỦA CỬA SỔ, giống nhau cho mọi mã.

    Trước 18/09 mẫu số là COUNT(*) — số kỳ mà RIÊNG mã đó có xuất — nên mã chỉ
    xuất 1 trong 3 kỳ có d_daily ngang mã xuất đều cả 3 kỳ, và tồn ít của nó
    thành Đỏ giả. Đo 14/09 trên toàn danh mục: 284 mã Đỏ có 8 mã chỉ 1 kỳ,
    19 mã 2 kỳ, 10 mã 3 kỳ.
    """
    s, engine = db
    rows = [(_ky(i), "DEU", 0, 300.0, 100.0, 200.0) for i in (1, 2, 3)]
    rows.append((_ky(2), "LE", 0, 300.0, 100.0, 200.0))       # chỉ 1 kỳ trong 3
    s.execute(text("INSERT INTO fact_usage_total (period, supply_code, is_vtyt, "
                   "so_luong_toan_vien, so_luong_hohap, d_baseline_thang) "
                   "VALUES (:p,:c,:v,:t,:h,:b)"),
              [dict(p=p, c=c, v=v, t=t, h=h, b=b) for p, c, v, t, h, b in rows])
    s.commit()
    views.tao_views(engine)

    d = {r[0]: (r[1], r[2]) for r in s.execute(text(
        "SELECT supply_code, d_daily, so_ky FROM v_supply_daily_demand"))}
    assert d["DEU"][0] == pytest.approx(900 / 3 / 30.0)       # 3 kỳ, tổng 900
    assert d["LE"][0] == pytest.approx(300 / 3 / 30.0)        # 1 kỳ có dòng, vẫn chia 3
    assert d["LE"][0] * 3 == pytest.approx(d["DEU"][0])       # KHÔNG bằng nhau
    assert d["DEU"][1] == 3 and d["LE"][1] == 1               # cột so_ky giữ nghĩa cũ


def test_co_ngot_p_mu_chi_ap_trong_khoi_noi_tru(db):
    """Co ngót tỷ trọng rổ mẫu nhỏ KHÔNG được đụng tới tỷ trọng ngoại trú.

    Trước 18/09 phép co ngót co về phân bố đều trên MỌI rổ kể cả NGT, kéo tỷ
    trọng nội trú lên 3–4 lần (J00-J06: NGT 79,6% → 73,1%) và phồng nhu cầu
    thuốc nội trú, vốn có định mức trên một lượt cao hơn hẳn ngoại trú.
    """
    s, engine = db
    k = _ky(1)
    s.execute(text("INSERT INTO fact_cases_by_care_level VALUES "
                   "(:k,'J00-J06','NGT',1000), (:k,'J00-J06','NT1',5), (:k,'J00-J06','NT2',15)"),
              {"k": k})
    s.commit()
    views.tao_views(engine)

    p = dss_demand.care_level_shares(s)["J00-J06"]
    assert p["NGT"] == pytest.approx(1000 / 1020)             # ngoại trú GIỮ NGUYÊN tỷ trọng thô
    assert p["NT1"] + p["NT2"] == pytest.approx(20 / 1020)    # khối nội trú giữ nguyên khối lượng
    assert sum(p.values()) == pytest.approx(1.0)
    # trong khối nội trú, rổ mẫu nhỏ hơn được kéo về phía phân bố đều
    assert 0.25 < p["NT1"] / (p["NT1"] + p["NT2"]) < 0.5
