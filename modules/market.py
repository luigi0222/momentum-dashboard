"""
市場全体の主要指標を取得するモジュール
VIX / S&P500 / NASDAQ / SOX / USD-JPY / 米10年金利 / Fear&Greed
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import yfinance as yf

_SYMBOLS = {
    "VIX":    ("^VIX",  "VIX",      False),   # (ticker, label, positive_is_good)
    "SP500":  ("^GSPC", "S&P500",   True),
    "NASDAQ": ("^IXIC", "NASDAQ",   True),
    "SOX":    ("^SOX",  "SOX",      True),
    "USDJPY": ("JPY=X", "USD/JPY",  True),
    "US10Y":  ("^TNX",  "米10年金利", None),   # None = neutral
}


def _fetch_one(key: str, symbol: str) -> tuple[str, dict]:
    try:
        hist = yf.Ticker(symbol).history(period="5d")
        if hist.empty:
            return key, None
        closes = hist["Close"].dropna()
        if len(closes) < 2:
            return key, {"value": round(float(closes.iloc[-1]), 2), "change_pct": 0.0}
        curr = float(closes.iloc[-1])
        prev = float(closes.iloc[-2])
        chg = (curr - prev) / prev * 100
        return key, {"value": round(curr, 2), "change_pct": round(chg, 2)}
    except Exception:
        return key, None


def _fetch_fear_greed() -> dict:
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=6)
        d = r.json()["data"][0]
        return {"value": int(d["value"]), "text": d["value_classification"]}
    except Exception:
        return {"value": None, "text": "N/A"}


def get_market_overview() -> dict:
    result = {}

    with ThreadPoolExecutor(max_workers=7) as ex:
        futs = {ex.submit(_fetch_one, k, sym): (k, label, pos)
                for k, (sym, label, pos) in _SYMBOLS.items()}
        fg_fut = ex.submit(_fetch_fear_greed)

        for fut in as_completed(futs):
            k, label, positive_is_good = futs[fut]
            data = fut.result()[1]
            result[k] = {
                "label": label,
                "positive_is_good": positive_is_good,
                **(data if data else {"value": None, "change_pct": 0.0}),
            }

        result["FEAR_GREED"] = {
            "label": "恐怖・貪欲",
            "positive_is_good": True,
            **fg_fut.result(),
        }

    return result
