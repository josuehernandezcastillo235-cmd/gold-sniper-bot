import requests
import pandas as pd
import numpy as np
import time
import uuid

from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator


# ============================================================
# XAU SNIPER AI V4.1
# MOTOR DE ESTRUCTURA + MOMENTUM + LIQUIDEZ
#
# PROVEEDOR:
# BiQuote
#
# MODO:
# PAPER / ESCÁNER
# ============================================================


BIQUOTE_BASE = "https://biquote.io/api"

SYMBOL = "XAUUSD"

INTERVALO_5M = "5m"
INTERVALO_15M = "15m"

BARRAS_5M = 300
BARRAS_15M = 200

ADX_MINIMO = 15

RSI_COMPRA = 52
RSI_VENTA = 48

RSI_CONFIRMACION_COMPRA = 55
RSI_CONFIRMACION_VENTA = 45

ATR_SL = 1.30
ATR_TP = 2.20

RR_MINIMO = 1.50

MINUTOS_REPETICION = 15

TIMEOUT = 12


# ============================================================
# ESTADO
# ============================================================

estado_prealerta = None

ultima_alerta_id = None
ultima_alerta_timestamp = 0

ultima_confirmacion_id = None
ultima_confirmacion_timestamp = 0


# ============================================================
# SESIÓN HTTP
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "XAU-Sniper-AI/4.1"
})


# ============================================================
# UTILIDADES
# ============================================================

def ahora_ms():

    return int(time.time() * 1000)


def limpiar_numero(valor):

    try:
        return float(valor)

    except Exception:
        return np.nan


def numero_fmt(valor):

    try:
        return f"{float(valor):.2f}"

    except Exception:
        return "N/D"


def precio_fmt(valor):

    try:
        return f"{float(valor):.2f}"

    except Exception:
        return "N/D"


# ============================================================
# DESCARGAR OHLC BIQUOTE
# ============================================================

def obtener_ohlc(
    intervalo,
    limite
):

    url = (
        f"{BIQUOTE_BASE}/"
        f"{SYMBOL}/ohlc"
    )

    params = {
        "interval": intervalo,
        "limit": limite
    }

    try:

        respuesta = SESSION.get(
            url,
            params=params,
            timeout=TIMEOUT
        )

        respuesta.raise_for_status()

        data = respuesta.json()

    except requests.RequestException as e:

        raise RuntimeError(
            f"BiQuote HTTP: {e}"
        )

    except ValueError:

        raise RuntimeError(
            "BiQuote devolvió JSON inválido"
        )

    if not isinstance(data, dict):

        raise RuntimeError(
            "Respuesta BiQuote inesperada"
        )

    barras = data.get("bars")

    if not barras:

        raise RuntimeError(
            f"BiQuote sin barras para {intervalo}"
        )

    df = pd.DataFrame(barras)

    columnas = [
        "openTime",
        "open",
        "high",
        "low",
        "close"
    ]

    faltantes = [
        c for c in columnas
        if c not in df.columns
    ]

    if faltantes:

        raise RuntimeError(
            "Faltan columnas BiQuote: "
            + ", ".join(faltantes)
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

    df["openTime"] = pd.to_datetime(
        df["openTime"],
        utc=True,
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            "openTime",
            "open",
            "high",
            "low",
            "close"
        ]
    )

    df = df.sort_values(
        "openTime"
    )

    df = df.drop_duplicates(
        subset=["openTime"]
    )

    if "isOpen" in df.columns:

        df = df[
            df["isOpen"] != True
        ]

    df = df.reset_index(
        drop=True
    )

    if len(df) < 80:

        raise RuntimeError(
            f"Datos insuficientes "
            f"{intervalo}: {len(df)}"
        )

    return df


# ============================================================
# INDICADORES
# ============================================================

