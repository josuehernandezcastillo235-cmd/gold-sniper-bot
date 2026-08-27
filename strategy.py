import requests
import pandas as pd
import numpy as np
import time
import uuid
from datetime import datetime, timezone

from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator


# ============================================================
# XAU SNIPER AI V4.3
# MOTOR:
# ESTRUCTURA + MOVIMIENTO + MOMENTUM + LIQUIDEZ
#
# PROVEEDOR:
# BiQuote
#
# MODO:
# PAPER / ESCÁNER
#
# FLUJO:
#
# ESTRUCTURA
#     ↓
# IMPULSO
#     ↓
# PULLBACK
#     ↓
# PREALERTA
#     ↓
# CONTINUACIÓN
#     ↓
# CONFIRMACIÓN
#
# CAMBIOS V4.3:
#
# 1. CONTROL DE FRESCURA DE DATOS
# 2. DETECCIÓN DE PROVEEDOR CONGELADO
# 3. DETECCIÓN DE REAPERTURA DE SESIÓN
# 4. RETRIES DE BiQuote
# 5. NO ANALIZAR VELAS OBSOLETAS
# 6. MEJOR DETECCIÓN IMPULSO/PULLBACK
# 7. MANTENER PREALERTAS Y CONFIRMACIONES
# 8. MANTENER SCORE / ATR / RR / IDS
# ============================================================


# ============================================================
# CONFIGURACIÓN BiQuote
# ============================================================

BIQUOTE_BASE = "https://biquote.io/api"

SYMBOL = "XAUUSD"

INTERVALO_5M = "5m"
INTERVALO_15M = "15m"

BARRAS_5M = 300
BARRAS_15M = 200


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

TIMEOUT = 12

# Número máximo de intentos contra BiQuote
BIQUOTE_REINTENTOS = 3

# Espera entre intentos
BIQUOTE_ESPERA_REINTENTO = 2


# ============================================================
# FRESCURA DE DATOS
#
# Si la última vela cerrada tiene demasiada antigüedad,
# NO debemos interpretar el mercado como si estuviera vivo.
#
# 5M:
# Una vela normalmente debería aparecer cada 5 minutos.
#
# Permitimos cierto margen por retrasos normales de API.
# ============================================================

MAX_ANTIGUEDAD_5M_MIN = 12

MAX_ANTIGUEDAD_15M_MIN = 25


# ============================================================
# SESIÓN
#
# El oro suele tener una pausa diaria.
#
# No queremos confundir:
#
# cierre diario
#     ↓
# hueco
#     ↓
# reapertura
#
# con:
#
# caída/impulso normal del mercado.
# ============================================================

DETECTAR_SALTO_SESION = True

MAX_SALTO_NORMAL_5M_MIN = 10
MAX_SALTO_NORMAL_15M_MIN = 25


# ============================================================
# INDICADORES
# ============================================================

ADX_MINIMO = 15

RSI_COMPRA = 52
RSI_VENTA = 48

RSI_CONFIRMACION_COMPRA = 54
RSI_CONFIRMACION_VENTA = 46


# ============================================================
# SL / TP
# ============================================================

ATR_SL = 1.30
ATR_TP = 2.20

RR_MINIMO = 1.50


# ============================================================
# PREALERTA
# ============================================================

MINUTOS_PREALERTA = 15

MINUTOS_REPETICION = 15


# ============================================================
# PULLBACK
# ============================================================

PULLBACK_MIN_ATR = 0.20
PULLBACK_MAX_ATR = 1.80


# ============================================================
# IMPULSO
# ============================================================

IMPULSO_CUERPO_ATR = 0.40
IMPULSO_RANGO_ATR = 0.70


# ============================================================
# CONTINUACIÓN
# ============================================================

CONTINUACION_RANGO_ATR = 0.45


# ============================================================
# ESTADO GLOBAL
# ============================================================

estado_prealerta = None

ultima_alerta_id = None
ultima_alerta_timestamp = 0

ultima_confirmacion_id = None
ultima_confirmacion_timestamp = 0


