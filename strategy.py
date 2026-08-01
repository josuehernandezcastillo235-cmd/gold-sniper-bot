import yfinance as yf
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

def analizar():
    df = yf.download("GC=F", period="5d", interval="5m", auto_adjust=False)

    if df.empty:
        return "❌ No se pudieron obtener datos."

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["EMA20"] = EMAIndicator(df["Close"], window=20).ema_indicator()
    df["EMA50"] = EMAIndicator(df["Close"], window=50).ema_indicator()
    df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

    atr = AverageTrueRange(
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        window=14
    )

    df["ATR"] = atr.average_true_range()

    ultimo = df.iloc[-1]

    precio = float(ultimo["Close"])
    rsi = float(ultimo["RSI"])
    atr_valor = float(ultimo["ATR"])

    if ultimo["EMA20"] > ultimo["EMA50"] and rsi > 55:

        sl = precio - atr_valor
        tp = precio + (atr_valor * 2)

        return f"""🥇 GOLD SNIPER ALERT

🟢 COMPRA

💵 Precio: {precio:.2f}

🎯 Entrada:
{precio:.2f}

🛑 Stop Loss:
{sl:.2f}

💰 Take Profit:
{tp:.2f}

📈 RSI: {rsi:.1f}
📊 Tendencia: Alcista
"""

    elif ultimo["EMA20"] < ultimo["EMA50"] and rsi < 45:

        sl = precio + atr_valor
        tp = precio - (atr_valor * 2)

        return f"""🥇 GOLD SNIPER ALERT

🔴 VENTA

💵 Precio: {precio:.2f}

🎯 Entrada:
{precio:.2f}

🛑 Stop Loss:
{sl:.2f}

💰 Take Profit:
{tp:.2f}

📉 RSI: {rsi:.1f}
📊 Tendencia: Bajista
"""

    return "😴 Sin señal"