def agregar_indicadores(df):

    df = df.copy()

    atr = AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    df["atr"] = atr.average_true_range()

    rsi = RSIIndicator(
        close=df["close"],
        window=14
    )

    df["rsi"] = rsi.rsi()

    adx = ADXIndicator(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    df["adx"] = adx.adx()
    df["di_plus"] = adx.adx_pos()
    df["di_minus"] = adx.adx_neg()

    df = df.replace(
        [np.inf, -np.inf],
        np.nan
    )

    df = df.dropna(
        subset=[
            "atr",
            "rsi",
            "adx",
            "di_plus",
            "di_minus"
        ]
    )

    if len(df) < 50:

        raise RuntimeError(
            "No hay suficientes datos "
            "después de indicadores."
        )

    return df.reset_index(
        drop=True
    )


# ============================================================
# PIVOTS
# ============================================================

def detectar_pivots(
    df,
    ventana=3
):

    df = df.copy()

    df["pivot_high"] = False
    df["pivot_low"] = False

    highs = df["high"].values
    lows = df["low"].values

    for i in range(
        ventana,
        len(df) - ventana
    ):

        bloque_high = highs[
            i - ventana:
            i + ventana + 1
        ]

        bloque_low = lows[
            i - ventana:
            i + ventana + 1
        ]

        if highs[i] == max(
            bloque_high
        ):

            df.loc[
                i,
                "pivot_high"
            ] = True

        if lows[i] == min(
            bloque_low
        ):

            df.loc[
                i,
                "pivot_low"
            ] = True

    return df


# ============================================================
# ÚLTIMOS PIVOTS
# ============================================================

def ultimos_pivots(df):

    ph = df[
        df["pivot_high"]
    ][
        ["openTime", "high"]
    ].tail(6)

    pl = df[
        df["pivot_low"]
    ][
        ["openTime", "low"]
    ].tail(6)

    highs = list(
        ph["high"].astype(float)
    )

    lows = list(
        pl["low"].astype(float)
    )

    return highs, lows


# ============================================================
# ESTRUCTURA
# ============================================================

def evaluar_estructura(df):

    highs, lows = ultimos_pivots(df)

    if len(highs) < 3 or len(lows) < 3:

        return {
            "regimen": "INDEFINIDO",
            "estructura": "SIN_DATOS",
            "bos_alcista": False,
            "bos_bajista": False,
            "choch_alcista": False,
            "choch_bajista": False,
            "swing_high": None,
            "swing_low": None,
            "hh": False,
            "hl": False,
            "lh": False,
            "ll": False
        }

    h1 = highs[-1]
    h2 = highs[-2]

    l1 = lows[-1]
    l2 = lows[-2]

    hh = h1 > h2
    hl = l1 > l2

    lh = h1 < h2
    ll = l1 < l2

    regimen = "LATERAL"
    estructura = "MIXTA"

    if hh and hl:

        regimen = "ALCISTA"
        estructura = "HH + HL"

    elif lh and ll:

        regimen = "BAJISTA"
        estructura = "LH + LL"

    elif hh and ll:

        regimen = "TRANSICION"
        estructura = "HH + LL"

    elif lh and hl:

        regimen = "TRANSICION"
        estructura = "LH + HL"

    cierre = float(
        df["close"].iloc[-1]
    )

    swing_high = h1
    swing_low = l1

    bos_alcista = (
        cierre > h2
    )

    bos_bajista = (
        cierre < l2
    )

    choch_alcista = (
        regimen == "TRANSICION"
        and cierre > h2
    )

    choch_bajista = (
        regimen == "TRANSICION"
        and cierre < l2
    )

    return {
        "regimen": regimen,
        "estructura": estructura,
        "bos_alcista": bos_alcista,
        "bos_bajista": bos_bajista,
        "choch_alcista": choch_alcista,
        "choch_bajista": choch_bajista,
        "swing_high": swing_high,
        "swing_low": swing_low,
        "hh": hh,
        "hl": hl,
        "lh": lh,
        "ll": ll
    }


# ============================================================
# MOMENTUM
# ============================================================

def evaluar_momentum(df):

    ult = df.iloc[-1]

    cierre = float(ult["close"])
    apertura = float(ult["open"])
    high = float(ult["high"])
    low = float(ult["low"])

    atr = float(ult["atr"])
    rsi = float(ult["rsi"])
    adx = float(ult["adx"])

    di_plus = float(
        ult["di_plus"]
    )

    di_minus = float(
        ult["di_minus"]
    )

    rango = high - low

    cuerpo = abs(
        cierre - apertura
    )

    vela_alcista = (
        cierre > apertura
    )

    vela_bajista = (
        cierre < apertura
    )

    impulso_alcista = (
        vela_alcista
        and atr > 0
        and cuerpo >= atr * 0.45
        and rango >= atr * 0.70
    )

    impulso_bajista = (
        vela_bajista
        and atr > 0
        and cuerpo >= atr * 0.45
        and rango >= atr * 0.70
    )

    momentum_alcista = (
        rsi >= RSI_COMPRA
        and di_plus > di_minus
    )

    momentum_bajista = (
        rsi <= RSI_VENTA
        and di_minus > di_plus
    )

    return {
        "precio": cierre,
        "atr": atr,
        "rsi": rsi,
        "adx": adx,
        "di_plus": di_plus,
        "di_minus": di_minus,
        "cuerpo": cuerpo,
        "rango": rango,
        "vela_alcista": vela_alcista,
        "vela_bajista": vela_bajista,
        "impulso_alcista": impulso_alcista,
        "impulso_bajista": impulso_bajista,
        "momentum_alcista": momentum_alcista,
        "momentum_bajista": momentum_bajista
    }


# ============================================================
# PULLBACK
# ============================================================

def detectar_pullback(
    df,
    estructura,
    momentum
):

    precio = momentum["precio"]
    atr = momentum["atr"]

    if atr <= 0:

        return {
            "pullback_compra": False,
            "pullback_venta": False
        }

    highs, lows = ultimos_pivots(df)

    if not highs or not lows:

        return {
            "pullback_compra": False,
            "pullback_venta": False
        }

    swing_high = highs[-1]
    swing_low = lows[-1]

    distancia_low = abs(
        precio - swing_low
    )

    distancia_high = abs(
        precio - swing_high
    )

    pullback_compra = (
        estructura["regimen"] == "ALCISTA"
        and distancia_low <= atr * 2.0
        and precio >= swing_low
    )

    pullback_venta = (
        estructura["regimen"] == "BAJISTA"
        and distancia_high <= atr * 2.0
        and precio <= swing_high
    )

    return {
        "pullback_compra":
            pullback_compra,

        "pullback_venta":
            pullback_venta
    }


# ============================================================
# CONTINUACIÓN
# ============================================================

def detectar_continuacion(
    df,
    momentum
):

    ult = df.iloc[-1]
    anterior = df.iloc[-2]

    close = float(
        ult["close"]
    )

    open_ = float(
        ult["open"]
    )

    high = float(
        ult["high"]
    )

    low = float(
        ult["low"]
    )

    prev_high = float(
        anterior["high"]
    )

    prev_low = float(
        anterior["low"]
    )

    atr = momentum["atr"]

    continuacion_compra = (
        close > prev_high
        and close > open_
        and (high - low) >= atr * 0.45
    )

    continuacion_venta = (
        close < prev_low
        and close < open_
        and (high - low) >= atr * 0.45
    )

    return {
        "continuacion_compra":
            continuacion_compra,

        "continuacion_venta":
            continuacion_venta
    }


# ============================================================
# SCORE COMPRA
# ============================================================

def calcular_score_compra(
    estructura,
    momentum,
    pullback,
    continuacion
):

    score = 0
    razones = []

    if estructura["regimen"] == "ALCISTA":

        score += 25
        razones.append(
            "estructura alcista"
        )

    if estructura["bos_alcista"]:

        score += 15
        razones.append(
            "BOS alcista"
        )

    if estructura["choch_alcista"]:

        score += 10
        razones.append(
            "CHoCH alcista"
        )

    if momentum["impulso_alcista"]:

        score += 15
        razones.append(
            "impulso alcista"
        )

    if momentum["momentum_alcista"]:

        score += 10
        razones.append(
            "momentum comprador"
        )

    if momentum["adx"] >= ADX_MINIMO:

        score += 10
        razones.append(
            "ADX válido"
        )

    if pullback["pullback_compra"]:

        score += 10
        razones.append(
            "pullback válido"
        )

    if continuacion["continuacion_compra"]:

        score += 15
        razones.append(
            "continuación confirmada"
        )

    return min(score, 100), razones


# ============================================================
# SCORE VENTA
# ============================================================

def calcular_score_venta(
    estructura,
    momentum,
    pullback,
    continuacion
):

    score = 0
    razones = []

    if estructura["regimen"] == "BAJISTA":

        score += 25
        razones.append(
            "estructura bajista"
        )

    if estructura["bos_bajista"]:

        score += 15
        razones.append(
            "BOS bajista"
        )

    if estructura["choch_bajista"]:

        score += 10
        razones.append(
            "CHoCH bajista"
        )

    if momentum["impulso_bajista"]:

        score += 15
        razones.append(
            "impulso bajista"
        )

    if momentum["momentum_bajista"]:

        score += 10
        razones.append(
            "momentum vendedor"
        )

    if momentum["adx"] >= ADX_MINIMO:

        score += 10
        razones.append(
            "ADX válido"
        )

    if pullback["pullback_venta"]:

        score += 10
        razones.append(
            "pullback válido"
        )

    if continuacion["continuacion_venta"]:

        score += 15
        razones.append(
            "continuación confirmada"
        )

    return min(score, 100), razones


# ============================================================
# NIVELES
# ============================================================

def calcular_niveles(
    direccion,
    precio,
    atr
):

    if atr <= 0:

        return (
            precio,
            precio,
            0
        )

    if direccion == "COMPRA":

        sl = precio - (
            atr * ATR_SL
        )

        tp = precio + (
            atr * ATR_TP
        )

    else:

        sl = precio + (
            atr * ATR_SL
        )

        tp = precio - (
            atr * ATR_TP
        )

    distancia_sl = abs(
        precio - sl
    )

    distancia_tp = abs(
        tp - precio
    )

    if distancia_sl <= 0:

        rr = 0

    else:

        rr = (
            distancia_tp /
            distancia_sl
        )

    return sl, tp, rr


# ============================================================
# RR
# ============================================================

def rr_valido(rr):

    return (
        rr >= RR_MINIMO
    )


# ============================================================
# ID
# ============================================================

def generar_id(
    direccion,
    precio
):

    bloque = int(
        time.time() // 900
    )

    return (
        f"{direccion}-"
        f"{bloque}-"
        f"{round(precio, 2)}"
    )


# ============================================================
# COOLDOWN
# ============================================================

def cooldown_activo():

    global ultima_alerta_timestamp

    if not ultima_alerta_timestamp:

        return False

    transcurrido = (
        time.time()
        - ultima_alerta_timestamp
    )

    return (
        transcurrido
        < MINUTOS_REPETICION * 60
    )


# ============================================================
# GUARDAR PREALERTA
# ============================================================

def guardar_prealerta(
    direccion,
    precio,
    atr,
    score,
    estructura,
    momentum
):

    global estado_prealerta
    global ultima_alerta_timestamp
    global ultima_alerta_id

    identificador = generar_id(
        direccion,
        precio
    )

    estado_prealerta = {
        "id": identificador,
        "direccion": direccion,
        "precio": precio,
        "atr": atr,
        "score": score,
        "timestamp": time.time(),
        "regimen": estructura["regimen"],
        "rsi": momentum["rsi"],
        "adx": momentum["adx"]
    }

    ultima_alerta_id = identificador
    ultima_alerta_timestamp = time.time()

    return identificador


# ============================================================
# PREALERTA VIGENTE
# ============================================================

def prealerta_vigente():

    global estado_prealerta

    if not estado_prealerta:

        return False

    edad = (
        time.time()
        - estado_prealerta["timestamp"]
    )

    if edad > MINUTOS_REPETICION * 60:

        estado_prealerta = None

        return False

    return True


# ============================================================
# DESCARTAR PREALERTA
# ============================================================

def descartar_prealerta(
    motivo
):

    global estado_prealerta

    anterior = estado_prealerta

    estado_prealerta = None

    if anterior is None:

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": "😴 SIN_SEÑAL"
        }

    return {
        "tipo": "DESCARTADA",
        "id": anterior["id"],
        "mensaje": (
            "🟠 XAU SNIPER AI V4.1\n\n"
            "❌ PREALERTA DESCARTADA\n\n"
            f"📌 Dirección: "
            f"{anterior['direccion']}\n"
            f"🆔 ID: "
            f"{anterior['id']}\n"
            f"📊 Score inicial: "
            f"{anterior['score']}/100\n\n"
            f"🧠 Motivo:\n"
            f"{motivo}\n\n"
            "🔍 La estructura ya no cumple "
            "las condiciones."
        )
    }