# ============================================================
# CONTROL DE VELAS
# ============================================================

ultima_vela_5m = None
ultima_vela_15m = None


# ============================================================
# CONTROL DE SESIÓN
# ============================================================

ultima_vela_real_5m = None
ultima_vela_real_15m = None

mercado_reabierto = False

ultimo_estado_datos = None


# ============================================================
# SESIÓN HTTP
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "XAU-Sniper-AI/4.3"
})


# ============================================================
# UTILIDADES
# ============================================================

def ahora_ms():

    return int(
        time.time() * 1000
    )


def ahora_utc():

    return datetime.now(
        timezone.utc
    )


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


def timestamp_utc():

    return ahora_utc().strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


# ============================================================
# CONVERTIR FECHA A UTC
# ============================================================

def convertir_utc(valor):

    try:

        fecha = pd.to_datetime(
            valor,
            utc=True,
            errors="coerce"
        )

        if pd.isna(fecha):

            return None

        return fecha

    except Exception:

        return None


# ============================================================
# ANTIGÜEDAD DE UNA VELA
# ============================================================

def antiguedad_minutos(fecha):

    fecha = convertir_utc(fecha)

    if fecha is None:

        return float("inf")

    ahora = pd.Timestamp.now(
        tz="UTC"
    )

    diferencia = (
        ahora - fecha
    ).total_seconds() / 60

    return max(
        0,
        diferencia
    )


# ============================================================
# FRESCURA 5M
# ============================================================

def datos_5m_frescos(df):

    if df is None or df.empty:

        return False

    ultima = df[
        "openTime"
    ].iloc[-1]

    edad = antiguedad_minutos(
        ultima
    )

    return (
        edad <=
        MAX_ANTIGUEDAD_5M_MIN
    )


# ============================================================
# FRESCURA 15M
# ============================================================

def datos_15m_frescos(df):

    if df is None or df.empty:

        return False

    ultima = df[
        "openTime"
    ].iloc[-1]

    edad = antiguedad_minutos(
        ultima
    )

    return (
        edad <=
        MAX_ANTIGUEDAD_15M_MIN
    )


# ============================================================
# DESCRIPCIÓN DEL ESTADO DE DATOS
# ============================================================

def diagnosticar_frescura(
    df5,
    df15
):

    if df5 is None or df5.empty:

        return {
            "ok": False,
            "motivo": "Sin datos 5M"
        }

    if df15 is None or df15.empty:

        return {
            "ok": False,
            "motivo": "Sin datos 15M"
        }

    ultima5 = df5[
        "openTime"
    ].iloc[-1]

    ultima15 = df15[
        "openTime"
    ].iloc[-1]

    edad5 = antiguedad_minutos(
        ultima5
    )

    edad15 = antiguedad_minutos(
        ultima15
    )

    fresco5 = (
        edad5 <=
        MAX_ANTIGUEDAD_5M_MIN
    )

    fresco15 = (
        edad15 <=
        MAX_ANTIGUEDAD_15M_MIN
    )

    return {
        "ok": (
            fresco5
            and fresco15
        ),
        "fresco5": fresco5,
        "fresco15": fresco15,
        "edad5": edad5,
        "edad15": edad15,
        "ultima5": ultima5,
        "ultima15": ultima15
    }


# ============================================================
# DETECTAR SALTO DE SESIÓN
# ============================================================

def detectar_salto_sesion(
    df,
    intervalo_minutos
):

    if df is None or len(df) < 2:

        return False

    t1 = convertir_utc(
        df["openTime"].iloc[-2]
    )

    t2 = convertir_utc(
        df["openTime"].iloc[-1]
    )

    if t1 is None or t2 is None:

        return False

    diferencia = (
        t2 - t1
    ).total_seconds() / 60

    return (
        diferencia >
        intervalo_minutos * 2
    )


# ============================================================
# ESTADO DE SESIÓN
# ============================================================

def evaluar_sesion(
    df5,
    df15
):

    salto5 = detectar_salto_sesion(
        df5,
        5
    )

    salto15 = detectar_salto_sesion(
        df15,
        15
    )

    return {
        "salto_5m": salto5,
        "salto_15m": salto15,
        "reapertura_detectada":
            salto5 or salto15
    }


