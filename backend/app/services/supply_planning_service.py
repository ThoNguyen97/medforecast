"""Đề xuất nhập kho từ dự báo phân cấp — có mức an toàn (theo khoảng bất định)
và lead time.

Luồng: dự báo số ca từng mã (điểm + cận trên) → phân bổ mức độ (severity_rates)
→ nhân định mức thuốc (disease_supply_norms) → nhu cầu; dùng CẬN TRÊN làm mức an
toàn → so tồn kho (mart_inventory) → đề xuất nhập. Kèm lead_time_days để biết thời
điểm đặt hàng.
"""
from __future__ import annotations
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.hierarchical_forecast_service import HierarchicalForecastService

SEVERITIES = ("mild", "moderate", "severe")


class SupplyPlanningService:
    def __init__(self, db: Session):
        self.db = db
        self.fc = HierarchicalForecastService(db)

    def _rows(self, sql: str, params: dict | None = None):
        try:
            return self.db.execute(text(sql), params or {}).fetchall()
        except SQLAlchemyError:
            self.db.rollback()
            return []

    def _severity(self) -> Dict[str, Dict[str, float]]:
        out = {}
        for r in self._rows("SELECT icd_code, mild_rate, moderate_rate, severe_rate "
                            "FROM severity_rates"):
            out[r[0]] = {"mild": float(r[1] or 0), "moderate": float(r[2] or 0),
                         "severe": float(r[3] or 0)}
        return out

    def _norms(self, icds: List[str]):
        if not icds:
            return []
        ph = ",".join(f":c{i}" for i in range(len(icds)))
        params = {f"c{i}": c for i, c in enumerate(icds)}
        return self._rows(
            f"SELECT n.icd_code, n.severity, n.quantity_per_case, s.supply_code, "
            f"s.drug_code, s.ten_hoat_chat, s.unit, s.group_name, s.lead_time_days "
            f"FROM disease_supply_norms n JOIN medical_supplies s ON s.id = n.supply_id "
            f"WHERE n.icd_code IN ({ph})", params)

    def _stock(self) -> Dict[str, int]:
        """Tồn kho khóa theo drug_code (mã thật). mart_inventory.supply_code = drug_code."""
        out = {}
        for r in self._rows("SELECT drug_code, supply_code, stock_quantity FROM mart_inventory"):
            dc = (str(r[0]) if r[0] is not None else "").strip()
            key = dc if dc.lower() not in ("", "nan", "none") else r[1]
            if key:
                out[str(key)] = out.get(str(key), 0) + int(r[2] or 0)
        return out

    def plan(self, block: str, method: str = "top_down_dynamic",
             region: str = "TOAN_QUOC") -> dict:
        fc = self.fc.forecast(block, method=method, region=region)
        by_code = fc["by_code"]            # điểm
        by_code_upper = fc["by_code_upper"]  # cận trên = cơ sở mức an toàn
        sev = self._severity()
        stock = self._stock()

        # ── Định mức + tỷ lệ nặng/nhẹ giờ ở MỨC NHÓM ─────────────────────────
        # Từ 10/08/2026, severity_rates và disease_supply_norms chuyển sang khoá
        # nhóm ('J09-J18'); các dòng severity mức mã đã bị xoá (tránh đúp nhu
        # cầu). Bản cũ của hàm này tra cả hai bảng bằng KHOÁ MÃ nên sau chuyển
        # đổi trả về 0 vật tư cho MỌI nhóm — trang Kế hoạch trống trơn.
        #
        # Cách tra mới, ưu tiên nhóm:
        #   • định mức: lấy dòng khoá NHÓM nếu có; không có mới rơi về dòng mã
        #     (KHÔNG trộn hai loại — trộn là cộng nhu cầu hai lần)
        #   • số ca cho dòng định mức nhóm = TỔNG các mã trong nhóm
        #   • tỷ lệ nặng/nhẹ: tra theo khoá của dòng định mức, thiếu thì rơi về
        #     khoá nhóm
        norms = self._norms([block] + list(by_code.keys()))
        dong_nhom = [r for r in norms if r[0] == block]
        if dong_nhom:
            norms = dong_nhom
        group_point = sum(by_code.values())
        group_upper = sum(by_code_upper.values())

        # gộp theo vật tư: nhu cầu điểm + nhu cầu an toàn (cận trên)
        agg: Dict[str, dict] = {}
        for (icd, severity, qty, scode, dcode, sname, unit, grp, lead) in norms:
            rate_map = sev.get(icd) or sev.get(block)
            if not rate_map or severity not in SEVERITIES:
                continue
            rate = rate_map[severity] / 100.0
            if icd == block:                       # định mức mức nhóm
                cases_point = group_point * rate
                cases_safe = group_upper * rate
            else:                                  # định mức mức mã (tương thích cũ)
                cases_point = by_code.get(icd, 0) * rate
                cases_safe = by_code_upper.get(icd, 0) * rate
            demand_point = cases_point * float(qty or 0)
            demand_safe = cases_safe * float(qty or 0)
            # 'nan' là chuỗi rác từ pandas — coi như không có drug_code,
            # nếu không hàng nghìn vật tư gộp chung một khoá và lệch kho.
            dc = (dcode or "").strip()
            key = dc if dc.lower() not in ("", "nan", "none") else scode
            it = agg.setdefault(key, {
                "supply_code": dcode or scode, "name": sname, "unit": unit,
                "group_name": grp, "lead_time_days": int(lead or 0),
                "demand_point": 0.0, "demand_safety": 0.0})
            it["demand_point"] += demand_point
            it["demand_safety"] += demand_safe

        items = []
        for key, it in agg.items():
            need_point = round(it["demand_point"])
            need_safety = round(it["demand_safety"])   # đã gồm dự phòng bất định
            cur = stock.get(key, 0)
            suggest = max(0, need_safety - cur)
            items.append({
                "supply_code": it["supply_code"], "name": it["name"], "unit": it["unit"],
                "group_name": it["group_name"], "lead_time_days": it["lead_time_days"],
                "demand_forecast": need_point,
                "safety_level": need_safety,       # mức an toàn (từ cận trên dự báo)
                "current_stock": cur,
                "suggested_import": suggest,
                "status": "shortage" if suggest > 0 else "sufficient",
            })
        items.sort(key=lambda x: x["suggested_import"], reverse=True)

        return {
            "block": block,
            "target_period": fc["target_period"],
            "method": method,
            "weather_used": fc.get("weather_used", False),
            "group_forecast": fc["group_forecast"],
            "group_interval": fc.get("group_interval"),
            "n_supplies": len(items),
            "n_shortage": sum(1 for x in items if x["status"] == "shortage"),
            "items": items,
        }
