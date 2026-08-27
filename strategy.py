import requests
import pandas as pd
import numpy as np
import time
import uuid

from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 1/9
#
# MOTOR:
# ESTRUCTURA + MOVIMIENTO + MOMENTUM + PULLBACK
# + CONTINUACIÓN + CONFIRMACIÓN
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

INTERVALO_ANALISIS = 100

ADX_MINIMO = 15

RSI_COMPRA = 52
RSI_VENTA = 48

RSI_CONFIRMACION_COMPRA = 54
RSI_CONFIRMACION_VENTA = 46

ATR_SL = 1.30
ATR_TP = 2.20

RR_MINIMO = 1.50

MINUTOS_PREALERTA = 15
MINUTOS_REPETICION = 15

PULLBACK_MIN_ATR = 0.20
PULLBACK_MAX_ATR = 1.80

IMPULSO_CUERPO_ATR = 0.40
IMPULSO_RANGO_ATR = 0.70

TIMEOUT = 12

# ------------------------------------------------------------
# Protección contra datos atrasados
# ------------------------------------------------------------

MAX_EDAD_DATOS_MINUTOS = 20

# ------------------------------------------------------------
# Estado
# ------------------------------------------------------------

estado_prealerta = None

ultima_alerta_id = None
ultima_alerta_timestamp = 0

ultima_confirmacion_id = None
ultima_confirmacion_timestamp = 0

ultima_vela_5m = None
ultima_vela_15m = None

# ------------------------------------------------------------
# Sesión HTTP
# ------------------------------------------------------------

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "XAU-Sniper-AI/4.2"
})


# ============================================================
# UTILIDADES
# ============================================================

def ahora():

    return time.time()


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


def minutos_desde(timestamp):

    try:
        return (
            time.time() - timestamp
        ) / 60.0
    except Exception:
        return 999999


# ============================================================
# FIN PARTE 1/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 2/9
# BIQUOTE + VALIDACIÓN DE DATOS
# ============================================================


def obtener_ohlc(intervalo, limite):

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
            "BiQuote devolvió JSON inválido."
        )

    if not isinstance(data, dict):

        raise RuntimeError(
            "Respuesta BiQuote inesperada."
        )

    barras = data.get("bars")

    if not barras:

        raise RuntimeError(
            f"BiQuote sin barras para {intervalo}."
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
        columna
        for columna in columnas
        if columna not in df.columns
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

    # --------------------------------------------------------
    # Nunca utilizar una vela marcada como abierta
    # --------------------------------------------------------

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
# VALIDAR ANTIGÜEDAD DE DATOS
# ============================================================

def validar_datos_recientes(df5, df15):

    ahora_utc = pd.Timestamp.now(
        tz="UTC"
    )

    ultima5 = df5["openTime"].iloc[-1]
    ultima15 = df15["openTime"].iloc[-1]

    edad5 = (
        ahora_utc - ultima5
    ).total_seconds() / 60.0

    edad15 = (
        ahora_utc - ultima15
    ).total_seconds() / 60.0

    print(
        f"🕐 Edad 5M: {edad5:.1f} minutos"
    )

    print(
        f"🕐 Edad 15M: {edad15:.1f} minutos"
    )

    if edad5 > MAX_EDAD_DATOS_MINUTOS:

        raise RuntimeError(
            "Datos 5M atrasados: "
            f"{edad5:.1f} minutos."
        )

    if edad15 > MAX_EDAD_DATOS_MINUTOS:

        raise RuntimeError(
            "Datos 15M atrasados: "
            f"{edad15:.1f} minutos."
        )

    return True


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
            "Datos insuficientes "
            "después de indicadores."
        )

    return df.reset_index(
        drop=True
    )