# ============================================================
# CONFIRMACIÓN
# ============================================================

def confirmar_prealerta(
    df5,
    df15,
    estructura5,
    estructura15,
    momentum5,
    continuacion5
):

    if not prealerta_vigente():

        return None

    p = estado_prealerta

    direccion = p["direccion"]

    precio = momentum5["precio"]
    rsi = momentum5["rsi"]
    adx = momentum5["adx"]

    if direccion == "COMPRA":

        confirmada = (
            estructura5["regimen"] == "ALCISTA"
            and estructura15["regimen"]
            in ["ALCISTA", "TRANSICION"]
            and continuacion5[
                "continuacion_compra"
            ]
            and rsi >= RSI_CONFIRMACION_COMPRA
            and adx >= ADX_MINIMO
            and precio >= p["precio"]
        )

        invalidada = (
            estructura5["regimen"] == "BAJISTA"
            or precio < (
                p["precio"]
                - p["atr"] * 0.80
            )
        )

    else:

        confirmada = (
            estructura5["regimen"] == "BAJISTA"
            and estructura15["regimen"]
            in ["BAJISTA", "TRANSICION"]
            and continuacion5[
                "continuacion_venta"
            ]
            and rsi <= RSI_CONFIRMACION_VENTA
            and adx >= ADX_MINIMO
            and precio <= p["precio"]
        )

        invalidada = (
            estructura5["regimen"] == "ALCISTA"
            or precio > (
                p["precio"]
                + p["atr"] * 0.80
            )
        )

    if invalidada:

        return descartar_prealerta(
            "La dirección perdió "
            "la estructura."
        )

    if not confirmada:

        return None

    return True


