#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chuyển cấu hình kết nối đã lưu trong app (system_config['his_sync.connection'])
từ máy chủ STA (172.16.1.48) sang SQL Server cục bộ chứa snapshot MEDFORECAST_DW.

    cd backend
    python scripts/cap_nhat_ket_noi_dw.py                       # localhost, Windows auth
    python scripts/cap_nhat_ket_noi_dw.py --instance SQLEXPRESS # localhost\\SQLEXPRESS
    python scripts/cap_nhat_ket_noi_dw.py --auth sql            # giữ UID/PWD đã lưu

Chỉ đổi host/instance/auth/source — giữ nguyên username, mật khẩu đã mã hoá,
driver, lookback. Chạy lại vô hại.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--instance", default="", help="tên instance (vd SQLEXPRESS); rỗng = instance mặc định, port 1433")
    ap.add_argument("--auth", choices=["windows", "sql"], default="windows")
    ap.add_argument("--driver", default="", help="tên driver ODBC; bỏ trống = giữ driver đã lưu (tự dò nếu máy không có)")
    a = ap.parse_args()

    from app.database import SessionLocal
    from app.models.system_config import SystemConfig
    from app.services.sync_config_service import CONFIG_KEY, MAC_DINH

    db = SessionLocal()
    try:
        row = db.query(SystemConfig).filter(SystemConfig.config_key == CONFIG_KEY).first()
        cu = json.loads(row.config_value) if row and row.config_value else {}
        moi = {**MAC_DINH, **cu}
        truoc = f"{moi.get('host')}\\{moi.get('instance')}" if moi.get("instance") else f"{moi.get('host')},{moi.get('port')}"
        from app.services.sync_config_service import driver_kha_dung
        driver, _ = driver_kha_dung(a.driver or moi.get("driver") or MAC_DINH["driver"])
        moi.update({"source": "sqlserver", "host": a.host, "instance": a.instance,
                    "auth": a.auth, "driver": driver, "trust_cert": True})
        if row is None:
            row = SystemConfig(config_key=CONFIG_KEY,
                               description="Kết nối CSDL nghiên cứu MEDFORECAST_DW cục bộ")
            db.add(row)
        row.description = "Kết nối CSDL nghiên cứu MEDFORECAST_DW cục bộ (mật khẩu đã mã hoá nếu dùng SQL auth)"
        row.config_value = json.dumps(moi, ensure_ascii=False)
        db.commit()
        sau = f"{a.host}\\{a.instance}" if a.instance else f"{a.host},{moi.get('port')}"
        print(f"Đã cập nhật {CONFIG_KEY}: SERVER {truoc} → {sau} · auth = {a.auth} · driver = {driver}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