# ============================================================
# FIN PARTE 2/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 3/9
# PIVOTS + ESTRUCTURA
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
    ].tail(8)

    pl = df[
        df["pivot_low"]
    ][
        ["openTime", "low"]
    ].tail(8)

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
# FIN PARTE 3/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 4/9
# MOMENTUM + IMPULSO + PULLBACK
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
        and cuerpo >= atr * IMPULSO_CUERPO_ATR
        and rango >= atr * IMPULSO_RANGO_ATR
    )

    impulso_bajista = (
        vela_bajista
        and cuerpo >= atr * IMPULSO_CUERPO_ATR
        and rango >= atr * IMPULSO_RANGO_ATR
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
            "pullback_venta": False,
            "impulso_previo_compra": False,
            "impulso_previo_venta": False,
            "retroceso_compra": False,
            "retroceso_venta": False
        }

    recientes = df.tail(6).copy()

    cuerpos = (
        recientes["close"]
        - recientes["open"]
    ).abs()

    rangos = (
        recientes["high"]
        - recientes["low"]
    )

    alcistas = (
        recientes["close"]
        > recientes["open"]
    )

    bajistas = (
        recientes["close"]
        < recientes["open"]
    )

    impulso_previo_compra = bool(
        (
            alcistas
            & (
                cuerpos
                >= recientes["atr"] * 0.40
            )
            & (
                rangos
                >= recientes["atr"] * 0.70
            )
        ).any()
    )

    impulso_previo_venta = bool(
        (
            bajistas
            & (
                cuerpos
                >= recientes["atr"] * 0.40
            )
            & (
                rangos
                >= recientes["atr"] * 0.70
            )
        ).any()
    )

    highs, lows = ultimos_pivots(df)

    if not highs or not lows:

        return {
            "pullback_compra": False,
            "pullback_venta": False,
            "impulso_previo_compra":
                impulso_previo_compra,
            "impulso_previo_venta":
                impulso_previo_venta,
            "retroceso_compra": False,
            "retroceso_venta": False
        }

    swing_high = highs[-1]
    swing_low = lows[-1]

    distancia_low = abs(
        precio - swing_low
    )

    distancia_high = abs(
        precio - swing_high
    )

    retroceso_compra = (
        estructura["regimen"] == "ALCISTA"
        and impulso_previo_compra
        and distancia_low >= atr * PULLBACK_MIN_ATR
        and distancia_low <= atr * PULLBACK_MAX_ATR
        and precio >= swing_low
    )

    retroceso_venta = (
        estructura["regimen"] == "BAJISTA"
        and impulso_previo_venta
        and distancia_high >= atr * PULLBACK_MIN_ATR
        and distancia_high <= atr * PULLBACK_MAX_ATR
        and precio <= swing_high
    )

    return {
        "pullback_compra":
            retroceso_compra,
        "pullback_venta":
            retroceso_venta,
        "impulso_previo_compra":
            impulso_previo_compra,
        "impulso_previo_venta":
            impulso_previo_venta,
        "retroceso_compra":
            retroceso_compra,
        "retroceso_venta":
            retroceso_venta
    }


# ============================================================
# FIN PARTE 4/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 5/9
# CONTINUACIÓN + SCORE
# ============================================================


def detectar_continuacion(
    df,
    momentum
):

    ult = df.iloc[-1]
    anterior = df.iloc[-2]

    close = float(ult["close"])
    open_ = float(ult["open"])

    high = float(ult["high"])
    low = float(ult["low"])

    prev_high = float(
        anterior["high"]
    )

    prev_low = float(
        anterior["low"]
    )

    atr = momentum["atr"]

    rango = high - low

    continuacion_compra = (
        close > prev_high
        and close > open_
        and rango >= atr * 0.45
    )

    continuacion_venta = (
        close < prev_low
        and close < open_
        and rango >= atr * 0.45
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
        razones.append("estructura alcista")

    if estructura["bos_alcista"]:
        score += 15
        razones.append("BOS alcista")

    if estructura["choch_alcista"]:
        score += 10
        razones.append("CHoCH alcista")

    if momentum["impulso_alcista"]:
        score += 15
        razones.append("impulso alcista")

    if momentum["momentum_alcista"]:
        score += 10
        razones.append("momentum comprador")

    if momentum["adx"] >= ADX_MINIMO:
        score += 10
        razones.append("ADX válido")

    if pullback["pullback_compra"]:
        score += 10
        razones.append("pullback válido")

    if continuacion["continuacion_compra"]:
        score += 15
        razones.append("continuación")

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
        razones.append("estructura bajista")

    if estructura["bos_bajista"]:
        score += 15
        razones.append("BOS bajista")

    if estructura["choch_bajista"]:
        score += 10
        razones.append("CHoCH bajista")

    if momentum["impulso_bajista"]:
        score += 15
        razones.append("impulso bajista")

    if momentum["momentum_bajista"]:
        score += 10
        razones.append("momentum vendedor")

    if momentum["adx"] >= ADX_MINIMO:
        score += 10
        razones.append("ADX válido")

    if pullback["pullback_venta"]:
        score += 10
        razones.append("pullback válido")

    if continuacion["continuacion_venta"]:
        score += 15
        razones.append("continuación")

    return min(score, 100), razones


# ============================================================
# FIN PARTE 5/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 6/9
# NIVELES + IDs + COOLDOWN + PREALERTAS
# ============================================================


def calcular_niveles(
    direccion,
    precio,
    atr
):

    if atr <= 0:
        return precio, precio, 0

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


def rr_valido(rr):

    return rr >= RR_MINIMO


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

    sufijo = uuid.uuid4().hex[:4]

    return (
        f"{direccion}-"
        f"{bloque}-"
        f"{round(precio, 2)}-"
        f"{sufijo}"
    )


# ============================================================
# COOLDOWN
# ============================================================

def cooldown_activo():

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

    if not estado_prealerta:
        return False

    edad = (
        time.time()
        - estado_prealerta["timestamp"]
    )

    return (
        edad <= MINUTOS_PREALERTA * 60
    )


# ============================================================
# EXPIRAR
# ============================================================

def expirar_prealerta():

    global estado_prealerta

    if not estado_prealerta:

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": "😴 SIN_SEÑAL"
        }

    anterior = estado_prealerta

    estado_prealerta = None

    direccion = anterior["direccion"]
    identificador = anterior["id"]
    score = anterior["score"]

    mensaje = (
        "🟠 XAU SNIPER AI V4.2\n\n"
        "⏰ PREALERTA EXPIRADA\n\n"
        f"📌 Dirección: {direccion}\n"
        f"🆔 ID: {identificador}\n"
        f"📊 Score inicial: {score}/100\n\n"
        "🧠 Motivo:\n"
        "No apareció la continuación "
        "necesaria dentro del tiempo "
        "establecido.\n\n"
        "❌ Setup cerrado."
    )

    return {
        "tipo": "DESCARTADA",
        "id": identificador,
        "mensaje": mensaje
    }