# ============================================================
# MENSAJE PREALERTA
# ============================================================

def construir_prealerta(
    direccion,
    identificador,
    precio,
    sl,
    tp,
    rr,
    score,
    estructura5,
    estructura15,
    momentum5
):

    emoji = (
        "🟢"
        if direccion == "COMPRA"
        else "🔴"
    )

    return (
        f"{emoji} XAU SNIPER AI V4.1\n\n"
        f"⚠️ PREALERTA {direccion}\n\n"
        f"🆔 ID: {identificador}\n"
        f"📊 Score: {score}/100\n"
        f"💰 Precio: {precio_fmt(precio)}\n\n"
        f"📈 5M: {estructura5['regimen']}\n"
        f"📊 15M: {estructura15['regimen']}\n\n"
        f"RSI 5M: "
        f"{numero_fmt(momentum5['rsi'])}\n"
        f"ADX 5M: "
        f"{numero_fmt(momentum5['adx'])}\n"
        f"DI+: "
        f"{numero_fmt(momentum5['di_plus'])}\n"
        f"DI-: "
        f"{numero_fmt(momentum5['di_minus'])}\n\n"
        f"🛑 SL referencia: "
        f"{precio_fmt(sl)}\n"
        f"🎯 TP referencia: "
        f"{precio_fmt(tp)}\n"
        f"📐 RR: 1:{numero_fmt(rr)}\n\n"
        "🧠 Estructura detectada.\n"
        "🔄 Esperando pullback + "
        "continuación.\n\n"
        "⚠️ AÚN NO CONFIRMADA"
    )


