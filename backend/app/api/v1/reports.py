"""Báo cáo — xem trước JSON và xuất PDF/Excel.

Routes
------
GET  /api/v1/reports/forecast-accuracy   độ lệch dự báo/thực tế theo bản ghi disease_forecasts
POST /api/v1/reports/export              xuất một trong 6 loại: epidemic, forecast, inventory,
                                         shortage, forecast-accuracy, dashboard-summary

Mọi con số về ca bệnh neo vào kỳ ĐÃ CHỐT (period_service); mọi con số về thiếu
hụt đi qua đúng chuỗi Tầng 1→2→3 của dss_dashboard/dss_alerts — báo cáo xuất ra
không được lệch với màn hình. Hai báo cáo cũ `consumption` và `inventory-turnover`
(đọc bảng supply_requirements đã ngừng sinh dữ liệu) gỡ 13/09/2026.
"""

import io
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.disease_forecast import DiseaseForecast
from app.models.inventory import Inventory
from app.models.medical_supply import MedicalSupply
from app.models.user import User


def _month_expr(col, fmt: str):
    """Định dạng tháng trên SQLite ('%m/%Y' hoặc '%Y-%m'). Hệ thống chỉ chạy
    SQLite (Postgres đã archive), không còn nhánh dialect."""
    return func.strftime(fmt, col)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])

# Ngưỡng DOI mặc định — chỉ dùng làm nhãn trong báo cáo tồn kho khi chưa đọc
# được dss.thresholds; phân loại thiếu hụt thật đi qua dss_alerts.
DOI_DO_NGAY = 18
DOI_VANG_NGAY = 36


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_date_range(
    start_date: Optional[date],
    end_date: Optional[date],
    default_days_back: int = 30,
    default_days_forward: int = 60,
):
    """Khoảng ngày mặc định: 30 ngày lùi → 60 ngày tới (bao cả kỳ dự báo)."""
    today = date.today()
    end = end_date or (today + timedelta(days=default_days_forward))
    start = start_date or (today - timedelta(days=default_days_back))
    return start, end


# ── Consumption Report ────────────────────────────────────────────────────────

# ── Forecast Accuracy Report ──────────────────────────────────────────────────

