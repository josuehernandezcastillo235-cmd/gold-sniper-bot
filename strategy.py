import yfinance as yf
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator

def analizar():
    df = yf.download("GC=F", period="5d", interval="5m", auto_adjust=False)

    if df.empty:
        return "❌ No se pudieron obtener datos."

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["EMA20"] = EMAIndicator(df["Close"], window=20).ema_indicator()
    df["EMA50"] = EMAIndicator(df["Close"], window=50).ema_indicator()
    df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

    ultimo = df.iloc[-1]

    if ultimo["EMA20"] > ultimo["EMA50"] and ultimo["RSI"] > 55:
        return "🟢 Posible COMPRA detectada"

    elif ultimo["EMA20"] < ultimo["EMA50"] and ultimo["RSI"] < 45:
        return "🔴 Posible VENTA detectada"

    else:
        return "😴 Sin señal"
