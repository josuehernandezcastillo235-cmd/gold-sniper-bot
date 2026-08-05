import requests
import pandas as pd
import os

from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

API_KEY = os.getenv("API_KEY")


def analizar():

    url = (
        "https://api.twelvedata.com/time_series"
        "?symbol=XAU/USD"
        "&interval=5min"
        "&outputsize=250"
        f"&apikey={API_KEY}"
    )

    data = requests.get(url).json()

    if "values" not in data:
        return f"❌ Error datos: {data.get('message', 'desconocido')}"

    df = pd.DataFrame(data["values"])
    df = df.iloc[::-1].reset_index(drop=True)

    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)

    # =========================
    # INDICADORES
    # =========================

    df["EMA20"] = EMAIndicator(df["close"], window=20).ema_indicator()
    df["EMA50"] = EMAIndicator(df["close"], window=50).ema_indicator()
    df["EMA200"] = EMAIndicator(df["close"], window=200).ema_indicator()

    df["RSI"] = RSIIndicator(df["close"], window=14).rsi()

    atr = AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14,
    )

    df["ATR"] = atr.average_true_range()

    adx = ADXIndicator(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14,
    )

    df["ADX"] = adx.adx()

    ultimo = df.iloc[-1]

    precio = float(ultimo["close"])
    ema20 = float(ultimo["EMA20"])
    ema50 = float(ultimo["EMA50"])
    ema200 = float(ultimo["EMA200"])

    rsi = float(ultimo["RSI"])
    atr_valor = float(ultimo["ATR"])
    adx_valor = float(ultimo["ADX"])

    # =========================
    # COMPRA
    # =========================

    if (
        ema20 > ema50 > ema200
        and rsi > 60
        and adx_valor > 25
        and precio <= ema20 + (atr_valor * 0.5)
    ):

        sl = precio - (atr_valor * 1.2)
        tp = precio + (atr_valor * 2.5)

        return f"""🥇 GOLD SNIPER BOT V2.0

🟢 COMPRA XAU/USD

💵 Precio:
{precio:.2f}

🎯 Entrada:
{precio:.2f}

🛑 Stop Loss:
{sl:.2f}

💰 Take Profit:
{tp:.2f}

📈 RSI:
{rsi:.1f}

🔥 ADX:
{adx_valor:.1f}

📊 Tend
