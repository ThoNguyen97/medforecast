"""LÕI DỰ BÁO TOP-DOWN HAI TẦNG.

Đặt tại: backend/app/forecasting/topdown.py

    Tầng A   dự báo TỔNG số ca hô hấp (J00-J06 + J09-J18 + J20-J22)
    Tầng B   phân rã tổng ra ba nhóm theo tỷ trọng cửa sổ trượt có co ngót

=============================================================================
VÌ SAO LÀ MODULE MỚI, KHÔNG SỬA ai_forecaster.py

`ai_forecaster.py` là bàn thí nghiệm: nó chạy năm mô hình song song trên từng
nhóm, đo ablation, đo độ phủ khoảng dự báo. Toàn bộ bảng so sánh trong báo cáo
tốt nghiệp sinh ra từ đó — kể cả những con số ÂM TÍNH (thời tiết không giúp,
XGBoost thua Ridge, seasonal-naive 40,8%). Xoá nó đi là xoá luôn phần chứng
minh khoa học.

Module này là mã CHẠY THẬT: một mô hình, một mục tiêu, đưa số lên dashboard.
Hai file phục vụ hai mục đích khác nhau và cùng tồn tại.

=============================================================================
VÌ SAO TẦNG A KHÔNG CÓ BIẾN THỜI TIẾT

Đặc tả ban đầu ghi "chỉ kích hoạt biến thời tiết cho J20-J22". Ở kiến trúc
Top-Down thì Tầng A chỉ có MỘT chuỗi tổng — không còn "mô hình J20-J22" để bật
thời tiết vào. Thêm nữa phép đo cũ cho thấy thời tiết chỉ giúp J20-J22 khi dùng
XGBoost (50,1% → 40,6%), không giúp Ridge; mà Tầng A dùng Ridge.

Kết luận: Tầng A chạy sạch, không thời tiết. Phần đo thời tiết giữ nguyên trong
`ai_forecaster.py` như một thí nghiệm đối chứng có kết quả âm tính — đó là kết
quả nghiên cứu, không phải thiếu sót.

=============================================================================
VÌ SAO TẦNG B PHẢI CO NGÓT

Tỷ trọng ba nhóm không ổn định: J20-J22 và J09-J18 đang trao đổi ca bệnh cho
nhau (tương quan +0,18 toàn chuỗi nhưng −0,39 từ 2024-01). Lấy thẳng tỷ trọng
12 kỳ gần nhất thì một tháng lệch sẽ kéo cả dự báo lệch theo.

Co ngót về phân bố biên dài hơn (24 kỳ):

    p̂_g = λ · p12_g  +  (1 − λ) · p24_g        λ = K / (K + K₀)

với K = số kỳ thật có trong cửa sổ ngắn, K₀ = 6. Cửa sổ đủ 12 kỳ → λ = 0,667.
Cửa sổ mới có 3 kỳ → λ = 0,333, tự động nghiêng về phân bố dài hạn.

`min_period` là chốt chặn cứng: cửa sổ trượt KHÔNG được với ngược vào chế độ mã
hoá cũ, dù thời gian trôi bao lâu.

=============================================================================
CHẠY

    cd backend
    python -m app.forecasting.topdown --backtest
    python -m app.forecasting.topdown --forecast
    python -m app.forecasting.topdown --save          # ghi forecast_accuracy
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TOAN_QUOC = "TOAN_QUOC"
BLOCKS: Tuple[str, ...] = ("J00-J06", "J09-J18", "J20-J22")

# Mặc định của Tầng B nếu chưa có `dss.block_share` trong system_config.
BLOCK_SHARE_DEFAULT: Dict[str, Any] = {
    "window_periods":   12,     # cửa sổ ngắn — tỷ trọng hiện hành
    "marginal_periods": 24,     # phân bố biên để co ngót về
    "shrink_k0":        6,
    # Chốt chặn cứng. Đợt chuyển mã J20↔J18 bắt đầu quanh đầu 2024; cửa sổ
    # trượt không bao giờ được với ngược trước mốc này.
    "min_period":       "2024-01",
}


@dataclass
class Config:
    db_path: str = "data/medforecast.db"
    lags: Tuple[int, ...] = (1, 2, 3, 12)
    horizons: Tuple[int, ...] = (1, 2, 3)
    n_test: int = 24
    min_train: int = 24
    ridge_alpha: float = 10.0
    interval_level: float = 0.80
    blocks: Sequence[str] = field(default_factory=lambda: BLOCKS)


# ─────────────────────────────────────────────────────────────────────────────
# Đọc dữ liệu
# ─────────────────────────────────────────────────────────────────────────────

def _connect(db_path: str) -> sqlite3.Connection:
    cx = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cx.row_factory = sqlite3.Row
    return cx


def load_block_cases(cfg: Config) -> pd.DataFrame:
    """Số ca theo kỳ × nhóm. Chỉ kỳ ĐÃ CHỐT, chỉ vùng TOAN_QUOC.

    `is_complete = 1` là bắt buộc: kỳ đang mở luôn thiếu dữ liệu (T9/2026 có 3
    ca trong khi T8 có 341) — để lọt vào tập huấn luyện là dạy mô hình rằng
    dịch vừa sụp đổ.
    """
    with _connect(cfg.db_path) as cx:
        df = pd.read_sql(
            "SELECT period, block_code, cases FROM mart_monthly_cases_by_block "
            "WHERE region = ? AND is_complete = 1 AND block_code IN (?,?,?) "
            "ORDER BY period, block_code",
            cx, params=(TOAN_QUOC, *BLOCKS))
    if df.empty:
        raise RuntimeError(
            "mart_monthly_cases_by_block không có kỳ nào is_complete = 1. "
            "Chạy pipeline ca bệnh trước.")
    return df


def load_total(cfg: Config) -> pd.DataFrame:
    """Chuỗi TỔNG — mục tiêu của Tầng A.

    Chỉ giữ kỳ có ĐỦ CẢ BA nhóm. Một kỳ khuyết một nhóm (J20-J22 khuyết
    2019-02) sẽ cho tổng thấp giả tạo, và mô hình học đó là một cú sụt thật.
    """
    df = load_block_cases(cfg)
    piv = df.pivot_table(index="period", columns="block_code",
                         values="cases", aggfunc="sum")
    du = piv.dropna(how="any")
    thieu = len(piv) - len(du)
    if thieu:
        logger.warning("Bỏ %d kỳ khuyết nhóm (tổng sẽ thấp giả nếu giữ lại): %s",
                       thieu, list(piv.index[piv.isna().any(axis=1)]))
    out = (du.sum(axis=1).rename("cases").reset_index()
             .sort_values("period").reset_index(drop=True))
    return out


def get_block_share_config(db_path: str) -> Dict[str, Any]:
    cfg = dict(BLOCK_SHARE_DEFAULT)
    try:
        with _connect(db_path) as cx:
            r = cx.execute("SELECT config_value FROM system_config "
                           "WHERE config_key = 'dss.block_share'").fetchone()
        if r:
            cfg.update(json.loads(r[0]))
    except Exception:                                    # noqa: BLE001
        logger.info("Chưa có dss.block_share — dùng mặc định %s", BLOCK_SHARE_DEFAULT)
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# Đặc trưng
# ─────────────────────────────────────────────────────────────────────────────

def make_features(total: pd.DataFrame, lags: Sequence[int]) -> Tuple[pd.DataFrame, List[str]]:
    """t, month, quarter, hai cặp điều hoà, và các biến trễ.

    `month` và `quarter` vào dưới dạng điều hoà sin/cos chứ không phải số
    nguyên: tháng 12 và tháng 1 kề nhau trên vòng năm, còn 12 và 1 thì cách
    nhau 11 đơn vị nếu để nguyên số.
    """
    d = total.copy()
    d["t"] = np.arange(len(d), dtype=float)
    m = d["period"].str[5:7].astype(int)
    d["month"] = m
    d["quarter"] = ((m - 1) // 3 + 1).astype(int)
    d["sin1"] = np.sin(2 * np.pi * m / 12)
    d["cos1"] = np.cos(2 * np.pi * m / 12)
    d["sin2"] = np.sin(4 * np.pi * m / 12)
    d["cos2"] = np.cos(4 * np.pi * m / 12)
    for L in lags:
        d[f"lag{L}"] = d["cases"].shift(L)

    feats = ["t", "month", "quarter", "sin1", "cos1", "sin2", "cos2"] + \
            [f"lag{L}" for L in lags]
    d = d.dropna(subset=feats + ["cases"]).reset_index(drop=True)
    return d, feats


def _fit_ridge(X: np.ndarray, y: np.ndarray, alpha: float):
    """Ridge có chuẩn hoá. Chuẩn hoá là bắt buộc, không phải trang trí:
    `t` chạy 0→90 còn `sin1` chạy −1→1; không chuẩn hoá thì hình phạt L2 rơi
    gần hết vào các cột biên độ nhỏ."""
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(StandardScaler(), Ridge(alpha=alpha)).fit(X, y)


# ─────────────────────────────────────────────────────────────────────────────
# Chỉ số sai số
# ─────────────────────────────────────────────────────────────────────────────

def wape(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    s = np.abs(y).sum()
    return float("nan") if s == 0 else float(100 * np.abs(y - p).sum() / s)


def mae(y, p) -> float:
    return float(np.abs(np.asarray(y, float) - np.asarray(p, float)).mean())


def rmse(y, p) -> float:
    return float(np.sqrt(((np.asarray(y, float) - np.asarray(p, float)) ** 2).mean()))


def r2(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    ss = ((y - y.mean()) ** 2).sum()
    return float("nan") if ss == 0 else float(1 - ((y - p) ** 2).sum() / ss)


# ─────────────────────────────────────────────────────────────────────────────
# TẦNG A — kiểm định walk-forward
# ─────────────────────────────────────────────────────────────────────────────

def backtest(cfg: Config) -> pd.DataFrame:
    """Rolling-origin, CẮT ĐÚNG TẦM DỰ BÁO.

    Để dự báo kỳ i với tầm h, mô hình chỉ được thấy dữ liệu tới kỳ i−h. Nếu
    huấn luyện tới i−1 rồi gọi đó là dự báo 3 tháng thì con số đẹp lên nhưng
    vô nghĩa — đó là lỗi phổ biến nhất trong các báo cáo dự báo chuỗi thời gian.

    Kèm `naive1` (giữ nguyên kỳ trước) làm đối chuẩn. Nếu mô hình không thắng
    naive1 ở h ≥ 2 thì mô hình không có giá trị.
    """
    total = load_total(cfg)
    d, feats = make_features(total, cfg.lags)
    n = len(d)
    n_test = min(cfg.n_test, max(6, n - cfg.min_train - 2))
    if n_test < 6:
        raise RuntimeError(f"Chỉ có {n} kỳ dùng được sau khi tạo biến trễ — "
                           f"không đủ để kiểm định (cần ≥ {cfg.min_train + 8}).")

    out: List[Dict[str, Any]] = []
    for h in cfg.horizons:
        for i in range(n - n_test, n):
            cut = i - h + 1                     # số dòng được phép huấn luyện
            if cut < cfg.min_train:
                continue
            tr = d.iloc[:cut]
            mdl = _fit_ridge(tr[feats].to_numpy(float),
                             tr["cases"].to_numpy(float), cfg.ridge_alpha)
            pred = float(mdl.predict(d.iloc[[i]][feats].to_numpy(float))[0])
            out.append({
                "h": h,
                "period": d["period"].iloc[i],
                "y": float(d["cases"].iloc[i]),
                "pred": max(0.0, pred),
                "naive1": float(d["cases"].iloc[cut - 1]),
                "n_train": cut,
            })
    bt = pd.DataFrame(out)
    if bt.empty:
        raise RuntimeError("Kiểm định không sinh được điểm nào — kiểm tra min_train.")
    return bt


def summarise(bt: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for h, g in bt.groupby("h"):
        for model, col in (("ridge_total", "pred"), ("naive1", "naive1")):
            rows.append({
                "model": model, "h": int(h), "n": len(g),
                "wape": round(wape(g.y, g[col]), 3),
                "mae":  round(mae(g.y, g[col]), 2),
                "rmse": round(rmse(g.y, g[col]), 2),
                "r2":   round(r2(g.y, g[col]), 3),
            })
    return pd.DataFrame(rows).sort_values(["h", "model"]).reset_index(drop=True)


def empirical_intervals(bt: pd.DataFrame, level: float = 0.80) -> Dict[int, Tuple[float, float]]:
    """Khoảng dự báo từ PHÂN VỊ CỦA TỶ SỐ thực/dự báo, không phải ±1,28·σ.

    Lý do: sai số số ca không đối xứng và không chuẩn — chuỗi bị giới hạn dưới
    ở 0 và có đuôi phải dày. Giả định chuẩn cho ra khoảng âm ở nhóm nhỏ và
    khoảng quá hẹp ở đỉnh mùa.

    Trả {h: (hệ số dưới, hệ số trên)}. Nhân trực tiếp vào điểm dự báo.
    """
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    out: Dict[int, Tuple[float, float]] = {}
    for h, g in bt.groupby("h"):
        r = (g.y / g.pred.replace(0, np.nan)).dropna()
        if len(r) < 8:
            out[int(h)] = (1.0, 1.0)
            continue
        out[int(h)] = (float(r.quantile(lo_q)), float(r.quantile(hi_q)))
    return out


def interval_coverage(bt: pd.DataFrame, level: float = 0.80) -> pd.DataFrame:
    """Độ phủ thực tế, tính kiểu bỏ-một-ra để không tự chấm điểm mình.

    Hệ số khoảng cho mỗi điểm được tính từ tất cả các điểm KHÁC. Không làm vậy
    thì độ phủ luôn ra đúng bằng `level` — một con số vô nghĩa.
    """
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    rows = []
    for h, g in bt.groupby("h"):
        g = g.reset_index(drop=True)
        r = (g.y / g.pred.replace(0, np.nan))
        trong = 0
        dem = 0
        for i in range(len(g)):
            khac = r.drop(index=i).dropna()
            if len(khac) < 8 or not np.isfinite(g.pred[i]) or g.pred[i] <= 0:
                continue
            lo = g.pred[i] * khac.quantile(lo_q)
            hi = g.pred[i] * khac.quantile(hi_q)
            dem += 1
            trong += int(lo <= g.y[i] <= hi)
        rows.append({"h": int(h), "n": dem, "muc_tieu_pct": round(100 * level, 1),
                     "do_phu_pct": round(100 * trong / dem, 1) if dem else float("nan")})
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# TẦNG B — tỷ trọng nhóm có co ngót
# ─────────────────────────────────────────────────────────────────────────────

def block_shares(cfg: Config) -> pd.DataFrame:
    """Tỷ trọng ba nhóm: cửa sổ trượt ngắn, co ngót về phân bố biên dài.

        p̂_g = λ · p_ngắn,g + (1 − λ) · p_biên,g        λ = K / (K + K₀)

    Trả kèm cả ba cột p_ngắn / p_biên / p̂ để giao diện và người đọc báo cáo
    thấy được co ngót đã dịch tỷ trọng đi bao nhiêu — không phải một con số
    rơi từ trên trời xuống.
    """
    sc = get_block_share_config(cfg.db_path)
    n_ngan = int(sc["window_periods"])
    n_bien = int(sc["marginal_periods"])
    k0 = float(sc["shrink_k0"])
    san = str(sc["min_period"])

    df = load_block_cases(cfg)
    df = df[df["period"] >= san]
    if df.empty:
        raise RuntimeError(f"Không có kỳ nào từ {san} trở đi trong "
                           f"mart_monthly_cases_by_block.")

    ky = sorted(df["period"].unique())
    ky_ngan = ky[-n_ngan:]
    ky_bien = ky[-n_bien:]

    def _share(periods: List[str]) -> pd.Series:
        s = (df[df["period"].isin(periods)]
             .groupby("block_code")["cases"].sum()
             .reindex(cfg.blocks).fillna(0.0))
        tong = s.sum()
        return s / tong if tong > 0 else s

    p_ngan = _share(ky_ngan)
    p_bien = _share(ky_bien)

    K = float(len(ky_ngan))
    lam = K / (K + k0)
    p_hat = lam * p_ngan + (1 - lam) * p_bien
    tong = p_hat.sum()
    if tong > 0:
        p_hat = p_hat / tong                      # chuẩn hoá lại cho chắc

    out = pd.DataFrame({
        "block_code": list(cfg.blocks),
        "p_ngan":     [round(float(p_ngan.get(b, 0)), 6) for b in cfg.blocks],
        "p_bien":     [round(float(p_bien.get(b, 0)), 6) for b in cfg.blocks],
        "p_hat":      [round(float(p_hat.get(b, 0)), 6) for b in cfg.blocks],
    })
    out["lambda"] = round(lam, 4)
    out["so_ky_ngan"] = len(ky_ngan)
    out["so_ky_bien"] = len(ky_bien)
    out["tu_ky"] = ky_ngan[0]
    out["den_ky"] = ky_ngan[-1]
    out["san_min_period"] = san
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Dự báo ra kỳ tới
# ─────────────────────────────────────────────────────────────────────────────

def _shift_period(period: str, months: int) -> str:
    y, m = period.split("-")
    t = int(y) * 12 + int(m) - 1 + months
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def forecast(cfg: Config, bt: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Dự báo Tầng A cho từng tầm, rồi phân rã bằng Tầng B.

    Khoảng dự báo của từng nhóm nhân đúng tỷ trọng của nhóm đó — cách này giả
    định tỷ trọng chắc chắn, nên khoảng nhóm HẸP HƠN thực tế. Đã ghi rõ trong
    `ghi_chu` để giao diện không trình bày nó như khoảng đã hiệu chỉnh đủ.
    """
    if bt is None:
        bt = backtest(cfg)
    hs = empirical_intervals(bt, cfg.interval_level)
    shares = block_shares(cfg)
    p_hat = dict(zip(shares["block_code"], shares["p_hat"]))

    total = load_total(cfg)
    d, feats = make_features(total, cfg.lags)
    ky_cuoi = d["period"].iloc[-1]

    mdl = _fit_ridge(d[feats].to_numpy(float), d["cases"].to_numpy(float),
                     cfg.ridge_alpha)

    rows: List[Dict[str, Any]] = []
    for h in cfg.horizons:
        # Dự báo h kỳ tới bằng cách trượt đặc trưng: các biến trễ ≥ h lấy được
        # từ dữ liệu thật; các biến trễ < h phải lấy chính dự báo trước đó.
        chuoi = total["cases"].tolist()
        for step in range(1, h + 1):
            ky = _shift_period(ky_cuoi, step)
            tam = pd.DataFrame({"period": total["period"].tolist() +
                                [_shift_period(ky_cuoi, s) for s in range(1, step + 1)],
                                "cases": chuoi + [np.nan]})
            tam.loc[tam.index[-1], "cases"] = 0.0     # chỗ giữ, không dùng làm nhãn
            dd = tam.copy()
            dd["t"] = np.arange(len(dd), dtype=float)
            m = dd["period"].str[5:7].astype(int)
            dd["month"] = m
            dd["quarter"] = ((m - 1) // 3 + 1).astype(int)
            dd["sin1"] = np.sin(2 * np.pi * m / 12); dd["cos1"] = np.cos(2 * np.pi * m / 12)
            dd["sin2"] = np.sin(4 * np.pi * m / 12); dd["cos2"] = np.cos(4 * np.pi * m / 12)
            for L in cfg.lags:
                dd[f"lag{L}"] = dd["cases"].shift(L)
            hang = dd.iloc[[-1]]
            if hang[feats].isna().any(axis=1).iloc[0]:
                break
            diem = max(0.0, float(mdl.predict(hang[feats].to_numpy(float))[0]))
            chuoi = chuoi + [diem]
        else:
            ky = _shift_period(ky_cuoi, h)
            lo_k, hi_k = hs.get(h, (1.0, 1.0))
            rows.append({"h": h, "period": ky, "muc": "TONG",
                         "block_code": None,
                         "diem": round(diem, 1),
                         "lo": round(diem * lo_k, 1),
                         "hi": round(diem * hi_k, 1)})
            for b in cfg.blocks:
                rows.append({"h": h, "period": ky, "muc": "NHOM",
                             "block_code": b,
                             "diem": round(diem * p_hat.get(b, 0), 1),
                             "lo": round(diem * lo_k * p_hat.get(b, 0), 1),
                             "hi": round(diem * hi_k * p_hat.get(b, 0), 1)})
            continue
        logger.warning("Không dự báo được tầm h=%d (thiếu biến trễ).", h)

    return {
        "ky_neo": ky_cuoi,
        "du_bao": pd.DataFrame(rows),
        "ty_trong": shares,
        "he_so_khoang": hs,
        "muc_tin_cay": cfg.interval_level,
        "ghi_chu": ("Khoảng của từng nhóm = khoảng của tổng × tỷ trọng, tức coi "
                    "tỷ trọng là chắc chắn. Khoảng nhóm vì vậy hẹp hơn thực tế."),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Ghi kết quả kiểm định
# ─────────────────────────────────────────────────────────────────────────────

DDL_ACCURACY = """
CREATE TABLE IF NOT EXISTS forecast_accuracy (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at       TEXT    NOT NULL,
    target       TEXT    NOT NULL,          -- 'TONG' hoặc mã nhóm
    model        TEXT    NOT NULL,
    h            INTEGER NOT NULL,
    n_points     INTEGER NOT NULL,
    wape         REAL,
    mae          REAL,
    rmse         REAL,
    r2           REAL,
    tu_ky        TEXT,
    den_ky       TEXT,
    do_phu_pct   REAL,
    muc_tin_cay  REAL,
    ghi_chu      TEXT
)
"""


def save_accuracy(cfg: Config, bt: pd.DataFrame, ghi_chu: str = "") -> int:
    """Ghi kết quả walk-forward vào `forecast_accuracy`.

    Mỗi lần chạy là một lô mới (`run_at`) — KHÔNG ghi đè lô trước. Lịch sử độ
    chính xác chính là bằng chứng mô hình không xấu đi theo thời gian, và nó
    cũng là bảng để phát hiện trôi dữ liệu.
    """
    cov = interval_coverage(bt, cfg.interval_level).set_index("h")["do_phu_pct"].to_dict()
    tong = summarise(bt)
    from datetime import datetime
    run_at = datetime.now().isoformat(timespec="seconds")

    cx = sqlite3.connect(cfg.db_path)
    try:
        cx.execute(DDL_ACCURACY)
        n = 0
        for _, r in tong.iterrows():
            g = bt[bt.h == r.h]
            cx.execute(
                "INSERT INTO forecast_accuracy (run_at,target,model,h,n_points,"
                "wape,mae,rmse,r2,tu_ky,den_ky,do_phu_pct,muc_tin_cay,ghi_chu) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_at, "TONG", r.model, int(r.h), int(r.n),
                 float(r.wape), float(r.mae), float(r.rmse), float(r.r2),
                 str(g.period.min()), str(g.period.max()),
                 cov.get(int(r.h)) if r.model == "ridge_total" else None,
                 cfg.interval_level if r.model == "ridge_total" else None,
                 ghi_chu))
            n += 1
        cx.commit()
        return n
    finally:
        cx.close()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _in(tieu_de: str, df) -> None:
    print(f"\n── {tieu_de} " + "─" * max(0, 66 - len(tieu_de)))
    print(df.to_string(index=False) if hasattr(df, "to_string") else df)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Dự báo Top-Down hai tầng")
    ap.add_argument("--db", default="data/medforecast.db")
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--forecast", action="store_true")
    ap.add_argument("--shares", action="store_true")
    ap.add_argument("--save", action="store_true", help="ghi vào forecast_accuracy")
    ap.add_argument("--n-test", type=int, default=24)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

    cfg = Config(db_path=a.db, n_test=a.n_test)
    if not (a.backtest or a.forecast or a.shares or a.save):
        a.backtest = a.forecast = True

    bt = None
    if a.backtest or a.save or a.forecast:
        bt = backtest(cfg)
    if a.backtest:
        _in("TẦNG A · kiểm định walk-forward", summarise(bt))
        _in("TẦNG A · độ phủ khoảng dự báo", interval_coverage(bt, cfg.interval_level))
    if a.shares or a.forecast:
        _in("TẦNG B · tỷ trọng nhóm có co ngót", block_shares(cfg))
    if a.forecast:
        kq = forecast(cfg, bt)
        _in(f"DỰ BÁO · neo tại kỳ {kq['ky_neo']}", kq["du_bao"])
        print("\n  " + kq["ghi_chu"])
    if a.save:
        n = save_accuracy(cfg, bt, ghi_chu="topdown Tầng A, Ridge, không thời tiết")
        print(f"\n  Đã ghi {n} dòng vào forecast_accuracy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
