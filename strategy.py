import requests
import pandas as pd
import os

from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

API_KEY = os.getenv("API_KEY")


def analizar():

    url = (
        "https://api.twelvedata.com/time_series"
        "?symbol=XAU/USD"
        "&interval=5min"
        "&outputsize=200"
        f"&apikey={API_KEY}"
    )

    data = requests.get(url).json()

    if "values" not in data:
        return f"❌ Error datos: {data.get('message', 'desconocido')}"

    df = pd.DataFrame(data["values"])

    df = df.iloc[::-1]

    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)

    # Indicadores
    df["EMA20"] = EMAIndicator(
        df["close"], window=20
    ).ema_indicator()

    df["EMA50"] = EMAIndicator(
        df["close"], window=50
    ).ema_indicator()

    df["EMA200"] = EMAIndicator(
        df["close"], window=200
    ).ema_indicator()

    df["RSI"] = RSIIndicator(
        df["close"], window=14
    ).rsi()

    atr = AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    df["ATR"] = atr.average_true_range()

    ultimo = df.iloc[-1]

    precio = float(ultimo["close"])
    rsi = float(ultimo["RSI"])
    atr_valor = float(ultimo["ATR"])

    # COMPRA
    if (
        ultimo["EMA20"] > ultimo["EMA50"]
        and ultimo["EMA50"] > ultimo["EMA200"]
        and rsi > 55
    ):

        sl = precio - atr_valor
        tp = precio + (atr_valor * 2)

        return f"""🥇 GOLD SNIPER ALERT

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

📊 Tendencia:
Alcista fuerte
"""


    # VENTA
    elif (
        ultimo["EMA20"] < ultimo["EMA50"]
        and ultimo["EMA50"] < ultimo["EMA200"]
        and rsi < 45
    ):

        sl = precio + atr_valor
        tp = precio - (atr_valor * 2)

        return f"""🥇 GOLD SNIPER ALERT

🔴 VENTA XAU/USD

💵 Precio:
{precio:.2f}

🎯 Entrada:
{precio:.2f}

🛑 Stop Loss:
{sl:.2f}

💰 Take Profit:
{tp:.2f}

📉 RSI:
{rsi:.1f}

📊 Tendencia:
Bajista fuerte
"""


    return "😴 Sin señal"        sl = precio - atr_valor
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
