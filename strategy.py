import requests
import pandas as pd
import os
import uuid

from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"


def obtener_datos(intervalo):

    url = (
        "https://api.twelvedata.com/time_series"
        f"?symbol={SYMBOL}"
        f"&interval={intervalo}"
        "&outputsize=250"
        f"&apikey={API_KEY}"
    )

    respuesta = requests.get(url, timeout=15)
    data = respuesta.json()

    if "values" not in data:
        raise Exception(
            data.get("message", "Error obteniendo datos")
        )

    df = pd.DataFrame(data["values"])

    df = df.iloc[::-1].reset_index(drop=True)

    for c in ["open", "high", "low", "close"]:
        df[c] = df[c].astype(float)

    return df



def calcular_indicadores(df):

    df["EMA20"] = EMAIndicator(
        df["close"],
        window=20
    ).ema_indicator()


    df["EMA50"] = EMAIndicator(
        df["close"],
        window=50
    ).ema_indicator()


    df["EMA200"] = EMAIndicator(
        df["close"],
        window=200
    ).ema_indicator()


    df["RSI"] = RSIIndicator(
        df["close"],
        window=14
    ).rsi()


    df["ATR"] = AverageTrueRange(
        df["high"],
        df["low"],
        df["close"],
        window=14
    ).average_true_range()


    df["ADX"] = ADXIndicator(
        df["high"],
        df["low"],
        df["close"],
        window=14
    ).adx()


    return df



def tendencia(df):

    vela = df.iloc[-1]

    if (
        vela.EMA20 >
        vela.EMA50 >
        vela.EMA200
    ):
        return "ALCISTA"


    if (
        vela.EMA20 <
        vela.EMA50 <
        vela.EMA200
    ):
        return "BAJISTA"


    return "LATERAL"



def confianza(
    tendencia5,
    tendencia15,
    rsi,
    adx,
    cerca
):

    puntos = 50


    if tendencia5 == tendencia15:
        puntos += 15


    if adx > 25:
        puntos += 15


    if rsi > 60 or rsi < 40:
        puntos += 10


    if cerca:
        puntos += 10


    return min(puntos, 95)



def analizar():

    try:

        df5 = obtener_datos("5min")
        df15 = obtener_datos("15min")

        df5 = calcular_indicadores(df5)
        df15 = calcular_indicadores(df15)


    except Exception as e:

        return f"❌ Error datos: {e}"



    vela = df5.iloc[-1]


    precio = float(vela.close)
    atr = float(vela.ATR)
    rsi = float(vela.RSI)
    adx = float(vela.ADX)


    tendencia5 = tendencia(df5)
    tendencia15 = tendencia(df15)


    cerca = abs(
        precio - float(vela.EMA20)
    ) <= atr * 0.6



    score = confianza(
        tendencia5,
        tendencia15,
        rsi,
        adx,
        cerca
    )



    if (
        tendencia5 == "ALCISTA"
        and tendencia15 == "ALCISTA"
        and rsi > 55
        and adx > 22
        and cerca
    ):

        sl = precio - (atr * 1.5)
        tp = precio + (atr * 3)


        return f"""
🥇 XAU SNIPER AI V3.0

ID: {uuid.uuid4().hex[:6]}

🟢 COMPRA

⭐ Confianza: {score}%

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

📋 OPERACIÓN

Entrada: {precio:.2f}

🛑 Stop Loss:
{sl:.2f}

🎯 Take Profit:
{tp:.2f}


RSI: {rsi:.1f}
ADX: {adx:.1f}
ATR: {atr:.2f}
"""



    if (
        tendencia5 == "BAJISTA"
        and tendencia15 == "BAJISTA"
        and rsi < 45
        and adx > 22
        and cerca
    ):

        sl = precio + (atr * 1.5)
        tp = precio - (atr * 3)


        return f"""
🥇 XAU SNIPER AI V3.0

ID: {uuid.uuid4().hex[:6]}

🔴 VENTA

⭐ Confianza: {score}%

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

📋 OPERACIÓN

Entrada: {precio:.2f}

🛑 Stop Loss:
{sl:.2f}

🎯 Take Profit:
{tp:.2f}


RSI: {rsi:.1f}
ADX: {adx:.1f}
ATR: {atr:.2f}
"""



    return "😴 Sin señal"
