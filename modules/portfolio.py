"""
保有ポジション管理・損益計算モジュール
USD/JPY レートでリアルタイム円換算
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

# ─── 保有銘柄（初期データ）────────────────────────────────────────
HOLDINGS: list[dict] = [
    # 米国株
    {"symbol": "ARM",   "name": "ARM Holdings",        "qty": 5,   "avg_cost": 349.07,   "currency": "USD", "sector": "AI・半導体"},
    {"symbol": "GOOG",  "name": "Alphabet (Google)",    "qty": 10,  "avg_cost": 374.604,  "currency": "USD", "sector": "通信・テック"},
    {"symbol": "JNJ",   "name": "Johnson & Johnson",    "qty": 7,   "avg_cost": 156.8914, "currency": "USD", "sector": "ヘルスケア"},
    {"symbol": "NVDA",  "name": "NVIDIA",               "qty": 25,  "avg_cost": 214.7592, "currency": "USD", "sector": "AI・半導体"},
    {"symbol": "PEP",   "name": "PepsiCo",              "qty": 10,  "avg_cost": 129.98,   "currency": "USD", "sector": "消費・生活"},
    {"symbol": "SPCX",  "name": "Procure Space ETF",    "qty": 4,   "avg_cost": 135.00,   "currency": "USD", "sector": "防衛・宇宙"},
    {"symbol": "TSLA",  "name": "Tesla",                "qty": 6,   "avg_cost": 266.57,   "currency": "USD", "sector": "消費・生活"},
    # 日本株
    {"symbol": "1321.T","name": "NF日経225 ETF",        "qty": 5,   "avg_cost": 69690,    "currency": "JPY", "sector": "日本株・分散"},
    {"symbol": "9202.T","name": "ANAホールディングス",  "qty": 100, "avg_cost": 2839,     "currency": "JPY", "sector": "航空・旅行"},
]


def _get_price(symbol: str) -> tuple[str, float | None, float]:
    """(symbol, current_price, day_change_pct) を返す"""
    try:
        hist = yf.Ticker(symbol).history(period="5d")
        if hist.empty:
            return symbol, None, 0.0
        closes = hist["Close"].dropna()
        curr = float(closes.iloc[-1])
        chg = 0.0
        if len(closes) >= 2:
            chg = (curr - float(closes.iloc[-2])) / float(closes.iloc[-2]) * 100
        return symbol, round(curr, 2), round(chg, 2)
    except Exception:
        return symbol, None, 0.0


def _get_usdjpy() -> float:
    try:
        hist = yf.Ticker("JPY=X").history(period="2d")
        if not hist.empty:
            return round(float(hist["Close"].dropna().iloc[-1]), 2)
    except Exception:
        pass
    return 150.0


def get_portfolio() -> dict:
    # 並列でUSD/JPYと全銘柄の価格を取得
    all_symbols = [h["symbol"] for h in HOLDINGS]

    with ThreadPoolExecutor(max_workers=8) as ex:
        price_futs = {ex.submit(_get_price, sym): sym for sym in all_symbols}
        fx_fut     = ex.submit(_get_usdjpy)
        price_map: dict[str, tuple] = {}
        for fut in as_completed(price_futs):
            sym, price, chg = fut.result()
            price_map[sym] = (price, chg)
        usdjpy = fx_fut.result()

    holdings_out = []
    total_cost_jpy    = 0.0
    total_current_jpy = 0.0
    total_day_pnl_jpy = 0.0

    for h in HOLDINGS:
        curr_price, day_chg = price_map.get(h["symbol"], (None, 0.0))
        if curr_price is None:
            curr_price = h["avg_cost"]   # フォールバック

        cost_native    = h["avg_cost"] * h["qty"]
        current_native = curr_price    * h["qty"]
        pnl_native     = current_native - cost_native
        pnl_pct        = pnl_native / cost_native * 100 if cost_native else 0

        if h["currency"] == "USD":
            cost_jpy    = cost_native    * usdjpy
            current_jpy = current_native * usdjpy
            pnl_jpy     = pnl_native     * usdjpy
        else:
            cost_jpy    = cost_native
            current_jpy = current_native
            pnl_jpy     = pnl_native

        day_pnl_jpy = current_jpy * (day_chg / 100)

        total_cost_jpy    += cost_jpy
        total_current_jpy += current_jpy
        total_day_pnl_jpy += day_pnl_jpy

        holdings_out.append({
            **h,
            "current_price":   round(curr_price, 2),
            "day_change_pct":  round(day_chg, 2),
            "cost_native":     round(cost_native, 2),
            "current_native":  round(current_native, 2),
            "pnl_native":      round(pnl_native, 2),
            "pnl_pct":         round(pnl_pct, 2),
            "current_jpy":     round(current_jpy, 0),
            "pnl_jpy":         round(pnl_jpy, 0),
            "day_pnl_jpy":     round(day_pnl_jpy, 0),
        })

    total_pnl_jpy  = total_current_jpy - total_cost_jpy
    total_pnl_pct  = total_pnl_jpy / total_cost_jpy * 100 if total_cost_jpy else 0

    return {
        "holdings":         sorted(holdings_out, key=lambda x: x["pnl_pct"], reverse=True),
        "usdjpy":           usdjpy,
        "total_cost_jpy":   round(total_cost_jpy, 0),
        "total_current_jpy":round(total_current_jpy, 0),
        "total_pnl_jpy":    round(total_pnl_jpy, 0),
        "total_pnl_pct":    round(total_pnl_pct, 2),
        "total_day_pnl_jpy":round(total_day_pnl_jpy, 0),
    }
