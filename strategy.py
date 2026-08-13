import requests
import pandas as pd
import os
import uuid

from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


API_KEY = os.getenv("API_KEY")
SYMBOL = "XAU/USD"


# =========================================================
# OBTENER DATOS
# =========================================================

def obtener_datos(intervalo):

    url = (
        "https://api.twelvedata.com/time_series"
        f"?symbol={SYMBOL}"
        f"&interval={intervalo}"
        "&outputsize=300"
        f"&apikey={API_KEY}"
    )

    respuesta = requests.get(
        url,
        timeout=15
    )

    respuesta.raise_for_status()

    data = respuesta.json()

    if "values" not in data:
        raise Exception(
            data.get(
                "message",
                "Error obteniendo datos"
            )
        )

    df = pd.DataFrame(data["values"])

    if df.empty:
        return df

    df = df.iloc[::-1].reset_index(drop=True)

    for columna in [
        "open",
        "high",
        "low",
        "close"
    ]:
        df[columna] = pd.to_numeric(
            df[columna],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "open",
            "high",
            "low",
            "close"
        ]
    ).reset_index(drop=True)

    return df


# =========================================================
# INDICADORES
# =========================================================

def calcular_indicadores(df):

    if df.empty:
        return df

    df = df.copy()

    df["EMA20"] = EMAIndicator(
        close=df["close"],
        window=20
    ).ema_indicator()

    df["EMA50"] = EMAIndicator(
        close=df["close"],
        window=50
    ).ema_indicator()

    df["EMA200"] = EMAIndicator(
        close=df["close"],
        window=200
    ).ema_indicator()

    df["RSI"] = RSIIndicator(
        close=df["close"],
        window=14
    ).rsi()

    df["ATR"] = AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    ).average_true_range()

    df["ADX"] = ADXIndicator(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    ).adx()

    return df


# =========================================================
# TENDENCIA
# =========================================================

def tendencia(df):

    if df.empty:
        return "LATERAL"

    vela = df.iloc[-1]

    if any(
        pd.isna(vela[x])
        for x in [
            "EMA20",
            "EMA50",
            "EMA200"
        ]
    ):
        return "LATERAL"

    if (
        vela["EMA20"]
        > vela["EMA50"]
        > vela["EMA200"]
    ):
        return "ALCISTA"

    if (
        vela["EMA20"]
        < vela["EMA50"]
        < vela["EMA200"]
    ):
        return "BAJISTA"

    return "LATERAL"


# =========================================================
# ANALIZAR
# =========================================================

