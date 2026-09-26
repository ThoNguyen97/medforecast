"""Orchestrator: nguồn → làm sạch/validate → DIM/FACT → MART.

- Nạp tăng dần theo watermark last_period trong sync_state, lùi
  PIPELINE_LOOKBACK_MONTHS tháng để bắt dữ liệu được mã hóa muộn.
- Idempotent: fact ghi theo kiểu xóa-rồi-chèn từng period, mart xây lại từ fact.
- Cổng kiểm tra chất lượng loại và đếm dòng lỗi.
- Đánh cờ COVID (2020–2021); cờ tháng trọn vẹn được tính lại mỗi lần chạy.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd
from sqlalchemy import delete, func, inspect as sa_inspect, select, text, update

from .connectors import SourceConnector
from .db import SessionLocal, init_db
from .icd_hierarchy import IcdHierarchy, TARGET_BLOCKS, normalize_icd
from . import models as m

logger = logging.getLogger(__name__)

COVID_YEARS = {2020, 2021}
TOAN_QUOC = "TOAN_QUOC"


def _current_period() -> str:
    """Tháng hiện tại dạng 'YYYY-MM', mốc phân định tháng đã trọn vẹn."""
    now = datetime.now()
    return f"{now.year:04d}-{now.month:02d}"


def _parse_period(month_str: str):
    """'MM/YYYY' -> (year, month, 'YYYY-MM', date(yyyy,mm,1)) hoặc None nếu lỗi."""
    try:
        mm, yyyy = str(month_str).split("/")
        y, mo = int(yyyy), int(mm)
        if not (1 <= mo <= 12 and 1900 < y < 2100):
            return None
        return y, mo, f"{y:04d}-{mo:02d}", date(y, mo, 1)
    except Exception:
        return None


class DataPipeline:
    def __init__(self, connector: SourceConnector, hierarchy: IcdHierarchy,
                 target_only: bool = False):
        self.connector = connector
        self.hier = hierarchy
        self.target_only = target_only  # chỉ giữ 3 nhóm đích hay toàn bộ

    # ── tiện ích watermark ──
    def _get_watermark(self, db) -> Optional[str]:
        row = db.execute(
            select(func.max(m.SyncState.last_period)).where(
                m.SyncState.source == self.connector.name,
                m.SyncState.status == "ok",
            )
        ).scalar()
        return row

    # ── chạy đầy đủ ──
    def run(self, incremental: bool = True) -> dict:
        init_db()
        db = SessionLocal()
        try:
            since = self._get_watermark(db) if incremental else None
            raw = self.connector.fetch_case_supply(since_period=since)
            inv = self.connector.fetch_inventory()
            # Số ca theo nhóm do nguồn tính sẵn (nếu có), dùng trong _build_marts.
            grp = self.connector.fetch_case_group(since_period=since)

            clean, rejected, max_period = self._transform_cases(raw)
            self._upsert_dims(db, clean, inv)
            self._upsert_facts(db, clean)
            self._refresh_completeness(db)
            self._build_marts(db, grp)
            self._build_weather_mart(db)
            self._load_inventory(db, inv)

            state = m.SyncState(
                source=self.connector.name,
                last_period=max_period or since,
                rows_ingested=int(len(clean)),
                rows_rejected=int(rejected),
                status="ok",
                message=f"since={since} max_period={max_period}",
            )
            db.add(state)
            db.commit()
            return {
                "source": self.connector.name,
                "since": since,
                "max_period": max_period,
                "rows_ingested": int(len(clean)),
                "rows_rejected": int(rejected),
                "inventory_rows": int(len(inv)),
            }
        except Exception as exc:
            db.rollback()
            db.add(m.SyncState(source=self.connector.name, status="failed",
                               message=str(exc)))
            db.commit()
            logger.exception("Pipeline failed")
            raise
        finally:
            db.close()

    # ── làm sạch + validate ca bệnh ──
    def _transform_cases(self, raw: pd.DataFrame):
        if raw.empty:
            return raw.assign(period=[]), 0, None
        df = raw.copy()
        df["icd_code"] = df["disease_code"].map(normalize_icd)      # 'j01' -> 'J01'
        df["region"] = df["region"].astype(str).str.strip()
        parsed = df["month"].map(_parse_period)

        # Cổng kiểm tra chất lượng
        valid_mask = (
            parsed.notna()
            & df["icd_code"].str.match(r"^[A-Z]\d{2}$").fillna(False)
            & df["cases"].notna()
            & (df["cases"].fillna(-1) >= 0)
            & df["region"].notna() & (df["region"] != "") & (df["region"].str.lower() != "nan")
        )
        rejected = int((~valid_mask).sum())
        df = df[valid_mask].copy()
        parsed = parsed[valid_mask]
        df["year"] = parsed.map(lambda p: p[0])
        df["month_num"] = parsed.map(lambda p: p[1])
        df["period"] = parsed.map(lambda p: p[2])
        df["recorded_date"] = parsed.map(lambda p: p[3])
        # Nhóm ICD: ưu tiên cột nguồn cấp (TM_ICD.PHANNHOM), chỉ tra TM_ICD.xlsx
        # cho dòng nguồn không cấp.
        tu_nguon = (df["disease_group"].astype(str).str.strip()
                    if "disease_group" in df.columns
                    else pd.Series("", index=df.index))
        tu_nguon = tu_nguon.replace({"": None, "nan": None, "None": None, "NaT": None})
        df["block_code"] = tu_nguon.fillna(df["icd_code"].map(self.hier.block_of))

        # Mã không map được nhóm thì loại.
        unknown = df["block_code"].isna()
        rejected += int(unknown.sum())
        df = df[~unknown].copy()

        if self.target_only:
            df = df[df["block_code"].isin(TARGET_BLOCKS)].copy()

        df["is_covid"] = df["year"].isin(COVID_YEARS)
        df["is_complete"] = df.apply(
            lambda r: not _is_current_month(int(r["year"]), int(r["month_num"])), axis=1
        )
        max_period = df["period"].max() if not df.empty else None
        return df, rejected, max_period

    # ── làm mới cờ tháng-trọn-vẹn ──
    def _refresh_completeness(self, db):
        """Tính lại `is_complete` cho toàn bộ fact theo tháng hiện tại.

        Cờ không được đóng băng lúc nạp: bản ghi tháng đang chạy có thể không được
        ghi lại, khi đó cờ kẹt ở False và tầng dự báo (lọc is_complete=1) loại tháng đó mãi.
        """
        cur = _current_period()
        db.execute(update(m.FactDiseaseCase)
                   .where(m.FactDiseaseCase.period < cur)
                   .values(is_complete=True))
        db.execute(update(m.FactDiseaseCase)
                   .where(m.FactDiseaseCase.period >= cur)
                   .values(is_complete=False))
        db.flush()

    # ── DIM ──
    def _upsert_dims(self, db, clean: pd.DataFrame, inv: pd.DataFrame):
        # dim_icd: từ mã xuất hiện + danh mục phân cấp; tên bệnh lấy từ cột
        # disease_name (TENICD của HIS).
        ten_theo_ma: dict = {}
        nhom_theo_ma: dict = {}
        if not clean.empty:
            for c, g in clean.groupby("icd_code"):
                ten = g["disease_name"].dropna().astype(str).str.strip()
                ten = ten[(ten != "") & (ten.str.lower() != "nan")]
                if not ten.empty:
                    ten_theo_ma[c] = ten.iloc[0][:400]
                if "block_code" in g.columns:
                    nb = g["block_code"].dropna().astype(str).str.strip()
                    if not nb.empty:
                        nhom_theo_ma[c] = nb.iloc[0]

        codes = set(clean["icd_code"]) if not clean.empty else set()
        existing_icd = {r.icd_code: r for r in db.query(m.DimIcd).all()}
        # Bổ sung tên cho mã đã có trong dim_icd nhưng icd_name rỗng.
        for code, row in existing_icd.items():
            if not row.icd_name and ten_theo_ma.get(code):
                row.icd_name = ten_theo_ma[code]
        for code in codes - set(existing_icd):
            block = nhom_theo_ma.get(code) or self.hier.block_of(code)
            chap = self.hier.chapter_of(code)
            db.add(m.DimIcd(
                icd_code=code, icd_name=ten_theo_ma.get(code, ""),
                block_code=block, block_name=self.hier.block_label(block) if block else None,
                chapter_code=chap, chapter_name=self.hier.chapter_name.get(chap, "") if chap else None,
                is_target=(block in TARGET_BLOCKS),
            ))
        # dim_region
        regions = set(clean["region"]) if not clean.empty else set()
        existing_reg = set(db.execute(select(m.DimRegion.region)).scalars().all())
        for reg in regions - existing_reg:
            db.add(m.DimRegion(region=reg))
        # dim_supply từ tồn kho + từ ca
        existing_sup = set(db.execute(select(m.DimSupply.supply_code)).scalars().all())
        sup_seen = set(existing_sup)
        if inv is not None and not inv.empty:
            for _, r in inv.iterrows():
                sc = str(r.get("supply_code") or "").strip()
                if sc and sc not in sup_seen:
                    sup_seen.add(sc)
                    db.add(m.DimSupply(
                        supply_code=sc[:60], drug_code=str(r.get("drug_code") or "")[:60],
                        name=str(r.get("ten_hoat_chat") or "")[:400], unit=str(r.get("unit") or "")[:40],
                        group_name=str(r.get("group_name") or "")[:255],
                        category=str(r.get("category") or "")[:80],
                    ))
        db.flush()

    # ── FACT (upsert idempotent theo period) ──
    def _upsert_facts(self, db, clean: pd.DataFrame):
        if clean.empty:
            return
        periods = sorted(clean["period"].unique())

        # fact_disease_case: số ca lặp theo nhiều dòng vật tư → lấy 1 giá trị/(period,icd,region)
        cases = (clean.groupby(["period", "year", "month_num", "recorded_date",
                                "icd_code", "block_code", "region", "is_covid", "is_complete"],
                               dropna=False)["cases"].max().reset_index())
        # Xóa các period sắp ghi rồi chèn lại (idempotent).
        db.execute(delete(m.FactDiseaseCase).where(m.FactDiseaseCase.period.in_(periods)))
        db.bulk_save_objects([
            m.FactDiseaseCase(
                period=r.period, year=int(r.year), month=int(r.month_num),
                recorded_date=r.recorded_date, icd_code=r.icd_code, block_code=r.block_code,
                region=r.region, cases=_safe_int(r.cases),
                is_covid=bool(r.is_covid), is_complete=bool(r.is_complete),
            ) for r in cases.itertuples(index=False)
        ])

        db.flush()

    # ── Số ca mức nhóm: dùng số nguồn cấp thay cho phép cộng dồn ──
    @staticmethod
    def _ap_so_ca_nhom(full: pd.DataFrame,
                       case_group: Optional[pd.DataFrame]) -> pd.DataFrame:
        if case_group is None or case_group.empty:
            logger.warning(
                "Nguồn không cấp số ca theo nhóm — mart_monthly_cases_by_block "
                "đang CỘNG DỒN số ca các mã con. Lượt khám mang nhiều mã trong "
                "cùng một nhóm sẽ bị đếm nhiều lần, tổng nhóm cao hơn thực tế. "
                "Đặt PIPELINE_CASE_GROUP_SQL_FILE=case_group_sta.sql để lấy số đúng.")
            return full

        g = case_group.copy()
        parsed = g["month"].map(_parse_period)
        g = g[parsed.notna()].copy()
        parsed = parsed[parsed.notna()]
        if g.empty:
            return full
        g["period"] = parsed.map(lambda p: p[2])
        g["block_code"] = g["disease_group"].astype(str).str.strip()
        g["region"] = g["region"].astype(str).str.strip()
        g["cases_nguon"] = pd.to_numeric(g["cases"], errors="coerce")
        g = (g.dropna(subset=["cases_nguon"])
              .groupby(["period", "block_code", "region"], as_index=False)["cases_nguon"].max())

        out = full.merge(g, on=["period", "block_code", "region"], how="left")
        thay = out["cases_nguon"].notna()
        lech = int((thay & (out["cases_nguon"] != out["cases"])).sum())
        out.loc[thay, "cases"] = out.loc[thay, "cases_nguon"]
        out["cases"] = out["cases"].astype(int)
        logger.info("Số ca mức nhóm lấy từ nguồn cho %d/%d dòng (%d dòng lệch "
                    "so với cách cộng dồn).", int(thay.sum()), len(out), lech)
        return out.drop(columns=["cases_nguon"])

    # ── MART (xây lại từ fact, idempotent) ──
    def _build_marts(self, db, case_group: Optional[pd.DataFrame] = None):
        # mart_monthly_cases_by_block: gộp theo tỉnh + bản TOAN_QUOC
        rows = db.execute(select(
            m.FactDiseaseCase.period, m.FactDiseaseCase.year, m.FactDiseaseCase.month,
            m.FactDiseaseCase.block_code, m.FactDiseaseCase.region,
            m.FactDiseaseCase.cases, m.FactDiseaseCase.is_covid, m.FactDiseaseCase.is_complete,
        )).all()
        if not rows:
            return
        fc = pd.DataFrame(rows, columns=["period", "year", "month", "block_code", "region",
                                         "cases", "is_covid", "is_complete"])

        def agg(g):
            return pd.Series({"cases": int(g["cases"].sum()),
                              "is_covid": bool(g["is_covid"].any()),
                              "is_complete": bool(g["is_complete"].all())})

        by_region = fc.groupby(["period", "year", "month", "block_code", "region"]).apply(agg, include_groups=False).reset_index()
        nat = fc.groupby(["period", "year", "month", "block_code"]).apply(agg, include_groups=False).reset_index()
        nat["region"] = TOAN_QUOC
        full = pd.concat([by_region, nat], ignore_index=True)

        # Thay số ca nhóm bằng số đếm DISTINCT do nguồn cấp: cộng số ca các mã con
        # đếm hai lần lượt khám mang hai mã cùng nhóm (J01 + J06 thuộc J00-J06).
        # Nguồn không cấp thì giữ phép cộng dồn và ghi cảnh báo.
        full = self._ap_so_ca_nhom(full, case_group)

        # Tên nhóm: ưu tiên tên nguồn cấp, sau đó bảng tra ICD, cuối cùng là mã nhóm.
        ten_nhom = {}
        if case_group is not None and not case_group.empty \
                and "disease_group_name" in case_group.columns:
            for g, n in (case_group.dropna(subset=["disease_group_name"])
                         .groupby("disease_group")["disease_group_name"].first().items()):
                ten = str(n).strip()
                if ten and ten.lower() != "nan":
                    ten_nhom[str(g).strip()] = ten

        def nhan_nhom(code):
            return ten_nhom.get(code) or self.hier.block_label(code)

        cur = _current_period()
        db.execute(delete(m.MartMonthlyCasesByBlock))
        db.bulk_save_objects([
            m.MartMonthlyCasesByBlock(
                period=r.period, year=int(r.year), month=int(r.month),
                block_code=r.block_code, block_name=nhan_nhom(r.block_code),
                region=r.region, cases=int(r.cases),
                is_covid=bool(r.is_covid),
                # Suy ra từ period thay vì cờ đã lưu, vì cờ lưu có thể lỗi thời.
                is_complete=(str(r.period) < cur),
            ) for r in full.itertuples(index=False)
        ])

        # mart_icd_share_in_block: tỷ trọng từng mã trong nhóm (toàn lịch sử, TOAN_QUOC)
        cr = db.execute(select(
            m.FactDiseaseCase.block_code, m.FactDiseaseCase.icd_code, m.FactDiseaseCase.cases,
        )).all()
        sh = pd.DataFrame(cr, columns=["block_code", "icd_code", "cases"])
        grp = sh.groupby(["block_code", "icd_code"])["cases"].sum().reset_index()
        tot = grp.groupby("block_code")["cases"].transform("sum")
        grp["share"] = (grp["cases"] / tot).fillna(0.0)
        db.execute(delete(m.MartIcdShareInBlock))
        db.bulk_save_objects([
            m.MartIcdShareInBlock(
                block_code=r.block_code, icd_code=r.icd_code, region=TOAN_QUOC,
                share=float(r.share), n_cases=int(r.cases),
            ) for r in grp.itertuples(index=False)
        ])
        db.flush()

    # ── thời tiết → mart_monthly_weather (từ environmental_data) ──
    def _build_weather_mart(self, db, primary_location: str = "TP. Hồ Chí Minh"):
        """Tổng hợp thời tiết theo tháng từ bảng environmental_data (nếu có).

        Kiểm tra bảng bằng inspector thay vì try/except + rollback: rollback sẽ huỷ
        cả dim/fact vừa ghi trong cùng transaction mà pipeline vẫn báo "ok".
        """
        # Dùng connection của session: trên SQLite, mở kết nối thứ hai giữa transaction
        # đang ghi gây "database is locked".
        if not sa_inspect(db.connection()).has_table("environmental_data"):
            logger.info("Chưa có bảng environmental_data — bỏ qua mart thời tiết.")
            return
        rows = db.execute(text(
            "SELECT recorded_at, location, temperature, humidity, rainfall "
            "FROM environmental_data")).fetchall()
        if not rows:
            return
        wdf = pd.DataFrame(rows, columns=["recorded_at", "location", "temp",
                                          "humidity", "rainfall"])
        wdf["recorded_at"] = pd.to_datetime(wdf["recorded_at"], errors="coerce")
        wdf = wdf.dropna(subset=["recorded_at"])
        loc = wdf[wdf["location"] == primary_location]
        src = (loc if len(loc) else wdf).copy()
        src["year"] = src["recorded_at"].dt.year
        src["month"] = src["recorded_at"].dt.month
        src["period"] = src["recorded_at"].dt.strftime("%Y-%m")
        agg = (src.groupby(["period", "year", "month"])[["temp", "humidity", "rainfall"]]
               .mean().reset_index())
        db.execute(delete(m.MartMonthlyWeather))
        db.bulk_save_objects([
            m.MartMonthlyWeather(
                period=r.period, year=int(r.year), month=int(r.month),
                region=TOAN_QUOC,
                temp=_safe_float(r.temp), humidity=_safe_float(r.humidity),
                rainfall=_safe_float(r.rainfall),
            ) for r in agg.itertuples(index=False)
        ])
        db.flush()

    # ── tồn kho → mart_inventory ──
    def _load_inventory(self, db, inv: pd.DataFrame):
        if inv is None or inv.empty:
            return
        today = date.today()
        db.execute(delete(m.MartInventory))
        marts = []
        for _, r in inv.iterrows():
            sc = str(r.get("supply_code") or "").strip()
            if not sc:
                continue
            qty = _safe_int(r.get("stock_quantity"))
            marts.append(m.MartInventory(
                supply_code=sc[:60], name=str(r.get("ten_hoat_chat") or "")[:400],
                drug_code=str(r.get("drug_code") or "")[:60], unit=str(r.get("unit") or "")[:40],
                group_name=str(r.get("group_name") or "")[:255], category=str(r.get("category") or "")[:80],
                stock_quantity=qty, snapshot_date=today,
            ))
        # bulk_save_objects vì danh mục vật tư có thể tới vài chục nghìn dòng.
        db.bulk_save_objects(marts)
        db.flush()


def _is_current_month(y: int, mo: int) -> bool:
    now = datetime.now()
    return (y == now.year and mo == now.month) or (y > now.year)


def _safe_int(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0
        return int(float(v))
    except Exception:
        return 0


def _safe_float(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0.0
        return float(v)
    except Exception:
        return 0.0
