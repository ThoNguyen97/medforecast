"""Tham số DSS và bảng tra định mức thực nghiệm — màn Quản trị (12/09/2026).

Routes
------
GET  /api/v1/dss/params     – Toàn bộ núm vặn của Tầng 2 + Tầng 3 (mọi người đọc được)
PUT  /api/v1/dss/params     – Sửa (Admin), ghi audit_logs qua ConfigService
GET  /api/v1/dss/norms      – Định mức thực nghiệm theo nhóm × rổ × mã (chỉ đọc)

Vì sao có file này
------------------
Trước 12/09 màn Quản trị có ba tab (Tỷ lệ Nhẹ/TB/Nặng, Định mức thuốc/vật
tư, Ngưỡng cảnh báo) sửa ba bảng mà DSS thật không đọc: Tầng 2 dùng định mức
THỰC NGHIỆM từ fact_usage/cases_by_care_level, Tầng 3 đọc `dss.thresholds`.
Bấm "Lưu" ở ba tab đó không đổi gì trên Dashboard. Ba tab được thay bằng
hai tab nối thẳng vào hai bản ghi `system_config` mà DSS thật sự đọc.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from app.models.user import User
from app.schemas.base import SystemConfigUpdate
from app.services import dss_alerts, dss_demand
from app.services.config_service import ConfigService

router = APIRouter(tags=["dss-config"])
logger = logging.getLogger(__name__)


# ── Mô tả từng tham số — hiện ngay dưới ô nhập để người sửa biết hệ quả ──────

MO_TA: Dict[str, Dict[str, Dict[str, Any]]] = {
    "thresholds": {
        "doi_red_days": {
            "ten": "Ngưỡng Đỏ (ngày tồn kho)",
            "y_nghia": "DOI ≤ giá trị này → Đỏ. Mặc định 18 = trung vị chu kỳ nhập kho đo ở Đ9.",
            "min": 1, "max": 365},
        "doi_amber_days": {
            "ten": "Ngưỡng Vàng (ngày tồn kho)",
            "y_nghia": "Đỏ < DOI ≤ giá trị này → Vàng; lớn hơn → Xanh. Mặc định 36 = hai chu kỳ nhập.",
            "min": 2, "max": 730},
        "horizon_days": {
            "ten": "Chân trời nhu cầu (ngày)",
            "y_nghia": "Nhu cầu dự báo D_i và thiếu hụt Δ = max(0, D_i − tồn hữu dụng) quy về số ngày này.",
            "min": 7, "max": 180},
        "fefo_window_days": {
            "ten": "Cửa sổ FEFO (ngày)",
            "y_nghia": "Lô hết hạn trong vòng bấy nhiêu ngày bị trừ khỏi tồn hữu dụng.",
            "min": 0, "max": 365},
        "overstock_factor": {
            "ten": "Hệ số tồn dư",
            "y_nghia": "Tồn hữu dụng > hệ số × nhu cầu chân trời được ghi chú là tồn dư (chỉ ghi chú, không đổi màu).",
            "min": 1, "max": 10},
    },
    "care_level": {
        "window_periods": {
            "ten": "Cửa sổ tính định mức (kỳ)",
            "y_nghia": "Số tháng gần nhất dùng để tính tỷ trọng rổ p̂ và định mức Norm. Đổi giá trị này là đổi mẫu số của mọi định mức.",
            "min": 3, "max": 36},
        "min_period": {
            "ten": "Kỳ sớm nhất được dùng",
            "y_nghia": "Không lấy dữ liệu trước kỳ này (Đ11: chế độ ghi nhận phân cấp đứt gãy đầu 2025). Định dạng YYYY-MM.",
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
            "Tầng 1  Ŷ_g — ensemble M12 theo nhóm ICD (J00-J06 / J09-J18 / J20-J22)",
            "Tầng 2  D_i = Σ_ro Ŷ_g · p̂(g,ro) · Norm(i,g,ro) + D_nền,i",
            "        p̂(g,ro) = ca(g,ro)/ca(g); Norm(i,g,ro) = Σ tiêu hao / Σ ca — cùng cửa sổ window_periods",
            "Tầng 3  DOI_i = tồn hữu dụng FEFO_i / (D_i / horizon_days); Đỏ ≤ doi_red_days, Vàng ≤ doi_amber_days",
        ],
    }


@router.get("/params")
def get_params(db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Hai bản ghi system_config mà Tầng 2 / Tầng 3 thật sự đọc, kèm mô tả."""
    return _doc_hien_tai(db)


def _kiem(nhom: str, gia_tri: Dict[str, Any]) -> Dict[str, Any]:
    """Ép kiểu + kiểm khoảng. Trả dict đã làm sạch; sai thì 422."""
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
    """Sửa một phần hoặc toàn bộ. Khoá không gửi giữ nguyên; ghi chú `nguon`
    trong JSON được giữ. Mỗi lần lưu là một dòng audit_logs (UPDATE_CONFIG)."""
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
    """Định mức thực nghiệm đang được Tầng 2 dùng — đúng con số nhân với
    Ŷ_g × p̂ — để kiểm chứng tại chỗ. Chỉ đọc: định mức tự cập nhật mỗi lần
    đồng bộ HIS, không có ô nhập tay."""
    try:
        return dss_demand.norms_payload(db, block=block, q=q, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