# ============================================================
# FIN PARTE 1
# ============================================================


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

    ultimo_error = None

    for intento in range(
        1,
        BIQUOTE_REINTENTOS + 1
    ):

        try:

            respuesta = SESSION.get(
                url,
                params=params,
                timeout=TIMEOUT
            )

            respuesta.raise_for_status()

            data = respuesta.json()

            if not isinstance(data, dict):

                raise RuntimeError(
                    "Respuesta BiQuote inesperada"
                )

            barras = data.get("bars")

            if not barras:

                raise RuntimeError(
                    f"BiQuote sin barras para "
                    f"{intervalo}"
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
                c
                for c in columnas
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

            # ------------------------------------------------
            # NO USAR VELA ACTUALMENTE ABIERTA
            # ------------------------------------------------

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

        except (
            requests.RequestException,
            ValueError,
            RuntimeError
        ) as e:

            ultimo_error = e

            print(
                f"⚠️ BiQuote intento "
                f"{intento}/"
                f"{BIQUOTE_REINTENTOS}: "
                f"{e}"
            )

            if intento < BIQUOTE_REINTENTOS:

                time.sleep(
                    BIQUOTE_ESPERA_REINTENTO
                )

    raise RuntimeError(
        f"BiQuote falló después de "
        f"{BIQUOTE_REINTENTOS} intentos: "
        f"{ultimo_error}"
    )


# ============================================================
# VALIDAR DATOS
# ============================================================

def validar_datos_mercado(
    df5,
    df15
):

    estado = diagnosticar_frescura(
        df5,
        df15
    )

    if not estado["ok"]:

        motivo = (
            "Datos posiblemente congelados.\n"
            f"5M: {estado.get('edad5', 0):.1f} min "
            f"de antigüedad.\n"
            f"15M: {estado.get('edad15', 0):.1f} min "
            f"de antigüedad."
        )

        return False, motivo

    return True, estado


# ============================================================
# DETECTAR DATOS REPETIDOS
# ============================================================

def detectar_velas_repetidas(
    df5,
    df15
):

    global ultima_vela_5m
    global ultima_vela_15m

    vela5 = str(
        df5["openTime"].iloc[-1]
    )

    vela15 = str(
        df15["openTime"].iloc[-1]
    )

    repetida5 = (
        ultima_vela_5m == vela5
    )

    repetida15 = (
        ultima_vela_15m == vela15
    )

    return {
        "repetida5": repetida5,
        "repetida15": repetida15,
        "ambas_repetidas":
            repetida5 and repetida15,
        "vela5": vela5,
        "vela15": vela15
    }


# ============================================================
# ACTUALIZAR CONTROL DE VELAS
# ============================================================

def actualizar_control_velas(
    df5,
    df15
):

    global ultima_vela_5m
    global ultima_vela_15m

    ultima_vela_5m = str(
        df5["openTime"].iloc[-1]
    )

    ultima_vela_15m = str(
        df15["openTime"].iloc[-1]
    )


# ============================================================
# FIN PARTE 2
# ============================================================


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

    # --------------------------------------------------------
    # VELOCIDAD DEL PRECIO
    # --------------------------------------------------------

    df["cuerpo"] = (
        df["close"] -
        df["open"]
    ).abs()

    df["rango"] = (
        df["high"] -
        df["low"]
    )

    df["direccion"] = np.where(
        df["close"] > df["open"],
        1,
        np.where(
            df["close"] < df["open"],
            -1,
            0
        )
    )

    # --------------------------------------------------------
    # FUERZA RELATIVA DE LA VELA
    # --------------------------------------------------------

    df["cuerpo_atr"] = np.where(
        df["atr"] > 0,
        df["cuerpo"] / df["atr"],
        0
    )

    df["rango_atr"] = np.where(
        df["atr"] > 0,
        df["rango"] / df["atr"],
        0
    )

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
    h3 = highs[-3]

    l1 = lows[-1]
    l2 = lows[-2]
    l3 = lows[-3]

    hh = h1 > h2
    hl = l1 > l2

    lh = h1 < h2
    ll = l1 < l2

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # BOS
    # --------------------------------------------------------

    bos_alcista = (
        cierre > h2
        and h2 >= h3
    )

    bos_bajista = (
        cierre < l2
        and l2 <= l3
    )

    # --------------------------------------------------------
    # CHoCH
    # --------------------------------------------------------

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
        "swing_high": h1,
        "swing_low": l1,
        "hh": hh,
        "hl": hl,
        "lh": lh,
        "ll": ll
    }


