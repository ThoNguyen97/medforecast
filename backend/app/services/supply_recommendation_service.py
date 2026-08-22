"""Supply Recommendation Service.

Triển khai logic tính nhu cầu thuốc và đề xuất nhập kho theo yêu cầu mục 4-7:

- Mục 4: Định mức thuốc/vật tư theo bệnh và mức độ (disease_supply_norm)
- Mục 5: Phân bổ số ca theo mức độ Nhẹ/Trung bình/Nặng (severity_rate)
- Mục 6: Tính nhu cầu thuốc = Σ(số ca × định mức) × (1 + dự phòng)
- Mục 7: Đề xuất nhập = max(0, nhu cầu + ngưỡng an toàn - tồn kho)
"""
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, extract, func
from sqlalchemy.orm import Session

from app.models.disease_case import DiseaseCase
from app.models.disease_forecast import DiseaseForecast
from app.models.disease_supply_norm import DiseaseSupplyNorm
from app.models.inventory import Inventory
from app.models.medical_supply import MedicalSupply
from app.models.severity_rate import SeverityRate
from app.models.supply_recommendation import SupplyRecommendation

logger = logging.getLogger(__name__)


# Hệ số dự phòng mặc định (15% cho kịch bản nguy cơ trung bình/cao)
DEFAULT_BUFFER_RATE = 15.0


def phan_muc_canh_bao(
    need_before_buffer: float,
    predicted_need: float,
    current_stock: float,
    co_du_lieu_ton: bool = True,
    unit: str = "",
    suggested_import: float = 0,
) -> Dict[str, Any]:
    """Phân mức cảnh báo 4 trạng thái theo Bảng 4 đề cương — mỗi mức kèm
    NGUYÊN NHÂN (số liệu đầu vào) và HÀNH ĐỘNG hỗ trợ.

    Ngữ nghĩa (từ chặt đến lỏng):
      ĐỎ   — tồn < nhu cầu CHƯA tính dự phòng → thiếu gần như chắc chắn,
             không còn đệm nào giữa kho và bệnh nhân.
      VÀNG — tồn đủ nhu cầu cơ bản nhưng DƯỚI ngưỡng an toàn (nhu cầu × (1 +
             dự phòng)) → một biến động nhỏ là thiếu.
      XANH — tồn ≥ ngưỡng an toàn.
      XÁM  — không đủ dữ liệu để kết luận (chưa có bản ghi tồn kho) → hiển thị
             thay vì im lặng, vì "không biết" khác với "đủ".
    Vì sao không gộp Đỏ/Vàng làm một: hành động khác nhau — Đỏ phải đặt NGAY
    (trong lead time), Vàng chỉ cần đưa vào kỳ đặt hàng kế tiếp.
    """
    n_truoc = float(need_before_buffer or 0)
    n_at = float(predicted_need or 0)
    ton = float(current_stock or 0)
    de_xuat = float(suggested_import or 0)

    if not co_du_lieu_ton:
        return {
            "level": "gray", "level_label": "Xám",
            "reason": "Chưa có bản ghi tồn kho cho vật tư này trong hệ thống.",
            "action": "Cập nhật tồn kho (đồng bộ HIS hoặc nhập tay) rồi tính lại.",
        }
    if ton < n_truoc:
        return {
            "level": "red", "level_label": "Đỏ",
            "reason": (f"Tồn {ton:,.0f} {unit} thấp hơn nhu cầu chưa tính dự phòng "
                       f"{n_truoc:,.0f} {unit} — không còn khoảng đệm."),
            "action": (f"Đặt hàng ngay {de_xuat:,.0f} {unit}, ưu tiên trong "
                       "thời gian cung ứng gần nhất."),
        }
    if ton < n_at:
        return {
            "level": "yellow", "level_label": "Vàng",
            "reason": (f"Tồn {ton:,.0f} {unit} đủ nhu cầu cơ bản {n_truoc:,.0f} "
                       f"nhưng dưới ngưỡng an toàn {n_at:,.0f} {unit}."),
            "action": (f"Đưa {de_xuat:,.0f} {unit} vào kỳ đặt hàng kế tiếp; "
                       "theo dõi sát số ca thực tế."),
        }
    return {
        "level": "green", "level_label": "Xanh",
        "reason": (f"Tồn {ton:,.0f} {unit} cao hơn ngưỡng an toàn "
                   f"{n_at:,.0f} {unit}."),
        "action": "Không cần nhập; theo dõi định kỳ theo lịch đồng bộ.",
    }


