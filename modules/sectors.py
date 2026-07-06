"""
セクター別モメンタムスコア計算モジュール
5指標 × 20pts = 100点満点でスコアリング
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import yfinance as yf

# ─── セクター定義 ──────────────────────────────────────────────────
SECTORS: dict[str, dict] = {
    "AI・半導体": {
        "etf": "SOXX",
        "stocks": ["NVDA", "AMD", "AVGO", "TSM", "ASML", "AMAT", "KLAC", "ARM"],
        "jp_stocks": ["6857.T", "8035.T", "6920.T", "7735.T"],
        "color": "#7c3aed",
        "icon": "🤖",
    },
    "防衛・宇宙": {
        "etf": "ITA",
        "stocks": ["LMT", "RTX", "NOC", "GD", "BA", "SPCX"],
        "jp_stocks": ["7011.T", "7013.T"],
        "color": "#1d4ed8",
        "icon": "🛡️",
    },
    "エネルギー": {
        "etf": "XLE",
        "stocks": ["XOM", "CVX", "COP", "SLB", "EOG"],
        "jp_stocks": ["5020.T", "5019.T"],
        "color": "#b45309",
        "icon": "⚡",
    },
    "金融": {
        "etf": "XLF",
        "stocks": ["JPM", "BAC", "WFC", "GS", "MS"],
        "jp_stocks": ["8306.T", "8316.T", "8411.T"],
        "color": "#0891b2",
        "icon": "🏦",
    },
    "ヘルスケア": {
        "etf": "XLV",
        "stocks": ["JNJ", "UNH", "PFE", "ABBV", "MRK"],
        "jp_stocks": ["4502.T", "4519.T"],
        "color": "#059669",
        "icon": "💊",
    },
    "消費・生活": {
        "etf": "XLY",
        "stocks": ["AMZN", "TSLA", "HD", "MCD", "PEP"],
        "jp_stocks": ["3382.T", "9983.T"],
        "color": "#e11d48",
        "icon": "🛍️",
    },
    "通信・テック": {
        "etf": "XLC",
        "stocks": ["GOOG", "META", "NFLX", "DIS", "VZ"],
        "jp_stocks": ["9432.T", "9984.T"],
        "color": "#6d28d9",
        "icon": "📡",
    },
    "インフラ・電力": {
        "etf": "XLU",
        "stocks": ["NEE", "DUK", "SO", "D", "AEP"],
        "jp_stocks": ["9501.T", "9503.T"],
        "color": "#713f12",
        "icon": "🏭",
    },
    "航空・旅行": {
        "etf": "JETS",
        "stocks": ["DAL", "UAL", "AAL", "LUV", "MAR"],
        "jp_stocks": ["9202.T", "9201.T"],
        "color": "#0f766e",
        "icon": "✈️",
    },
    "商社・資源": {
        "etf": "DBC",
        "stocks": ["GLD", "SLV", "FCX", "NEM", "BHP"],
        "jp_stocks": ["8031.T", "8053.T", "8058.T"],
        "color": "#c2410c",
        "icon": "⛏️",
    },
}


# ─── 指標計算 ─────────────────────────────────────────────────────

def _rsi(prices: np.ndarray, period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_g = np.mean(gains[:period])
    avg_l = np.mean(losses[:period])
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return round(100 - 100 / (1 + rs), 1)


def _score(metrics: dict) -> int:
    s = 0

    # ① 当日リターン (0–20 pts)
    r = metrics.get("day_return", 0)
    if r >= 0.025:   s += 20
    elif r >= 0.01:  s += 15
    elif r >= 0:     s += 10
    elif r >= -0.01: s += 5
    # else 0

    # ② 5日リターン (0–20 pts)
    r5 = metrics.get("return_5d", 0)
    if r5 >= 0.04:   s += 20
    elif r5 >= 0.02: s += 15
    elif r5 >= 0:    s += 10
    elif r5 >= -0.03: s += 4
    # else 0

    # ③ RSI (0–20 pts)
    rsi = metrics.get("rsi", 50)
    if 55 <= rsi <= 70:   s += 20
    elif 50 <= rsi < 55:  s += 15
    elif 45 <= rsi < 50:  s += 10
    elif 70 < rsi <= 80:  s += 12
    elif 30 <= rsi < 45:  s += 5
    # else 0

    # ④ MA20との乖離率 (0–20 pts)
    ma = metrics.get("ma20_pct", 0)
    if ma >= 0.03:   s += 20
    elif ma >= 0.01: s += 15
    elif ma >= 0:    s += 10
    elif ma >= -0.02: s += 5
    # else 0

    # ⑤ 出来高比率 (0–20 pts)
    vr = metrics.get("vol_ratio", 1)
    if vr >= 2.0:    s += 20
    elif vr >= 1.5:  s += 16
    elif vr >= 1.2:  s += 12
    elif vr >= 1.0:  s += 8
    elif vr >= 0.8:  s += 4
    # else 0

    return min(100, max(0, s))


def _label(score: int) -> str:
    if score >= 80: return "強い"
    if score >= 65: return "やや強い"
    if score >= 50: return "中立"
    return "弱い"


# ─── ETFデータ取得 ────────────────────────────────────────────────

def _fetch_etf(etf: str) -> tuple[str, dict | None]:
    try:
        hist = yf.Ticker(etf).history(period="30d")
        if hist.empty or len(hist) < 3:
            return etf, None
        prices  = hist["Close"].dropna().values.astype(float)
        volumes = hist["Volume"].dropna().values.astype(float)
        if len(prices) < 3:
            return etf, None
        return etf, {"prices": prices, "volumes": volumes}
    except Exception:
        return etf, None


def get_all_sectors() -> list[dict]:
    etf_list = [info["etf"] for info in SECTORS.values()]

    # 並列ダウンロード
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(_fetch_etf, etf): etf for etf in etf_list}
        hist_map: dict[str, dict | None] = {}
        for fut in as_completed(futs):
            etf, data = fut.result()
            hist_map[etf] = data

    results = []
    for name, info in SECTORS.items():
        etf  = info["etf"]
        data = hist_map.get(etf)

        if data is None:
            results.append({
                "name": name, "etf": etf, "icon": info["icon"],
                "color": info["color"], "score": 50, "label": "取得中",
                "day_return": 0, "return_5d": 0, "rsi": 50,
                "ma20_pct": 0, "vol_ratio": 1, "current_price": None,
            })
            continue

        prices  = data["prices"]
        volumes = data["volumes"]
        curr    = prices[-1]
        prev    = prices[-2]
        day_r   = (curr - prev) / prev
        r5d     = (curr - prices[-6]) / prices[-6] if len(prices) >= 6 else 0
        ma20    = float(np.mean(prices[-20:])) if len(prices) >= 20 else float(np.mean(prices))
        ma_pct  = (curr - ma20) / ma20
        rsi_val = _rsi(prices)
        vavg    = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else float(np.mean(volumes))
        vr      = float(volumes[-1]) / vavg if vavg > 0 else 1.0

        metrics = {
            "day_return": day_r, "return_5d": r5d,
            "rsi": rsi_val, "ma20_pct": ma_pct, "vol_ratio": vr,
        }
        sc = _score(metrics)

        results.append({
            "name": name,
            "etf": etf,
            "stocks": info["stocks"],
            "jp_stocks": info.get("jp_stocks", []),
            "icon": info["icon"],
            "color": info["color"],
            "score": sc,
            "label": _label(sc),
            "day_return": round(day_r * 100, 2),
            "return_5d":  round(r5d   * 100, 2),
            "rsi":        rsi_val,
            "ma20_pct":   round(ma_pct * 100, 2),
            "vol_ratio":  round(vr, 2),
            "current_price": round(float(curr), 2),
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)