# ============================================================
# FIN PARTE 3
# ============================================================


# ============================================================
# MOMENTUM
# ============================================================

def evaluar_momentum(df):

    ult = df.iloc[-1]

    cierre = float(
        ult["close"]
    )

    apertura = float(
        ult["open"]
    )

    high = float(
        ult["high"]
    )

    low = float(
        ult["low"]
    )

    atr = float(
        ult["atr"]
    )

    rsi = float(
        ult["rsi"]
    )

    adx = float(
        ult["adx"]
    )

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
        and cuerpo >=
        atr * IMPULSO_CUERPO_ATR
        and rango >=
        atr * IMPULSO_RANGO_ATR
    )

    impulso_bajista = (
        vela_bajista
        and atr > 0
        and cuerpo >=
        atr * IMPULSO_CUERPO_ATR
        and rango >=
        atr * IMPULSO_RANGO_ATR
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
        "impulso_alcista":
            impulso_alcista,
        "impulso_bajista":
            impulso_bajista,
        "momentum_alcista":
            momentum_alcista,
        "momentum_bajista":
            momentum_bajista
    }


# ============================================================
# IMPULSO RECIENTE
# ============================================================

def detectar_impulso_reciente(
    df,
    direccion
):

    recientes = df.tail(6).copy()

    if len(recientes) < 3:

        return False

    if direccion == "COMPRA":

        condiciones = (
            (recientes["close"] >
             recientes["open"])
            &
            (recientes["cuerpo"] >=
             recientes["atr"] * 0.40)
            &
            (recientes["rango"] >=
             recientes["atr"] * 0.70)
        )

    else:

        condiciones = (
            (recientes["close"] <
             recientes["open"])
            &
            (recientes["cuerpo"] >=
             recientes["atr"] * 0.40)
            &
            (recientes["rango"] >=
             recientes["atr"] * 0.70)
        )

    return bool(
        condiciones.any()
    )


