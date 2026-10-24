import requests, telebot

TOKEN = "8712193895:AAEVRwDIcpHGTC9Pzef5jSBhNNuHnqgFodc"
bot = telebot.TeleBot(TOKEN)

def get_crypto_klines(symbol, interval, limit=100):
    for u in [f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
              f"https://api3.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"]:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if r.status_code == 200:
                return [[float(x) for x in c[:6]] for c in r.json()]
        except Exception:
            continue
    return None

def get_forex_klines(symbol, interval="1d", limit=100):
    fx = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "JPY=X",
          "AUDUSD": "AUDUSD=X", "USDCAD": "CAD=X", "USDCHF": "CHF=X",
          "NZDUSD": "NZDUSD=X", "XAUUSD": "GC=F", "GOLD": "GC=F"}
    t = fx.get(symbol.upper(), f"{symbol.upper()}=X")
    tf = {"1w": "1wk", "1d": "1d", "4h": "1h", "15m": "15m"}.get(interval, "1d")
    rng = "60d" if tf in ["1h", "15m"] else "1y"
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range={rng}&interval={tf}",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.status_code == 200:
            q = r.json()['chart']['result'][0]['indicators']['quote'][0]
            c = []
            for i in range(len(q['close'])):
                if q['open'][i] is not None and q['close'][i] is not None:
                    c.append([0, float(q['open'][i]), float(q['high'][i]), float(q['low'][i]), float(q['close'][i]), 0.0])
            return c[-limit:]
    except Exception:
        pass
    return None

def fetch_data(sym, interval, limit=100):
    s = sym.replace("/", "").upper()
    if s in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "XAUUSD", "GOLD"] or s.endswith("=X"):
        return get_forex_klines(s, interval, limit)
    if not s.endswith("USDT") and not s.endswith("BUSD"):
        s += "USDT"
    return get_crypto_klines(s, interval, limit)

def detect_msnr_zones(candles, window=3):
    z = []
    if not candles or len(candles) < window * 2 + 1: return z
    for i in range(window, len(candles) - window):
        h = [c[2] for c in candles[i - window : i + window + 1]]
        l = [c[3] for c in candles[i - window : i + window + 1]]
        cur = candles[i]
        if cur[2] == max(h): z.append(('Resistance', max(cur[1], cur[4]), cur[2]))
        if cur[3] == min(l): z.append(('Support', min(cur[1], cur[4]), cur[3]))
    return z

def detect_engulfing(candles):
    if not candles or len(candles) < 3: return "None"
    p, c = candles[-2], candles[-1]
    if p[4] <= p[1] and c[4] > c[1] and c[4] >= p[1] and c[1] <= p[4]: return "Bullish Engulfing"
    if p[4] >= p[1] and c[4] < c[1] and c[4] <= p[1] and c[1] >= p[4]: return "Bearish Engulfing"
    if p[4] > p[1] and c[2] > p[2] and c[4] < p[1]: return "Bearish Engulfing Failed (Trap)"
    if p[4] < p[1] and c[3] < p[3] and c[4] > p[1]: return "Bullish Engulfing Failed (Trap)"
    return "Neutral"

def evaluate_alchemist(symbol):
    d1 = fetch_data(symbol, "1d", limit=45)
    if not d1: return f"❌ Could not retrieve `{symbol}`. Try `BTCUSDT`, `EURUSD`, or `XAUUSD`."
    cmp = d1[-1][4]
    d1_zones = detect_msnr_zones(d1)
    sups = [z[1] for z in d1_zones if z[0] == 'Support' and z[1] < cmp]
    res = [z[1] for z in d1_zones if z[0] == 'Resistance' and z[1] > cmp]
    sup = f"{max(sups):.4f}" if sups else "None nearby"
    nearest_res = f"{min(res):.4f}" if res else "None nearby"

    h4 = fetch_data(symbol, "4h", limit=35)
    h4_bos = "Consolidating"
    if h4:
        recent_h = max([c[2] for c in h4[-12:-2]])
        recent_l = min([c[3] for c in h4[-12:-2]])
        if h4[-1][4] > recent_h: h4_bos = "Bullish BOS Confirmed"
        elif h4[-1][4] < recent_l: h4_bos = "Bearish BOS Confirmed"

    m15 = fetch_data(symbol, "15m", limit=30)
    sweep_status = "No sweep detected"
    engulf_status = detect_engulfing(m15)
    if m15:
        m15_low = min([c[3] for c in m15[-14:-2]])
        m15_high = max([c[2] for c in m15[-14:-2]])
        last = m15[-1]
        if last[3] < m15_low and last[4] > m15_low: sweep_status = "SSL Swept (Bullish Rejection)"
        elif last[2] > m15_high and last[4] < m15_high: sweep_status = "BSL Swept (Bearish Rejection)"

    report = (
        f"🧪 *ALCHEMIST SCANNER: {symbol.upper()}*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💵 *CMP:* `{cmp}`\n\n"
        f"🏛 *HTF (Daily) MSNR:*\n"
        f"• Nearest Resistance: `{nearest_res}`\n"
        f"• Nearest Support: `{sup}`\n\n"
        f"⚡ *Mid-TF (4H) Structure:*\n"
        f"• {h4_bos}\n\n"
        f"🎯 *LTF (15m) Trigger Engine:*\n"
        f"• Liquidity: *{sweep_status}*\n"
        f"• Pattern: *{engulf_status}*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
    )
    if "SSL Swept" in sweep_status and "Bullish" in engulf_status and sup != "None nearby":
        report += "🔥 *Verdict:* High-Probability **BUY** Setup aligning with MSNR Support & Liquidity Sweep."
    elif "BSL Swept" in sweep_status and "Bearish" in engulf_status and nearest_res != "None nearby":
        report += "🔥 *Verdict:* High-Probability **SELL** Setup aligning with MSNR Resistance & Liquidity Sweep."
    elif "SSL Swept" in sweep_status or "BSL Swept" in sweep_status:
        report += "👀 *Verdict:* Liquidity sweep detected. Awaiting 15m engulfing candle close."
    else:
        report += "⏳ *Verdict:* Waiting for price to tap an HTF key level."
    return report

@bot.message_handler(commands=['start', 'help'])
def send_welcome(m):
    bot.reply_to(m, "👋 *Alchemist EMS Scanner is Online!*\n\nSend any asset:\n• `EURUSD`, `GBPUSD`, `XAUUSD`\n• `BTCUSDT`, `ETHUSDT`, `SOLUSDT`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_text(m):
    p = m.text.strip().upper()
    status = bot.reply_to(m, f"🔍 Scanning {p} across HTF MSNR, 4H BOS, and 15m Sweeps...")
    rep = evaluate_alchemist(p)
    bot.edit_message_text(rep, chat_id=status.chat.id, message_id=status.message_id, parse_mode="Markdown")

print("Bot is running! Go to Telegram.")
bot.infinity_polling()
