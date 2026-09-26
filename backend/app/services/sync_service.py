"""Đồng bộ dữ liệu từ MEDFORECAST_DW (STA) vào SQLite của ứng dụng: fact/mart, bốn luồng DSS,
bảng nghiệp vụ; và trạng thái lần đồng bộ gần nhất.
"""
from __future__ import annotations
import logging
import os
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data_pipeline.icd_hierarchy import IcdHierarchy
from app.data_pipeline.connectors import SqlServerConnector
from app.data_pipeline import dss_loader
from app.data_pipeline.pipeline import DataPipeline
from app.services import sync_config_service


def lam_sach(v, mac_dinh: str = "") -> str:
    """Chuẩn hoá chuỗi từ mart; rỗng/'nan'/'none'/'nat'/'null' coi là thiếu và trả `mac_dinh`."""
    t = str(v).strip() if v is not None else ""
    return mac_dinh if t.lower() in ("", "nan", "none", "nat", "null") else t


# Thuộc tính danh mục đồng bộ mart → medical_supplies: (cột đích, cột nguồn).
# `category` phải có, nếu không mã đã tồn tại giữ mãi nhãn cũ.
COT_DONG_BO = (
    ("drug_code", "drug_code"),
    ("ten_hoat_chat", "name"),
    ("unit", "unit"),
    ("group_name", "group_name"),
    ("category", "category"),
)


def cap_nhat_thuoc_tinh_vat_tu(supply, dong_mart) -> list:
    """Chép thuộc tính danh mục từ dòng mart sang MedicalSupply đã có; trả danh sách cột đã đổi.
    Giá trị rỗng bên nguồn không ghi đè giá trị đang có.
    """
    da_doi = []
    for cot_dich, cot_nguon in COT_DONG_BO:
        cu = getattr(supply, cot_dich, None)
        moi = lam_sach(getattr(dong_mart, cot_nguon, None), cu or "")
        if moi != cu:
            setattr(supply, cot_dich, moi)
            da_doi.append(cot_dich)
    return da_doi

logger = logging.getLogger(__name__)


def _ban_ghi_json(df) -> list:
    """DataFrame → list[dict] tuần tự hoá JSON được: numpy scalar về kiểu Python, NaN về None."""
    if df is None or getattr(df, "empty", True):
        return []
    out = []
    for rec in df.to_dict("records"):
        d = {}
        for k, v in rec.items():
            if v is None:
                d[k] = None
            elif hasattr(v, "item"):                      # numpy scalar
                v = v.item()
                if isinstance(v, float):
                    v = None if v != v else (int(v) if v.is_integer() else v)
                d[k] = v
            elif isinstance(v, float):
                d[k] = None if v != v else (int(v) if v.is_integer() else v)
            else:
                d[k] = v
        out.append(d)
    return out


def _ngan_gon(exc: Exception) -> str:
    """Rút thông điệp pyodbc về phần sau '[SQL Server]'."""
    m = str(exc)
    if "[SQL Server]" in m:
        m = m.split("[SQL Server]")[-1]
    return m.strip().rstrip("')\"").strip()[:160]


def _build_pipeline(db: Optional[Session] = None) -> DataPipeline:
    icd_dir = os.environ.get("PIPELINE_ICD_DIR", "../data")
    hier = IcdHierarchy.from_dir_optional(icd_dir)

    # Cấu hình lưu trong DB ưu tiên hơn .env.
    connector = None
    if db is not None:
        try:
            connector = sync_config_service.build_connector(db)
        except RuntimeError:
            raise                    # cấu hình có nhưng thiếu trường
        except Exception as exc:     # bảng chưa tạo: dùng .env
            logger.warning("Không đọc được cấu hình kết nối trong DB (%s) — "
                           "dùng biến môi trường.", exc)
    if connector is not None:
        logger.info("Đồng bộ theo cấu hình kết nối lưu trong DB.")
        return DataPipeline(connector, hier)

    conn = os.environ.get("PIPELINE_SQLSERVER_CONN", "").strip()
    if not conn:
        raise RuntimeError(
            "Chưa cấu hình CSDL nghiên cứu MEDFORECAST_DW: vào Quản trị → "
            "Nguồn dữ liệu (CSDL DW), bấm Kiểm tra kết nối rồi Lưu; hoặc đặt "
            "PIPELINE_SQLSERVER_CONN trong backend/.env.")
    # Chuỗi ODBC thuần được bọc qua odbc_connect.
    if "://" not in conn:
        from urllib.parse import quote_plus
        conn = "mssql+pyodbc:///?odbc_connect=" + quote_plus(conn)
    connector = SqlServerConnector(conn)
    return DataPipeline(connector, hier)