@router.get("/forecast-accuracy")
async def get_forecast_accuracy_report(
    start_date: Optional[date] = Query(None, description="Report start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Report end date (YYYY-MM-DD)"),
    disease_type: Optional[str] = Query(
        None,
        description="Filter by disease type: dengue_fever, seasonal_flu, respiratory_disease",
    ),
    model_used: Optional[str] = Query(
        None,
        description="Filter by model: xgboost, lstm, prophet, ensemble",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """
    Return forecast accuracy metrics over time.

    Shows MAE, RMSE, and MAPE trends for each model, broken down by disease
    type.  Useful for monitoring model performance degradation over time.

    Filters
    -------
    start_date   : start of the reporting period (default: 30 days ago)
    end_date     : end of the reporting period (default: today)
    disease_type : restrict to a specific disease
    model_used   : restrict to a specific model name
    """
    start, end = _default_date_range(start_date, end_date)

    logger.info(
        "Forecast accuracy report requested by user=%s period=%s to %s "
        "disease_type=%s model_used=%s",
        current_user.username, start, end, disease_type, model_used,
    )

    query = (
        db.query(
            DiseaseForecast.forecast_date,
            DiseaseForecast.disease_type,
            DiseaseForecast.model_used,
            DiseaseForecast.model_accuracy_mae,
            DiseaseForecast.model_accuracy_rmse,
            DiseaseForecast.model_accuracy_mape,
            DiseaseForecast.predicted_cases,
            DiseaseForecast.confidence_lower,
            DiseaseForecast.confidence_upper,
        )
        .filter(
            DiseaseForecast.forecast_date >= start,
            DiseaseForecast.forecast_date <= end,
        )
    )

    if disease_type:
        query = query.filter(DiseaseForecast.disease_type == disease_type)
    if model_used:
        query = query.filter(DiseaseForecast.model_used == model_used)

    rows = query.order_by(DiseaseForecast.forecast_date).all()

    # Aggregate per model
    model_stats: Dict[str, Dict] = {}
    time_series: List[Dict] = []

    for row in rows:
        model = row.model_used or "unknown"
        if model not in model_stats:
            model_stats[model] = {
                "model": model,
                "sample_count": 0,
                "mae_values": [],
                "rmse_values": [],
                "mape_values": [],
            }
        stats = model_stats[model]
        stats["sample_count"] += 1
        if row.model_accuracy_mae is not None:
            stats["mae_values"].append(float(row.model_accuracy_mae))
        if row.model_accuracy_rmse is not None:
            stats["rmse_values"].append(float(row.model_accuracy_rmse))
        if row.model_accuracy_mape is not None:
            stats["mape_values"].append(float(row.model_accuracy_mape))

        time_series.append({
            "date": str(row.forecast_date),
            "disease_type": row.disease_type,
            "model": model,
            "predicted_cases": row.predicted_cases,
            "confidence_lower": row.confidence_lower,
            "confidence_upper": row.confidence_upper,
            "mae": float(row.model_accuracy_mae) if row.model_accuracy_mae is not None else None,
            "rmse": float(row.model_accuracy_rmse) if row.model_accuracy_rmse is not None else None,
            "mape": float(row.model_accuracy_mape) if row.model_accuracy_mape is not None else None,
        })

    # Compute averages per model
    model_summary = []
    for model, stats in model_stats.items():
        mae_vals = stats["mae_values"]
        rmse_vals = stats["rmse_values"]
        mape_vals = stats["mape_values"]
        model_summary.append({
            "model": model,
            "sample_count": stats["sample_count"],
            "avg_mae": round(sum(mae_vals) / len(mae_vals), 4) if mae_vals else None,
            "avg_rmse": round(sum(rmse_vals) / len(rmse_vals), 4) if rmse_vals else None,
            "avg_mape": round(sum(mape_vals) / len(mape_vals), 4) if mape_vals else None,
            "min_mae": round(min(mae_vals), 4) if mae_vals else None,
            "min_rmse": round(min(rmse_vals), 4) if rmse_vals else None,
        })

    # Best model by lowest avg MAPE
    best_model = None
    if model_summary:
        ranked = sorted(
            [m for m in model_summary if m["avg_mape"] is not None],
            key=lambda m: m["avg_mape"],
        )
        if ranked:
            best_model = ranked[0]["model"]

    return {
        "report_type": "forecast-accuracy",
        "period": {"start_date": str(start), "end_date": str(end)},
        "filters": {"disease_type": disease_type, "model_used": model_used},
        "summary": {
            "total_forecasts": len(rows),
            "models_evaluated": len(model_stats),
            "best_model_by_mape": best_model,
        },
        "model_performance": model_summary,
        "time_series": time_series,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ── Inventory Turnover Report ─────────────────────────────────────────────────

# ── Export Report ─────────────────────────────────────────────────────────────

class ReportExportRequest:
    """Simple holder – we use a Pydantic model below."""


from pydantic import BaseModel


class ExportReportRequest(BaseModel):
    """Body của POST /export."""

    report_type: str          # epidemic | forecast | inventory | shortage | forecast-accuracy | dashboard-summary
    format: str = "pdf"       # pdf | excel

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location: Optional[str] = None
    category: Optional[str] = None
    disease_type: Optional[str] = None
    model_used: Optional[str] = None


@router.post("/export")
async def export_report(
    payload: ExportReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Xuất PDF/Excel: epidemic (tình hình dịch bệnh), forecast (dự báo ca),
    inventory (tồn kho), shortage (thiếu hụt), forecast-accuracy (độ lệch
    dự báo), dashboard-summary (toàn bộ KPI Tổng quan)."""
    SUPPORTED_TYPES = {
        "epidemic", "forecast", "inventory", "shortage",
        "forecast-accuracy", "dashboard-summary",
    }
    if payload.report_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported report_type '{payload.report_type}'. "
                   f"Must be one of: {sorted(SUPPORTED_TYPES)}",
        )

    if payload.format not in ("pdf", "excel"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{payload.format}'. Use 'pdf' or 'excel'.",
        )

    logger.info(
        "Export report type=%s format=%s requested by user=%s",
        payload.report_type, payload.format, current_user.username,
    )

    start, end = _default_date_range(payload.start_date, payload.end_date)

    if payload.report_type == "forecast-accuracy":
        data = await _build_accuracy_data(db, start, end, payload.disease_type, payload.model_used)
        return (
            _render_accuracy_pdf(data, start, end)
            if payload.format == "pdf"
            else _render_accuracy_excel(data, start, end)
        )

    if payload.report_type == "dashboard-summary":
        data = await _build_dashboard_summary_data(db)
        return (
            _render_dashboard_summary_pdf(data)
            if payload.format == "pdf"
            else _render_dashboard_summary_excel(data)
        )

    if payload.report_type == "epidemic":
        data = await _build_epidemic_data(db, start, end, payload.disease_type, payload.location)
        return (
            _render_epidemic_pdf(data, start, end)
            if payload.format == "pdf"
            else _render_epidemic_excel(data, start, end)
        )

    if payload.report_type == "forecast":
        data = await _build_forecast_data(db, start, end, payload.disease_type, payload.location)
        return (
            _render_forecast_pdf(data, start, end)
            if payload.format == "pdf"
            else _render_forecast_excel(data, start, end)
        )

    if payload.report_type == "inventory":
        data = await _build_inventory_data(db, payload.category)
        return (
            _render_inventory_pdf(data)
            if payload.format == "pdf"
            else _render_inventory_excel(data)
        )

    if payload.report_type == "shortage":
        data = await _build_shortage_data(db, start, end, payload.disease_type)
        return (
            _render_shortage_pdf(data, start, end)
            if payload.format == "pdf"
            else _render_shortage_excel(data, start, end)
        )

    # Không tới được: SUPPORTED_TYPES đã chặn từ đầu hàm. Giữ 400 để tường minh.
    raise HTTPException(status_code=400,
                        detail=f"Loại báo cáo không hỗ trợ: {payload.report_type}")


# ── Internal data-fetching helpers (reused by export) ────────────────────────

async def _build_accuracy_data(
    db: Session,
    start: date,
    end: date,
    disease_type: Optional[str],
    model_used: Optional[str],
) -> list:
    query = db.query(DiseaseForecast).filter(
        DiseaseForecast.forecast_date >= start,
        DiseaseForecast.forecast_date <= end,
    )
    if disease_type:
        query = query.filter(DiseaseForecast.disease_type == disease_type)
    if model_used:
        query = query.filter(DiseaseForecast.model_used == model_used)
    return query.order_by(DiseaseForecast.forecast_date).all()


# ── PDF rendering helpers ─────────────────────────────────────────────────────

# Đăng ký font Unicode (DejaVu Sans) một lần khi module load — hỗ trợ tiếng Việt.
# Nếu register thất bại, các renderer sẽ tự fallback về Helvetica (không có dấu).
PDF_FONT_REGULAR = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"
_FONT_REGISTERED = False


def _register_unicode_fonts() -> None:
    """Đăng ký DejaVu Sans (Regular + Bold) nếu chưa đăng ký.

    Các font này đi kèm matplotlib (là dependency hiện có) nên không cần
    phụ thuộc vào font hệ thống. Nếu không tìm thấy, giữ font Helvetica
    mặc định và log cảnh báo.
    """
    global _FONT_REGISTERED, PDF_FONT_REGULAR, PDF_FONT_BOLD
    if _FONT_REGISTERED:
        return
    try:
        import os
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # Tìm thư mục font DejaVu trong matplotlib
        try:
            import matplotlib  # type: ignore

            font_dir = os.path.join(
                os.path.dirname(matplotlib.__file__),
                "mpl-data",
                "fonts",
                "ttf",
            )
            regular = os.path.join(font_dir, "DejaVuSans.ttf")
            bold = os.path.join(font_dir, "DejaVuSans-Bold.ttf")
        except Exception:
            regular = bold = ""

        # Fallback: font hệ thống macOS / Linux
        if not (os.path.exists(regular) and os.path.exists(bold)):
            for candidate in (
                "/Library/Fonts/Arial Unicode.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ):
                if os.path.exists(candidate):
                    regular = candidate
                    bold = candidate  # cùng file dùng cho cả bold (sẽ bold giả lập)
                    break

        if not (regular and os.path.exists(regular)):
            logger.warning(
                "PDF font: không tìm thấy font Unicode, giữ Helvetica (không hỗ trợ tiếng Việt)."
            )
            _FONT_REGISTERED = True
            return

        pdfmetrics.registerFont(TTFont("DejaVuSans", regular))
        if bold and os.path.exists(bold) and bold != regular:
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold))
            PDF_FONT_BOLD = "DejaVuSans-Bold"
        else:
            PDF_FONT_BOLD = "DejaVuSans"
        PDF_FONT_REGULAR = "DejaVuSans"

        # Map family để các style có thể dùng <b>...</b> trong Paragraph
        from reportlab.pdfbase.pdfmetrics import registerFontFamily

        registerFontFamily(
            "DejaVuSans",
            normal="DejaVuSans",
            bold=PDF_FONT_BOLD,
            italic="DejaVuSans",
            boldItalic=PDF_FONT_BOLD,
        )
        logger.info("PDF font: registered DejaVu Sans Unicode fonts.")
    except Exception as exc:
        logger.warning("PDF font registration failed: %s", exc)
    finally:
        _FONT_REGISTERED = True


def _get_reportlab():
    """Import reportlab or raise a clean 500 error."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Spacer,
        )
        # Đăng ký font Unicode (idempotent)
        _register_unicode_fonts()
        return colors, A4, landscape, getSampleStyleSheet, cm, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="reportlab library not available for PDF export",
        )


def _patch_styles_for_unicode(styles) -> None:
    """Áp dụng font Unicode lên tất cả các paragraph styles (Title, Heading, Normal, Italic...)."""
    for name in (
        "Normal",
        "BodyText",
        "Italic",
        "Title",
        "Heading1",
        "Heading2",
        "Heading3",
        "Heading4",
    ):
        try:
            style = styles[name]
            # Dùng bold hay regular tuỳ tên style
            if "Heading" in name or name == "Title":
                style.fontName = PDF_FONT_BOLD
            else:
                style.fontName = PDF_FONT_REGULAR
        except KeyError:
            pass


def _base_table_style(colors):
    """Return a shared base TableStyle list."""
    return [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (-1, -1), PDF_FONT_REGULAR),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EBF3FB")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]


def _render_accuracy_pdf(forecasts: list, start: date, end: date) -> Response:
    colors, A4, landscape, getSampleStyleSheet, cm, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer = _get_reportlab()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1 * cm,
        rightMargin=1 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    _patch_styles_for_unicode(styles)
    story = [
        Paragraph(
            f"Forecast Accuracy Report – {start} to {end}  "
            f"(Generated {datetime.now().strftime('%Y-%m-%d %H:%M')})",
            styles["Title"],
        ),
        Spacer(1, 0.4 * cm),
    ]

    table_data = [["Date", "Disease Type", "Model", "Predicted Cases", "MAE", "RMSE", "MAPE (%)"]]
    for fc in forecasts:
        table_data.append([
            str(fc.forecast_date),
            fc.disease_type or "",
            fc.model_used or "",
            str(fc.predicted_cases),
            f"{float(fc.model_accuracy_mae):.2f}" if fc.model_accuracy_mae is not None else "-",
            f"{float(fc.model_accuracy_rmse):.2f}" if fc.model_accuracy_rmse is not None else "-",
            f"{float(fc.model_accuracy_mape):.2f}" if fc.model_accuracy_mape is not None else "-",
        ])

    if len(table_data) == 1:
        story.append(Paragraph("No forecast accuracy data found for the selected period.", styles["Normal"]))
    else:
        col_widths = [3 * cm, 4.5 * cm, 3.5 * cm, 4 * cm, 3 * cm, 3 * cm, 3.5 * cm]
        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle(_base_table_style(colors)))
        story.append(tbl)

    doc.build(story)
    buf.seek(0)
    filename = f"forecast_accuracy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Dashboard Summary Export ─────────────────────────────────────────────────


async def _build_dashboard_summary_data(db: Session) -> Dict:
    """Toàn bộ chỉ số của trang Tổng quan cho báo cáo `dashboard-summary`.

    Số ca neo vào KỲ ĐÃ CHỐT gần nhất (period_service ← mart_monthly_cases_by_block,
    is_complete = 1), không phải tháng lịch hiện tại: tháng đang chạy mới có vài
    ngày dữ liệu, so với nó thì "xu hướng" và "dự báo/thực tế" đều ra hàng
    nghìn phần trăm. Nhu cầu và cảnh báo đi đúng chuỗi Tầng 1→2→3 của
    dss_dashboard để báo cáo không lệch màn hình.
    """
    from app.services import dss_dashboard, dss_alerts, period_service as ps

    today = date.today()
    anchor = ps.get_period_anchor(db)
    last_closed, prev_closed = anchor["last_closed_period"], anchor["prev_closed_period"]

    total_current = ps.cases_in_period(db, last_closed)
    cases_trend = ps.trend_pct(db, last_closed, prev_closed) or 0.0

    fc, th, nhu_cau, nhu_cau_meta = dss_dashboard.tang1_tang2(db)
    predicted_next = int(round(fc["total"]["point"])) if fc.get("ready") and fc["total"].get("point") is not None else 0
    predicted_trend = (
        round(100.0 * (predicted_next - total_current) / total_current, 1)
        if total_current > 0 and fc.get("ready") else 0.0
    )

    al_focus = dss_alerts.alert_rows(db, demand=nhu_cau, only_focus=True)
    dem_focus = dss_dashboard._counts(al_focus)
    shortage_count = dem_focus["red"] + dem_focus["amber"]
    overall_risk = ps.assess_overall_risk(cases_trend, dem_focus["red"], dem_focus["amber"])["level"]

    # Xu hướng 6 kỳ đã chốt, kèm cùng kỳ năm trước — cùng nguồn mart.
    trend_rows = []
    for row in ps.case_series(db, n_periods=6, end_period=last_closed):
        p = row["period"]
        trend_rows.append({
            "month": f"T{int(p[5:7])}", "period": p,
            "this_year": int(row["cases"] or 0),
            "last_year": int(ps.cases_in_period(db, ps.shift_period(p, -12)) or 0),
        })

    # Top 5 thuốc demand vs stock — cùng bảng "Nhu cầu 30 ngày" của Cảnh báo
    # thiếu hụt (delta_need = max(0, d_forecast - s_usable)), không phải
    # SupplyRequirement (đã dừng sinh dữ liệu — xem _archive/README.md).
    focus_rows = list(al_focus.get("rows") or [])
    top_demand = sorted(
        (r for r in focus_rows if r.get("d_forecast") is not None),
        key=lambda r: -(r.get("delta_need") or 0),
    )[:5]
    demand_rows = [
        {
            "supply_name": r["ten"] or r["supply_code"],
            "unit": r["don_vi"],
            "demand": int(round(r["d_forecast"] or 0)),
            "stock": int(round(r["s_usable"] or 0)),
        }
        for r in top_demand
    ]

    # Bảng cảnh báo top 5 (Đỏ trước, Vàng sau) — cùng thứ tự với trang Cảnh báo.
    _thu_tu = {"red": 0, "amber": 1, "green": 2, "grey": 3}
    _severity_vi = {"red": "critical", "amber": "high"}
    top_alerts = sorted(
        (r for r in focus_rows if r.get("muc") in ("red", "amber")),
        key=lambda r: (_thu_tu[r["muc"]], r["doi"] if r["doi"] is not None else 10 ** 9),
    )[:5]
    alerts_list = [
        {
            "supply_name": r["ten"] or r["supply_code"],
            "current_stock": int(round(r["s_usable"] or 0)),
            "required_stock": int(round(r["d_forecast"])) if r.get("d_forecast") is not None else 0,
            "severity": _severity_vi.get(r["muc"], r["muc"]),
        }
        for r in top_alerts
    ]

    return {
        "as_of": today.isoformat(),
        "month_label": f"{last_closed[5:7]}/{last_closed[:4]}" if last_closed else "—",
        "last_closed_period": last_closed,
        "open_period": anchor["open_period"],
        "forecast_period": fc.get("target_period"),
        "kpi": {
            "total_cases_current": int(total_current),
            "cases_trend_pct": cases_trend,
            "predicted_cases_next_month": int(predicted_next),
            "predicted_trend_pct": predicted_trend,
            "shortage_supplies_count": int(shortage_count),
            "overall_risk": overall_risk,
        },
        "case_trend": trend_rows,
        "demand_vs_stock": demand_rows,
        "alerts": alerts_list,
    }


def _render_dashboard_summary_pdf(data: Dict) -> Response:
    """Render báo cáo tổng quan Dashboard ra file PDF."""
    colors, A4, landscape, getSampleStyleSheet, cm, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer = _get_reportlab()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    _patch_styles_for_unicode(styles)
    story = []

    # Title
    story.append(Paragraph(
        f"Báo cáo Dashboard tổng quan - tháng {data['month_label']}",
        styles["Title"],
    ))
    story.append(Paragraph(
        f"Thời điểm xuất: {datetime.now().strftime('%d/%m/%Y %H:%M')} | "
        f"Dữ liệu đến ngày: {data['as_of']}",
        styles["Italic"],
    ))
    story.append(Spacer(1, 0.5 * cm))

    base_style = _base_table_style(colors)

    # 1. KPI table
    story.append(Paragraph("<b>I. Chỉ số tổng quan (KPI)</b>", styles["Heading2"]))
    kpi = data["kpi"]
    kpi_table = Table(
        [
            ["Chỉ số", "Giá trị", "Xu hướng"],
            [
                "Tổng số ca hiện tại",
                f"{kpi['total_cases_current']:,}",
                f"{kpi['cases_trend_pct']:+.1f}%",
            ],
            [
                "Số ca dự báo tháng tới",
                f"{kpi['predicted_cases_next_month']:,}",
                f"{kpi['predicted_trend_pct']:+.1f}%",
            ],
            [
                "Thuốc thiếu hụt",
                f"{kpi['shortage_supplies_count']:,} mục",
                "—",
            ],
            ["Mức nguy cơ chung", kpi["overall_risk"], "—"],
        ],
        colWidths=[8 * cm, 5 * cm, 4 * cm],
        repeatRows=1,
    )
    kpi_table.setStyle(TableStyle(base_style))
    story.append(kpi_table)
    story.append(Spacer(1, 0.5 * cm))

    # 2. Case trend table
    story.append(Paragraph("<b>II. Xu hướng ca bệnh 6 tháng</b>", styles["Heading2"]))
    trend_data = [["Tháng", "Năm nay", "Năm trước"]]
    for r in data["case_trend"]:
        trend_data.append([r["month"], f"{r['this_year']:,}", f"{r['last_year']:,}"])
    trend_table = Table(trend_data, colWidths=[4 * cm, 5 * cm, 5 * cm], repeatRows=1)
    trend_table.setStyle(TableStyle(base_style))
    story.append(trend_table)
    story.append(Spacer(1, 0.5 * cm))

    # 3. Demand vs Stock table
    story.append(Paragraph("<b>III. Nhu cầu vs Tồn kho (Top 5)</b>", styles["Heading2"]))

    # Style nhỏ cho text dài trong cell, tự wrap
    from reportlab.lib.styles import ParagraphStyle

    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName=PDF_FONT_REGULAR,
        fontSize=8,
        leading=10,
        wordWrap="CJK",  # cho phép wrap ở mọi vị trí, kể cả không có space
    )

    if data["demand_vs_stock"]:
        ds_data = [["Thuốc", "Đơn vị", "Tồn kho", "Nhu cầu"]]
        for r in data["demand_vs_stock"]:
            ds_data.append([
                Paragraph(r["supply_name"], cell_style),
                Paragraph(r["unit"] or "", cell_style),
                f"{r['stock']:,}",
                f"{r['demand']:,}",
            ])
        ds_table = Table(ds_data, colWidths=[8.5 * cm, 2 * cm, 2.7 * cm, 2.8 * cm], repeatRows=1)
        ds_table.setStyle(TableStyle(base_style))
        story.append(ds_table)
    else:
        story.append(Paragraph("Không có dữ liệu nhu cầu trong 60 ngày tới.", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    # 4. Alerts table
    story.append(Paragraph("<b>IV. Cảnh báo thiếu hụt thuốc (Top 5)</b>", styles["Heading2"]))
    if data["alerts"]:
        severity_label = {"critical": "Nguy hiểm", "high": "Thiếu hụt", "medium": "Cảnh báo"}
        a_data = [["Thuốc", "Tồn hiện tại", "Định mức", "Trạng thái"]]
        for a in data["alerts"]:
            a_data.append([
                Paragraph(a["supply_name"], cell_style),
                f"{a['current_stock']:,}",
                f"{a['required_stock']:,}",
                severity_label.get(a["severity"], a["severity"]),
            ])
        a_table = Table(a_data, colWidths=[8.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm], repeatRows=1)
        style = list(base_style)
        # Color severity column
        for row_num, a in enumerate(data["alerts"], 1):
            sev = a["severity"]
            if sev == "critical":
                style.append(("TEXTCOLOR", (3, row_num), (3, row_num), colors.red))
            elif sev == "high":
                style.append(("TEXTCOLOR", (3, row_num), (3, row_num), colors.orange))
            else:
                style.append(("TEXTCOLOR", (3, row_num), (3, row_num), colors.HexColor("#B45309")))
            style.append(("FONTNAME", (3, row_num), (3, row_num), PDF_FONT_BOLD))
        a_table.setStyle(TableStyle(style))
        story.append(a_table)
    else:
        story.append(Paragraph("Không có cảnh báo nào.", styles["Normal"]))

    doc.build(story)
    buf.seek(0)
    filename = f"dashboard_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



# ═══════════════════════════════════════════════════════════════════════════
# Module 8 — Smart Medical Reports: Data Builders cho 5 loại mới
# ═══════════════════════════════════════════════════════════════════════════


async def _build_epidemic_data(
    db: Session,
    start: date,
    end: date,
    disease_type: Optional[str],
    location: Optional[str],
) -> Dict:
    """Báo cáo Tình hình dịch bệnh: số ca theo tháng × bệnh × khu vực."""
    from app.models.disease_case import DiseaseCase

    q = db.query(
        _month_expr(DiseaseCase.recorded_at, "%m/%Y").label("month"),
        DiseaseCase.disease_type,
        DiseaseCase.location,
        func.sum(DiseaseCase.case_count).label("total"),
    ).filter(
        DiseaseCase.recorded_at >= datetime(start.year, start.month, start.day),
        DiseaseCase.recorded_at <= datetime(end.year, end.month, end.day),
    )
    if disease_type:
        q = q.filter(DiseaseCase.disease_type == disease_type)
    if location:
        q = q.filter(DiseaseCase.location == location)
    rows = q.group_by(
        _month_expr(DiseaseCase.recorded_at, "%m/%Y"),
        DiseaseCase.disease_type,
        DiseaseCase.location,
    ).order_by(
        _month_expr(DiseaseCase.recorded_at, "%Y-%m"),
        DiseaseCase.disease_type,
    ).all()

    items = [
        {
            "month": r.month,
            "disease_type": r.disease_type,
            "disease_label": _vi_disease(r.disease_type),
            "location": r.location,
            "total": int(r.total or 0),
        }
        for r in rows
    ]
    total_cases = sum(it["total"] for it in items)
    return {
        "items": items,
        "total_cases": total_cases,
        "filters": {"disease_type": disease_type, "location": location},
    }


async def _build_forecast_data(
    db: Session,
    start: date,
    end: date,
    disease_type: Optional[str],
    location: Optional[str],
) -> Dict:
    """Báo cáo Dự báo ca bệnh: predicted_cases + risk + explanation."""
    from app.models.disease_forecast import DiseaseForecast

    q = db.query(DiseaseForecast).filter(
        DiseaseForecast.forecast_date >= start,
        DiseaseForecast.forecast_date <= end,
    )
    if disease_type:
        q = q.filter(DiseaseForecast.disease_type == disease_type)
    if location:
        q = q.filter(DiseaseForecast.location == location)
    rows = q.order_by(DiseaseForecast.forecast_date.desc()).all()

    risk_label = {
        "low": "Thấp",
        "medium": "Trung bình",
        "high": "Cao",
        "very_high": "Rất cao",
    }

    from app.services.actual_case_service import do_lech_pct, so_ca_thuc_te

    def _thuc_te(r) -> Optional[int]:
        # Ưu tiên số nhập tay (nếu có), còn lại lấy từ disease_cases.
        if r.actual_cases is not None:
            return int(r.actual_cases)
        if r.forecast_date is None:
            return None
        return so_ca_thuc_te(db, r.icd_code, r.forecast_date, r.location)

    def _do_lech(r) -> Optional[float]:
        if r.deviation_pct is not None:
            return float(r.deviation_pct)
        return do_lech_pct(r.predicted_cases, _thuc_te(r))

    items = [
        {
            "month": r.forecast_date.strftime("%m/%Y") if r.forecast_date else "—",
            "disease_label": _vi_disease(r.disease_type),
            "location": r.location or "Toàn thành phố",
            "predicted_cases": r.predicted_cases or 0,
            "actual_cases": _thuc_te(r),
            "deviation_pct": _do_lech(r),
            "baseline_cases": r.baseline_cases or 0,
            "risk_level": r.risk_level or "",
            "risk_label": risk_label.get(r.risk_level or "", "—"),
            "explanation": (r.explanation or "")[:300],
        }
        for r in rows
    ]
    return {
        "items": items,
        "filters": {"disease_type": disease_type, "location": location},
    }


async def _build_inventory_data(
    db: Session,
    category: Optional[str],
) -> Dict:
    """Báo cáo Tồn kho thuốc — CÙNG chuỗi với trang Quản lý thuốc và Cảnh báo
    (dss_alerts.alert_rows, toàn danh mục): tồn hữu dụng FEFO, tiêu hao/ngày,
    DOI và nhãn Đỏ/Vàng/Xanh/Xám. Trước 13/09/2026 báo cáo này xếp loại theo
    `inventory.safety_stock` — cột chỉ có giá trị ở 34/5.051 dòng — nên ra một
    hệ nhãn thứ hai mâu thuẫn với trang Cảnh báo.

    Chỉ gồm mã có tiêu hao trong 12 kỳ đã chốt (mã chưa từng xuất không có
    mẫu số nên không đo được DOI, không đưa vào báo cáo).
    """
    from app.services import dss_alerts

    al = dss_alerts.alert_rows(db, only_focus=False)
    th = al.get("tong_hop") or {}
    nguong = th.get("nguong") or {}

    items = []
    for r in (al.get("rows") or []):
        dm = r.get("danh_muc") or "Khác"
        if category and dm != category:
            continue
        items.append(
            {
                "supply_code": r["supply_code"],
                "supply_name": r["ten"] or r["supply_code"],
                "category": dm,
                "unit": r["don_vi"] or "",
                "current_stock": int(round(r["s_total"] or 0)),
                "usable_stock": int(round(r["s_usable"] or 0)),
                "d_daily": round(float(r["d_daily"] or 0), 2),
                "doi": round(float(r["doi"]), 1) if r.get("doi") is not None else None,
                "status": _NHAN_MUC[r["muc"]],
            }
        )
    thu_tu = {"Đỏ": 0, "Vàng": 1, "Xanh": 2, "Xám": 3}
    items.sort(key=lambda x: (thu_tu[x["status"]], x["doi"] if x["doi"] is not None else 10 ** 9))
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "red": sum(1 for x in items if x["status"] == "Đỏ"),
            "amber": sum(1 for x in items if x["status"] == "Vàng"),
            "green": sum(1 for x in items if x["status"] == "Xanh"),
            "grey": sum(1 for x in items if x["status"] == "Xám"),
            "red_days": float(nguong.get("red_days") or 18),
            "amber_days": float(nguong.get("amber_days") or 36),
            "stock_source": th.get("nguon_ton_kho") or "khong_co",
        },
    }


