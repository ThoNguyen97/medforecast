"""Connector nguồn dữ liệu, trừu tượng hóa để đổi nguồn không phải sửa pipeline.

- FileConnector     : đọc file export CSV/Excel.
- SqlServerConnector: đọc view vw_MedForecast_* trong MEDFORECAST_DW (STA) qua pyodbc.

Cả hai trả về cùng một "hợp đồng dữ liệu" (cùng tên cột) để các tầng sau không
cần biết nguồn đến từ đâu.

Hợp đồng:
  fetch_case_supply(since_period) -> DataFrame[
      month, disease_code, disease_name, region, cases,
      supply_code, supply_name, supply_quantity, supply_unit, supply_category, note]
  fetch_inventory() -> DataFrame[
      supply_code, drug_code, ten_hoat_chat, unit, group_name, category,
      stock_quantity, description]

Cột `cases`: tổng số ca của (tháng × mã ICD × tỉnh), lặp lại trên mọi dòng vật tư
của cùng nhóm; pipeline lấy `max()` theo nhóm để khử lặp. Nguồn không được trả
`1 AS cases` theo từng lượt khám, nếu không chuỗi số ca phẳng bằng 1 mà không báo lỗi.

Nạp tăng dần: mã ICD thường được chốt trễ vài tuần, nên connector lùi
`PIPELINE_LOOKBACK_MONTHS` tháng (mặc định 3) và nạp lại cửa sổ đó. An toàn vì
pipeline ghi fact theo kiểu xóa-rồi-chèn từng tháng (idempotent).
"""
from __future__ import annotations

import abc
import logging
import re
import os
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

CASE_COLUMNS = [
    "month", "disease_code", "disease_name", "disease_group", "region", "cases",
    "supply_code", "supply_name", "supply_quantity", "supply_unit",
    "supply_category", "note",
]
# Số ca theo nhóm ICD là luồng riêng, không suy ra được từ CASE_COLUMNS: cộng số ca
# các mã con sẽ đếm hai lần lượt khám mang hai mã cùng nhóm (J01 + J06). Chỉ HIS còn
# mã lượt khám để đếm DISTINCT; nguồn không cấp được thì trả rỗng và pipeline cộng dồn.
CASE_GROUP_COLUMNS = [
    "month", "disease_group", "disease_group_name", "region", "cases",
]
INV_COLUMNS = [
    "supply_code", "drug_code", "ten_hoat_chat", "unit",
    "group_name", "category", "stock_quantity", "description",
]
CASE_NUMERIC = ["cases", "supply_quantity"]
CASE_GROUP_NUMERIC = ["cases"]
INV_NUMERIC = ["stock_quantity"]

# Số tháng lùi lại khi nạp tăng dần, để bắt dữ liệu được nhập/mã hóa muộn.
LOOKBACK_MONTHS = int(os.environ.get("PIPELINE_LOOKBACK_MONTHS", "3"))
# Đọc theo lô để không nạp toàn bộ lịch sử HIS vào RAM.
SQL_CHUNK_SIZE = int(os.environ.get("PIPELINE_SQL_CHUNKSIZE", "50000"))
# Thời gian chờ tối đa khi truy vấn HIS (giây).
SQL_TIMEOUT = int(os.environ.get("PIPELINE_SQL_TIMEOUT", "60"))
# Mốc rất sớm dùng khi chưa từng đồng bộ (nạp toàn bộ lịch sử).
EPOCH_DATE = "1900-01-01"

# Thư mục chứa câu SQL đọc nguồn, tách khỏi mã Python để chỉnh theo schema mà không sửa code.
SQL_DIR = Path(__file__).parent / "sql"


_RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_RE_LINE_COMMENT = re.compile(r"--[^\n]*")


def _bo_chu_thich(sql: str) -> str:
    """Bóc chú thích /* */ và -- khỏi câu SQL (lý do: xem ghi chú ở khối SQL bên dưới)."""
    return _RE_LINE_COMMENT.sub(" ", _RE_BLOCK_COMMENT.sub(" ", sql)).strip()