# ============================================================
# PULLBACK REAL
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

    impulso_previo_compra = (
        detectar_impulso_reciente(
            df,
            "COMPRA"
        )
    )

    impulso_previo_venta = (
        detectar_impulso_reciente(
            df,
            "VENTA"
        )
    )

    highs, lows = ultimos_pivots(
        df
    )

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

    # --------------------------------------------------------
    # COMPRA
    # --------------------------------------------------------

    retroceso_compra = (
        estructura["regimen"]
        == "ALCISTA"

        and

        impulso_previo_compra

        and

        distancia_low >=
        atr * PULLBACK_MIN_ATR

        and

        distancia_low <=
        atr * PULLBACK_MAX_ATR

        and

        precio >= swing_low
    )

    # --------------------------------------------------------
    # VENTA
    # --------------------------------------------------------

    retroceso_venta = (
        estructura["regimen"]
        == "BAJISTA"

        and

        impulso_previo_venta

        and

        distancia_high >=
        atr * PULLBACK_MIN_ATR

        and

        distancia_high <=
        atr * PULLBACK_MAX_ATR

        and

        precio <= swing_high
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
# FIN PARTE 4
# ============================================================


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

    rango = high - low

    continuacion_compra = (
        close > prev_high
        and close > open_
        and rango >=
        atr * CONTINUACION_RANGO_ATR
    )

    continuacion_venta = (
        close < prev_low
        and close < open_
        and rango >=
        atr * CONTINUACION_RANGO_ATR
    )

    return {
        "continuacion_compra":
            continuacion_compra,

        "continuacion_venta":
            continuacion_venta
    }


# ============================================================
# LIQUIDEZ / EXTREMOS
# ============================================================

def evaluar_liquidez(df):

    if len(df) < 10:

        return {
            "liquidez_alta": None,
            "liquidez_baja": None,
            "distancia_alta": None,
            "distancia_baja": None
        }

    ultimas = df.tail(20)

    liquidez_alta = float(
        ultimas["high"].max()
    )

    liquidez_baja = float(
        ultimas["low"].min()
    )

    precio = float(
        df["close"].iloc[-1]
    )

    return {
        "liquidez_alta":
            liquidez_alta,

        "liquidez_baja":
            liquidez_baja,

        "distancia_alta":
            abs(
                liquidez_alta - precio
            ),

        "distancia_baja":
            abs(
                precio - liquidez_baja
            )
    }


# ============================================================
# SCORE COMPRA
# ============================================================

def calcular_score_compra(
    estructura,
    momentum,
    pullback,
    continuacion,
    liquidez=None
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

    if continuacion[
        "continuacion_compra"
    ]:

        score += 15
        razones.append(
            "continuación confirmada"
        )

    return min(
        score,
        100
    ), razones


# ============================================================
# SCORE VENTA
# ============================================================

def calcular_score_venta(
    estructura,
    momentum,
    pullback,
    continuacion,
    liquidez=None
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

    if continuacion[
        "continuacion_venta"
    ]:

        score += 15
        razones.append(
            "continuación confirmada"
        )

    return min(
        score,
        100
    ), razones


# ============================================================
# FIN PARTE 5
# ============================================================


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
        <
        MINUTOS_REPETICION * 60
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

    ultima_alerta_timestamp = (
        time.time()
    )

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
        -
        estado_prealerta["timestamp"]
    )

    if edad > (
        MINUTOS_PREALERTA * 60
    ):

        return False

    return True


# ============================================================
# EXPIRACIÓN
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

    return {
        "tipo": "DESCARTADA",
        "id": anterior["id"],
        "mensaje": (
            "🟠 XAU SNIPER AI V4.3\n\n"
            "⏰ PREALERTA EXPIRADA\n\n"
            f"📌 Dirección: "
            f"{anterior['direccion']}\n"
            f"🆔 ID: "
            f"{anterior['id']}\n"
            f"📊 Score inicial: "
            f"{anterior['score']}/100\n\n"
            "🧠 Motivo:\n"
            "No apareció la continuación "
            "necesaria dentro del tiempo "
            "establecido.\n\n"
            "❌ Setup cerrado."
        )
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

    return {
        "tipo": "DESCARTADA",
        "id": anterior["id"],
        "mensaje": (
            "🟠 XAU SNIPER AI V4.3\n\n"
            "❌ PREALERTA DESCARTADA\n\n"
            f"📌 Dirección: "
            f"{anterior['direccion']}\n"
            f"🆔 ID: "
            f"{anterior['id']}\n"
            f"📊 Score inicial: "
            f"{anterior['score']}/100\n\n"
            "🧠 Motivo:\n"
            f"{motivo}\n\n"
            "🔍 Setup invalidado."
        )
    }


# ============================================================
# FIN PARTE 6
# ============================================================


# ============================================================
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
        -
        estado_prealerta["timestamp"]
    )

    if edad > (
        MINUTOS_PREALERTA * 60
    ):

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
            estructura5["regimen"]
            == "BAJISTA"
            or
            precio <
            (
                p["precio"]
                -
                p["atr"] * 0.80
            )
        )

        if invalidada:

            return descartar_prealerta(
                "La estructura alcista "
                "se perdió o el precio "
                "invalidó la prealerta."
            )

        confirmada = (
            estructura5["regimen"]
            == "ALCISTA"

            and

            estructura15["regimen"]
            in [
                "ALCISTA",
                "TRANSICION"
            ]

            and

            continuacion5[
                "continuacion_compra"
            ]

            and

            rsi >=
            RSI_CONFIRMACION_COMPRA

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
                "condiciones aún incompletas"
            )

        return {
            "tipo": "ESPERANDO",
            "id": p["id"],
            "mensaje": (
                "⏳ XAU SNIPER AI V4.3\n\n"
                "⚠️ PREALERTA ACTIVA\n\n"
                f"🆔 ID: {p['id']}\n"
                "🟢 Dirección: COMPRA\n\n"
                "🔍 Todavía NO confirmada.\n\n"
                "Falta:\n"
                +
                "\n".join(
                    f"• {m}"
                    for m in motivos
                )
            )
        }

    # ========================================================
    # VENTA
    # ========================================================

    invalidada = (
        estructura5["regimen"]
        == "ALCISTA"
        or
        precio >
        (
            p["precio"]
            +
            p["atr"] * 0.80
        )
    )

    if invalidada:

        return descartar_prealerta(
            "La estructura bajista "
            "se perdió o el precio "
            "invalidó la prealerta."
        )

    confirmada = (
        estructura5["regimen"]
        == "BAJISTA"

        and

        estructura15["regimen"]
        in [
            "BAJISTA",
            "TRANSICION"
        ]

        and

        continuacion5[
            "continuacion_venta"
        ]

        and

        rsi <=
        RSI_CONFIRMACION_VENTA

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
            "condiciones aún incompletas"
        )

    return {
        "tipo": "ESPERANDO",
        "id": p["id"],
        "mensaje": (
            "⏳ XAU SNIPER AI V4.3\n\n"
            "⚠️ PREALERTA ACTIVA\n\n"
            f"🆔 ID: {p['id']}\n"
            "🔴 Dirección: VENTA\n\n"
            "🔍 Todavía NO confirmada.\n\n"
            "Falta:\n"
            +
            "\n".join(
                f"• {m}"
                for m in motivos
            )
        )
    }


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
        f"{emoji} XAU SNIPER AI V4.3\n\n"
        f"⚠️ PREALERTA {direccion}\n\n"
        f"🆔 ID: {identificador}\n"
        f"📊 Score: {score}/100\n"
        f"💰 Precio: "
        f"{precio_fmt(precio)}\n\n"
        f"📈 5M: "
        f"{estructura5['regimen']}\n"
        f"📊 15M: "
        f"{estructura15['regimen']}\n\n"
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
# FIN PARTE 7
# ============================================================


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
        f"{emoji} XAU SNIPER AI V4.3\n\n"
        f"🔥 ALERTA CONFIRMADA: "
        f"{direccion}\n\n"
        f"🆔 ID: {identificador}\n"
        f"📊 Score: {score}/100\n"
        f"💰 Entrada referencia: "
        f"{precio_fmt(precio)}\n\n"
        f"📈 5M: "
        f"{estructura5['regimen']}\n"
        f"📊 15M: "
        f"{estructura15['regimen']}\n\n"
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
    score_venta,
    liquidez=None
):

    mensaje = (
        "📋 DIAGNÓSTICO XAU SNIPER\n\n"

        f"5M: "
        f"{estructura5['regimen']}\n"

        f"15M: "
        f"{estructura15['regimen']}\n\n"

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

    if liquidez is not None:

        mensaje += (
            "\n\n💧 LIQUIDEZ\n"
            f"Alta: "
            f"{precio_fmt("
                liquidez['liquidez_alta']
            )}\n"
            f"Baja: "
            f"{precio_fmt("
                liquidez['liquidez_baja']
            )}"
        )

    return mensaje


