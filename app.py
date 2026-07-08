"""
セクター別モメンタム投資ダッシュボード
Flask + Flask-Caching（5分キャッシュ）
"""
import os
from datetime import datetime
from flask import Flask, jsonify, render_template
from flask_caching import Cache
from dotenv import load_dotenv

from modules.market    import get_market_overview
from modules.sectors   import get_all_sectors
from modules.portfolio import get_portfolio

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
cache = Cache(app, config={
    "CACHE_TYPE":            "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,   # 5分
})

# ─── ページ ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

# ─── API ──────────────────────────────────────────────────────────

@app.route("/api/all")
@cache.cached(timeout=300, key_prefix="api_all")
def api_all():
    """フロントエンドが1回で全データを取得するエンドポイント"""
    market    = get_market_overview()
    sectors   = get_all_sectors()
    portfolio = get_portfolio()
    alerts    = _build_alerts(sectors, portfolio)
    return jsonify({
        "market":    market,
        "sectors":   sectors,
        "portfolio": portfolio,
        "alerts":    alerts,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })

@app.route("/api/market")
@cache.cached(timeout=300)
def api_market():
    return jsonify(get_market_overview())

@app.route("/api/sectors")
@cache.cached(timeout=300)
def api_sectors():
    return jsonify(get_all_sectors())

@app.route("/api/portfolio")
@cache.cached(timeout=300)
def api_portfolio():
    return jsonify(get_portfolio())

@app.route("/health")
def health():
    return jsonify({"ok": True, "time": datetime.now().isoformat()})

# ─── アラート生成 ─────────────────────────────────────────────────

def _build_alerts(sectors: list[dict], portfolio: dict) -> list[dict]:
    alerts = []
    portfolio_sectors = {h["sector"] for h in portfolio.get("holdings", [])}

    for s in sectors:
        sc   = s["score"]
        name = s["name"]
        icon = s["icon"]

        # 強いモメンタム (≥80)
        if sc >= 80:
            related = name in portfolio_sectors
            alerts.append({
                "type":    "momentum",
                "emoji":   "🚀",
                "sector":  name,
                "score":   sc,
                "title":   f"{icon} {name}  強いモメンタム",
                "details": [
                    f"本日 {s['day_return']:+.2f}%",
                    f"5日  {s['return_5d']:+.2f}%",
                    f"RSI  {s['rsi']}",
                    f"出来高比 {s['vol_ratio']:.1f}x",
                ],
                "portfolio_related": related,
            })

        # 押し目候補 (≤30)
        elif sc <= 30:
            related = name in portfolio_sectors
            alerts.append({
                "type":    "dip",
                "emoji":   "📉",
                "sector":  name,
                "score":   sc,
                "title":   f"{icon} {name}  押し目候補",
                "details": [
                    f"本日 {s['day_return']:+.2f}%",
                    f"5日  {s['return_5d']:+.2f}%",
                    f"RSI  {s['rsi']} (低水準)",
                    f"MA20乖離 {s['ma20_pct']:+.2f}%",
                ],
                "portfolio_related": related,
            })

        # 初動シグナル候補（弱から中立以上へ移行 & 出来高急増）
        elif 50 <= sc < 65 and s.get("vol_ratio", 1) >= 1.5:
            alerts.append({
                "type":    "early",
                "emoji":   "✨",
                "sector":  name,
                "score":   sc,
                "title":   f"{icon} {name}  初動シグナル候補",
                "details": [
                    f"出来高急増 {s['vol_ratio']:.1f}x",
                    f"本日 {s['day_return']:+.2f}%",
                    f"5日  {s['return_5d']:+.2f}%",
                ],
                "portfolio_related": name in portfolio_sectors,
            })

    # 保有銘柄の本日大きな動き
    for h in portfolio.get("holdings", []):
        chg = h.get("day_change_pct", 0)
        if abs(chg) >= 3:
            emoji = "📈" if chg > 0 else "📉"
            alerts.append({
                "type":    "position",
                "emoji":   emoji,
                "sector":  h["sector"],
                "score":   None,
                "title":   f"{emoji} 保有銘柄  {h['name']}  {chg:+.2f}%",
                "details": [
                    f"本日損益 ¥{h['day_pnl_jpy']:+,.0f}",
                    f"取得単価 {h['avg_cost']} {h['currency']}",
                    f"現在値   {h['current_price']} {h['currency']}",
                ],
                "portfolio_related": True,
            })

    return alerts

# ─── 起動 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