# ============================================================
# DESCARTAR
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

    direccion = anterior["direccion"]
    identificador = anterior["id"]
    score = anterior["score"]

    mensaje = (
        "🟠 XAU SNIPER AI V4.2\n\n"
        "❌ PREALERTA DESCARTADA\n\n"
        f"📌 Dirección: {direccion}\n"
        f"🆔 ID: {identificador}\n"
        f"📊 Score inicial: {score}/100\n\n"
        "🧠 Motivo:\n"
        f"{motivo}\n\n"
        "🔍 Setup invalidado."
    )

    return {
        "tipo": "DESCARTADA",
        "id": identificador,
        "mensaje": mensaje
    }


# ============================================================
# FIN PARTE 6/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 7/9
# CONFIRMACIÓN
# ============================================================


def confirmar_prealerta(
    estructura5,
    estructura15,
    momentum5,
    continuacion5
):

    global estado_prealerta

    if not estado_prealerta:
        return None

    edad = (
        time.time()
        - estado_prealerta["timestamp"]
    )

    if edad > MINUTOS_PREALERTA * 60:
        return expirar_prealerta()

    p = estado_prealerta

    direccion = p["direccion"]

    precio = momentum5["precio"]
    rsi = momentum5["rsi"]
    adx = momentum5["adx"]

    # ========================================================
    # COMPRA
    # ========================================================

    if direccion == "COMPRA":

        invalidada = (
            estructura5["regimen"] == "BAJISTA"
            or
            precio < (
                p["precio"]
                - p["atr"] * 0.80
            )
        )

        if invalidada:

            return descartar_prealerta(
                "La estructura alcista "
                "se perdió o el precio "
                "invalidó la prealerta."
            )

        confirmada = (
            estructura5["regimen"] == "ALCISTA"
            and
            estructura15["regimen"]
            in ["ALCISTA", "TRANSICION"]
            and
            continuacion5[
                "continuacion_compra"
            ]
            and
            rsi >= RSI_CONFIRMACION_COMPRA
            and
            adx >= ADX_MINIMO
            and
            precio >= p["precio"]
        )

        if confirmada:
            return True

        motivos = []

        if estructura5["regimen"] != "ALCISTA":
            motivos.append(
                "5M aún no está alcista"
            )

        if estructura15["regimen"] not in [
            "ALCISTA",
            "TRANSICION"
        ]:
            motivos.append(
                "15M no acompaña"
            )

        if not continuacion5[
            "continuacion_compra"
        ]:
            motivos.append(
                "falta continuación"
            )

        if rsi < RSI_CONFIRMACION_COMPRA:
            motivos.append(
                "RSI aún no confirma"
            )

        if adx < ADX_MINIMO:
            motivos.append(
                "ADX insuficiente"
            )

        if not motivos:
            motivos.append(
                "esperando nueva vela"
            )

        return {
            "tipo": "ESPERANDO",
            "id": p["id"],
            "mensaje": (
                "⏳ XAU SNIPER AI V4.2\n\n"
                "⚠️ PREALERTA ACTIVA\n\n"
                f"🆔 ID: {p['id']}\n"
                "🟢 Dirección: COMPRA\n\n"
                "🔍 Todavía NO confirmada.\n\n"
                "Falta:\n"
                + "\n".join(
                    f"• {m}"
                    for m in motivos
                )
            )
        }

    # ========================================================
    # VENTA
    # ========================================================

    invalidada = (
        estructura5["regimen"] == "ALCISTA"
        or
        precio > (
            p["precio"]
            + p["atr"] * 0.80
        )
    )

    if invalidada:

        return descartar_prealerta(
            "La estructura bajista "
            "se perdió o el precio "
            "invalidó la prealerta."
        )

    confirmada = (
        estructura5["regimen"] == "BAJISTA"
        and
        estructura15["regimen"]
        in ["BAJISTA", "TRANSICION"]
        and
        continuacion5[
            "continuacion_venta"
        ]
        and
        rsi <= RSI_CONFIRMACION_VENTA
        and
        adx >= ADX_MINIMO
        and
        precio <= p["precio"]
    )

    if confirmada:
        return True

    motivos = []

    if estructura5["regimen"] != "BAJISTA":
        motivos.append(
            "5M aún no está bajista"
        )

    if estructura15["regimen"] not in [
        "BAJISTA",
        "TRANSICION"
    ]:
        motivos.append(
            "15M no acompaña"
        )

    if not continuacion5[
        "continuacion_venta"
    ]:
        motivos.append(
            "falta continuación"
        )

    if rsi > RSI_CONFIRMACION_VENTA:
        motivos.append(
            "RSI aún no confirma"
        )

    if adx < ADX_MINIMO:
        motivos.append(
            "ADX insuficiente"
        )

    if not motivos:
        motivos.append(
            "esperando nueva vela"
        )

    return {
        "tipo": "ESPERANDO",
        "id": p["id"],
        "mensaje": (
            "⏳ XAU SNIPER AI V4.2\n\n"
            "⚠️ PREALERTA ACTIVA\n\n"
            f"🆔 ID: {p['id']}\n"
            "🔴 Dirección: VENTA\n\n"
            "🔍 Todavía NO confirmada.\n\n"
            "Falta:\n"
            + "\n".join(
                f"• {m}"
                for m in motivos
            )
        )
    }