# ============================================================
# MENSAJE CONFIRMADO
# ============================================================

def construir_confirmacion(
    direccion,
    identificador,
    precio,
    sl,
    tp,
    rr,
    score,
    estructura5,
    estructura15,
    momentum5
):

    emoji = (
        "🟢"
        if direccion == "COMPRA"
        else "🔴"
    )

    return (
        f"{emoji} XAU SNIPER AI V4.1\n\n"
        f"🔥 ALERTA CONFIRMADA: "
        f"{direccion}\n\n"
        f"🆔 ID: {identificador}\n"
        f"📊 Score: {score}/100\n"
        f"💰 Entrada referencia: "
        f"{precio_fmt(precio)}\n\n"
        f"📈 5M: {estructura5['regimen']}\n"
        f"📊 15M: {estructura15['regimen']}\n\n"
        f"RSI: "
        f"{numero_fmt(momentum5['rsi'])}\n"
        f"ADX: "
        f"{numero_fmt(momentum5['adx'])}\n\n"
        f"🛑 SL referencia: "
        f"{precio_fmt(sl)}\n"
        f"🎯 TP referencia: "
        f"{precio_fmt(tp)}\n"
        f"📐 RR: 1:{numero_fmt(rr)}\n\n"
        "🚀 Impulso + Pullback + "
        "Continuación detectados.\n\n"
        "⚠️ PAPER / ESCÁNER"
    )