_NHAN_MUC = {"red": "Đỏ", "amber": "Vàng", "green": "Xanh", "grey": "Xám"}


async def _build_shortage_data(
    db: Session,
    start: date,
    end: date,
    disease_type: Optional[str],
) -> Dict:
    """Báo cáo Thiếu hụt thuốc — đọc từ CÙNG tầng Cảnh báo thiếu hụt
    (dss_dashboard.tang1_tang2 → dss_alerts.alert_rows) thay vì SupplyRequirement
    (bảng đã dừng sinh dữ liệu — xem _archive/README.md).

    Đây là ảnh chụp TẠI THỜI ĐIỂM XUẤT báo cáo (Đỏ/Vàng theo DOI, nhu cầu dự
    báo `horizon_days` ngày tới), không phải tổng dồn theo khoảng [start, end]
    như bản cũ — công thức DSS hợp nhất không tách thuốc theo từng bệnh nên
    `disease_type` không còn áp dụng để lọc (bỏ qua nếu có truyền).
    """
    from app.services import dss_dashboard, dss_alerts

    _, _, nhu_cau, _ = dss_dashboard.tang1_tang2(db)
    al = dss_alerts.alert_rows(db, demand=nhu_cau, only_focus=False)

    items = []
    for r in (al.get("rows") or []):
        shortage = r.get("delta_need")
        if not shortage or shortage <= 0:
            continue
        items.append(
            {
                "supply_name": r["ten"] or r["supply_code"],
                "category": _vi_category(r.get("danh_muc")),
                "unit": r["don_vi"],
                "demand": int(round(r["d_forecast"])) if r.get("d_forecast") is not None else 0,
                "stock": int(round(r["s_usable"] or 0)),
                "shortage": int(round(shortage)),
            }
        )
    items.sort(key=lambda x: -x["shortage"])
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "total_shortage": sum(x["shortage"] for x in items),
        },
    }




