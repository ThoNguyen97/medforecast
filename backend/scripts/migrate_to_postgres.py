"""Chuyển TOÀN BỘ dữ liệu từ SQLite (medforecast.db) sang DB đích (PostgreSQL).

CHẠY SAU KHI backend đã khởi động 1 lần với DATABASE_URL trỏ Postgres (để các bảng
đã được tạo). Mặc định copy mọi bảng ứng dụng; các bảng kho trung gian
(mart_/fact_/stg_/dim_/sync_state) bỏ qua — sẽ được sinh lại khi bấm "Đồng bộ HIS"
(đặt COPY_ALL=1 nếu muốn copy cả chúng).

Điểm quan trọng so với bản cũ:
  * Copy theo ĐÚNG THỨ TỰ khóa ngoại (cha trước, con sau) — tránh lỗi FK.
  * Xóa dữ liệu cũ ở đích theo thứ tự NGƯỢC lại.
  * RESET SEQUENCE (auto-increment) sau khi copy — không bị trùng ID khi app
    ghi bản ghi mới (lỗi kinh điển khi migrate sang Postgres).
  * Ép kiểu boolean (SQLite lưu 0/1) và NaN→NULL.
  * Kiểm tra lại số dòng nguồn/đích từng bảng, in bảng tổng kết.

Cách chạy (PowerShell), từ thư mục backend:
    $env:SQLITE_PATH="./data/medforecast.db"
    $env:TARGET_DB_URL="postgresql+psycopg2://medforecast:PASS@localhost:5432/medforecast"
    python scripts\migrate_to_postgres.py
Trên Linux/VPS:
    SQLITE_PATH=./data/medforecast.db \
    TARGET_DB_URL=postgresql+psycopg2://medforecast:PASS@localhost:5432/medforecast \
    python scripts/migrate_to_postgres.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd
from sqlalchemy import MetaData, create_engine, inspect, text

SKIP_PREFIX = ("mart_", "fact_", "stg_", "dim_")
SKIP_NAMES = {"sync_state", "sqlite_sequence", "alembic_version"}


def main() -> None:
    src_path = os.environ.get("SQLITE_PATH", "./data/medforecast.db")
    tgt_url = os.environ.get("TARGET_DB_URL") or os.environ.get("DATABASE_URL")
    copy_all = os.environ.get("COPY_ALL", "0") == "1"
    if not tgt_url or tgt_url.startswith("sqlite"):
        print("Lỗi: đặt TARGET_DB_URL (hoặc DATABASE_URL) trỏ PostgreSQL.")
        sys.exit(1)
    if not os.path.exists(src_path):
        print(f"Lỗi: không thấy file SQLite: {src_path}")
        sys.exit(1)

    src = create_engine(f"sqlite:///{src_path}")
    tgt = create_engine(tgt_url)

    src_tables = set(inspect(src).get_table_names())

    # Phản chiếu schema ĐÍCH để biết thứ tự khóa ngoại (cha → con)
    meta = MetaData()
    meta.reflect(bind=tgt)
    ordered = [t.name for t in meta.sorted_tables]  # cha trước, con sau

    def skipped(name: str) -> bool:
        if name in SKIP_NAMES:
            return True
        if not copy_all and name.startswith(SKIP_PREFIX):
            return True
        return False

    todo = [t for t in ordered if t in src_tables and not skipped(t)]
    missing = [t for t in sorted(src_tables) if t not in set(ordered) and not skipped(t)]
    for t in missing:
        print(f"  bỏ qua {t} (chưa có bảng ở đích — hãy chạy backend trước)")

    tgt_insp = inspect(tgt)

    # 1) Xóa dữ liệu cũ ở đích theo thứ tự NGƯỢC (con trước, cha sau) để không vướng FK
    with tgt.begin() as conn:
        for t in reversed(todo):
            conn.exec_driver_sql(f'DELETE FROM "{t}"')

    # 2) Copy theo thứ tự cha → con
    copied: list[tuple[str, int]] = []
    for t in todo:
        df = pd.read_sql(f'SELECT * FROM "{t}"', src)
        if df.empty:
            copied.append((t, 0))
            continue
        # boolean: SQLite lưu 0/1 — Postgres cần True/False (giữ NULL)
        for col in tgt_insp.get_columns(t):
            cname, ctype = col["name"], str(col["type"]).upper()
            if cname in df.columns and "BOOL" in ctype:
                df[cname] = df[cname].map(
                    lambda v: None if pd.isna(v) else bool(v)
                ).astype("boolean")
        # NaN → NULL cho mọi cột object
        df = df.where(pd.notnull(df), None)
        df.to_sql(t, tgt, if_exists="append", index=False, chunksize=500)
        copied.append((t, len(df)))
        print(f"  copy {t}: {len(df)} dòng")

    # 3) Reset sequence auto-increment về max(id) — bắt buộc trên Postgres
    with tgt.begin() as conn:
        for t in todo:
            pk_cols = tgt_insp.get_pk_constraint(t).get("constrained_columns") or []
            for pk in pk_cols:
                seq = conn.execute(
                    text("SELECT pg_get_serial_sequence(:tbl, :col)"),
                    {"tbl": f'"{t}"', "col": pk},
                ).scalar()
                if seq:
                    conn.execute(
                        text(
                            f'SELECT setval(:seq, COALESCE((SELECT MAX("{pk}") FROM "{t}"), 0) + 1, false)'
                        ),
                        {"seq": seq},
                    )

    # 4) Đối chiếu số dòng nguồn/đích
    print("\n===== KIỂM TRA SỐ DÒNG =====")
    ok = True
    with src.connect() as sc, tgt.connect() as tc:
        for t, n in copied:
            n_src = sc.exec_driver_sql(f'SELECT COUNT(*) FROM "{t}"').scalar()
            n_tgt = tc.exec_driver_sql(f'SELECT COUNT(*) FROM "{t}"').scalar()
            flag = "OK " if n_src == n_tgt else "SAI"
            if n_src != n_tgt:
                ok = False
            print(f"  [{flag}] {t:35s} nguồn={n_src:<8} đích={n_tgt}")

    if ok:
        print("\n✅ Migrate xong — mọi bảng khớp số dòng. Sequence đã reset.")
    else:
        print("\n❌ Có bảng lệch số dòng — xem lại phía trên.")
        sys.exit(2)


if __name__ == "__main__":
    main()
