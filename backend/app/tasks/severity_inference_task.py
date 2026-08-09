"""Celery task — Tự động suy luận tỷ lệ severity từ dữ liệu lịch sử (mục 5.2).

Chạy theo 2 cách:
1. Celery beat schedule (định kỳ hằng đêm).
2. Trigger thủ công sau khi import CSV disease_cases (dispatch qua .delay()
   trong endpoint, hoặc sync fallback nếu broker không sẵn).

Mỗi lần chạy ghi 1 dòng vào ``system_logs`` để admin có thể audit lại.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.system_log import SystemLog
from app.services.severity_inference_service import SeverityInferenceService

logger = logging.getLogger(__name__)


def _run_recompute(force: bool, trigger: str, updated_by: Optional[str]) -> Dict[str, Any]:
    """Logic core, dùng chung cho Celery worker và sync fallback.

    Args:
        force: True = phân loại lại toàn bộ ca, False = chỉ ca chưa có severity.
        trigger: nguồn gọi (vd "csv_import", "scheduled", "manual_api").
        updated_by: username người gọi (nếu có).

    Returns:
        Dict thống kê kết quả: số bệnh updated/skipped + chi tiết.
    """
    db = SessionLocal()
    try:
        service = SeverityInferenceService(db)
        results = service.update_severity_rates_from_history(
            force=force,
            updated_by=updated_by,
        )
        updated = len([r for r in results if r["status"] == "updated"])
        skipped = len([r for r in results if r["status"] == "skipped"])

        # Ghi system_log để audit
        log_msg_lines = [
            f"Auto severity recompute by {trigger} (force={force}).",
            f"Updated {updated} disease(s), skipped {skipped}.",
        ]
        for r in results:
            if r["status"] == "updated":
                new = r["new"]
                log_msg_lines.append(
                    f"  - {r['icd_code']} ({r['total_cases']} cases): "
                    f"{new['mild_rate']}/{new['moderate_rate']}/{new['severe_rate']}%"
                )
            else:
                log_msg_lines.append(
                    f"  - {r['icd_code']}: skipped — {r.get('reason', 'no reason')}"
                )

        db.add(SystemLog(
            log_level="INFO",
            module_name="severity_inference_task",
            message="\n".join(log_msg_lines),
        ))
        db.commit()

        logger.info(
            "Auto severity recompute (%s, force=%s): updated=%d skipped=%d",
            trigger, force, updated, skipped,
        )

        return {
            "trigger": trigger,
            "force": force,
            "updated": updated,
            "skipped": skipped,
            "diseases": results,
        }

    except Exception as exc:
        logger.exception("Auto severity recompute failed: %s", exc)
        try:
            db.rollback()
            db.add(SystemLog(
                log_level="ERROR",
                module_name="severity_inference_task",
                message=f"Auto severity recompute failed ({trigger}): {exc}",
            ))
            db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(name="recompute_severity_rates", bind=True)
def recompute_severity_rates_task(
    self,
    force: bool = False,
    trigger: str = "scheduled",
    updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Celery task — chạy `_run_recompute` trong worker."""
    self.update_state(state="STARTED", meta={"trigger": trigger, "force": force})
    return _run_recompute(force=force, trigger=trigger, updated_by=updated_by)


def dispatch_recompute(
    force: bool = False,
    trigger: str = "csv_import",
    updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper — dispatch task qua Celery, sync fallback nếu broker không sẵn.

    Dùng trong các endpoint API muốn chạy auto-recompute mà không chặn response.
    Nếu Celery broker không có (vd dev local), sẽ chạy sync ngay luôn.
    """
    # Bước 1: probe broker — nếu không kết nối được thì chạy sync luôn để demo
    # vẫn hoạt động khi không có Redis/worker.
    try:
        with celery_app.connection_or_acquire() as conn:
            conn.ensure_connection(max_retries=1, timeout=1.0)
        broker_alive = True
    except Exception as exc:
        logger.info(
            "Celery broker unreachable (%s) — running severity recompute synchronously.",
            exc,
        )
        broker_alive = False

    if not broker_alive:
        result = _run_recompute(force=force, trigger=trigger, updated_by=updated_by)
        result["mode"] = "sync_fallback"
        return result

    # Bước 2: broker OK → dispatch async
    try:
        async_result = recompute_severity_rates_task.delay(
            force=force, trigger=trigger, updated_by=updated_by,
        )
        return {
            "mode": "async",
            "task_id": async_result.id,
            "trigger": trigger,
            "force": force,
        }
    except Exception as exc:
        logger.warning(
            "Celery dispatch failed (%s) — running severity recompute synchronously.",
            exc,
        )
        result = _run_recompute(force=force, trigger=trigger, updated_by=updated_by)
        result["mode"] = "sync_fallback"
        return result