# ============================================================
# ERROR
# ============================================================

def construir_error(
    mensaje
):

    return {
        "tipo": "ERROR",
        "mensaje": (
            "❌ XAU SNIPER AI V4.3\n\n"
            "⚠️ Error de datos / motor\n\n"
            f"{mensaje}\n\n"
            "📡 Proveedor: BiQuote\n"
            "🛑 El bot continúa ejecutándose."
        )
    }


# ============================================================
# ESTADO DE DATOS
# ============================================================

def construir_estado_datos(
    df5,
    df15
):

    estado = diagnosticar_frescura(
        df5,
        df15
    )

    if not estado["ok"]:

        return {
            "ok": False,
            "mensaje": (
                "🚨 DATOS NO FRESCOS\n\n"
                f"5M: "
                f"{estado.get('edad5', 0):.1f} min\n"
                f"15M: "
                f"{estado.get('edad15', 0):.1f} min\n\n"
                "⛔ No se generarán señales "
                "con datos atrasados."
            )
        }

    return {
        "ok": True,
        "mensaje": (
            "✅ DATOS FRESCOS\n"
            f"5M: "
            f"{estado['edad5']:.1f} min\n"
            f"15M: "
            f"{estado['edad15']:.1f} min"
        )
    }


# ============================================================
# FIN PARTE 8
# ============================================================


