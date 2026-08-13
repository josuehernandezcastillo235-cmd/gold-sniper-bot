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
        "&outputsize=100"
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

def analizar():

    df_5m = calcular_indicadores(
        obtener_datos("5min")
    )

    df_15m = calcular_indicadores(
        obtener_datos("15min")
    )

    if df_5m.empty or df_15m.empty:
        return "😴 Sin señal"

    vela5 = df_5m.iloc[-1]
    anterior5 = df_5m.iloc[-2]

    vela15 = df_15m.iloc[-1]

    # =========================
    # DATOS PRINCIPALES
    # =========================

    precio = float(vela5["close"])

    ema20 = float(vela5["EMA20"])
    ema50 = float(vela5["EMA50"])
    ema200 = float(vela5["EMA200"])

    rsi = float(vela5["RSI"])
    adx = float(vela5["ADX"])
    atr = float(vela5["ATR"])

    close_anterior = float(anterior5["close"])
    ema20_anterior = float(anterior5["EMA20"])

    # =========================
    # TENDENCIA
    # =========================

    tendencia5 = tendencia(df_5m)
    tendencia15 = tendencia(df_15m)

    # =========================
    # DIRECCIÓN DE EMA
    # =========================

    emas_alcistas = (
        ema20 > ema50
        and ema50 > ema200
    )

    emas_bajistas = (
        ema20 < ema50
        and ema50 < ema200
    )

    # =========================
    # PENDIENTE EMA20
    # =========================

    ema20_subiendo = ema20 > ema20_anterior
    ema20_bajando = ema20 < ema20_anterior

    # =========================
    # DISTANCIA A EMA20
    # =========================

    distancia_ema = abs(precio - ema20)

    cerca_ema = distancia_ema <= atr * 0.8

    demasiado_lejos = distancia_ema > atr * 1.5

    # =========================
    # CONFIRMACIÓN DE VELA
    # =========================

    vela_alcista = (
        float(vela5["close"]) > float(vela5["open"])
    )

    vela_bajista = (
        float(vela5["close"]) < float(vela5["open"])
    )

    # =========================
    # PULLBACK
    # =========================

    pullback_compra = (
        close_anterior <= ema20_anterior
        and precio > ema20
    )

    pullback_venta = (
        close_anterior >= ema20_anterior
        and precio < ema20
    )

    # =========================
    # FILTRO DE MERCADO
    # =========================

    mercado_fuerte = adx >= 25

    # =========================
    # COMPRA
    # =========================

    compra = (
        tendencia5 == "ALCISTA"
        and tendencia15 == "ALCISTA"
        and emas_alcistas
        and ema20_subiendo
        and mercado_fuerte
        and rsi >= 52
        and rsi <= 68
        and cerca_ema
        and not demasiado_lejos
        and vela_alcista
    )

    # =========================
    # VENTA
    # =========================

    venta = (
        tendencia5 == "BAJISTA"
        and tendencia15 == "BAJISTA"
        and emas_bajistas
        and ema20_bajando
        and mercado_fuerte
        and rsi >= 32
        and rsi <= 48
        and cerca_ema
        and not demasiado_lejos
        and vela_bajista
    )

    # =========================
    # CONFIRMACIÓN EXTRA
    # =========================

    if compra and not pullback_compra:
        return "😴 Sin señal"

    if venta and not pullback_venta:
        return "😴 Sin señal"

    if not compra and not venta:
        return "😴 Sin señal"

    # =========================
    # ENTRADA
    # =========================

    entrada = round(precio, 2)
    atr = round(atr, 2)

    if compra:

        direccion = "COMPRA"

        sl = round(
            entrada - atr * 1.5,
            2
        )

        tp = round(
            entrada + atr * 3,
            2
        )

    else:

        direccion = "VENTA"

        sl = round(
            entrada + atr * 1.5,
            2
        )

        tp = round(
            entrada - atr * 3,
            2
        )

    # =========================
    # SCORE
    # =========================

    score = 0

    # Tendencia 5M
    if (
        (compra and tendencia5 == "ALCISTA")
        or
        (venta and tendencia5 == "BAJISTA")
    ):
        score += 15

    # Tendencia 15M
    if (
        (compra and tendencia15 == "ALCISTA")
        or
        (venta and tendencia15 == "BAJISTA")
    ):
        score += 15

    # EMA alineadas
    if compra and emas_alcistas:
        score += 15

    if venta and emas_bajistas:
        score += 15

    # ADX
    if adx >= 30:
        score += 15
    elif adx >= 25:
        score += 10

    # RSI saludable
    if compra and 55 <= rsi <= 65:
        score += 10

    elif venta and 35 <= rsi <= 45:
        score += 10

    # Precio cerca de EMA20
    if cerca_ema:
        score += 10

    # Pullback confirmado
    if pullback_compra or pullback_venta:
        score += 10

    # Vela de confirmación
    if (
        compra and vela_alcista
    ) or (
        venta and vela_bajista
    ):
        score += 10

    score = min(score, 100)

    # =========================
    # ID
    # =========================

    identificador = uuid.uuid4().hex[:6]

    # =========================
    # MENSAJE
    # =========================

    emoji = "🟢" if direccion == "COMPRA" else "🔴"

    return f"""🥇 XAU SNIPER AI V3.2

ID: {identificador}

{emoji} {direccion}

⭐ Calidad de señal: {score}/100

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

📋 OPERACIÓN

Entrada: {entrada:.2f}

🛑 Stop Loss:
{sl:.2f}

🎯 Take Profit:
{tp:.2f}

📈 RSI: {rsi:.1f}
📊 ADX: {adx:.1f}
📏 ATR: {atr:.2f}

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}
EMA200: {ema200:.2f}

🔄 Pullback confirmado
"""