def _ascii_filename(s: str) -> str:
    """Chuyển string tiếng Việt sang dạng ASCII không dấu để dùng trong HTTP header."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Bỏ ký tự đặc biệt không phải ASCII còn lại
    return ascii_only.encode("ascii", errors="ignore").decode("ascii") or "report"


def _vi_disease(key: str) -> str:
    return {
        "dengue_fever": "Sốt xuất huyết",
        "seasonal_flu": "Cúm mùa",
        "respiratory_disease": "Bệnh hô hấp",
        "viral_infection": "Nhiễm virus",
    }.get(key or "", key or "—")


def _vi_category(key: str) -> str:
    return {
        "medicine": "Thuốc",
        "mask": "Khẩu trang",
        "glove": "Găng tay",
        "test_kit": "Kit XN",
        "disinfectant": "Hoá chất",
        "iv_fluid": "Dịch truyền",
        "other": "Khác",
    }.get(key or "", key or "—")



# ═══════════════════════════════════════════════════════════════════════════
# PDF Renderers cho 4 loại (epidemic / forecast / inventory / shortage)
# ═══════════════════════════════════════════════════════════════════════════


def _generic_pdf(
    title: str,
    period_label: str,
    headers: list[str],
    rows: list[list[str]],
    col_widths_cm: list[float],
    summary_lines: Optional[list[str]] = None,
    landscape_mode: bool = True,
) -> Response:
    """Helper: render bảng đơn giản ra PDF với font Unicode.

    col_widths_cm: list số float — đơn vị cm (sẽ được nhân với 1*cm bên trong).
    """
    colors, A4, _landscape, getSampleStyleSheet, cm, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer = _get_reportlab()

    pagesize = _landscape(A4) if landscape_mode else A4
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=pagesize,
        leftMargin=1 * cm,
        rightMargin=1 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    _patch_styles_for_unicode(styles)
    story = [
        Paragraph(title, styles["Title"]),
        Paragraph(
            f"Kỳ báo cáo: {period_label} | Xuất lúc: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            styles["Italic"],
        ),
        Spacer(1, 0.4 * cm),
    ]

    # Wrap text dài trong cell bằng Paragraph
    from reportlab.lib.styles import ParagraphStyle
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName=PDF_FONT_REGULAR,
        fontSize=8,
        leading=10,
        wordWrap="CJK",
    )

    if not rows:
        story.append(Paragraph("Không có dữ liệu trong kỳ báo cáo này.", styles["Normal"]))
    else:
        # Convert col_widths_cm sang ReportLab unit
        col_widths = [w * cm for w in col_widths_cm]
        # Convert rows: nếu cell quá dài thì wrap
        formatted_rows: list[list] = [headers]
        for r in rows:
            formatted_rows.append([
                Paragraph(str(c), cell_style) if isinstance(c, str) and len(c) > 30 else str(c)
                for c in r
            ])
        tbl = Table(formatted_rows, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle(_base_table_style(colors)))
        story.append(tbl)

    if summary_lines:
        story.append(Spacer(1, 0.4 * cm))
        for line in summary_lines:
            story.append(Paragraph(line, styles["Normal"]))

    doc.build(story)
    buf.seek(0)
    safe = title.replace(" ", "_").replace("/", "-")[:40]
    # Encode tên file theo RFC 5987 vì HTTP headers chỉ chấp nhận Latin-1
    from urllib.parse import quote as _quote
    filename_ascii = _ascii_filename(safe) + f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filename_utf8 = _quote(safe + f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename_ascii}"; '
                f"filename*=UTF-8''{filename_utf8}"
            )
        },
    )


def _render_epidemic_pdf(data: Dict, start: date, end: date) -> Response:
    rows = [
        [it["month"], it["disease_label"], it["location"], f"{it['total']:,}"]
        for it in data["items"]
    ]
    return _generic_pdf(
        title="Báo cáo Tình hình Dịch bệnh",
        period_label=f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}",
        headers=["Tháng", "Bệnh", "Khu vực", "Số ca"],
        rows=rows,
        col_widths_cm=[3, 5, 8, 4],
        summary_lines=[f"<b>Tổng số ca trong kỳ:</b> {data['total_cases']:,}"],
        landscape_mode=False,
    )


def _render_forecast_pdf(data: Dict, start: date, end: date) -> Response:
    rows = [
        [
            it["month"],
            it["disease_label"],
            it["location"],
            f"{it['predicted_cases']:,}",
            f"{it['actual_cases']:,}" if it["actual_cases"] is not None else "—",
            f"{it['deviation_pct']:+.1f}%" if it["deviation_pct"] is not None else "—",
            it["risk_label"],
            it["explanation"][:200],
        ]
        for it in data["items"]
    ]
    return _generic_pdf(
        title="Báo cáo Dự báo Ca bệnh",
        period_label=f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}",
        headers=[
            "Tháng", "Bệnh", "Khu vực", "Dự báo", "Thực tế", "Độ lệch",
            "Mức nguy cơ", "Lý do",
        ],
        rows=rows,
        col_widths_cm=[2.2, 3.8, 4.0, 2.2, 2.2, 2.2, 2.4, 6.0],
    )


def _render_inventory_pdf(data: Dict) -> Response:
    rows = [
        [
            it["supply_code"],
            it["supply_name"],
            it["category"],
            it["unit"],
            f"{it['current_stock']:,}",
            f"{it['usable_stock']:,}",
            f"{it['d_daily']:,.2f}",
            "—" if it["doi"] is None else f"{it['doi']:,.1f}",
            it["status"],
        ]
        for it in data["items"]
    ]
    s = data["summary"]
    return _generic_pdf(
        title="Báo cáo Tồn kho Thuốc",
        period_label=datetime.now().strftime("%d/%m/%Y"),
        headers=["Mã", "Thuốc", "Danh mục", "ĐVT", "Tồn kho", "Tồn hữu dụng", "Tiêu hao/ngày", "DOI (ngày)", "Nhãn"],
        rows=rows,
        col_widths_cm=[1.8, 6.2, 3.0, 1.6, 2.0, 2.2, 2.2, 2.0, 1.6],
        summary_lines=[
            f"<b>Tổng thuốc:</b> {s['total']:,} | "
            f"<b>Đỏ:</b> {s['red']:,} | <b>Vàng:</b> {s['amber']:,} | "
            f"<b>Xanh:</b> {s['green']:,} | <b>Xám:</b> {s['grey']:,}",
            f"DOI = tồn hữu dụng (FEFO) / tiêu hao ngày · Đỏ ≤ {s['red_days']:.0f} · "
            f"Vàng ≤ {s['amber_days']:.0f} ngày · Nguồn tồn: {s['stock_source']}",
        ],
    )


def _render_shortage_pdf(data: Dict, start: date, end: date) -> Response:
    rows = [
        [
            it["supply_name"],
            it["category"],
            it["unit"],
            f"{it['demand']:,}",
            f"{it['stock']:,}",
            f"{it['shortage']:,}",
        ]
        for it in data["items"]
    ]
    s = data["summary"]
    return _generic_pdf(
        title="Báo cáo Thiếu hụt Thuốc",
        period_label=f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}",
        headers=["Thuốc", "Loại", "ĐVT", "Nhu cầu", "Tồn kho", "Mức thiếu"],
        rows=rows,
        col_widths_cm=[7.5, 3, 2, 2.5, 2.5, 2.5],
        summary_lines=[
            f"<b>Số thuốc thiếu:</b> {s['total']:,} | "
            f"<b>Tổng lượng thiếu:</b> {s['total_shortage']:,}"
        ],
    )




# ═══════════════════════════════════════════════════════════════════════════
# Excel Renderers — dùng openpyxl
# ═══════════════════════════════════════════════════════════════════════════


def _generic_excel(
    sheet_title: str,
    headers: list[str],
    rows: list[list],
    column_widths: list[int],
    filename_prefix: str,
    title_line: Optional[str] = None,
) -> Response:
    """Helper: render bảng đơn giản ra Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openpyxl chưa được cài",
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]

    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    start_row = 1
    if title_line:
        ws.cell(row=1, column=1, value=title_line)
        ws.cell(row=1, column=1).font = Font(bold=True, size=12)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        start_row = 3

    for col_num, h in enumerate(headers, 1):
        c = ws.cell(row=start_row, column=col_num, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = align_center

    for r_idx, row in enumerate(rows, start=start_row + 1):
        for c_idx, value in enumerate(row, start=1):
            ws.cell(row=r_idx, column=c_idx, value=value)

    for col_num, w in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(col_num)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    from urllib.parse import quote as _quote
    name_base = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{_ascii_filename(name_base)}"; '
                f"filename*=UTF-8''{_quote(name_base)}"
            )
        },
    )