# ============================================================
# DIAGNÓSTICO
# ============================================================

def construir_diagnostico(
    estructura5,
    estructura15,
    momentum5,
    pullback5,
    continuacion5
):

    return (
        "📋 DIAGNÓSTICO XAU SNIPER\n\n"
        f"5M: {estructura5['regimen']}\n"
        f"15M: {estructura15['regimen']}\n\n"
        f"RSI: "
        f"{numero_fmt(momentum5['rsi'])}\n"
        f"ADX: "
        f"{numero_fmt(momentum5['adx'])}\n"
        f"DI+: "
        f"{numero_fmt(momentum5['di_plus'])}\n"
        f"DI-: "
        f"{numero_fmt(momentum5['di_minus'])}\n\n"
        f"Pullback compra: "
        f"{pullback5['pullback_compra']}\n"
        f"Pullback venta: "
        f"{pullback5['pullback_venta']}\n\n"
        f"Continuación compra: "
        f"{continuacion5['continuacion_compra']}\n"
        f"Continuación venta: "
        f"{continuacion5['continuacion_venta']}"
    )


# ============================================================
# ERROR
# ============================================================

def construir_error(
    mensaje
):

    return {
        "tipo": "ERROR",
        "mensaje": (
            "❌ XAU SNIPER AI V4.1\n\n"
            "⚠️ Error de datos / motor\n\n"
            f"{mensaje}\n\n"
            "📡 Proveedor: BiQuote\n"
            "🛑 El bot continúa ejecutándose."
        )
    }


# ============================================================
# ANALIZAR
# ============================================================

