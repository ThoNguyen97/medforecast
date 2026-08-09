"""Đọc chuỗi số ca theo tháng từ MART / FACT (mức nhóm và mức mã)."""
from __future__ import annotations
import sqlite3
from typing import Dict, List
import pandas as pd


def _q(db_path: str, sql: str, params=()):
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def list_blocks(db_path: str, region: str = "TOAN_QUOC") -> List[str]:
    rows = _q(db_path,
              "select distinct block_code from mart_monthly_cases_by_block "
              "where region=? order by block_code", (region,))
    return [r[0] for r in rows]


def group_series(db_path: str, block: str, region: str = "TOAN_QUOC",
                 complete_only: bool = True,
                 from_period: str | None = None) -> pd.DataFrame:
    """Chuỗi tháng của cả NHÓM: [period, year, month, cases, is_covid].

    `from_period` dạng 'YYYY-MM' cắt lịch sử từ mốc đó trở đi.

    Vì sao cần: chuỗi có DỊCH CHUYỂN MỨC NỀN thì học trên giai đoạn mức cũ sẽ
    kéo dự báo xuống và hụt liên tục — sai một chiều, không tự sửa qua các kỳ.
    Đo mức dịch chuyển bằng mục 7 của `sql_his/06_danh_gia_du_lieu.sql`; tỷ số
    gần đây / trước đó vượt 2,0 là dấu hiệu phải cắt.

    Đánh đổi: cắt càng gần thì càng ít chu kỳ mùa vụ để học. Đừng chọn bằng cảm
    tính — chạy `run_eval.py --from-period` vài mốc rồi so MASE.
    """
    sql = ("select period, year, month, cases, is_covid, is_complete "
           "from mart_monthly_cases_by_block where region=? and block_code=? "
           "order by period")
    rows = _q(db_path, sql, (region, block))
    df = pd.DataFrame(rows, columns=["period", "year", "month", "cases",
                                     "is_covid", "is_complete"])
    if complete_only and not df.empty:
        df = df[df["is_complete"] == 1].reset_index(drop=True)
    if from_period and not df.empty:
        df = df[df["period"] >= from_period].reset_index(drop=True)
    df["cases"] = df["cases"].astype(float)
    df["is_covid"] = df["is_covid"].astype(bool)
    return df


def code_series(db_path: str, block: str,
                complete_only: bool = True,
                from_period: str | None = None) -> Dict[str, pd.DataFrame]:
    """Chuỗi tháng cho từng MÃ trong nhóm (gộp toàn quốc từ fact_disease_case)."""
    sql = ("select period, year, month, icd_code, sum(cases) as cases, "
           "max(is_covid) as is_covid, min(is_complete) as is_complete "
           "from fact_disease_case where block_code=? "
           "group by period, year, month, icd_code order by period")
    rows = _q(db_path, sql, (block,))
    df = pd.DataFrame(rows, columns=["period", "year", "month", "icd_code",
                                     "cases", "is_covid", "is_complete"])
    out: Dict[str, pd.DataFrame] = {}
    for code, g in df.groupby("icd_code"):
        g = g.sort_values("period").reset_index(drop=True)
        if complete_only:
            g = g[g["is_complete"] == 1].reset_index(drop=True)
        if from_period:
            g = g[g["period"] >= from_period].reset_index(drop=True)
        g["cases"] = g["cases"].astype(float)
        g["is_covid"] = g["is_covid"].astype(bool)
        out[code] = g[["period", "year", "month", "cases", "is_covid"]]
    return out


def fixed_shares(db_path: str, block: str) -> Dict[str, float]:
    rows = _q(db_path,
              "select icd_code, share from mart_icd_share_in_block "
              "where block_code=?", (block,))
    return {r[0]: float(r[1]) for r in rows}


def weather_series(db_path: str, region: str = "TOAN_QUOC") -> pd.DataFrame:
    """Thời tiết theo tháng: [period, temp, humidity, rainfall]. Rỗng nếu chưa có."""
    rows = _q(db_path,
              "select period, temp, humidity, rainfall from mart_monthly_weather "
              "where region=? order by period", (region,))
    df = pd.DataFrame(rows, columns=["period", "temp", "humidity", "rainfall"])
    for c in ["temp", "humidity", "rainfall"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def join_weather(cases_df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    """Ghép thời tiết vào chuỗi ca theo period (left join)."""
    if weather_df is None or weather_df.empty:
        return cases_df
    return cases_df.merge(weather_df, on="period", how="left")
