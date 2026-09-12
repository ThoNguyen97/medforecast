"""Tự động suy luận tỷ lệ severity từ dữ liệu lịch sử (mục 5.2).

Chạy ĐỒNG BỘ, ngay trong request đã kích hoạt nó (hiện chỉ có một nơi:
endpoint import CSV disease_cases).

Lịch sử: bản đầu bọc hàm này trong một Celery task và chỉ chạy đồng bộ khi
"broker không sẵn". Thực tế broker CHƯA BAO GIỜ sẵn — không có service
worker nào trong docker-compose và không nơi nào gọi .delay() ngoài chính
file này — nên nhánh đồng bộ là nhánh duy nhất từng chạy, còn nhánh async
chỉ tồn tại trên giấy. Gỡ Celery ngày 09/09/2026 (xem _archive/dich_vu_chet/).

Mỗi lần chạy ghi 1 dòng vào ``system_logs`` để admin audit lại.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

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


def dispatch_recompute(
    force: bool = False,
    trigger: str = "csv_import",
    updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Chạy lại phép suy luận severity, đồng bộ.

    Giữ nguyên tên và chữ ký cũ để nơi gọi (api/v1/disease_cases.py) không
    phải đổi. Khoá "mode" trong kết quả cũng giữ giá trị "sync_fallback" để
    giao diện hiện có đọc được như trước.
    """
    result = _run_recompute(force=force, trigger=trigger, updated_by=updated_by)
    result["mode"] = "sync_fallback"
    return result