def analizar():

    global estado_prealerta
    global ultima_confirmacion_id
    global ultima_confirmacion_timestamp

    try:

        print(
            "📡 Descargando datos desde BiQuote..."
        )

        df5 = obtener_ohlc(
            INTERVALO_5M,
            BARRAS_5M
        )

        df15 = obtener_ohlc(
            INTERVALO_15M,
            BARRAS_15M
        )

        print(
            f"✅ BiQuote 5M: "
            f"{len(df5)} velas"
        )

        print(
            f"✅ BiQuote 15M: "
            f"{len(df15)} velas"
        )

        # ----------------------------------------------------
        # INDICADORES
        # ----------------------------------------------------

        df5 = agregar_indicadores(df5)
        df15 = agregar_indicadores(df15)

        # ----------------------------------------------------
        # PIVOTS
        # ----------------------------------------------------

        df5 = detectar_pivots(df5)
        df15 = detectar_pivots(df15)

        # ----------------------------------------------------
        # ESTRUCTURA
        # ----------------------------------------------------

        estructura5 = evaluar_estructura(df5)
        estructura15 = evaluar_estructura(df15)

        # ----------------------------------------------------
        # MOMENTUM
        # ----------------------------------------------------

        momentum5 = evaluar_momentum(df5)

        # ----------------------------------------------------
        # PULLBACK
        # ----------------------------------------------------

        pullback5 = detectar_pullback(
            df5,
            estructura5,
            momentum5
        )

        # ----------------------------------------------------
        # CONTINUACIÓN
        # ----------------------------------------------------

        continuacion5 = detectar_continuacion(
            df5,
            momentum5
        )

        print(
            f"📊 5M: "
            f"{estructura5['regimen']}"
        )

        print(
            f"📊 15M: "
            f"{estructura15['regimen']}"
        )

        print(
            f"💰 Precio: "
            f"{momentum5['precio']:.2f}"
        )

        print(
            f"RSI: "
            f"{momentum5['rsi']:.2f}"
        )

        print(
            f"ADX: "
            f"{momentum5['adx']:.2f}"
        )

        # ====================================================
        # PREALERTA EXISTENTE
        # ====================================================

        if prealerta_vigente():

            print(
                "⚠️ PREALERTA ACTIVA: "
                f"{estado_prealerta['id']}"
            )

            confirmacion = confirmar_prealerta(
                df5,
                df15,
                estructura5,
                estructura15,
                momentum5,
                continuacion5
            )

            # ------------------------------------------------
            # DESCARTADA
            # ------------------------------------------------

            if isinstance(
                confirmacion,
                dict
            ):

                return confirmacion

            # ------------------------------------------------
            # CONFIRMADA
            # ------------------------------------------------

            if confirmacion is True:

                direccion = (
                    estado_prealerta[
                        "direccion"
                    ]
                )

                precio = (
                    momentum5["precio"]
                )

                atr = (
                    momentum5["atr"]
                )

                if direccion == "COMPRA":

                    score, _ = (
                        calcular_score_compra(
                            estructura5,
                            momentum5,
                            pullback5,
                            continuacion5
                        )
                    )

                else:

                    score, _ = (
                        calcular_score_venta(
                            estructura5,
                            momentum5,
                            pullback5,
                            continuacion5
                        )
                    )

                sl, tp, rr = calcular_niveles(
                    direccion,
                    precio,
                    atr
                )

                if not rr_valido(rr):

                    return descartar_prealerta(
                        "RR insuficiente "
                        "al confirmar."
                    )

                identificador = (
                    estado_prealerta["id"]
                )

                ultima_confirmacion_id = (
                    identificador
                )

                ultima_confirmacion_timestamp = (
                    time.time()
                )

                mensaje = construir_confirmacion(
                    direccion,
                    identificador,
                    precio,
                    sl,
                    tp,
                    rr,
                    score,
                    estructura5,
                    estructura15,
                    momentum5
                )

                estado_prealerta = None

                print(
                    "🔥 PREALERTA CONFIRMADA"
                )

                return {
                    "tipo": "CONFIRMADA",
                    "id": identificador,
                    "mensaje": mensaje
                }

            # ------------------------------------------------
            # TODAVÍA ESPERANDO
            # ------------------------------------------------

            print(
                "⏳ Prealerta todavía "
                "esperando confirmación."
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "⏳ Prealerta activa. "
                    "Esperando continuación."
                )
            }

        # ====================================================
        # COOLDOWN
        # ====================================================

        if cooldown_activo():

            print(
                "🧊 Cooldown activo."
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "🧊 Cooldown activo."
                )
            }


        # ====================================================
        # SCORE
        # ====================================================

        score_compra, razones_compra = (
            calcular_score_compra(
                estructura5,
                momentum5,
                pullback5,
                continuacion5
            )
        )

        score_venta, razones_venta = (
            calcular_score_venta(
                estructura5,
                momentum5,
                pullback5,
                continuacion5
            )
        )

        print(
            f"🎯 Score COMPRA: "
            f"{score_compra}/100"
        )

        print(
            f"🎯 Score VENTA: "
            f"{score_venta}/100"
        )

        # ====================================================
        # SETUP COMPRA
        # ====================================================

        setup_compra = (
            estructura5["regimen"]
            == "ALCISTA"
            and
            estructura15["regimen"]
            in [
                "ALCISTA",
                "TRANSICION"
            ]
            and
            momentum5["momentum_alcista"]
            and
            momentum5["adx"]
            >= ADX_MINIMO
            and
            pullback5["pullback_compra"]
        )

        # ====================================================
        # SETUP VENTA
        # ====================================================

        setup_venta = (
            estructura5["regimen"]
            == "BAJISTA"
            and
            estructura15["regimen"]
            in [
                "BAJISTA",
                "TRANSICION"
            ]
            and
            momentum5["momentum_bajista"]
            and
            momentum5["adx"]
            >= ADX_MINIMO
            and
            pullback5["pullback_venta"]
        )

        # ====================================================
        # PREALERTA COMPRA
        # ====================================================

        if (
            setup_compra
            and score_compra >= 55
        ):

            direccion = "COMPRA"

            precio = momentum5["precio"]
            atr = momentum5["atr"]

            sl, tp, rr = calcular_niveles(
                direccion,
                precio,
                atr
            )

            if not rr_valido(rr):

                print(
                    "❌ Compra descartada "
                    "por RR."
                )

                return {
                    "tipo": "SIN_SEÑAL",
                    "mensaje": (
                        "😴 Compra descartada: "
                        "RR insuficiente."
                    )
                }

            identificador = guardar_prealerta(
                direccion,
                precio,
                atr,
                score_compra,
                estructura5,
                momentum5
            )

            mensaje = construir_prealerta(
                direccion,
                identificador,
                precio,
                sl,
                tp,
                rr,
                score_compra,
                estructura5,
                estructura15,
                momentum5
            )

            print(
                "⚠️ NUEVA PREALERTA COMPRA"
            )

            return {
                "tipo": "PREALERTA",
                "id": identificador,
                "mensaje": mensaje
            }

        # ====================================================
        # PREALERTA VENTA
        # ====================================================

        if (
            setup_venta
            and score_venta >= 55
        ):

            direccion = "VENTA"

            precio = momentum5["precio"]
            atr = momentum5["atr"]

            sl, tp, rr = calcular_niveles(
                direccion,
                precio,
                atr
            )

            if not rr_valido(rr):

                print(
                    "❌ Venta descartada "
                    "por RR."
                )

                return {
                    "tipo": "SIN_SEÑAL",
                    "mensaje": (
                        "😴 Venta descartada: "
                        "RR insuficiente."
                    )
                }

            identificador = guardar_prealerta(
                direccion,
                precio,
                atr,
                score_venta,
                estructura5,
                momentum5
            )

            mensaje = construir_prealerta(
                direccion,
                identificador,
                precio,
                sl,
                tp,
                rr,
                score_venta,
                estructura5,
                estructura15,
                momentum5
            )

            print(
                "⚠️ NUEVA PREALERTA VENTA"
            )

            return {
                "tipo": "PREALERTA",
                "id": identificador,
                "mensaje": mensaje
            }


        # ====================================================
        # SIN SEÑAL
        # ====================================================

        diagnostico = construir_diagnostico(
            estructura5,
            estructura15,
            momentum5,
            pullback5,
            continuacion5
        )

        print(diagnostico)

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": "😴 SIN_SEÑAL"
        }

    # ========================================================
    # ERROR CONTROLADO
    # ========================================================

    except RuntimeError as e:

        print(
            f"⚠️ ERROR DE DATOS: {e}"
        )

        return construir_error(
            str(e)
        )

    except requests.RequestException as e:

        print(
            f"⚠️ ERROR HTTP: {e}"
        )

        return construir_error(
            f"Error HTTP: {e}"
        )

    except Exception as e:

        print(
            f"❌ ERROR INTERNO STRATEGY: {e}"
        )

        return construir_error(
            f"Error interno: {e}"
        )


# ============================================================
# FIN XAU SNIPER AI V4.1
# ============================================================