# ── Excel: 5 loại mới ──────────────────────────────────────────────────────


def _render_epidemic_excel(data: Dict, start: date, end: date) -> Response:
    rows = [
        [it["month"], it["disease_label"], it["location"], it["total"]]
        for it in data["items"]
    ]
    return _generic_excel(
        sheet_title="Tình hình dịch bệnh",
        headers=["Tháng", "Bệnh", "Khu vực", "Số ca"],
        rows=rows,
        column_widths=[12, 24, 28, 12],
        filename_prefix="bao_cao_dich_benh",
        title_line=f"Báo cáo Tình hình Dịch bệnh — {start.strftime('%d/%m/%Y')} đến {end.strftime('%d/%m/%Y')}",
    )


def _render_forecast_excel(data: Dict, start: date, end: date) -> Response:
    rows = [
        [
            it["month"],
            it["disease_label"],
            it["location"],
            it["predicted_cases"],
            it["actual_cases"] if it["actual_cases"] is not None else "—",
            f"{it['deviation_pct']:+.1f}%" if it["deviation_pct"] is not None else "—",
            it["baseline_cases"],
            it["risk_label"],
            it["explanation"],
        ]
        for it in data["items"]
    ]
    return _generic_excel(
        sheet_title="Dự báo ca bệnh",
        headers=[
            "Tháng", "Bệnh", "Khu vực", "Số ca dự báo", "Số ca thực tế",
            "Độ lệch", "Ca nền", "Mức nguy cơ", "Lý do dự báo",
        ],
        rows=rows,
        column_widths=[10, 22, 24, 14, 14, 10, 12, 14, 60],
        filename_prefix="bao_cao_du_bao",
        title_line=f"Báo cáo Dự báo Ca bệnh — {start.strftime('%d/%m/%Y')} đến {end.strftime('%d/%m/%Y')}",
    )


