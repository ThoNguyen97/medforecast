"""Kiểm tra các sửa lỗi của tầng đồng bộ HIS (data_pipeline).

Chạy từ thư mục `backend/`:
    python scripts/verify_his_pipeline.py --data-dir ../data

Script dùng nguồn file + SQLite tạm nên KHÔNG cần HIS thật và không đụng vào DB
của ứng dụng. Nội dung kiểm tra:
  1. Bảng environmental_data vắng mặt không làm rollback mất fact/mart (lỗi im lặng).
  2. Watermark có lùi lại để bắt dữ liệu về muộn (PIPELINE_LOOKBACK_MONTHS).
  3. Cờ is_complete được tính lại mỗi lần chạy, tự sửa bản ghi bị kẹt.
  4. Hợp đồng cột được ép chặt khi nguồn trả thiếu/thừa cột.
  5. Đường đọc SQL Server (text() + tham số + đọc theo lô), mô phỏng bằng SQLite.
  6. Kiểm tra ngược: SQL kiểu `1 AS cases` cho ra 1 ca/tháng — minh họa vì sao
     DEFAULT_CASE_SQL phải đếm COUNT(DISTINCT lượt khám).
  7. Tính idempotent: chạy lại nhiều lần cho cùng kết quả.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")

# cho phép chạy từ backend/ hoặc backend/scripts/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

FAIL: list[str] = []
TMP = tempfile.mkdtemp(prefix="medforecast_verify_")


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  [PASS] " if cond else "  [FAIL] ") + name + (f"  — {detail}" if detail else ""))
    if not cond:
        FAIL.append(name)


def fresh_db(name: str, with_env_table: bool = True) -> str:
    path = os.path.join(TMP, name)
    if os.path.exists(path):
        os.remove(path)
    if with_env_table:
        c = sqlite3.connect(path)
        c.execute("create table environmental_data(recorded_at text, location text,"
                  " temperature real, humidity real, rainfall real)")
        c.commit()
        c.close()
    return path


def run_pipeline(db_path: str, data_dir: str, incremental: bool = False) -> dict:
    """Nạp lại module để engine bám đúng PIPELINE_DB_URL của lần chạy này."""
    os.environ["PIPELINE_DB_URL"] = f"sqlite:///{db_path}"
    for mod in [m for m in list(sys.modules) if m.startswith("app.data_pipeline")]:
        del sys.modules[mod]
    from app.data_pipeline.connectors import FileConnector
    from app.data_pipeline.icd_hierarchy import IcdHierarchy
    from app.data_pipeline.pipeline import DataPipeline
    hier = IcdHierarchy.from_files(f"{data_dir}/TM_ICD.xlsx",
                                   f"{data_dir}/TM_ICD_CHUONG.xlsx")
    return DataPipeline(FileConnector(data_dir), hier).run(incremental=incremental)


def q(db_path: str, sql: str):
    c = sqlite3.connect(db_path)
    try:
        return c.execute(sql).fetchall()
    finally:
        c.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Kiểm tra tầng đồng bộ HIS")
    ap.add_argument("--data-dir", default="../data",
                    help="thư mục chứa CSV nguồn + TM_ICD*.xlsx")
    args = ap.parse_args()
    data_dir = args.data_dir

    # ── mốc so sánh: chạy đầy đủ trên DB có sẵn bảng environmental_data ──
    print("\n[0] Mốc so sánh (chạy đầy đủ)")
    base = fresh_db("base.db")
    run_pipeline(base, data_dir)
    ref_fact = q(base, "select count(*),sum(cases) from fact_disease_case")[0]
    ref_mart = q(base, "select count(*) from mart_monthly_cases_by_block")[0][0]
    ref_usage = q(base, "select count(*) from fact_supply_usage")[0][0]
    check("nạp được fact", ref_fact[0] > 0, f"{ref_fact[0]} dòng / {ref_fact[1]} ca")
    check("dựng được mart", ref_mart > 0, f"{ref_mart} dòng")

    # ── 1. lỗi rollback im lặng ──
    print("\n[1] DB thiếu bảng environmental_data không được làm mất dữ liệu")
    p = fresh_db("noenv.db", with_env_table=False)
    res = run_pipeline(p, data_dir)
    check("pipeline chạy xong", res["rows_ingested"] > 0, str(res["rows_ingested"]))
    check("fact KHÔNG bị rollback",
          q(p, "select count(*),sum(cases) from fact_disease_case")[0] == ref_fact)
    check("mart vẫn được dựng",
          q(p, "select count(*) from mart_monthly_cases_by_block")[0][0] == ref_mart)
    check("fact_supply_usage vẫn đủ",
          q(p, "select count(*) from fact_supply_usage")[0][0] == ref_usage)

    # ── 2. watermark lookback ──
    print("\n[2] Watermark lùi lại để bắt dữ liệu về muộn")
    from app.data_pipeline.connectors import (FileConnector, lookback_period,
                                              shift_period, LOOKBACK_MONTHS)
    check("shift_period lùi qua năm", shift_period("2026-02", -3) == "2025-11",
          str(shift_period("2026-02", -3)))
    check("chưa có watermark -> None", lookback_period(None) is None)

    fc = FileConnector(data_dir)
    full = fc.fetch_case_supply()
    last = max(f"{s.split('/')[1]}-{s.split('/')[0]}" for s in full["month"])
    inc = fc.fetch_case_supply(since_period=last)
    months_inc = sorted({f"{s.split('/')[1]}-{s.split('/')[0]}" for s in inc["month"]})
    check(f"nạp lại cửa sổ {LOOKBACK_MONTHS + 1} tháng",
          len(months_inc) == LOOKBACK_MONTHS + 1, str(months_inc))
    check("tháng ở mốc watermark VẪN được nạp lại", last in months_inc)
    check("không nạp thừa toàn bộ lịch sử", len(inc) < len(full))

    # ── 3. is_complete ──
    print("\n[3] Cờ tháng-trọn-vẹn được tính lại mỗi lần chạy")
    p2 = fresh_db("complete.db")
    run_pipeline(p2, data_dir)
    victim = q(p2, "select max(period) from fact_disease_case "
                   "where period < strftime('%Y-%m','now')")[0][0]
    c = sqlite3.connect(p2)
    c.execute("update fact_disease_case set is_complete=0 where period=?", (victim,))
    c.commit()
    c.close()
    stuck = q(p2, f"select count(*) from fact_disease_case "
                  f"where period='{victim}' and is_complete=0")[0][0]
    check("giả lập được trạng thái cờ bị kẹt", stuck > 0, f"{victim}: {stuck} dòng")
    run_pipeline(p2, data_dir, incremental=True)
    check("lần đồng bộ sau tự sửa cờ kẹt",
          q(p2, f"select count(*) from fact_disease_case "
                f"where period='{victim}' and is_complete=0")[0][0] == 0)
    cur = pd.Timestamp.today().strftime("%Y-%m")
    check("mọi tháng quá khứ đều trọn vẹn",
          q(p2, f"select count(*) from fact_disease_case "
                f"where period<'{cur}' and is_complete=0")[0][0] == 0)
    check("tháng hiện tại không bị coi là trọn vẹn",
          q(p2, f"select count(*) from mart_monthly_cases_by_block "
                f"where period>='{cur}' and is_complete=1")[0][0] == 0)

    # ── 4. hợp đồng cột ──
    print("\n[4] Hợp đồng cột khi nguồn trả thiếu/thừa/lệch thứ tự")
    from app.data_pipeline.connectors import _conform, CASE_COLUMNS, CASE_NUMERIC
    messy = pd.DataFrame({"region": ["Hà Nội"], "month": ["01/2026"], "cases": ["7"],
                          "disease_code": ["J01"], "cot_thua": ["x"]})
    out = _conform(messy, CASE_COLUMNS, CASE_NUMERIC)
    check("đủ và đúng thứ tự cột", list(out.columns) == CASE_COLUMNS)
    check("bỏ cột thừa", "cot_thua" not in out.columns)
    check("bù cột thiếu bằng NULL", out["supply_code"].isna().all())
    check("ép kiểu số", out["cases"].iloc[0] == 7 and out["cases"].dtype.kind in "if")

    # ── 5. đường đọc SQL Server ──
    print("\n[5] Đường đọc SQL Server: text() + tham số + đọc theo lô")
    his = os.path.join(TMP, "his.db")
    eng = create_engine(f"sqlite:///{his}")
    with eng.begin() as conn:
        conn.exec_driver_sql("create table kham(encounter_id int, ngay_kham text,"
                             " disease_code text, disease_name text, region text)")
        conn.exec_driver_sql("create table dungvt(encounter_id int, supply_code text,"
                             " supply_name text, qty real, unit text, cat text)")
        for r in [(1, '2026-01-05', 'J01', 'Viêm xoang', 'Hà Nội'),
                  (2, '2026-01-09', 'J01', 'Viêm xoang', 'Hà Nội'),
                  (3, '2026-01-20', 'J01', 'Viêm xoang', 'Hà Nội'),
                  (4, '2026-02-02', 'J01', 'Viêm xoang', 'Hà Nội')]:
            conn.exec_driver_sql("insert into kham values (?,?,?,?,?)", r)
        for r in [(1, 'AMOT', 'Amoxicilin', 10.0, 'Viên', 'KS'),
                  (2, 'AMOT', 'Amoxicilin', 14.0, 'Viên', 'KS'),
                  (2, 'NEMT', 'Esomeprazol', 5.0, 'Viên', 'TH'),
                  (3, 'AMOT', 'Amoxicilin', 6.0, 'Viên', 'KS'),
                  (4, 'AMOT', 'Amoxicilin', 8.0, 'Viên', 'KS')]:
            conn.exec_driver_sql("insert into dungvt values (?,?,?,?,?,?)", r)

    # Bản dịch SQLite của DEFAULT_CASE_SQL — GIỮ NGUYÊN cấu trúc CTE và cách đếm ca.
    sqlite_case_sql = """
    WITH ca AS (
        SELECT DISTINCT encounter_id, ngay_kham, disease_code, disease_name, region
        FROM kham WHERE ngay_kham >= :since_date
    ),
    ca_thang AS (
        SELECT strftime('%m/%Y', ngay_kham) AS month, disease_code,
               MAX(disease_name) AS disease_name, region,
               COUNT(DISTINCT encounter_id) AS cases
        FROM ca GROUP BY strftime('%m/%Y', ngay_kham), disease_code, region
    ),
    vt_thang AS (
        SELECT strftime('%m/%Y', c.ngay_kham) AS month, c.disease_code, c.region,
               d.supply_code, MAX(d.supply_name) AS supply_name,
               SUM(d.qty) AS supply_quantity, MAX(d.unit) AS supply_unit,
               MAX(d.cat) AS supply_category
        FROM ca c JOIN dungvt d ON d.encounter_id = c.encounter_id
        GROUP BY strftime('%m/%Y', c.ngay_kham), c.disease_code, c.region, d.supply_code
    )
    SELECT ct.month, ct.disease_code, ct.disease_name, ct.region, ct.cases,
           vt.supply_code, vt.supply_name, vt.supply_quantity, vt.supply_unit,
           vt.supply_category, NULL AS note
    FROM ca_thang ct
    LEFT JOIN vt_thang vt ON vt.month = ct.month
                         AND vt.disease_code = ct.disease_code
                         AND vt.region = ct.region
    """

    from app.data_pipeline.connectors import SqlServerConnector
    src = SqlServerConnector("sqlite://", case_sql=sqlite_case_sql, chunk_size=2)
    src._engine = eng

    df = src.fetch_case_supply()
    check("đọc theo lô ghép lại đủ dòng", len(df) == 3, f"{len(df)} dòng")
    check("hợp đồng cột đúng", list(df.columns) == CASE_COLUMNS)
    jan = df[df["month"] == "01/2026"]
    check("cases = số lượt khám (3), không phải 1", set(jan["cases"]) == {3},
          str(sorted(set(jan["cases"]))))
    check("cases lặp trên mọi dòng vật tư", len(jan) == 2, f"{len(jan)} dòng vật tư")
    check("lượng vật tư cộng đúng (10+14+6=30)",
          jan[jan["supply_code"] == "AMOT"]["supply_quantity"].iloc[0] == 30.0)
    check("tham số :since_date truyền được qua text()",
          len(src.fetch_case_supply(since_period="2026-02")) == 3)
    check("lọc theo cột ngày hoạt động đúng",
          set(src.fetch_case_supply(since_period="2026-05")["month"]) == {"02/2026"})

    import inspect as _inspect
    import pandas.io.sql as _psql
    check("pandas dùng exec_driver_sql cho chuỗi thô (vì sao phải bọc text())",
          "exec_driver_sql" in _inspect.getsource(_psql.SQLDatabase.execute))

    # ── 6. kiểm tra ngược ──
    print("\n[6] Kiểm tra ngược: SQL kiểu '1 AS cases' sẽ hỏng thế nào")
    bad_sql = """
    SELECT strftime('%m/%Y', k.ngay_kham) AS month, k.disease_code, k.disease_name,
           k.region, 1 AS cases, d.supply_code, d.supply_name,
           d.qty AS supply_quantity, d.unit AS supply_unit, d.cat AS supply_category,
           NULL AS note
    FROM kham k LEFT JOIN dungvt d ON d.encounter_id = k.encounter_id
    WHERE k.ngay_kham >= :since_date
    """
    bad = SqlServerConnector("sqlite://", case_sql=bad_sql)
    bad._engine = eng
    from app.data_pipeline.icd_hierarchy import IcdHierarchy
    from app.data_pipeline.pipeline import DataPipeline
    pp = DataPipeline.__new__(DataPipeline)
    pp.hier = IcdHierarchy.from_files(f"{data_dir}/TM_ICD.xlsx",
                                      f"{data_dir}/TM_ICD_CHUONG.xlsx")
    pp.target_only = False
    clean_bad, _, _ = pp._transform_cases(bad.fetch_case_supply())
    agg_bad = clean_bad.groupby(["period", "icd_code", "region"])["cases"].max()
    clean_ok, _, _ = pp._transform_cases(df)
    agg_ok = clean_ok.groupby(["period", "icd_code", "region"])["cases"].max()
    check("SQL kiểu cũ cho ra đúng 1 ca/tháng — SAI", set(agg_bad) == {1},
          str(sorted(set(agg_bad))))
    check("SQL mới cho đúng 3 ca tháng 01/2026",
          int(agg_ok.loc[("2026-01", "J01", "Hà Nội")]) == 3)

    # ── 7. idempotent ──
    print("\n[7] Tính idempotent (chạy lại 3 lần)")
    p3 = fresh_db("idem.db")
    counts = []
    for _ in range(3):
        run_pipeline(p3, data_dir, incremental=True)
        counts.append(q(p3, "select count(*),sum(cases) from fact_disease_case")[0])
    check("3 lần chạy cho cùng kết quả", len(set(counts)) == 1, str(counts))
    check("khớp mốc so sánh", counts[0] == ref_fact, str(counts[0]))

    print("\n" + "=" * 62)
    print("KẾT QUẢ:", "TẤT CẢ PASS" if not FAIL else f"{len(FAIL)} TEST HỎNG: {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(code)
