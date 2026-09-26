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
    """Chuỗi tháng của cả nhóm; `from_period` ('YYYY-MM') cắt lịch sử từ mốc đó."""
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
    """Chuỗi tháng từng mã trong nhóm, gộp toàn quốc."""
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
    """Thời tiết theo tháng; rỗng nếu chưa có."""
    rows = _q(db_path,
              "select period, temp, humidity, rainfall from mart_monthly_weather "
              "where region=? order by period", (region,))
    df = pd.DataFrame(rows, columns=["period", "temp", "humidity", "rainfall"])
    for c in ["temp", "humidity", "rainfall"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def join_weather(cases_df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    """Left join thời tiết vào chuỗi ca theo period."""
    if weather_df is None or weather_df.empty:
        return cases_df
    return cases_df.merge(weather_df, on="period", how="left")
