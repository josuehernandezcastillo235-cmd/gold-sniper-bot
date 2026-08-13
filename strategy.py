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


def analizar():

    try:

        print("")
        print("===================================")
        print("🔎 DIAGNÓSTICO XAU/USD V3.2")
        print("===================================")

        df5 = obtener_datos("5min")
        df15 = obtener_datos("15min")

        if df5.empty or df15.empty:
            print("❌ No hay datos")
            return "😴 Sin señal"

        df5 = calcular_indicadores(df5)
        df15 = calcular_indicadores(df15)

        if len(df5) < 210 or len(df15) < 210:
            print(
                f"❌ Historial insuficiente: "
                f"5M={len(df5)} | 15M={len(df15)}"
            )
            return "😴 Sin señal"

        vela = df5.iloc[-1]
        anterior = df5.iloc[-2]

        precio = float(vela["close"])

        ema20 = float(vela["EMA20"])
        ema50 = float(vela["EMA50"])
        ema200 = float(vela["EMA200"])

        ema20_anterior = float(
            anterior["EMA20"]
        )

        rsi = float(vela["RSI"])
        adx = float(vela["ADX"])
        atr = float(vela["ATR"])

        tendencia5 = tendencia(df5)
        tendencia15 = tendencia(df15)

        apertura = float(
            vela["open"]
        )

        maximo = float(
            vela["high"]
        )

        minimo = float(
            vela["low"]
        )

        close_anterior = float(
            anterior["close"]
        )

        # ===================================
        # CONDICIONES
        # ===================================

        emas_alcistas = (
            ema20 > ema50
            and ema50 > ema200
        )

        emas_bajistas = (
            ema20 < ema50
            and ema50 < ema200
        )

        ema20_subiendo = (
            ema20 > ema20_anterior
        )

        ema20_bajando = (
            ema20 < ema20_anterior
        )

        distancia_ema = abs(
            precio - ema20
        )

        cerca_ema = (
            distancia_ema <= atr * 1.0
        )

        demasiado_lejos = (
            distancia_ema > atr * 1.8
        )

        vela_alcista = (
            precio > apertura
        )

        vela_bajista = (
            precio < apertura
        )

        pullback_compra_clasico = (
            close_anterior <= ema20_anterior
            and precio > ema20
        )

        pullback_venta_clasico = (
            close_anterior >= ema20_anterior
            and precio < ema20
        )

        toque_ema_compra = (
            minimo <= ema20
            and precio > ema20
        )

        toque_ema_venta = (
            maximo >= ema20
            and precio < ema20
        )

        pullback_compra = (
            pullback_compra_clasico
            or toque_ema_compra
        )

        pullback_venta = (
            pullback_venta_clasico
            or toque_ema_venta
        )

        mercado_fuerte = (
            adx >= 25
        )

        # ===================================
        # MOSTRAR DATOS
        # ===================================

        print(
            f"💰 Precio: {precio:.2f}"
        )

        print(
            f"📊 Tendencia 5M: {tendencia5}"
        )

        print(
            f"📊 Tendencia 15M: {tendencia15}"
        )

        print(
            f"EMA20: {ema20:.2f}"
        )

        print(
            f"EMA50: {ema50:.2f}"
        )

        print(
            f"EMA200: {ema200:.2f}"
        )

        print(
            f"RSI: {rsi:.2f}"
        )

        print(
            f"ADX: {adx:.2f}"
        )

        print(
            f"ATR: {atr:.2f}"
        )

        print(
            f"📏 Distancia EMA20: "
            f"{distancia_ema:.2f}"
        )

        # ===================================
        # DIAGNÓSTICO COMPRA
        # ===================================

        print("")
        print("🟢 COMPRA")

        print(
            f"5M alcista: "
            f"{tendencia5 == 'ALCISTA'}"
        )

        print(
            f"15M alcista: "
            f"{tendencia15 == 'ALCISTA'}"
        )

        print(
            f"EMAs alcistas: "
            f"{emas_alcistas}"
        )

        print(
            f"EMA20 subiendo: "
            f"{ema20_subiendo}"
        )

        print(
            f"ADX >= 25: "
            f"{mercado_fuerte}"
        )

        print(
            f"RSI 52-68: "
            f"{52 <= rsi <= 68}"
        )

        print(
            f"Cerca EMA20: "
            f"{cerca_ema}"
        )

        print(
            f"No demasiado lejos: "
            f"{not demasiado_lejos}"
        )

        print(
            f"Vela alcista: "
            f"{vela_alcista}"
        )

        print(
            f"Pullback compra: "
            f"{pullback_compra}"
        )

        # ===================================
        # DIAGNÓSTICO VENTA
        # ===================================

        print("")
        print("🔴 VENTA")

        print(
            f"5M bajista: "
            f"{tendencia5 == 'BAJISTA'}"
        )

        print(
            f"15M bajista: "
            f"{tendencia15 == 'BAJISTA'}"
        )

        print(
            f"EMAs bajistas: "
            f"{emas_bajistas}"
        )

        print(
            f"EMA20 bajando: "
            f"{ema20_bajando}"
        )

        print(
            f"ADX >= 25: "
            f"{mercado_fuerte}"
        )

        print(
            f"RSI 32-48: "
            f"{32 <= rsi <= 48}"
        )

        print(
            f"Cerca EMA20: "
            f"{cerca_ema}"
        )

        print(
            f"No demasiado lejos: "
            f"{not demasiado_lejos}"
        )

        print(
            f"Vela bajista: "
            f"{vela_bajista}"
        )

        print(
            f"Pullback venta: "
            f"{pullback_venta}"
        )

        # ===================================
        # SEÑAL COMPRA
        # ===================================

        compra = (
            tendencia5 == "ALCISTA"
            and tendencia15 == "ALCISTA"
            and emas_alcistas
            and ema20_subiendo
            and mercado_fuerte
            and 52 <= rsi <= 68
            and cerca_ema
            and not demasiado_lejos
            and vela_alcista
            and pullback_compra
        )

        # ===================================
        # SEÑAL VENTA
        # ===================================

        venta = (
            tendencia5 == "BAJISTA"
            and tendencia15 == "BAJISTA"
            and emas_bajistas
            and ema20_bajando
            and mercado_fuerte
            and 32 <= rsi <= 48
            and cerca_ema
            and not demasiado_lejos
            and vela_bajista
            and pullback_venta
        )

        # ===================================
        # SI NO HAY SEÑAL
        # ===================================

        if not compra and not venta:

            print("")
            print("❌ NO HAY SEÑAL")
            print("===================================")

            return "😴 Sin señal"

        # ===================================
        # OPERACIÓN
        # ===================================

        if compra:

            direccion = "COMPRA"

            sl = round(
                precio - atr * 1.5,
                2
            )

            tp = round(
                precio + atr * 3,
                2
            )

        else:

            direccion = "VENTA"

            sl = round(
                precio + atr * 1.5,
                2
            )

            tp = round(
                precio - atr * 3,
                2
            )

        # ===================================
        # SCORE
        # ===================================

        score = 0

        score += 15
        score += 15
        score += 15

        if adx >= 30:
            score += 15
        else:
            score += 10

        if compra and 55 <= rsi <= 65:
            score += 10

        elif venta and 35 <= rsi <= 45:
            score += 10

        if cerca_ema:
            score += 10

        if pullback_compra or pullback_venta:
            score += 10

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

        identificador = (
            uuid.uuid4().hex[:6]
        )

        emoji = (
            "🟢"
            if compra
            else "🔴"
        )

        print("")
        print(
            f"🚨 SEÑAL DETECTADA: "
            f"{direccion}"
        )

        print("===================================")

        return f"""🥇 XAU SNIPER AI V3.2

ID: {identificador}

{emoji} {direccion}

⭐ Calidad de señal: {score}/100

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

📋 OPERACIÓN

Entrada: {precio:.2f}

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

    except Exception as e:

        print(
            f"❌ ERROR STRATEGY: {e}"
        )

        return f"❌ Error estrategia: {e}"