# ============================================================
# FIN PARTE 7/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 8/9
# MENSAJES + DIAGNÓSTICO
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

    if direccion == "COMPRA":
        emoji = "🟢"
    else:
        emoji = "🔴"

    return (
        f"{emoji} XAU SNIPER AI V4.2\n\n"
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
        "🧠 Estructura + movimiento "
        "detectados.\n"
        "🔄 Esperando continuación.\n\n"
        "⚠️ AÚN NO CONFIRMADA"
    )


# ============================================================
# CONFIRMACIÓN
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

    if direccion == "COMPRA":
        emoji = "🟢"
    else:
        emoji = "🔴"

    return (
        f"{emoji} XAU SNIPER AI V4.2\n\n"
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
    continuacion5,
    score_compra,
    score_venta
):

    return (
        "📋 DIAGNÓSTICO XAU SNIPER\n\n"
        f"5M: {estructura5['regimen']}\n"
        f"15M: {estructura15['regimen']}\n"
        f"Estructura 5M: "
        f"{estructura5['estructura']}\n\n"
        f"RSI: "
        f"{numero_fmt(momentum5['rsi'])}\n"
        f"ADX: "
        f"{numero_fmt(momentum5['adx'])}\n"
        f"DI+: "
        f"{numero_fmt(momentum5['di_plus'])}\n"
        f"DI-: "
        f"{numero_fmt(momentum5['di_minus'])}\n\n"
        f"🎯 Score COMPRA: "
        f"{score_compra}/100\n"
        f"🎯 Score VENTA: "
        f"{score_venta}/100\n\n"
        f"🔄 Pullback compra: "
        f"{pullback5['pullback_compra']}\n"
        f"🔄 Pullback venta: "
        f"{pullback5['pullback_venta']}\n\n"
        f"💥 Impulso compra: "
        f"{pullback5['impulso_previo_compra']}\n"
        f"💥 Impulso venta: "
        f"{pullback5['impulso_previo_venta']}\n\n"
        f"🚀 Continuación compra: "
        f"{continuacion5['continuacion_compra']}\n"
        f"🚀 Continuación venta: "
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
            "❌ XAU SNIPER AI V4.2\n\n"
            "⚠️ Error de datos / motor\n\n"
            f"{mensaje}\n\n"
            "📡 Proveedor: BiQuote\n"
            "🛑 El bot continúa ejecutándose."
        )
    }