def _load_sql(filename: str) -> str:
    """Đọc câu SQL từ thư mục sql/; thiếu file thì ghi log và trả "" để app vẫn khởi động."""
    path = SQL_DIR / filename
    try:
        return _bo_chu_thich(path.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.error("Không đọc được câu SQL %s: %s", path, exc)
        return ""


def _period_key(month_str: str) -> str:
    """'MM/YYYY' -> 'YYYY-MM' để so sánh watermark."""
    try:
        mm, yyyy = str(month_str).split("/")
        return f"{int(yyyy):04d}-{int(mm):02d}"
    except Exception:
        return ""


def shift_period(period: str, months: int) -> Optional[str]:
    """'YYYY-MM' dịch đi `months` tháng (âm = lùi). None nếu period sai định dạng."""
    try:
        y, m = str(period).split("-")
        total = int(y) * 12 + (int(m) - 1) + months
        if total < 0:
            return None
        return f"{total // 12:04d}-{total % 12 + 1:02d}"
    except Exception:
        return None


def lookback_period(since_period: Optional[str],
                    months: int = LOOKBACK_MONTHS) -> Optional[str]:
    """Mốc bắt đầu nạp = watermark lùi `months` tháng (bao gồm chính mốc đó)."""
    if not since_period:
        return None
    return shift_period(since_period, -abs(months)) or since_period


def _conform(df: pd.DataFrame, columns: Iterable[str],
             numeric: Iterable[str]) -> pd.DataFrame:
    """Ép DataFrame về đúng hợp đồng cột: bù cột thiếu, bỏ cột thừa, ép kiểu số.

    Tránh KeyError khó truy ở tầng sau khi SQL nguồn trả thiếu/thừa/lệch thứ tự cột.
    """
    columns = list(columns)
    if df is None:
        df = pd.DataFrame(columns=columns)
    missing = [c for c in columns if c not in df.columns]
    if missing:
        logger.warning("Nguồn thiếu cột %s — điền NULL để giữ hợp đồng dữ liệu.", missing)
    for c in missing:
        df[c] = None
    extra = [c for c in df.columns if c not in columns]
    if extra:
        logger.info("Bỏ qua cột thừa từ nguồn: %s", extra)
    df = df[columns].copy()
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


class SourceConnector(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def fetch_case_supply(self, since_period: Optional[str] = None) -> pd.DataFrame: ...

    @abc.abstractmethod
    def fetch_inventory(self) -> pd.DataFrame: ...

    def fetch_case_group(self, since_period: Optional[str] = None) -> pd.DataFrame:
        """Số ca đã đếm DISTINCT ở mức nhóm ICD.

        Không bắt buộc: trả rỗng thì pipeline cộng dồn từ mã (chấp nhận đếm trùng
        ca đa chẩn đoán trong cùng nhóm, có ghi cảnh báo).
        """
        return _conform(None, CASE_GROUP_COLUMNS, CASE_GROUP_NUMERIC)


class FileConnector(SourceConnector):
    """Đọc nguồn từ thư mục file export CSV/Excel."""
    name = "file"

    def __init__(self, data_dir: str | Path,
                 case_file: str = "data_GIAAN_6_2019_2026.csv",
                 inventory_file: str = "data_TonKho_GiaAn_2019-2026.csv",
                 case_group_file: str = "data_CaBenh_Nhom.csv"):
        self.data_dir = Path(data_dir)
        self.case_file = case_file
        self.inventory_file = inventory_file
        self.case_group_file = case_group_file

    def fetch_case_supply(self, since_period: Optional[str] = None) -> pd.DataFrame:
        df = pd.read_csv(self.data_dir / self.case_file, dtype=str)
        df = _conform(df, CASE_COLUMNS, CASE_NUMERIC)
        start = lookback_period(since_period)
        if start:
            # `>=` + lookback: nạp lại vài tháng gần nhất để bắt dữ liệu về muộn.
            df = df[df["month"].map(_period_key) >= start]
        return df

    def fetch_inventory(self) -> pd.DataFrame:
        df = pd.read_csv(self.data_dir / self.inventory_file, dtype=str)
        return _conform(df, INV_COLUMNS, INV_NUMERIC)

    def fetch_case_group(self, since_period: Optional[str] = None) -> pd.DataFrame:
        """File export số ca theo nhóm (từ MF_CaBenh_Nhom); không có file thì trả rỗng."""
        path = self.data_dir / self.case_group_file
        if not path.exists():
            return _conform(None, CASE_GROUP_COLUMNS, CASE_GROUP_NUMERIC)
        df = _conform(pd.read_csv(path, dtype=str),
                      CASE_GROUP_COLUMNS, CASE_GROUP_NUMERIC)
        start = lookback_period(since_period)
        if start:
            df = df[df["month"].map(_period_key) >= start]
        return df


class SqlServerConnector(SourceConnector):
    """Đọc view vw_MedForecast_* trong MEDFORECAST_DW (SQL Server trên STA).

    Yêu cầu pyodbc và driver ODBC msodbcsql17/18 (riêng `unixodbc-dev` chưa đủ). Chuỗi kết nối:
      mssql+pyodbc://user:pass@host:1433/DB?driver=ODBC+Driver+18+for+SQL+Server
          &Encrypt=yes&TrustServerCertificate=yes

    Câu SQL trong thư mục sql/ phải giữ tên cột đầu ra (CASE_COLUMNS / INV_COLUMNS) và
    tham số `:since_date`. Đổi file qua PIPELINE_CASE_SQL_FILE / PIPELINE_INVENTORY_SQL_FILE.
    """
    name = "sqlserver"

    def __init__(self, conn_str: str,
                 case_sql: Optional[str] = None,
                 inventory_sql: Optional[str] = None,
                 case_group_sql: Optional[str] = None,
                 chunk_size: int = SQL_CHUNK_SIZE):
        self.conn_str = conn_str
        # Thứ tự ưu tiên: tham số truyền vào > file chỉ định qua biến môi trường
        # > file mặc định trong sql/ (bản đọc view STA).
        self.case_sql = case_sql or _sql_from_env(
            "PIPELINE_CASE_SQL_FILE", "case_sta.sql")
        self.inventory_sql = inventory_sql or _sql_from_env(
            "PIPELINE_INVENTORY_SQL_FILE", "inventory_sta.sql")
        # Luồng số ca theo nhóm do thủ tục PROD tính sẵn; không đặt biến môi trường
        # thì để trống và pipeline cộng dồn từ mã.
        self.case_group_sql = case_group_sql if case_group_sql is not None else (
            _load_sql(os.environ["PIPELINE_CASE_GROUP_SQL_FILE"])
            if os.environ.get("PIPELINE_CASE_GROUP_SQL_FILE") else "")
        self.chunk_size = chunk_size
        self._engine = None

    def _check_sql(self, sql: str, what: str) -> str:
        if not sql.strip():
            raise RuntimeError(
                f"Chưa có câu SQL đọc {what} từ HIS. Kiểm tra thư mục "
                f"{SQL_DIR} hoặc biến môi trường PIPELINE_*_SQL_FILE.")
        return sql

    def _engine_(self):
        if self._engine is None:
            from sqlalchemy import create_engine  # import trễ để dev không cần driver
            self._engine = create_engine(
                self.conn_str,
                pool_pre_ping=True,      # phát hiện kết nối đã chết (VPN/firewall ngắt)
                pool_recycle=1800,       # làm mới kết nối mỗi 30 phút
                connect_args={"timeout": SQL_TIMEOUT},
            )
        return self._engine

    def _read(self, sql: str, params: dict) -> pd.DataFrame:
        """Đọc theo lô.

        Bắt buộc bọc text(): với chuỗi SQL thô, pandas đẩy tham số thẳng xuống DBAPI,
        mà pyodbc (paramstyle 'qmark') không nhận dict.
        """
        stmt = text(sql)
        reader = pd.read_sql(stmt, self._engine_(), params=params or None,
                             chunksize=self.chunk_size)
        parts = [c for c in reader]
        if not parts:
            return pd.DataFrame()
        return pd.concat(parts, ignore_index=True)

    def fetch_case_supply(self, since_period: Optional[str] = None) -> pd.DataFrame:
        self._check_sql(self.case_sql, "ca bệnh")
        start = lookback_period(since_period)
        params = {}
        if ":since_date" in self.case_sql:
            params["since_date"] = f"{start}-01" if start else EPOCH_DATE
        elif start:
            logger.warning(
                "case_sql không có tham số :since_date — sẽ nạp lại TOÀN BỘ lịch sử "
                "mỗi lần đồng bộ. Thêm 'AND <cột ngày khám> >= :since_date' vào SQL.")
        df = self._read(self.case_sql, params)
        return _conform(df, CASE_COLUMNS, CASE_NUMERIC)

    def fetch_inventory(self) -> pd.DataFrame:
        self._check_sql(self.inventory_sql, "tồn kho")
        df = self._read(self.inventory_sql, {})
        return _conform(df, INV_COLUMNS, INV_NUMERIC)

    def fetch_case_group(self, since_period: Optional[str] = None) -> pd.DataFrame:
        if not self.case_group_sql.strip():
            return _conform(None, CASE_GROUP_COLUMNS, CASE_GROUP_NUMERIC)
        start = lookback_period(since_period)
        params = {}
        if ":since_date" in self.case_group_sql:
            params["since_date"] = f"{start}-01" if start else EPOCH_DATE
        df = self._read(self.case_group_sql, params)
        return _conform(df, CASE_GROUP_COLUMNS, CASE_GROUP_NUMERIC)


# ── Nạp câu SQL ──
# Câu SQL nằm trong sql/, không nhúng trong Python, để chỉnh theo schema mà không sửa code.
#   sql/case_sta.sql          ca bệnh + vật tư (vw_MedForecast_CaBenh)
#   sql/case_group_sta.sql    số ca theo nhóm ICD (vw_MedForecast_CaBenhNhom)
#   sql/inventory_sta.sql     tồn kho (vw_MedForecast_TonKho)
#
# Chú thích SQL được bóc trước khi gửi: SQLAlchemy text() coi mọi `:ten` là tham số kể cả
# trong /* */, còn pyodbc bóc chú thích trước khi đếm dấu hỏi, gây lệch số tham số.
#
# Chỉ định file khác qua PIPELINE_CASE_SQL_FILE / PIPELINE_INVENTORY_SQL_FILE
# (đường dẫn tuyệt đối, hoặc tên file trong thư mục sql/).
def _sql_from_env(env_var: str, default_file: str) -> str:
    name = os.environ.get(env_var, default_file)
    path = Path(name)
    if path.is_absolute() or path.parent != Path("."):
        try:
            return _bo_chu_thich(path.read_text(encoding="utf-8"))
        except OSError as exc:
            logger.error("Không đọc được câu SQL %s: %s", path, exc)
            return ""
    return _load_sql(name)