# ============================================================
# ANALIZAR
# ============================================================

def analizar():

    global estado_prealerta
    global ultima_confirmacion_id
    global ultima_confirmacion_timestamp
    global ultima_vela_5m
    global ultima_vela_15m
    global ultima_vela_real_5m
    global ultima_vela_real_15m
    global mercado_reabierto
    global ultimo_estado_datos

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

        # ====================================================
        # DESCARGA
        # ====================================================

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

        # ====================================================
        # ÚLTIMAS VELAS
        # ====================================================

        vela5 = str(
            df5["openTime"].iloc[-1]
        )

        vela15 = str(
            df15["openTime"].iloc[-1]
        )

        print(
            f"🕐 Última vela 5M: "
            f"{vela5}"
        )

        print(
            f"🕐 Última vela 15M: "
            f"{vela15}"
        )

        # ====================================================
        # FRESCURA
        # ====================================================

        estado_datos = construir_estado_datos(
            df5,
            df15
        )

        print(
            estado_datos["mensaje"]
        )

        # ----------------------------------------------------
        # SI BIQUOTE ESTÁ ATRASADO
        # ----------------------------------------------------

        if not estado_datos["ok"]:

            ultimo_estado_datos = (
                "ATRASADO"
            )

            # Si había una prealerta, no dejamos
            # que sobreviva artificialmente durante
            # una interrupción de datos.

            if estado_prealerta is not None:

                return descartar_prealerta(
                    "BiQuote está devolviendo "
                    "datos atrasados. "
                    "La prealerta queda "
                    "invalidada hasta recibir "
                    "datos frescos."
                )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "🚨 DATOS ATRASADOS\n\n"
                    "BiQuote no está entregando "
                    "velas suficientemente "
                    "recientes.\n\n"
                    "⛔ No se genera señal."
                )
            }

        ultimo_estado_datos = (
            "FRESCO"
        )

        # ====================================================
        # REPETICIÓN DE VELAS
        # ====================================================

        repetidas = detectar_velas_repetidas(
            df5,
            df15
        )

        if repetidas["ambas_repetidas"]:

            print(
                "ℹ️ Las últimas velas son "
                "las mismas del análisis "
                "anterior."
            )

            print(
                "🟢 Datos siguen siendo frescos."
            )

        elif (
            repetidas["repetida5"]
            or
            repetidas["repetida15"]
        ):

            print(
                "ℹ️ Una temporalidad "
                "todavía no tiene vela nueva."
            )

        else:

            print(
                "🆕 Hay nuevas velas "
                "cerradas."
            )

        # ====================================================
        # DETECTAR REAPERTURA
        # ====================================================

        sesion = evaluar_sesion(
            df5,
            df15
        )

        if sesion[
            "reapertura_detectada"
        ]:

            mercado_reabierto = True

            print(
                "🔓 POSIBLE REAPERTURA "
                "DE SESIÓN DETECTADA"
            )

            print(
                "🧹 Reiniciando referencia "
                "de velas."
            )

            ultima_vela_real_5m = None
            ultima_vela_real_15m = None

        else:

            mercado_reabierto = False

        # ====================================================
        # ACTUALIZAR CONTROL
        # ====================================================

        actualizar_control_velas(
            df5,
            df15
        )

        ultima_vela_real_5m = vela5
        ultima_vela_real_15m = vela15

        # ====================================================
        # INDICADORES
        # ====================================================

        df5 = agregar_indicadores(
            df5
        )

        df15 = agregar_indicadores(
            df15
        )

        # ====================================================
        # PIVOTS
        # ====================================================

        df5 = detectar_pivots(
            df5
        )

        df15 = detectar_pivots(
            df15
        )

        # ====================================================
        # ESTRUCTURA
        # ====================================================

        estructura5 = evaluar_estructura(
            df5
        )

        estructura15 = evaluar_estructura(
            df15
        )

        # ====================================================
        # MOMENTUM
        # ====================================================

        momentum5 = evaluar_momentum(
            df5
        )

        # ====================================================
        # PULLBACK
        # ====================================================

        pullback5 = detectar_pullback(
            df5,
            estructura5,
            momentum5
        )

        # ====================================================
        # CONTINUACIÓN
        # ====================================================

        continuacion5 = detectar_continuacion(
            df5,
            momentum5
        )

        # ====================================================
        # LIQUIDEZ
        # ====================================================

        liquidez5 = evaluar_liquidez(
            df5
        )

        # ====================================================
        # LOG
        # ====================================================

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
            f"DI+: "
            f"{momentum5['di_plus']:.2f}"
        )

        print(
            f"DI-: "
            f"{momentum5['di_minus']:.2f}"
        )

        print(
            f"💥 Impulso compra: "
            f"{momentum5['impulso_alcista']}"
        )

        print(
            f"💥 Impulso venta: "
            f"{momentum5['impulso_bajista']}"
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
                continuacion5,
                liquidez5
            )
        )

        score_venta, razones_venta = (
            calcular_score_venta(
                estructura5,
                momentum5,
                pullback5,
                continuacion5,
                liquidez5
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

            resultado_confirmacion = (
                confirmar_prealerta(
                    estructura5,
                    estructura15,
                    momentum5,
                    continuacion5
                )
            )

            if isinstance(
                resultado_confirmacion,
                dict
            ):

                return resultado_confirmacion

            if resultado_confirmacion is True:

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
                            continuacion5,
                            liquidez5
                        )
                    )

                else:

                    score, _ = (
                        calcular_score_venta(
                            estructura5,
                            momentum5,
                            pullback5,
                            continuacion5,
                            liquidez5
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
                "mensaje": (
                    "🧊 Cooldown activo."
                )
            }

        # ====================================================
        # SETUPS
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

            pullback5[
                "pullback_compra"
            ]
        )

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

            pullback5[
                "pullback_venta"
            ]
        )

        # ====================================================
        # EVITAR CONFLICTO DE DIRECCIONES
        # ====================================================

        if (
            setup_compra
            and setup_venta
        ):

            print(
                "⚠️ Setup ambiguo: "
                "compra y venta simultáneas."
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "😴 SIN_SEÑAL\n\n"
                    "⚠️ Estructura ambigua."
                )
            }

        # ====================================================
        # PREALERTA COMPRA
        # ====================================================

        if (
            setup_compra
            and
            score_compra >= 50
        ):

            direccion = "COMPRA"

            precio = momentum5[
                "precio"
            ]

            atr = momentum5[
                "atr"
            ]

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

            identificador = (
                guardar_prealerta(
                    direccion,
                    precio,
                    atr,
                    score_compra,
                    estructura5,
                    momentum5
                )
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

            precio = momentum5[
                "precio"
            ]

            atr = momentum5[
                "atr"
            ]

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

            identificador = (
                guardar_prealerta(
                    direccion,
                    precio,
                    atr,
                    score_venta,
                    estructura5,
                    momentum5
                )
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
        # DIAGNÓSTICO
        # ====================================================

        diagnostico = construir_diagnostico(
            estructura5,
            estructura15,
            momentum5,
            pullback5,
            continuacion5,
            score_compra,
            score_venta,
            liquidez5
        )

        print(
            diagnostico
        )

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
# FIN XAU SNIPER AI V4.3
# ============================================================