def _render_inventory_excel(data: Dict) -> Response:
    rows = [
        [
            it["supply_code"],
            it["supply_name"],
            it["category"],
            it["unit"],
            it["current_stock"],
            it["usable_stock"],
            it["d_daily"],
            it["doi"],
            it["status"],
        ]
        for it in data["items"]
    ]
    s = data["summary"]
    return _generic_excel(
        sheet_title="Tồn kho thuốc",
        headers=["Mã", "Thuốc", "Danh mục", "ĐVT", "Tồn kho", "Tồn hữu dụng (FEFO)", "Tiêu hao/ngày", "DOI (ngày)", "Nhãn"],
        rows=rows,
        column_widths=[10, 40, 18, 8, 12, 16, 14, 12, 8],
        filename_prefix="bao_cao_ton_kho_thuoc",
        title_line=(f"Báo cáo Tồn kho Thuốc — {datetime.now().strftime('%d/%m/%Y')} · "
                    f"Đỏ ≤ {s['red_days']:.0f} · Vàng ≤ {s['amber_days']:.0f} ngày"),
    )


def _render_shortage_excel(data: Dict, start: date, end: date) -> Response:
    rows = [
        [
            it["supply_name"],
            it["category"],
            it["unit"],
            it["demand"],
            it["stock"],
            it["shortage"],
        ]
        for it in data["items"]
    ]
    return _generic_excel(
        sheet_title="Thiếu hụt",
        headers=["Thuốc", "Loại", "ĐVT", "Nhu cầu", "Tồn kho", "Mức thiếu"],
        rows=rows,
        column_widths=[40, 14, 8, 14, 14, 14],
        filename_prefix="bao_cao_thieu_hut",
        title_line=f"Báo cáo Thiếu hụt Thuốc — {start.strftime('%d/%m/%Y')} đến {end.strftime('%d/%m/%Y')}",
    )




