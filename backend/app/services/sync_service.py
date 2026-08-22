"""Service đồng bộ dữ liệu từ nguồn (HIS SQL Server / file) vào DB trung gian.

Bọc DataPipeline để dashboard gọi qua API:
  - run_sync(): kéo dữ liệu MỚI (khám bệnh + tồn kho) → STAGING → CLEAN → MART.
  - get_status(): trạng thái lần đồng bộ gần nhất + số liệu hiện có.

Cấu hình lấy theo THỨ TỰ ƯU TIÊN:
  1. Bảng system_config trong DB (admin lưu từ màn hình Quản trị → Kết nối HIS)
     — xem app/services/sync_config_service.py
  2. Biến môi trường PIPELINE_* trong .env (cách cũ, vẫn chạy khi DB chưa có gì)
Pipeline ghi vào DB theo PIPELINE_DB_URL, mặc định = DATABASE_URL của app
(để mart nằm CHUNG DB với ứng dụng).
"""
from __future__ import annotations
import logging
import os
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data_pipeline.icd_hierarchy import IcdHierarchy
from app.data_pipeline.connectors import FileConnector, SqlServerConnector
from app.data_pipeline.pipeline import DataPipeline
from app.services import sync_config_service

logger = logging.getLogger(__name__)


def _build_pipeline(db: Optional[Session] = None) -> DataPipeline:
    icd_dir = os.environ.get("PIPELINE_ICD_DIR", "../data")
    # Không bắt buộc có TM_ICD*.xlsx: nguồn STA đã kèm sẵn cột disease_group.
    hier = IcdHierarchy.from_dir_optional(icd_dir)

    # 1) Cấu hình admin đã lưu trong DB — thắng .env, đổi không cần restart.
    connector = None
    if db is not None:
        try:
            connector = sync_config_service.build_connector(db)
        except RuntimeError:
            raise                    # cấu hình DB có nhưng thiếu trường — báo thẳng
        except Exception as exc:     # bảng chưa migrate v.v. — rơi về .env
            logger.warning("Không đọc được cấu hình kết nối trong DB (%s) — "
                           "dùng biến môi trường.", exc)
    if connector is not None:
        logger.info("Đồng bộ theo cấu hình kết nối lưu trong DB.")
        return DataPipeline(connector, hier)

    # 2) Cách cũ: biến môi trường
    source = os.environ.get("PIPELINE_SOURCE", "file")
    if source == "sqlserver":
        conn = os.environ.get("PIPELINE_SQLSERVER_CONN")
        if not conn:
            raise RuntimeError(
                "Chưa cấu hình kết nối HIS: vào Quản trị → Kết nối HIS, "
                "hoặc đặt PIPELINE_SQLSERVER_CONN trong .env.")
        connector = SqlServerConnector(conn)
    else:
        connector = FileConnector(os.environ.get("PIPELINE_DATA_DIR", "../data"))
    return DataPipeline(connector, hier)


class SyncService:
    def __init__(self, db: Session):
        self.db = db

    def run_sync(self, full: bool = False) -> dict:
        """Chạy một lần đồng bộ. incremental theo watermark (mặc định)."""
        result = _build_pipeline(self.db).run(incremental=not full)
        result["mode"] = "full" if full else "incremental"
        # Nửa sau của "Đồng bộ": các trang cũ (Dịch tễ, Tồn kho, Dashboard) đọc
        # bảng nghiệp vụ chứ không đọc mart — phải làm mới cả chúng, nếu không
        # bấm Đồng bộ chỉ cập nhật được các trang dự báo.
        try:
            result.update(self._lam_moi_bang_nghiep_vu())
        except Exception as exc:
            logger.exception("Làm mới bảng nghiệp vụ thất bại")
            result["legacy_refresh_error"] = str(exc)[:300]
        return result

    def _lam_moi_bang_nghiep_vu(self) -> dict:
        """Đổ dữ liệu từ tầng pipeline (fact/mart) sang các bảng nghiệp vụ cũ.

        VÌ SAO CẦN BƯỚC NÀY
        Ứng dụng có hai lớp dữ liệu hình thành theo lịch sử phát triển:
          - bảng nghiệp vụ (disease_cases, medical_supplies, inventory) — trước
            giờ nạp bằng chức năng import file CSV, phục vụ các trang Dịch tễ,
            Tồn kho, Dashboard;
          - tầng pipeline (fact_*, mart_*) — do job đồng bộ dựng, phục vụ dự báo
            phân cấp và kế hoạch vật tư.
        Job đồng bộ chỉ ghi lớp thứ hai. Không có cầu nối này thì sau khi nối
        HIS, các trang cũ vẫn hiển thị dữ liệu CSV import từ trước — hai màn
        hình cạnh nhau ra hai con số khác nhau.

        Cách làm: disease_cases XOÁ-RỒI-CHÈN toàn bộ từ fact_disease_case (nguồn
        chân lý duy nhất, chạy lại không nhân đôi); medical_supplies/inventory
        thì UPSERT theo supply_code — giữ nguyên safety_stock, giá, lead time
        người dùng đã nhập tay.
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

        # DB cũ tạo trước khi model có cột disease_group: create_all KHÔNG thêm
        # cột vào bảng đã tồn tại, nên tự ALTER ở đây (SQLite lẫn Postgres đều
        # chấp nhận cú pháp này; chạy lại lần nữa thì cột đã có, bỏ qua).
        from sqlalchemy import inspect as sa_inspect
        cot = {c["name"] for c in
               sa_inspect(self.db.connection()).get_columns("disease_cases")}
        if "disease_group" not in cot:
            self.db.execute(text(
                "ALTER TABLE disease_cases ADD COLUMN disease_group VARCHAR(20)"))
            logger.info("Đã thêm cột disease_group vào disease_cases.")

        # 1) disease_cases — xoá-rồi-chèn, mỗi dòng = (tháng × mã × tỉnh)
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
                data_source="HIS-STA",
            ) for r in facts
        ])

        def _sach(v, mac_dinh=""):
            """pandas NaN đi qua chuỗi hoá thành 'nan' — đã làm 4.680 vật tư
            mang drug_code='nan', khiến trang Kế hoạch gộp nghìn thuốc làm một
            dòng. Mọi giá trị chữ từ mart phải qua đây."""
            t = str(v).strip() if v is not None else ""
            return mac_dinh if t.lower() in ("", "nan", "none", "nat", "null") else t

        # 2) medical_supplies + inventory — upsert theo supply_code
        co_san = {s.supply_code: s for s in self.db.query(MedicalSupply).all()}
        inv_theo_id = {i.supply_id: i for i in self.db.query(Inventory).all()}
        them_vt = 0
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
                s.drug_code = _sach(t.drug_code, s.drug_code)
                s.ten_hoat_chat = _sach(t.name, s.ten_hoat_chat)
                s.unit = _sach(t.unit, s.unit)
                s.group_name = _sach(t.group_name, s.group_name)

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
                "legacy_inventory_updated": len(ton_kho)}

    def get_status(self) -> dict:
        """Trạng thái đồng bộ + số liệu hiện có (an toàn nếu bảng chưa tồn tại)."""
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
        return out
