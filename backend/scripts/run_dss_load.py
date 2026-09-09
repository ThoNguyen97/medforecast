#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NẠP BỐN LUỒNG DSS TỪ STA VỀ DB LOCAL
=============================================================================
Đặt tại: backend/scripts/run_dss_load.py

    cd backend
    python scripts/run_dss_load.py                # nạp tăng dần (lùi 3 kỳ)
    python scripts/run_dss_load.py --full         # nạp lại toàn bộ lịch sử
    python scripts/run_dss_load.py --flow usage_total

Kết nối STA lấy từ chính cấu hình đã lưu trong ứng dụng
(`system_config['his_sync.connection']`, mật khẩu đã mã hoá) qua
`sync_config_service.build_connector` — cùng đường mà nút "Đồng bộ HIS" trên
giao diện đang dùng, nên không phải khai báo lại chuỗi kết nối ở đâu cả.

-----------------------------------------------------------------------------
VÌ SAO CHẠY RIÊNG, KHÔNG GẮN VÀO NÚT ĐỒNG BỘ SẴN CÓ

Bốn luồng này có nhịp khác luồng ca bệnh: tiêu hao toàn viện chỉ cần nạp mỗi
tuần, tồn kho theo lô nên nạp mỗi ngày (nó là ảnh chụp), còn ca bệnh chạy
hằng ngày. Quan trọng hơn, `DataPipeline.run()` gói toàn
bộ staging → dim → fact → mart trong MỘT transaction; thêm ba luồng vào giữa
nghĩa là một lỗi ở luồng mới sẽ rollback cả phần đang chạy tốt.

Khi đã chạy ổn định vài tuần thì gọi `load_all()` ngay sau `DataPipeline.run()`
trong `sync_service.py` — nhưng ở khối try/except RIÊNG.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Cho phép chạy trực tiếp từ thư mục backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dss_load")


def main() -> int:
    ap = argparse.ArgumentParser(description="Nạp bốn luồng DSS từ STA")
    ap.add_argument("--full", action="store_true",
                    help="nạp lại toàn bộ lịch sử thay vì tăng dần")
    ap.add_argument("--flow", choices=["usage_total", "cases_care_level",
                                       "usage_care_level", "inventory_lot"],
                    help="chỉ nạp một luồng")
    a = ap.parse_args()

    from app.database import SessionLocal
    from app.data_pipeline import dss_loader
    from app.services import sync_config_service

    db = SessionLocal()
    try:
        try:
            connector = sync_config_service.build_connector(db)
        except Exception as exc:                     # noqa: BLE001
            log.error("Không dựng được kết nối STA: %s", exc)
            log.error("Kiểm tra Quản trị → Kết nối HIS, hoặc chạy thử nút "
                      "'Kiểm tra kết nối' trên giao diện trước.")
            return 2

        if connector.name != "sqlserver":
            log.error("Nguồn hiện tại là '%s' — ba luồng DSS chỉ đọc được từ STA "
                      "(SQL Server). Đổi nguồn trong Quản trị → Kết nối HIS.",
                      connector.name)
            return 2

        dss_loader.ensure_tables(db)

        if a.flow:
            ket_qua = {"flows": [dss_loader.load_flow(db, connector, a.flow, full=a.full)]}
        else:
            ket_qua = dss_loader.load_all(db, connector, full=a.full)

        print("\n" + "=" * 72)
        print("KẾT QUẢ NẠP")
        print("=" * 72)
        loi = 0
        for r in ket_qua["flows"]:
            if r["status"] == "ok":
                print(f"  {r['table']:<28} {r['rows']:>8,} dòng · {r['periods']:>3} kỳ "
                      f"· {r.get('min_period')} → {r.get('max_period')}")
            else:
                loi += 1
                print(f"  {r['flow']:<28} {r['status'].upper()}: {r.get('message', '')}")
        print("=" * 72)

        if loi:
            print("\n  Có luồng lỗi. Ba nghi ngờ theo thứ tự:")
            print("   1) View bên STA chưa tồn tại — chạy G1_01_STA_sua_bang.sql")
            print("   2) Thủ tục PROD chưa nạp:")
            print("        EXEC dbo.usp_MedForecast_DayTieuHaoToanVien @SoThang = 24;")
            print("        EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1;   -- bản v3")
            print("        EXEC dbo.usp_MedForecast_DayKhoCungUng;                 -- cho inventory_lot")
            print("   3) Tài khoản ứng dụng chưa được GRANT SELECT trên view mới")
            return 1

        print("\n  Bước tiếp theo: python scripts/verify_g1.py")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