# ── Excel cho 4 loại legacy ─────────────────────────────────────────────────


def _render_accuracy_excel(forecasts, start: date, end: date) -> Response:
    rows = [
        [
            str(fc.forecast_date),
            fc.disease_type or "",
            fc.model_used or "",
            fc.predicted_cases,
            float(fc.model_accuracy_mae) if fc.model_accuracy_mae is not None else None,
            float(fc.model_accuracy_rmse) if fc.model_accuracy_rmse is not None else None,
            float(fc.model_accuracy_mape) if fc.model_accuracy_mape is not None else None,
        ]
        for fc in forecasts
    ]
    return _generic_excel(
        sheet_title="Độ chính xác",
        headers=["Ngày", "Bệnh", "Mô hình", "Dự báo", "MAE", "RMSE", "MAPE %"],
        rows=rows,
        column_widths=[12, 22, 14, 12, 12, 12, 12],
        filename_prefix="bao_cao_chinh_xac",
        title_line=f"Báo cáo Độ chính xác Dự báo — {start.strftime('%d/%m/%Y')} đến {end.strftime('%d/%m/%Y')}",
    )


def _render_dashboard_summary_excel(data: Dict) -> Response:
    """Dashboard summary có 4 phần — gộp vào 1 sheet với section."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise HTTPException(
            status_code=500, detail="openpyxl chưa được cài",
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dashboard"

    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    section_font = Font(bold=True, size=11, color="1F4E79")

    row = 1
    ws.cell(row=row, column=1, value=f"Báo cáo Dashboard - tháng {data['month_label']}").font = Font(bold=True, size=12)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
    row += 2

    # Phần I: KPI
    ws.cell(row=row, column=1, value="I. Chỉ số tổng quan (KPI)").font = section_font
    row += 1
    kpi_headers = ["Chỉ số", "Giá trị", "Xu hướng"]
    for c, h in enumerate(kpi_headers, 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.fill = header_fill
        cell.font = header_font
    row += 1
    kpi = data["kpi"]
    kpi_rows = [
        ("Tổng số ca hiện tại", kpi["total_cases_current"], f"{kpi['cases_trend_pct']:+.1f}%"),
        ("Số ca dự báo tháng tới", kpi["predicted_cases_next_month"], f"{kpi['predicted_trend_pct']:+.1f}%"),
        ("Thuốc thiếu hụt", f"{kpi['shortage_supplies_count']} mục", "—"),
        ("Mức nguy cơ chung", kpi["overall_risk"], "—"),
    ]
    for r in kpi_rows:
        for c, v in enumerate(r, 1):
            ws.cell(row=row, column=c, value=v)
        row += 1
    row += 1

    # Phần II: Xu hướng 6 tháng
    ws.cell(row=row, column=1, value="II. Xu hướng ca bệnh 6 tháng").font = section_font
    row += 1
    for c, h in enumerate(["Tháng", "Năm nay", "Năm trước"], 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.fill = header_fill
        cell.font = header_font
    row += 1
    for r in data["case_trend"]:
        ws.cell(row=row, column=1, value=r["month"])
        ws.cell(row=row, column=2, value=r["this_year"])
        ws.cell(row=row, column=3, value=r["last_year"])
        row += 1
    row += 1

    # Phần III: Demand vs Stock
    ws.cell(row=row, column=1, value="III. Nhu cầu vs Tồn kho (Top 5)").font = section_font
    row += 1
    for c, h in enumerate(["Thuốc", "ĐVT", "Tồn kho", "Nhu cầu"], 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.fill = header_fill
        cell.font = header_font
    row += 1
    for r in data["demand_vs_stock"]:
        ws.cell(row=row, column=1, value=r["supply_name"])
        ws.cell(row=row, column=2, value=r["unit"] or "")
        ws.cell(row=row, column=3, value=r["stock"])
        ws.cell(row=row, column=4, value=r["demand"])
        row += 1
    row += 1

    # Phần IV: Cảnh báo
    ws.cell(row=row, column=1, value="IV. Cảnh báo thiếu hụt thuốc (Top 5)").font = section_font
    row += 1
    for c, h in enumerate(["Thuốc", "Tồn hiện tại", "Định mức", "Trạng thái"], 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.fill = header_fill
        cell.font = header_font
    row += 1
    severity_label = {"critical": "Nguy hiểm", "high": "Thiếu hụt", "medium": "Cảnh báo"}
    for a in data["alerts"]:
        ws.cell(row=row, column=1, value=a["supply_name"])
        ws.cell(row=row, column=2, value=a["current_stock"])
        ws.cell(row=row, column=3, value=a["required_stock"])
        ws.cell(row=row, column=4, value=severity_label.get(a["severity"], a["severity"]))
        row += 1

    for col_num, w in enumerate([34, 14, 14, 14], 1):
        ws.column_dimensions[get_column_letter(col_num)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"dashboard_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