class SyncService:
    def __init__(self, db: Session):
        self.db = db

    def run_sync(self, full: bool = False) -> dict:
        """Một lần đồng bộ: pipeline fact/mart, bốn luồng DSS, bảng nghiệp vụ; phần lỗi không chặn phần khác."""
        pipeline = _build_pipeline(self.db)
        result = pipeline.run(incremental=not full)
        result["mode"] = "full" if full else "incremental"

        try:
            dss = dss_loader.load_all(self.db, pipeline.connector, full=full)
            result["dss_flows"] = dss["flows"]
            result["dss_ok"] = dss["ok"]
            result["dss_failed"] = dss["failed"]
            if dss["failed"]:
                logger.warning("Đồng bộ DSS: %d/%d luồng lỗi — %s", dss["failed"],
                               len(dss["flows"]),
                               "; ".join(f"{f['flow']}: {f.get('message','')[:80]}"
                                         for f in dss["flows"] if f["status"] == "failed"))
        except Exception as exc:                          # noqa: BLE001
            self.db.rollback()
            logger.exception("Nạp luồng DSS thất bại")
            result["dss_error"] = str(exc)[:300]

        try:
            result.update(self._lam_moi_bang_nghiep_vu())
        except Exception as exc:                          # noqa: BLE001
            self.db.rollback()
            logger.exception("Làm mới bảng nghiệp vụ thất bại")
            result["legacy_refresh_error"] = str(exc)[:300]

        result["sta"] = self.trang_thai_sta(pipeline.connector)

        try:
            from app.services import dss_dashboard
            result["forecast_runs_verified"] = dss_dashboard.fill_actuals(self.db)
        except Exception as exc:                          # noqa: BLE001
            logger.warning("fill_actuals sau đồng bộ lỗi: %s", exc)

        # View Tầng 2/3 phụ thuộc bảng fact do đợt đồng bộ này tạo, nên tạo lại ở đây.
        try:
            from app.data_pipeline.views import tao_views
            kq_view = tao_views()
            result["views"] = {k: v for k, v in kq_view.items() if v != "đã tạo"} or "đủ 4 view"
        except Exception as exc:                          # noqa: BLE001
            logger.warning("Tạo view sau đồng bộ lỗi: %s", exc)
        return result

    # ── Mốc chốt dữ liệu nguồn ──
    @staticmethod
    def trang_thai_sta(connector) -> dict:
        """Đọc MF_Watermark và MF_SyncLog trên MEDFORECAST_DW để phát hiện job PROD lỗi.
        Trả {"available", "watermarks", "last_pushes", "warning"}; connector không phải SQL Server thì available=False.
        """
        out = {"available": False, "watermarks": [], "last_pushes": [], "warning": None}
        if not isinstance(connector, SqlServerConnector):
            return out
        loi = []
        wm = lg = None
        try:
            wm = connector._read(                          # noqa: SLF001
                "SELECT TenLuong, CONVERT(varchar(10), MocDaDay, 120) AS MocDaDay, "
                "       CONVERT(varchar(19), LanChayCuoi, 120) AS LanChayCuoi "
                "FROM dbo.MF_Watermark ORDER BY TenLuong", {})
        except Exception as exc:                          # noqa: BLE001
            loi.append(f"MF_Watermark: {_ngan_gon(exc)}")
        try:
            lg = connector._read(                          # noqa: SLF001
                "SELECT TOP 8 CONVERT(varchar(19), BatDau, 120) AS BatDau, "
                "       CONVERT(varchar(19), KetThuc, 120) AS KetThuc, "
                "       TrangThai, SoDongCaBenh, TongSoCa, LEFT(ThongDiep, 400) AS ThongDiep "
                "FROM dbo.MF_SyncLog ORDER BY Id DESC", {})
        except Exception as exc:                          # noqa: BLE001
            loi.append(f"MF_SyncLog: {_ngan_gon(exc)}")

        out["available"] = wm is not None or lg is not None
        out["watermarks"] = _ban_ghi_json(wm)
        out["last_pushes"] = _ban_ghi_json(lg)
        # Ưu tiên lỗi của job hơn lỗi quyền đọc.
        failed = [r for r in out["last_pushes"] if str(r.get("TrangThai", "")).lower() == "failed"]
        if out["last_pushes"] and str(out["last_pushes"][0].get("TrangThai", "")).lower() != "ok":
            out["warning"] = ("Lần cập nhật kho trung gian gần nhất KHÔNG thành công: "
                              + str(out["last_pushes"][0].get("ThongDiep", ""))[:200])
        elif failed:
            out["warning"] = f"{len(failed)}/{len(out['last_pushes'])} lần cập nhật gần đây thất bại — xem nhật ký."
        elif loi:
            out["warning"] = ("Không đọc được MF_Watermark/MF_SyncLog trong MEDFORECAST_DW ("
                              + "; ".join(loi) + ").")
        return out

    def _lam_moi_bang_nghiep_vu(self) -> dict:
        """Đổ fact/mart sang bảng nghiệp vụ: disease_cases xoá rồi chèn, medical_supplies/inventory upsert
        theo supply_code và giữ safety_stock đã nhập tay.
        """
        from datetime import date, datetime

        from app.data_pipeline import models as pm
        from app.data_pipeline.db import SessionLocal as PipeSession
        from app.models.disease_case import DiseaseCase
        from app.models.inventory import Inventory
        from app.models.medical_supply import MedicalSupply

        pdb = PipeSession()
        try:
            facts = pdb.query(
                pm.FactDiseaseCase.year, pm.FactDiseaseCase.month,
                pm.FactDiseaseCase.icd_code, pm.FactDiseaseCase.block_code,
                pm.FactDiseaseCase.region, pm.FactDiseaseCase.cases).all()
            ten_icd = {r.icd_code: (r.icd_name or r.icd_code)
                       for r in pdb.query(pm.DimIcd).all()}
            ton_kho = pdb.query(pm.MartInventory).all()
        finally:
            pdb.close()

        # create_all không thêm cột vào bảng đã có; bổ sung disease_group nếu thiếu.
        from sqlalchemy import inspect as sa_inspect
        cot = {c["name"] for c in
               sa_inspect(self.db.connection()).get_columns("disease_cases")}
        if "disease_group" not in cot:
            self.db.execute(text(
                "ALTER TABLE disease_cases ADD COLUMN disease_group VARCHAR(20)"))
            logger.info("Đã thêm cột disease_group vào disease_cases.")

        # disease_cases: mỗi dòng = (tháng × mã × tỉnh).
        self.db.query(DiseaseCase).delete()
        self.db.bulk_save_objects([
            DiseaseCase(
                recorded_at=datetime(r.year, r.month, 1),
                recorded_date=date(r.year, r.month, 1),
                icd_code=r.icd_code,
                disease_name=ten_icd.get(r.icd_code, r.icd_code),
                disease_group=r.block_code,
                disease_type="respiratory",
                case_count=int(r.cases or 0),
                location=r.region,
                data_source="MEDFORECAST_DW",
            ) for r in facts
        ])

        _sach = lam_sach

        co_san = {s.supply_code: s for s in self.db.query(MedicalSupply).all()}
        inv_theo_id = {i.supply_id: i for i in self.db.query(Inventory).all()}
        them_vt = sua_vt = 0
        for t in ton_kho:
            s = co_san.get(t.supply_code)
            if s is None:
                s = MedicalSupply(
                    supply_code=t.supply_code,
                    drug_code=_sach(t.drug_code),
                    ten_hoat_chat=_sach(t.name, t.supply_code),
                    unit=_sach(t.unit),
                    group_name=_sach(t.group_name),
                    category=_sach(t.category, "medicine"),
                    description=t.name,
                )
                self.db.add(s)
                self.db.flush()          # lấy s.id cho inventory
                co_san[t.supply_code] = s
                them_vt += 1
            else:
                if cap_nhat_thuoc_tinh_vat_tu(s, t):
                    sua_vt += 1

            inv = inv_theo_id.get(s.id)
            if inv is None:
                self.db.add(Inventory(supply_id=s.id,
                                      current_stock=int(t.stock_quantity or 0),
                                      safety_stock=0))
            else:
                inv.current_stock = int(t.stock_quantity or 0)

        self.db.commit()
        return {"legacy_disease_rows": len(facts),
                "legacy_supplies_new": them_vt,
                "legacy_supplies_updated": sua_vt,
                "legacy_inventory_updated": len(ton_kho)}

    def get_status(self) -> dict:
        """Trạng thái đồng bộ và số liệu hiện có; an toàn khi bảng chưa tồn tại."""
        out = {"last_sync": None, "disease_cases": 0, "inventory_items": 0,
               "latest_period": None, "history": []}

        def q1(sql):
            try:
                return self.db.execute(text(sql)).fetchone()
            except Exception:
                return None

        row = q1("SELECT source, last_period, rows_ingested, rows_rejected, status, "
                 "run_at FROM sync_state WHERE status='ok' ORDER BY id DESC LIMIT 1")
        if row:
            out["last_sync"] = {"source": row[0], "last_period": row[1],
                                "rows_ingested": row[2], "rows_rejected": row[3],
                                "status": row[4], "run_at": str(row[5])}
        c = q1("SELECT COUNT(*), COALESCE(SUM(cases),0), MAX(period) FROM fact_disease_case")
        if c:
            out["disease_cases"] = int(c[1] or 0)
            out["latest_period"] = c[2]
        i = q1("SELECT COUNT(*) FROM mart_inventory")
        if i:
            out["inventory_items"] = int(i[0] or 0)
        hist = None
        try:
            hist = self.db.execute(text(
                "SELECT source, last_period, rows_ingested, status, run_at "
                "FROM sync_state ORDER BY id DESC LIMIT 5")).fetchall()
        except Exception:
            hist = []
        out["history"] = [{"source": r[0], "last_period": r[1], "rows_ingested": r[2],
                           "status": r[3], "run_at": str(r[4])} for r in (hist or [])]

        out["dss_tables"] = {}
        for t, k in (("fact_usage_total", "period"), ("fact_cases_by_care_level", "period"),
                     ("fact_usage_by_care_level", "period"), ("fact_inventory_lot", "snapshot_date")):
            r = q1(f"SELECT COUNT(*), MAX({k}) FROM {t}")
            out["dss_tables"][t] = {"rows": int(r[0] or 0), "latest": r[1]} if r else None

        # Không trả host/IP để tránh lộ hạ tầng.
        try:
            from app.services.sync_config_service import get_config
            cfg = get_config(self.db)
            out["source"] = {"kind": cfg.get("source", "file"),
                             "database": cfg.get("database") if cfg.get("source") == "sqlserver" else None}
        except Exception:                                 # noqa: BLE001
            out["source"] = {"kind": "unknown", "database": None}

        try:
            out["sta"] = self.trang_thai_sta(_build_pipeline(self.db).connector)
        except Exception as exc:                          # noqa: BLE001
            out["sta"] = {"available": False, "warning": str(exc)[:160]}
        return out
