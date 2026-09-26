"""API tham số DSS và bảng tra định mức thực nghiệm cho màn Quản trị.
Quản lý hai khoá system_config: dss.care_level (Tầng 2) và dss.thresholds (Tầng 3).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from app.models.user import User
from app.schemas.base import SystemConfigUpdate
from app.services import dss_alerts, dss_demand
from app.services.config_service import ConfigService

router = APIRouter(tags=["dss-config"])
logger = logging.getLogger(__name__)


# ── Mô tả tham số (hiển thị dưới ô nhập) ──

MO_TA: Dict[str, Dict[str, Dict[str, Any]]] = {
    "thresholds": {
        "doi_red_days": {
            "ten": "Ngưỡng Đỏ (ngày tồn kho)",
            "y_nghia": "DOI ≤ giá trị này → Đỏ. Mặc định 18 = trung vị chu kỳ nhập kho thực tế của bệnh viện.",
            "min": 1, "max": 365},
        "doi_amber_days": {
            "ten": "Ngưỡng Vàng (ngày tồn kho)",
            "y_nghia": "Đỏ < DOI ≤ giá trị này → Vàng; lớn hơn → Xanh. Mặc định 36 = hai chu kỳ nhập.",
            "min": 2, "max": 730},
        "horizon_days": {
            "ten": "Chân trời nhu cầu (ngày)",
            "y_nghia": ("Cột 'Nhu cầu dự báo' và 'Thiếu hụt' tính cho bấy nhiêu ngày tới. "
                        "KHÔNG đổi DOI và không đổi màu: D_i co giãn theo tham số này nên "
                        "D_i / horizon giữ nguyên. Đặt bằng ngưỡng Vàng thì mọi mã Đỏ/Vàng "
                        "đều có số thiếu hụt > 0."),
            "min": 7, "max": 180},
        "fefo_window_days": {
            "ten": "Cửa sổ cận date (ngày)",
            "y_nghia": ("Chỉ để THỐNG KÊ: lượng của lô hết hạn trong vòng bấy nhiêu ngày mà "
                        "không kịp dùng được cộng vào cột 'sắp hết hạn'. Tồn hữu dụng FEFO "
                        "không phụ thuộc tham số này."),
            "min": 0, "max": 365},
    },
    "care_level": {
        "window_periods": {
            "ten": "Cửa sổ tính định mức (kỳ)",
            "y_nghia": "Số tháng gần nhất dùng để tính tỷ trọng rổ p̂ và định mức Norm. Đổi giá trị này là đổi mẫu số của mọi định mức.",
            "min": 3, "max": 36},
        "min_period": {
            "ten": "Kỳ sớm nhất được dùng",
            "y_nghia": "Không lấy dữ liệu trước kỳ này (cách ghi nhận phân cấp chăm sóc trong HIS thay đổi từ đầu 2025). Định dạng YYYY-MM.",
            "kieu": "ky"},
        "min_cases_per_bucket": {
            "ten": "Ngưỡng mẫu nhỏ (ca / rổ)",
            "y_nghia": "Rổ có ít hơn bấy nhiêu ca trong cửa sổ thì dùng định mức GỘP toàn nhóm thay vì chia cho vài ca.",
            "min": 1, "max": 1000},
        "shrink_k0": {
            "ten": "Hằng co ngót K₀",
            "y_nghia": "Tỷ trọng rổ mẫu nhỏ được tin λ = n/(n+K₀); phần còn lại kéo về phân bố đều. K₀ càng lớn càng thận trọng.",
            "min": 0, "max": 100},
    },
}


class DssParamsUpdate(BaseModel):
    thresholds: Optional[Dict[str, Any]] = Field(None, description="Khoá con của dss.thresholds cần đổi")
    care_level: Optional[Dict[str, Any]] = Field(None, description="Khoá con của dss.care_level cần đổi")


def _doc_hien_tai(db: Session) -> Dict[str, Any]:
    th = dss_alerts.get_thresholds(db)
    cl = dss_demand.care_cfg(db)
    return {
        "thresholds": {
            "gia_tri": {k: th.get(k) for k in dss_alerts.THRESHOLDS_DEFAULT},
            "mac_dinh": dict(dss_alerts.THRESHOLDS_DEFAULT),
            "mo_ta": MO_TA["thresholds"],
            "nguon": th.get("nguon"),
            "config_key": "dss.thresholds",
        },
        "care_level": {
            "gia_tri": {k: cl.get(k) for k in dss_demand.CARE_LEVEL_DEFAULT},
            "mac_dinh": dict(dss_demand.CARE_LEVEL_DEFAULT),
            "mo_ta": MO_TA["care_level"],
            "nguon": cl.get("nguon"),
            "config_key": "dss.care_level",
        },
        "cong_thuc": [
            "Tầng 1  Ŷ_g — ensemble thống kê theo nhóm ICD (J00-J06 / J09-J18 / J20-J22)",
            "Tầng 2  D_i = Σ_ro Ŷ_g · p̂(g,ro) · Norm(i,g,ro) + D_nền,i",
            "        p̂(g,ro) = ca(g,ro)/ca(g); Norm(i,g,ro) = Σ tiêu hao / Σ ca — cùng cửa sổ window_periods",
            "Tầng 3  DOI_i = tồn hữu dụng FEFO_i / (D_i / horizon_days); Đỏ ≤ doi_red_days, Vàng ≤ doi_amber_days",
            "        Thiếu hụt_i = D_i − tồn hữu dụng_i, không âm (chưa trừ hàng đang về)",
            "        mã không có D_i → không có mẫu số → Xám, lý do 'chưa có dự báo'",
        ],
    }


@router.get("/params")
def get_params(db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Giá trị hiện hành, mặc định và mô tả của tham số Tầng 2 / Tầng 3, kèm công thức."""
    return _doc_hien_tai(db)