def analizar():

    try:

        # -------------------------------------------------
        # DATOS
        # -------------------------------------------------

        df5 = obtener_datos("5min")
        print("✅ Datos 5M recibidos")
        df15 = obtener_datos("15min")

        if df5.empty or df15.empty:
            return "😴 Sin señal"

        # -------------------------------------------------
        # INDICADORES
        # -------------------------------------------------

        df5 = calcular_indicadores(df5)
        df15 = calcular_indicadores(df15)

        if len(df5) < 210 or len(df15) < 210:
            return "😴 Sin señal"

        # -------------------------------------------------
        # VELAS
        # -------------------------------------------------

        vela5 = df5.iloc[-1]
        anterior5 = df5.iloc[-2]

        # -------------------------------------------------
        # DATOS
        # -------------------------------------------------

        precio = float(
            vela5["close"]
        )

        apertura = float(
            vela5["open"]
        )

        maximo = float(
            vela5["high"]
        )

        minimo = float(
            vela5["low"]
        )

        close_anterior = float(
            anterior5["close"]
        )

        # -------------------------------------------------
        # EMAS
        # -------------------------------------------------

        ema20 = float(
            vela5["EMA20"]
        )

        ema50 = float(
            vela5["EMA50"]
        )

        ema200 = float(
            vela5["EMA200"]
        )

        ema20_anterior = float(
            anterior5["EMA20"]
        )

        # -------------------------------------------------
        # INDICADORES
        # -------------------------------------------------

        rsi = float(
            vela5["RSI"]
        )

        adx = float(
            vela5["ADX"]
        )

        atr = float(
            vela5["ATR"]
        )

        if any(
            pd.isna(x)
            for x in [
                precio,
                ema20,
                ema50,
                ema200,
                rsi,
                adx,
                atr
            ]
        ):
            return "😴 Sin señal"

        if atr <= 0:
            return "😴 Sin señal"

        # -------------------------------------------------
        # TENDENCIAS
        # -------------------------------------------------

        tendencia5 = tendencia(df5)
        tendencia15 = tendencia(df15)

        # -------------------------------------------------
        # EMAS
        # -------------------------------------------------

        emas_alcistas = (
            ema20 > ema50
            and ema50 > ema200
        )

        emas_bajistas = (
            ema20 < ema50
            and ema50 < ema200
        )

        # -------------------------------------------------
        # DIRECCIÓN EMA20
        # -------------------------------------------------

        ema20_subiendo = (
            ema20 > ema20_anterior
        )

        ema20_bajando = (
            ema20 < ema20_anterior
        )

        # -------------------------------------------------
        # DISTANCIA A EMA20
        # -------------------------------------------------

        distancia_ema = abs(
            precio - ema20
        )

        # Zona razonable alrededor de EMA20
        cerca_ema = (
            distancia_ema <= atr * 1.5
        )

        # Evita perseguir movimientos demasiado extendidos
        demasiado_lejos = (
            distancia_ema > atr * 2.0
        )

        # -------------------------------------------------
        # VELA
        # -------------------------------------------------

        vela_alcista = (
            precio > apertura
        )

        vela_bajista = (
            precio < apertura
        )

        # -------------------------------------------------
        # PULLBACK CLÁSICO
        # -------------------------------------------------

        pullback_compra_clasico = (
            close_anterior <= ema20_anterior
            and precio > ema20
        )

        pullback_venta_clasico = (
            close_anterior >= ema20_anterior
            and precio < ema20
        )

        # -------------------------------------------------
        # TOQUE DE EMA20
        # -------------------------------------------------

        toque_ema_compra = (
            minimo <= ema20
            and precio > ema20
        )

        toque_ema_venta = (
            maximo >= ema20
            and precio < ema20
        )

        # -------------------------------------------------
        # PULLBACK FLEXIBLE
        # -------------------------------------------------

        pullback_compra = (
            pullback_compra_clasico
            or toque_ema_compra
            or (
                distancia_ema <= atr * 0.8
                and vela_alcista
            )
        )

        pullback_venta = (
            pullback_venta_clasico
            or toque_ema_venta
            or (
                distancia_ema <= atr * 0.8
                and vela_bajista
            )
        )

        # -------------------------------------------------
        # FUERZA
        # -------------------------------------------------

        mercado_fuerte = (
            adx >= 25
        )

        # -------------------------------------------------
        # CONFIRMACIÓN 15M
        # -------------------------------------------------
        #
        # Si 15M está claramente en tendencia,
        # exigimos esa tendencia.
        #
        # Si 15M está lateral pero las EMAs de 5M
        # están perfectamente alineadas y ADX es fuerte,
        # permitimos la entrada.
        #

        confirmacion15_compra = (
            tendencia15 == "ALCISTA"
            or (
                tendencia15 == "LATERAL"
                and emas_alcistas
                and adx >= 30
            )
        )

        confirmacion15_venta = (
            tendencia15 == "BAJISTA"
            or (
                tendencia15 == "LATERAL"
                and emas_bajistas
                and adx >= 30
            )
        )

        # -------------------------------------------------
        # COMPRA
        # -------------------------------------------------

        compra = (
            tendencia5 == "ALCISTA"
            and confirmacion15_compra
            and emas_alcistas
            and ema20_subiendo
            and mercado_fuerte
            and 52 <= rsi <= 68
            and cerca_ema
            and not demasiado_lejos
            and vela_alcista
            and pullback_compra
        )

        # -------------------------------------------------
        # VENTA
        # -------------------------------------------------

        venta = (
            tendencia5 == "BAJISTA"
            and confirmacion15_venta
            and emas_bajistas
            and ema20_bajando
            and mercado_fuerte
            and 32 <= rsi <= 48
            and cerca_ema
            and not demasiado_lejos
            and vela_bajista
            and pullback_venta
        )

        # -------------------------------------------------
        # SIN SEÑAL
        # -------------------------------------------------

        if not compra and not venta:
            return "😴 Sin señal"

        # -------------------------------------------------
        # OPERACIÓN
        # -------------------------------------------------

        entrada = round(
            precio,
            2
        )

        atr_redondeado = round(
            atr,
            2
        )

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

        # -------------------------------------------------
        # SCORE
        # -------------------------------------------------

        score = 0

        # Tendencia 5M
        score += 15

        # Confirmación 15M
        if tendencia15 in [
            "ALCISTA",
            "BAJISTA"
        ]:
            score += 15
        else:
            score += 10

        # EMAs
        if compra and emas_alcistas:
            score += 15

        elif venta and emas_bajistas:
            score += 15

        # ADX
        if adx >= 30:
            score += 15

        elif adx >= 25:
            score += 10

        # RSI
        if compra and 55 <= rsi <= 65:
            score += 10

        elif venta and 35 <= rsi <= 45:
            score += 10

        # Cercanía EMA
        if cerca_ema:
            score += 10

        # Pullback
        if pullback_compra or pullback_venta:
            score += 10

        # Vela
        if (
            compra and vela_alcista
        ) or (
            venta and vela_bajista
        ):
            score += 10

        score = min(
            score,
            100
        )

        # -------------------------------------------------
        # ID
        # -------------------------------------------------

        identificador = (
            uuid.uuid4().hex[:6]
        )

        emoji = (
            "🟢"
            if direccion == "COMPRA"
            else "🔴"
        )

        # -------------------------------------------------
        # MENSAJE
        # -------------------------------------------------

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
📏 ATR: {atr_redondeado:.2f}

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}
EMA200: {ema200:.2f}

🔄 Pullback confirmado
"""

    except Exception as e:

        print(
            f"❌ ERROR STRATEGY: {e}"
        )

        return (
            f"❌ Error estrategia: {e}"
        )