# ============================================================
# FIN PARTE 8/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 9/9
# MOTOR PRINCIPAL
# ============================================================


def analizar():

    global estado_prealerta
    global ultima_confirmacion_id
    global ultima_confirmacion_timestamp
    global ultima_vela_5m
    global ultima_vela_15m

    try:

        print(
            "==================================="
        )

        print(
            "🔍 ANALIZANDO XAU/USD..."
        )

        print(
            "==================================="
        )

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
            f"✅ BiQuote 5M: {len(df5)} velas"
        )

        print(
            f"✅ BiQuote 15M: {len(df15)} velas"
        )

        vela5 = str(
            df5["openTime"].iloc[-1]
        )

        vela15 = str(
            df15["openTime"].iloc[-1]
        )

        print(
            f"🕐 Última vela 5M: {vela5}"
        )

        print(
            f"🕐 Última vela 15M: {vela15}"
        )

        # ----------------------------------------------------
        # Protección contra datos atrasados
        # ----------------------------------------------------

        validar_datos_recientes(
            df5,
            df15
        )

        # ----------------------------------------------------
        # Detectar si llegaron velas nuevas
        # ----------------------------------------------------

        vela_nueva_5m = (
            ultima_vela_5m != vela5
        )

        vela_nueva_15m = (
            ultima_vela_15m != vela15
        )

        if (
            not vela_nueva_5m
            and not vela_nueva_15m
        ):

            print(
                "ℹ️ No hay velas nuevas "
                "desde el análisis anterior."
            )

        else:

            print(
                "🆕 Hay datos nuevos."
            )

        ultima_vela_5m = vela5
        ultima_vela_15m = vela15

        # ----------------------------------------------------
        # Indicadores
        # ----------------------------------------------------

        df5 = agregar_indicadores(df5)
        df15 = agregar_indicadores(df15)

        # ----------------------------------------------------
        # Pivots
        # ----------------------------------------------------

        df5 = detectar_pivots(df5)
        df15 = detectar_pivots(df15)

        # ----------------------------------------------------
        # Estructura
        # ----------------------------------------------------

        estructura5 = evaluar_estructura(
            df5
        )

        estructura15 = evaluar_estructura(
            df15
        )

        # ----------------------------------------------------
        # Momentum
        # ----------------------------------------------------

        momentum5 = evaluar_momentum(
            df5
        )

        # ----------------------------------------------------
        # Pullback
        # ----------------------------------------------------

        pullback5 = detectar_pullback(
            df5,
            estructura5,
            momentum5
        )

        # ----------------------------------------------------
        # Continuación
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

        print(
            f"💥 Impulso compra: "
            f"{pullback5['impulso_previo_compra']}"
        )

        print(
            f"💥 Impulso venta: "
            f"{pullback5['impulso_previo_venta']}"
        )

        print(
            f"🚀 Continuación compra: "
            f"{continuacion5['continuacion_compra']}"
        )

        print(
            f"🚀 Continuación venta: "
            f"{continuacion5['continuacion_venta']}"
        )

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
        # PREALERTA EXISTENTE
        # ====================================================

        if estado_prealerta is not None:

            print(
                "⚠️ PREALERTA ACTIVA: "
                f"{estado_prealerta['id']}"
            )

            resultado = confirmar_prealerta(
                estructura5,
                estructura15,
                momentum5,
                continuacion5
            )

            if isinstance(
                resultado,
                dict
            ):

                return resultado

            if resultado is True:

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

        # ====================================================
        # COOLDOWN
        # ====================================================

        if cooldown_activo():

            print(
                "🧊 Cooldown activo."
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": "🧊 Cooldown activo."
            }

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
            and
            score_compra >= 50
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
            and
            score_venta >= 50
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
            continuacion5,
            score_compra,
            score_venta
        )

        print(
            diagnostico
        )

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": "😴 SIN_SEÑAL"
        }

    # ========================================================
    # ERRORES CONTROLADOS
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
# FIN PARTE 9/9
# FIN XAU SNIPER AI V4.2
# ============================================================
