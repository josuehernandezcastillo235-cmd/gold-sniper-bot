import requests
import pandas as pd
import os
import uuid

from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


# =========================================================
# CONFIGURACIÓN
# =========================================================

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

    df = pd.DataFrame(
        data["values"]
    )

    if df.empty:
        return df

    # Twelve Data entrega las velas de más reciente
    # a más antigua. Las invertimos.
    df = df.iloc[::-1].reset_index(
        drop=True
    )

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
    ).reset_index(
        drop=True
    )

    return df


# =========================================================
# INDICADORES
# =========================================================

def calcular_indicadores(df):

    if df.empty:
        return df

    df = df.copy()

    # -----------------------------------------------------
    # EMA
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    df["RSI"] = RSIIndicator(
        close=df["close"],
        window=14
    ).rsi()

    # -----------------------------------------------------
    # ATR
    # -----------------------------------------------------

    df["ATR"] = AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    ).average_true_range()

    # -----------------------------------------------------
    # ADX / DI
    # -----------------------------------------------------

    adx = ADXIndicator(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    df["ADX"] = adx.adx()

    df["DI_PLUS"] = adx.adx_pos()

    df["DI_MINUS"] = adx.adx_neg()

    return df


# =========================================================
# TENDENCIA
# =========================================================

def tendencia(df):

    if df.empty:
        return "LATERAL"

    vela = df.iloc[-1]

    valores = [
        vela["EMA20"],
        vela["EMA50"],
        vela["EMA200"]
    ]

    if any(
        pd.isna(x)
        for x in valores
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

        # =================================================
        # DATOS
        # =================================================

        df5 = obtener_datos("5min")

        df15 = obtener_datos("15min")

        print(
            "✅ Datos 5M y 15M recibidos"
        )

        if (
            df5.empty
            or df15.empty
        ):

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": "😴 Sin señal"
            }


        # =================================================
        # INDICADORES
        # =================================================

        df5 = calcular_indicadores(
            df5
        )

        df15 = calcular_indicadores(
            df15
        )

        print(
            "✅ Indicadores calculados"
        )

        if (
            len(df5) < 220
            or len(df15) < 220
        ):

            print(
                "⚠️ Historial insuficiente"
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": "😴 Historial insuficiente"
            }


        # =================================================
        # VELAS
        # =================================================

        vela = df5.iloc[-1]

        anterior = df5.iloc[-2]

        anterior2 = df5.iloc[-3]

        vela15 = df15.iloc[-1]


        # =================================================
        # PRECIO
        # =================================================

        precio = float(
            vela["close"]
        )

        apertura = float(
            vela["open"]
        )


        # =================================================
        # EMA
        # =================================================

        ema20 = float(
            vela["EMA20"]
        )

        ema50 = float(
            vela["EMA50"]
        )

        ema200 = float(
            vela["EMA200"]
        )

        ema20_ant = float(
            anterior["EMA20"]
        )

        ema20_ant2 = float(
            anterior2["EMA20"]
        )


        # =================================================
        # INDICADORES
        # =================================================

        rsi = float(
            vela["RSI"]
        )

        rsi_anterior = float(
            anterior["RSI"]
        )

        adx = float(
            vela["ADX"]
        )

        adx_anterior = float(
            anterior["ADX"]
        )

        di_plus = float(
            vela["DI_PLUS"]
        )

        di_minus = float(
            vela["DI_MINUS"]
        )

        atr = float(
            vela["ATR"]
        )


        # =================================================
        # VALIDACIÓN
        # =================================================

        valores = [
            precio,
            ema20,
            ema50,
            ema200,
            rsi,
            rsi_anterior,
            adx,
            adx_anterior,
            di_plus,
            di_minus,
            atr
        ]

        if any(
            pd.isna(x)
            for x in valores
        ):

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": "😴 Indicadores incompletos"
            }

        if atr <= 0:

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": "😴 ATR inválido"
            }


        # =================================================
        # TENDENCIAS
        # =================================================

        tendencia5 = tendencia(
            df5
        )

        tendencia15 = tendencia(
            df15
        )


        # =================================================
        # EMA
        # =================================================

        ema20_subiendo = (
            ema20 > ema20_ant
        )

        ema20_bajando = (
            ema20 < ema20_ant
        )

        ema20_acelerando_alza = (
            ema20 > ema20_ant
            and ema20_ant > ema20_ant2
        )

        ema20_acelerando_baja = (
            ema20 < ema20_ant
            and ema20_ant < ema20_ant2
        )


        # =================================================
        # ESTRUCTURA
        # =================================================

        maximos_recientes = df5[
            "high"
        ].iloc[-7:-1]

        minimos_recientes = df5[
            "low"
        ].iloc[-7:-1]

        maximo_reciente = float(
            maximos_recientes.max()
        )

        minimo_reciente = float(
            minimos_recientes.min()
        )

        cerca_maximo = (
            precio
            >= maximo_reciente - atr * 0.5
        )

        cerca_minimo = (
            precio
            <= minimo_reciente + atr * 0.5
        )

        ruptura_alcista = (
            precio > maximo_reciente
        )

        ruptura_bajista = (
            precio < minimo_reciente
        )


        # =================================================
        # DISTANCIA EMA
        # =================================================

        distancia_ema = abs(
            precio - ema20
        )

        cerca_ema = (
            distancia_ema <= atr * 1.2
        )

        demasiado_lejos = (
            distancia_ema > atr * 2.0
        )


        # =================================================
        # VELA
        # =================================================

        vela_alcista = (
            precio > apertura
        )

        vela_bajista = (
            precio < apertura
        )


        # =================================================
        # RSI
        # =================================================

        rsi_subiendo = (
            rsi > rsi_anterior
        )

        rsi_bajando = (
            rsi < rsi_anterior
        )

        momentum_alcista = (
            rsi >= 50
            and rsi <= 68
            and rsi_subiendo
        )

        momentum_bajista = (
            rsi <= 50
            and rsi >= 32
            and rsi_bajando
        )


        # =================================================
        # ADX
        # =================================================

        adx_fuerte = (
            adx >= 20
        )

        adx_creciendo = (
            adx > adx_anterior
        )


        # =================================================
        # DI
        # =================================================

        fuerza_compradora = (
            di_plus > di_minus
        )

        fuerza_vendedora = (
            di_minus > di_plus
        )


        # =================================================
        # ESTRUCTURA
        # =================================================

        estructura_alcista = (
            precio > ema50
            and ema20 >= ema50
        )

        estructura_bajista = (
            precio < ema50
            and ema20 <= ema50
        )


        # =================================================
        # CONTEXTO 15M
        # =================================================

        contexto_alcista_15 = (
            tendencia15 == "ALCISTA"
            or (
                tendencia15 == "LATERAL"
                and vela15["EMA20"]
                > vela15["EMA50"]
            )
        )

        contexto_bajista_15 = (
            tendencia15 == "BAJISTA"
            or (
                tendencia15 == "LATERAL"
                and vela15["EMA20"]
                < vela15["EMA50"]
            )
        )


        # =================================================
        # SCORE BASE
        #
        # IMPORTANTE:
        # EMA20 y ADX NO SON NECESARIOS PARA LA
        # ADVERTENCIA ANTICIPADA.
        # =================================================

        score_compra = 0

        if tendencia5 == "ALCISTA":
            score_compra += 25

        elif tendencia5 == "LATERAL":
            score_compra += 8

        if contexto_alcista_15:
            score_compra += 20

        if estructura_alcista:
            score_compra += 20

        if momentum_alcista:
            score_compra += 15

        if fuerza_compradora:
            score_compra += 10

        if cerca_maximo:
            score_compra += 5

        if ruptura_alcista:
            score_compra += 5


        score_venta = 0

        if tendencia5 == "BAJISTA":
            score_venta += 25

        elif tendencia5 == "LATERAL":
            score_venta += 8

        if contexto_bajista_15:
            score_venta += 20

        if estructura_bajista:
            score_venta += 20

        if momentum_bajista:
            score_venta += 15

        if fuerza_vendedora:
            score_venta += 10

        if cerca_minimo:
            score_venta += 5

        if ruptura_bajista:
            score_venta += 5


        # =================================================
        # PUNTOS DE CONFIRMACIÓN
        #
        # Estos NO forman parte del requisito de
        # advertencia anticipada.
        # =================================================

        if ema20_subiendo:
            score_compra += 5

        if ema20_acelerando_alza:
            score_compra += 3

        if adx_fuerte:
            score_compra += 5

        if adx_creciendo:
            score_compra += 2


        if ema20_bajando:
            score_venta += 5

        if ema20_acelerando_baja:
            score_venta += 3

        if adx_fuerte:
            score_venta += 5

        if adx_creciendo:
            score_venta += 2


        score_compra = min(
            score_compra,
            100
        )

        score_venta = min(
            score_venta,
            100
        )


        # =================================================
        # DIAGNÓSTICO
        # =================================================

        print(
            "==================================="
        )

        print(
            "🔎 XAU SNIPER AI V3.3"
        )

        print(
            f"💰 Precio: {precio:.2f}"
        )

        print(
            f"📊 5M={tendencia5} | "
            f"15M={tendencia15}"
        )

        print(
            f"📈 EMA20={ema20:.2f} | "
            f"EMA50={ema50:.2f} | "
            f"EMA200={ema200:.2f}"
        )

        print(
            f"RSI={rsi:.1f} | "
            f"ADX={adx:.1f}"
        )

        print(
            f"DI+={di_plus:.1f} | "
            f"DI-={di_minus:.1f}"
        )

        print(
            f"⭐ SCORE COMPRA={score_compra}"
        )

        print(
            f"⭐ SCORE VENTA={score_venta}"
        )

        print(
            f"📈 EMA20 subiendo={ema20_subiendo}"
        )

        print(
            f"📊 ADX fuerte={adx_fuerte}"
        )


        # =================================================
        # FILTRO DE EXTENSIÓN
        # =================================================

        if demasiado_lejos:

            print(
                "⚠️ Precio demasiado alejado de EMA20"
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "😴 Precio demasiado "
                    "alejado de EMA20"
                )
            }


        # =================================================
        # POSIBLE COMPRA ANTICIPADA
        #
        # NO exige:
        # ❌ EMA20 subiendo
        # ❌ ADX >= 20
        #
        # Sí necesita:
        # ✅ Contexto 15M
        # ✅ Estructura
        # ✅ Momentum RSI
        # ✅ DI+
        # =================================================

        posible_compra = (
            score_compra >= 80
            and score_compra > score_venta
            and contexto_alcista_15
            and estructura_alcista
            and momentum_alcista
            and fuerza_compradora
        )


        # =================================================
        # POSIBLE VENTA ANTICIPADA
        # =================================================

        posible_venta = (
            score_venta >= 80
            and score_venta > score_compra
            and contexto_bajista_15
            and estructura_bajista
            and momentum_bajista
            and fuerza_vendedora
        )


        # =================================================
        # COMPRA CONFIRMADA
        #
        # Aquí SÍ exigimos:
        # ✅ EMA20 subiendo
        # ✅ ADX >= 20
        # =================================================

        compra_confirmada = (
            posible_compra
            and ema20_subiendo
            and adx_fuerte
        )


        # =================================================
        # VENTA CONFIRMADA
        # =================================================

        venta_confirmada = (
            posible_venta
            and ema20_bajando
            and adx_fuerte
        )


        # =================================================
        # COMPRA CONFIRMADA
        # =================================================

        if compra_confirmada:

            entrada = round(
                precio,
                2
            )

            sl = round(
                entrada - atr * 1.3,
                2
            )

            tp = round(
                entrada + atr * 2.2,
                2
            )

            identificador = (
                uuid.uuid4().hex[:6]
            )

            print(
                "🟢 COMPRA CONFIRMADA"
            )

            mensaje = f"""🥇 XAU SNIPER AI V3.3

ID: {identificador}

🟢 COMPRA CONFIRMADA

⭐ Score: {score_compra}/100

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

DI+: {di_plus:.1f}
DI-: {di_minus:.1f}

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}
EMA200: {ema200:.2f}

✅ EMA20 confirmada
✅ ADX fuerte
🧠 Momentum alcista
"""

            return {
                "tipo": "COMPRA",
                "mensaje": mensaje,
                "precio": entrada
            }


        # =================================================
        # VENTA CONFIRMADA
        # =================================================

        if venta_confirmada:

            entrada = round(
                precio,
                2
            )

            sl = round(
                entrada + atr * 1.3,
                2
            )

            tp = round(
                entrada - atr * 2.2,
                2
            )

            identificador = (
                uuid.uuid4().hex[:6]
            )

            print(
                "🔴 VENTA CONFIRMADA"
            )

            mensaje = f"""🥇 XAU SNIPER AI V3.3

ID: {identificador}

🔴 VENTA CONFIRMADA

⭐ Score: {score_venta}/100

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

DI+: {di_plus:.1f}
DI-: {di_minus:.1f}

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}
EMA200: {ema200:.2f}

✅ EMA20 confirmada
✅ ADX fuerte
🧠 Momentum bajista
"""

            return {
                "tipo": "VENTA",
                "mensaje": mensaje,
                "precio": entrada
            }


        # =================================================
        # POSIBLE COMPRA ANTICIPADA
        # =================================================

        if posible_compra:

            entrada = round(
                precio,
                2
            )

            sl = round(
                entrada - atr * 1.3,
                2
            )

            tp = round(
                entrada + atr * 2.2,
                2
            )

            identificador = (
                uuid.uuid4().hex[:6]
            )

            print(
                "🟡 POSIBLE COMPRA ANTICIPADA"
            )

            mensaje = f"""🥇 X
