import requests
import pandas as pd
import os
import time

from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"


def obtener_datos(intervalo):
    url = (
        "https://api.twelvedata.com/time_series"
        f"?symbol={SYMBOL}&interval={intervalo}"
        "&outputsize=250"
        f"&apikey={API_KEY}"
    )

    respuesta = requests.get(url, timeout=15)
    data = respuesta.json()

    if "values" not in data:
        raise Exception(data.get("message", "Error obteniendo datos"))

    df = pd.DataFrame(data["values"])

    df = df.iloc[::-1].reset_index(drop=True)

    columnas = ["open", "high", "low", "close"]

    for c in columnas:
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



def analizar_tendencia(df):

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



def calcular_confianza(
    tendencia,
    tendencia15,
    rsi,
    adx,
    cerca
):

    puntos = 50


    if tendencia == tendencia15:
        puntos += 15


    if adx > 25:
        puntos += 15


    if rsi > 60 or rsi < 40:
        puntos += 10


    if cerca:
        puntos += 10


    if puntos > 95:
        puntos = 95


    return puntos



def analizar():

    try:

        df5 = obtener_datos("5min")
        df15 = obtener_datos("15min")


        df5 = calcular_indicadores(df5)
        df15 = calcular_indicadores(df15)


    except Exception as e:

        return f"❌ Error datos: {e}"



    actual = df5.iloc[-1]
    actual15 = df15.iloc[-1]


    precio = float(actual.close)

    ema20 = float(actual.EMA20)
    ema50 = float(actual.EMA50)
    ema200 = float(actual.EMA200)

    rsi = float(actual.RSI)
    atr = float(actual.ATR)
    adx = float(actual.ADX)


    tendencia5 = analizar_tendencia(df5)
    tendencia15 = analizar_tendencia(df15)



    cerca_ema = (
        abs(precio - ema20)
        <= atr * 0.6
    )


    confianza = calcular_confianza(
        tendencia5,
        tendencia15,
        rsi,
        adx,
        cerca_ema
    )



    # COMPRA

    if (
        tendencia5 == "ALCISTA"
        and tendencia15 == "ALCISTA"
        and rsi > 55
        and adx > 22
        and cerca_ema
    ):

        sl = precio - (atr * 1.5)
        tp = precio + (atr * 3)


        return f"""
🥇 XAU SNIPER AI V4.0

🟢 COMPRA

⭐ Confianza: {confianza}%

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



    # VENTA

    if (
        tendencia5 == "BAJISTA"
        and tendencia15 == "BAJISTA"
        and rsi < 45
        and adx > 22
        and cerca_ema
    ):


        sl = precio + (atr * 1.5)
        tp = precio - (atr * 3)


        return f"""
🥇 XAU SNIPER AI V4.0

🔴 VENTA

⭐ Confianza: {confianza}%

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