def _kiem(nhom: str, gia_tri: Dict[str, Any]) -> Dict[str, Any]:
    """Ép kiểu và kiểm tra miền giá trị; trả dict đã làm sạch, sai thì 422."""
    out: Dict[str, Any] = {}
    for k, v in gia_tri.items():
        mt = MO_TA[nhom].get(k)
        if mt is None:
            raise HTTPException(422, f"Khoá không hợp lệ: {nhom}.{k}")
        if mt.get("kieu") == "ky":
            sv = str(v).strip()
            if len(sv) != 7 or sv[4] != "-" or not (sv[:4].isdigit() and sv[5:].isdigit()) \
                    or not 1 <= int(sv[5:]) <= 12:
                raise HTTPException(422, f"{k} phải có dạng YYYY-MM")
            out[k] = sv
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            raise HTTPException(422, f"{k} phải là số")
        if not (mt["min"] <= fv <= mt["max"]):
            raise HTTPException(422, f"{k} phải trong [{mt['min']}, {mt['max']}]")
        out[k] = int(fv) if fv.is_integer() else fv
    return out


@router.put("/params")
def update_params(body: DssParamsUpdate, request: Request,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_admin_user)) -> Dict[str, Any]:
    """Sửa một phần hoặc toàn bộ tham số (Admin); khoá không gửi giữ nguyên, có ghi audit_logs."""
    svc = ConfigService(db)
    ip = request.client.host if request.client else "unknown"
    da_doi: Dict[str, Any] = {}

    if body.thresholds:
        moi = _kiem("thresholds", body.thresholds)
        hien = dss_alerts.get_thresholds(db)
        gop = {**hien, **moi}
        if float(gop["doi_red_days"]) >= float(gop["doi_amber_days"]):
            raise HTTPException(422, "Ngưỡng Đỏ phải nhỏ hơn ngưỡng Vàng.")
        svc.update_config("dss.thresholds",
                          SystemConfigUpdate(config_value=json.dumps(gop, ensure_ascii=False)),
                          updated_by_user_id=current_user.id, ip_address=ip)
        da_doi["thresholds"] = moi

    if body.care_level:
        moi = _kiem("care_level", body.care_level)
        hien = dss_demand.care_cfg(db)
        gop = {**hien, **moi}
        svc.update_config("dss.care_level",
                          SystemConfigUpdate(config_value=json.dumps(gop, ensure_ascii=False)),
                          updated_by_user_id=current_user.id, ip_address=ip)
        da_doi["care_level"] = moi

    if not da_doi:
        raise HTTPException(422, "Không có gì để lưu.")
    logger.info("DSS params đổi bởi %s: %s", current_user.username, da_doi)
    out = _doc_hien_tai(db)
    out["da_doi"] = da_doi
    return out


@router.get("/norms")
def get_norms(block: str = Query("J00-J06", description="J00-J06 | J09-J18 | J20-J22"),
              q: Optional[str] = Query(None, description="Lọc theo mã / tên hoạt chất"),
              limit: int = Query(50, ge=1, le=500),
              offset: int = Query(0, ge=0),
              db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Định mức thực nghiệm Tầng 2 đang dùng (chỉ đọc, tự cập nhật sau đồng bộ HIS)."""
    try:
        return dss_demand.norms_payload(db, block=block, q=q, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