class SupplyRecommendationService:
    """Service tính nhu cầu thuốc và đề xuất nhập kho."""

    def __init__(self, db: Session):
        self.db = db

    # ── Helper queries ──────────────────────────────────────────────────────

    def _get_severity_rate(self, icd_code: str) -> Optional[SeverityRate]:
        """Lấy tỷ lệ Nhẹ/TB/Nặng cho 1 bệnh."""
        return (
            self.db.query(SeverityRate)
            .filter(SeverityRate.icd_code == icd_code)
            .first()
        )

    def _get_supply_norms(self, icd_code: str) -> Dict[int, Dict[str, Any]]:
        """Lấy định mức thuốc/vật tư cho 1 bệnh, group theo supply_id.

        Returns:
            {supply_id: {"supply": MedicalSupply, "mild": int, "moderate": int, "severe": int}}
        """
        rows = (
            self.db.query(DiseaseSupplyNorm, MedicalSupply)
            .join(MedicalSupply, MedicalSupply.id == DiseaseSupplyNorm.supply_id)
            .filter(DiseaseSupplyNorm.icd_code == icd_code)
            .all()
        )

        result: Dict[int, Dict[str, Any]] = {}
        for norm, supply in rows:
            sid = supply.id
            if sid not in result:
                result[sid] = {
                    "supply": supply,
                    "mild": 0,
                    "moderate": 0,
                    "severe": 0,
                }
            if norm.severity == "mild":
                result[sid]["mild"] = norm.quantity_per_case
            elif norm.severity == "moderate":
                result[sid]["moderate"] = norm.quantity_per_case
            elif norm.severity == "severe":
                result[sid]["severe"] = norm.quantity_per_case
        return result

    def _get_inventory(self, supply_id: int) -> Dict[str, int]:
        """Lấy tồn kho hiện tại + ngưỡng an toàn cho 1 supply.

        Trả về tổng (nếu có nhiều dòng inventory cho cùng supply).
        """
        row = (
            self.db.query(
                func.coalesce(func.sum(Inventory.current_stock), 0).label("current"),
                func.coalesce(func.max(Inventory.safety_stock), 0).label("safety"),
            )
            .filter(Inventory.supply_id == supply_id)
            .first()
        )
        so_dong = (
            self.db.query(func.count(Inventory.id))
            .filter(Inventory.supply_id == supply_id).scalar() or 0
        )
        return {
            "current_stock": int(row.current if row else 0),
            "safety_stock": int(row.safety if row else 0),
            # found=False → mức cảnh báo XÁM: "không biết" khác với "tồn = 0"
            "found": bool(so_dong > 0),
        }

    # ── Core calculation (mục 5.1 + 6 + 7) ──────────────────────────────────

    def calculate_for_disease(
        self,
        icd_code: str,
        predicted_cases: int,
        forecast_month: date,
        buffer_rate: float = DEFAULT_BUFFER_RATE,
    ) -> Dict[str, Any]:
        """Tính nhu cầu + đề xuất nhập cho 1 bệnh trong 1 tháng.

        Args:
            icd_code: Mã ICD bệnh (J20, J06, J02, J01)
            predicted_cases: Tổng số ca dự báo
            forecast_month: Tháng dự báo
            buffer_rate: Hệ số dự phòng (mặc định 15%)

        Returns:
            Dict gồm: severity_breakdown, items[] với từng thuốc và đề xuất nhập
        """
        severity = self._get_severity_rate(icd_code)
        if not severity:
            raise ValueError(
                f"Không tìm thấy tỷ lệ severity cho bệnh {icd_code}. "
                f"Vui lòng cấu hình severity_rate trước."
            )

        norms = self._get_supply_norms(icd_code)
        if not norms:
            raise ValueError(
                f"Không tìm thấy định mức thuốc cho bệnh {icd_code}. "
                f"Vui lòng cấu hình disease_supply_norm trước."
            )

        # Mục 5.1: Phân bổ số ca theo mức độ
        mild_cases = round(predicted_cases * float(severity.mild_rate) / 100)
        moderate_cases = round(predicted_cases * float(severity.moderate_rate) / 100)
        # Đảm bảo tổng = predicted_cases (làm tròn)
        severe_cases = predicted_cases - mild_cases - moderate_cases
        if severe_cases < 0:
            severe_cases = 0

        # Mục 6 + 7: Tính cho từng thuốc
        items: List[Dict[str, Any]] = []
        for sid, data in norms.items():
            supply = data["supply"]

            # Mục 6: Nhu cầu trước dự phòng = Σ(số ca × định mức)
            need_before_buffer = (
                mild_cases * data["mild"]
                + moderate_cases * data["moderate"]
                + severe_cases * data["severe"]
            )

            # Bỏ qua thuốc không dùng cho bệnh này (định mức = 0 cho mọi mức)
            if need_before_buffer <= 0:
                continue

            # Mục 6: Ngưỡng AT (Nhu cầu cuối) = Nhu cầu trước dự phòng × (1 + % dự phòng)
            calculated_safety_stock = round(need_before_buffer * (1 + buffer_rate / 100))

            # Nhu cầu cuối = Ngưỡng AT (theo thiết lập: 2 con số bằng nhau)
            predicted_need = calculated_safety_stock

            # Mục 7: Đề xuất nhập = max(0, Nhu cầu cuối - Tồn kho)
            # Luôn dùng Nhu cầu cuối (tính theo công thức), không dùng giá trị từ Inventory
            inv = self._get_inventory(sid)
            suggested_import = max(0, predicted_need - inv["current_stock"])

            items.append({
                "supply_id": sid,
                "supply_code": supply.supply_code,
                "drug_code": supply.drug_code,
                "ten_hoat_chat": supply.ten_hoat_chat,
                "unit": supply.unit,
                "group_name": supply.group_name,
                # Định mức theo mức độ
                "norm_mild": data["mild"],
                "norm_moderate": data["moderate"],
                "norm_severe": data["severe"],
                # Tính toán
                "need_before_buffer": need_before_buffer,
                "buffer_rate": buffer_rate,
                "predicted_need": predicted_need,
                # Ngưỡng AT được tính tự động theo công thức (= Nhu cầu cuối)
                "calculated_safety_stock": calculated_safety_stock,
                # Tồn kho
                "current_stock": inv["current_stock"],
                "safety_stock": calculated_safety_stock,  # Luôn dùng giá trị tính toán, không lấy từ Inventory
                # Đề xuất nhập (mục 7)
                "suggested_import": suggested_import,
                # Trạng thái cũ (giữ tương thích) + 4 mức theo Bảng 4 đề cương
                "status": "shortage" if suggested_import > 0 else "sufficient",
                **phan_muc_canh_bao(need_before_buffer, predicted_need,
                                    inv["current_stock"], inv.get("found", True),
                                    supply.unit or "", suggested_import),
            })

        # Sort theo suggested_import giảm dần (cần nhập nhiều nhất lên đầu)
        items.sort(key=lambda x: x["suggested_import"], reverse=True)

        return {
            "icd_code": icd_code,
            "disease_name": severity.disease_name,
            "forecast_month": forecast_month.isoformat(),
            "predicted_cases": predicted_cases,
            # Mục 5.1
            "severity_breakdown": {
                "mild_rate": float(severity.mild_rate),
                "moderate_rate": float(severity.moderate_rate),
                "severe_rate": float(severity.severe_rate),
                "mild_cases": mild_cases,
                "moderate_cases": moderate_cases,
                "severe_cases": severe_cases,
            },
            "buffer_rate": buffer_rate,
            "total_supplies": len(items),
            "total_suggested_import_value": sum(i["suggested_import"] for i in items),
            "items": items,
        }

    # ── Aggregation across diseases ─────────────────────────────────────────

    def calculate_for_month(
        self,
        forecast_month: date,
        location: Optional[str] = None,
        buffer_rate: float = DEFAULT_BUFFER_RATE,
    ) -> Dict[str, Any]:
        """Tính nhu cầu + đề xuất nhập cho tất cả bệnh trong 1 tháng.

        Lấy số ca dự báo từ disease_forecasts (nếu chưa có forecast → dùng case_count thực tế).
        Sau đó cộng dồn nhu cầu của từng thuốc qua các bệnh để có total đề xuất nhập.
        """
        # Lấy danh sách bệnh có severity_rate
        all_severities = self.db.query(SeverityRate).all()

        # Cho mỗi bệnh, lấy số ca dự báo trong tháng
        per_disease: List[Dict[str, Any]] = []
        for sev in all_severities:
            predicted = self._get_predicted_cases(
                icd_code=sev.icd_code,
                forecast_month=forecast_month,
                location=location,
            )
            if predicted <= 0:
                continue
            try:
                result = self.calculate_for_disease(
                    icd_code=sev.icd_code,
                    predicted_cases=predicted,
                    forecast_month=forecast_month,
                    buffer_rate=buffer_rate,
                )
                per_disease.append(result)
            except ValueError as exc:
                logger.warning("Skip disease %s: %s", sev.icd_code, exc)

        # Aggregate qua các bệnh: tổng nhu cầu cho mỗi thuốc
        aggregated: Dict[int, Dict[str, Any]] = {}
        for d in per_disease:
            for it in d["items"]:
                sid = it["supply_id"]
                if sid not in aggregated:
                    aggregated[sid] = {
                        "supply_id": sid,
                        "supply_code": it["supply_code"],
                        "drug_code": it["drug_code"],
                        "ten_hoat_chat": it["ten_hoat_chat"],
                        "unit": it["unit"],
                        "group_name": it["group_name"],
                        "current_stock": it["current_stock"],
                        "safety_stock": it["safety_stock"],
                        "buffer_rate": buffer_rate,
                        # Cộng dồn
                        "need_before_buffer_total": 0,
                        "predicted_need_total": 0,
                        "by_disease": [],
                    }
                aggregated[sid]["need_before_buffer_total"] += it["need_before_buffer"]
                aggregated[sid]["predicted_need_total"] += it["predicted_need"]
                aggregated[sid]["by_disease"].append({
                    "icd_code": d["icd_code"],
                    "disease_name": d["disease_name"],
                    "predicted_cases": d["predicted_cases"],
                    "predicted_need": it["predicted_need"],
                })

        # Tính suggested_import dựa trên total need
        agg_items: List[Dict[str, Any]] = []
        for sid, data in aggregated.items():
            # Ngưỡng AT = Nhu cầu cuối (luôn dùng giá trị tính toán, không lấy từ Inventory)
            data["safety_stock"] = data["predicted_need_total"]
            
            # Đề xuất nhập = max(0, Nhu cầu cuối - Tồn kho)
            data["suggested_import"] = max(0, data["predicted_need_total"] - data["current_stock"])
            data["status"] = (
                "shortage" if data["suggested_import"] > 0 else "sufficient"
            )
            data.update(phan_muc_canh_bao(
                data["need_before_buffer_total"], data["predicted_need_total"],
                data["current_stock"], data.get("found", True),
                data.get("unit") or "", data["suggested_import"]))
            agg_items.append(data)

        agg_items.sort(key=lambda x: x["suggested_import"], reverse=True)

        return {
            "forecast_month": forecast_month.isoformat(),
            "location": location,
            "buffer_rate": buffer_rate,
            "diseases": per_disease,
            "total_supplies": len(agg_items),
            "items": agg_items,
        }

    def _get_predicted_cases(
        self,
        icd_code: str,
        forecast_month: date,
        location: Optional[str] = None,
    ) -> int:
        """Lấy số ca dự báo cho 1 bệnh trong 1 tháng.

        Ưu tiên:
        1. disease_forecast (nếu đã chạy phân tích)
        2. Fallback: tổng case_count từ disease_cases (dữ liệu thực tế)

        Lưu ý quan trọng về địa lý:
        - Nếu CHỈ ĐỊNH location → lấy đúng forecast mới nhất của khu vực đó.
        - Nếu KHÔNG chỉ định (toàn quốc) → KHÔNG được SUM tất cả forecast vì các
          khu vực chồng lấn ("Toàn thành phố" ⊇ "TP. Hồ Chí Minh" ⊇ "Quận 1")
          sẽ bị đếm trùng. Thay vào đó lấy bản ghi forecast MỚI NHẤT
          (theo created_at) cho (icd, tháng) — phản ánh lần phân tích gần nhất.
        """
        base = self.db.query(DiseaseForecast).filter(
            DiseaseForecast.icd_code == icd_code,
            extract("year", DiseaseForecast.forecast_date) == forecast_month.year,
            extract("month", DiseaseForecast.forecast_date) == forecast_month.month,
        )

        if location:
            # Đúng 1 khu vực → lấy forecast mới nhất của khu vực đó
            from app.utils.province_alias import province_aliases
            latest = (
                base.filter(DiseaseForecast.location.in_(province_aliases(location)))
                .order_by(DiseaseForecast.created_at.desc())
                .first()
            )
            if latest and latest.predicted_cases:
                return int(latest.predicted_cases)
        else:
            # Toàn quốc → ưu tiên lấy forecast có location=NULL (toàn thành phố/toàn quốc)
            nationwide = (
                base.filter(DiseaseForecast.location.is_(None))
                .order_by(DiseaseForecast.created_at.desc())
                .first()
            )
            if nationwide and nationwide.predicted_cases:
                return int(nationwide.predicted_cases)
            
            # Fallback: lấy bản ghi mới nhất của bất kỳ khu vực nào
            latest = base.order_by(DiseaseForecast.created_at.desc()).first()
            if latest and latest.predicted_cases:
                return int(latest.predicted_cases)

        # 2. Fallback: tổng case_count thực tế.
        # dieu_kien_benh: icd_code giờ có thể là KHOÁ NHÓM ('J09-J18') vì
        # severity_rates đã chuyển sang mức nhóm — so bằng (=) sẽ ra 0 ca
        # và nhóm bị bỏ qua trong tính nhu cầu một cách âm thầm.
        from app.utils.icd_groups import dieu_kien_benh
        q2 = self.db.query(func.sum(DiseaseCase.case_count)).filter(
            dieu_kien_benh(DiseaseCase, icd_code),
            extract("year", DiseaseCase.recorded_at) == forecast_month.year,
            extract("month", DiseaseCase.recorded_at) == forecast_month.month,
        )
        if location:
            from app.utils.province_alias import province_aliases
            q2 = q2.filter(DiseaseCase.location.in_(province_aliases(location)))
        return int(q2.scalar() or 0)

    # ── Persistence ─────────────────────────────────────────────────────────

    def save_recommendations(
        self,
        recommendations: Dict[str, Any],
        created_by: Optional[str] = None,
    ) -> int:
        """Lưu kết quả tính toán vào bảng supply_recommendations.

        Args:
            recommendations: Output từ calculate_for_disease()
            created_by: Username người tạo

        Returns:
            Số dòng đã lưu
        """
        forecast_month = date.fromisoformat(recommendations["forecast_month"])
        icd_code = recommendations["icd_code"]
        disease_name = recommendations["disease_name"]
        breakdown = recommendations["severity_breakdown"]

        # Xóa dữ liệu cũ cho cùng (forecast_month, icd_code) để tránh trùng
        self.db.query(SupplyRecommendation).filter(
            and_(
                SupplyRecommendation.forecast_month == forecast_month,
                SupplyRecommendation.icd_code == icd_code,
            )
        ).delete(synchronize_session=False)

        count = 0
        for it in recommendations["items"]:
            rec = SupplyRecommendation(
                forecast_month=forecast_month,
                icd_code=icd_code,
                disease_name=disease_name,
                supply_id=it["supply_id"],
                drug_code=it["drug_code"],
                ten_hoat_chat=it["ten_hoat_chat"],
                predicted_cases=recommendations["predicted_cases"],
                predicted_mild=breakdown["mild_cases"],
                predicted_moderate=breakdown["moderate_cases"],
                predicted_severe=breakdown["severe_cases"],
                need_before_buffer=it["need_before_buffer"],
                buffer_rate=it["buffer_rate"],
                predicted_need=it["predicted_need"],
                current_stock=it["current_stock"],
                safety_stock=it["safety_stock"],
                suggested_import=it["suggested_import"],
                status="pending",
                created_by=created_by,
            )
            self.db.add(rec)
            count += 1

        self.db.commit()
        logger.info(
            "Saved %d supply recommendations for %s (%s)",
            count, icd_code, forecast_month,
        )
        return count
