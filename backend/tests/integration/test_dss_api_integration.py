# -*- coding: utf-8 -*-
"""Hợp đồng API DSS trên CSDL rỗng: trả 200 kèm trạng thái chưa có dữ liệu, không 500;
PUT /dss/params kiểm khoảng và ràng buộc Đỏ < Vàng.
"""
import json

import pytest
from sqlalchemy import text

from app.data_pipeline import views
from app.data_pipeline.models import MartMonthlyCasesByBlock  # noqa: F401  (đăng ký bảng)


@pytest.fixture
def dss_db(db_engine, db_session):
    """Dựng bảng mart, bảng tự quản, cấu hình DSS và view trên CSDL test."""
    from app.data_pipeline.models import Base as _B          # cùng Base với app
    _B.metadata.create_all(bind=db_engine)
    views.dam_bao_luoc_do(engine=db_engine, db=db_session)
    return db_session


def test_dashboard_v2_db_rong(client, admin_headers, dss_db):
    r = client.get("/api/v1/dashboard/v2", headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("meta", "cases", "forecast", "demand", "risk", "catalogue", "alerts",
              "doi_by_category", "trend", "care_level", "quality", "data_status", "insights"):
        assert k in d, k
    assert d["forecast"]["ready"] is False
    assert d["demand"]["ready"] is False
    assert d["risk"]["counts"]["total"] == 0
    assert d["meta"]["thresholds"] == {"red_days": 18.0, "amber_days": 36.0}


def test_dashboard_v2_level_sai_400(client, admin_headers, dss_db):
    r = client.get("/api/v1/dashboard/v2?level=blue", headers=admin_headers)
    assert r.status_code == 400


def test_alerts_v2_db_rong(client, admin_headers, dss_db):
    r = client.get("/api/v1/dashboard/v2/alerts?focus=false&limit=10", headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total"] == 0 and d["rows"] == []
    assert d["counts"]["san_sang"] in (True, False)
    assert "basis" in d and "DOI" in d["basis"]


def test_dss_params_get_put(client, admin_headers, dss_db):
    r = client.get("/api/v1/dss/params", headers=admin_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["thresholds"]["gia_tri"]["doi_red_days"] == 18
    assert d["care_level"]["gia_tri"]["min_period"] == "2025-04"

    # Đỏ ≥ Vàng → 422
    r = client.put("/api/v1/dss/params", headers=admin_headers,
                   json={"thresholds": {"doi_red_days": 40}})
    assert r.status_code == 422
    # Khoá lạ → 422
    r = client.put("/api/v1/dss/params", headers=admin_headers,
                   json={"care_level": {"abc": 1}})
    assert r.status_code == 422
    # Hợp lệ → lưu, đọc lại thấy
    r = client.put("/api/v1/dss/params", headers=admin_headers,
                   json={"thresholds": {"doi_red_days": 14, "doi_amber_days": 28},
                         "care_level": {"min_period": "2025-06"}})
    assert r.status_code == 200, r.text
    assert r.json()["da_doi"]["thresholds"] == {"doi_red_days": 14, "doi_amber_days": 28}
    raw = dss_db.execute(text("SELECT config_value FROM system_config "
                              "WHERE config_key = 'dss.thresholds'")).scalar()
    assert json.loads(raw)["doi_red_days"] == 14


def test_config_put_chan_khoa_chuyen_biet(client, admin_headers, dss_db):
    for k in ("dss.thresholds", "dss.care_level", "his_sync.connection"):
        r = client.put(f"/api/v1/config/{k}", headers=admin_headers,
                       json={"config_value": "{}"})
        assert r.status_code == 422, k


def test_dss_norms_db_rong(client, admin_headers, dss_db):
    r = client.get("/api/v1/dss/norms?block=J00-J06", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 0
    r = client.get("/api/v1/dss/norms?block=K00", headers=admin_headers)
    assert r.status_code == 400


def test_report_dashboard_summary_db_rong(client, admin_headers, dss_db):
    r = client.post("/api/v1/reports/export", headers=admin_headers,
                    json={"report_type": "dashboard-summary", "format": "excel"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_report_ton_kho_thuoc_theo_doi(client, admin_headers, dss_db):
    """Báo cáo Tồn kho xuất được Excel và PDF trên CSDL rỗng (ngưỡng mặc định 18/36)."""
    for fmt, ct in (("excel", "application/vnd.openxmlformats"), ("pdf", "application/pdf")):
        r = client.post("/api/v1/reports/export", headers=admin_headers,
                        json={"report_type": "inventory", "format": fmt})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith(ct)


def test_alerts_v2_limit_toan_danh_muc(client, admin_headers, dss_db):
    """Danh mục DOI lấy được trong một lần gọi với limit 2000."""
    assert client.get("/api/v1/dashboard/v2/alerts?focus=false&limit=2000",
                      headers=admin_headers).status_code == 200
    assert client.get("/api/v1/dashboard/v2/alerts?focus=false&limit=2001",
                      headers=admin_headers).status_code == 422


def test_supply_requirements_summary_db_rong(client, admin_headers, dss_db):
    r = client.get("/api/v1/supply-requirements/summary", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["total_supplies"] == 0


def test_endpoint_cu_da_go(client, admin_headers, dss_db):
    for path in ("/api/v1/dashboard/overview", "/api/v1/dashboard/summary",
                 "/api/v1/dashboard/risk-status", "/api/v1/dashboard/critical-alerts",
                 "/api/v1/forecast-hier/blocks", "/api/v1/supplies",
                 "/api/v1/admin/safety-rate", "/api/v1/supply-requirements"):
        assert client.get(path, headers=admin_headers).status_code == 404, path
