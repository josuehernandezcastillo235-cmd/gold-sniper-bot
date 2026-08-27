# ============================================================
# XAU SNIPER AI V4.2
# MOTOR DE ESTRUCTURA + MOMENTUM + LIQUIDEZ
# TWELVE DATA
# ============================================================

import os
import time
import uuid
from datetime import datetime, timezone

import requests
import pandas as pd
import numpy as np

from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange


# ============================================================
# CONFIGURACIÓN
# ============================================================

API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"

INTERVALO_5M = "5min"
INTERVALO_15M = "15min"

URL_TWELVE_DATA = "https://api.twelvedata.com/time_series"

TIMEOUT = 15

VELAS_5M = 300
VELAS_15M = 200

# ------------------------------------------------------------
# FRESCURA MÁXIMA
# ------------------------------------------------------------

MAX_EDAD_5M = 12 * 60
MAX_EDAD_15M = 20 * 60

# Si una API devuelve una vela más de 90 segundos
# hacia el futuro respecto al servidor, los datos son inválidos.
MAX_FUTURO = 90

# ------------------------------------------------------------
# ESTRUCTURA
# ------------------------------------------------------------

PIVOT_LEFT = 2
PIVOT_RIGHT = 2

SWING_LOOKBACK = 30

# ------------------------------------------------------------
# MOMENTUM
# ------------------------------------------------------------

ADX_MINIMO = 15

RSI_COMPRA = 52
RSI_VENTA = 48

RSI_CONFIRMACION_COMPRA = 55
RSI_CONFIRMACION_VENTA = 45

# ------------------------------------------------------------
# RIESGO
# ------------------------------------------------------------

ATR_SL = 1.30
ATR_TP = 2.20

RR_MINIMO = 1.50

# ------------------------------------------------------------
# SCORE
# ------------------------------------------------------------

SCORE_PREALERTA = 65
SCORE_CONFIRMACION = 75

# ------------------------------------------------------------
# ESTADO INTERNO
# ------------------------------------------------------------

ultima_vela_5m = None
ultima_vela_15m = None

prealerta_activa = None

confirmaciones_enviadas = set()

ultimo_error_datos = None

# Evita que el motor haga señales sobre exactamente
# el mismo cierre de 5M.
ultimo_cierre_analizado = None


# ============================================================
# UTILIDADES
# ============================================================

def ahora_utc():

    return datetime.now(timezone.utc)


def numero(valor, default=np.nan):

    try:
        return float(valor)

    except Exception:

        return default


def fmt(valor, decimales=2):

    try:

        if pd.isna(valor):
            return "N/D"

        return f"{float(valor):.{decimales}f}"

    except Exception:

        return "N/D"


def intervalo_minutos(intervalo):

    if intervalo == "5min":
        return 5

    if intervalo == "15min":
        return 15

    return 5


# ============================================================
# VALIDACIÓN API KEY
# ============================================================

def validar_api_key():

    if not API_KEY:

        raise RuntimeError(
            "❌ Falta API_KEY de Twelve Data en Railway."
        )


# ============================================================
# DESCARGA TWELVE DATA
# ============================================================

def descargar_serie(intervalo, outputsize):

    validar_api_key()

    params = {
        "symbol": SYMBOL,
        "interval": intervalo,
        "outputsize": outputsize,
        "apikey": API_KEY,
        "format": "JSON",
        "timezone": "UTC"
    }

    respuesta = requests.get(
        URL_TWELVE_DATA,
        params=params,
        timeout=TIMEOUT
    )

    respuesta.raise_for_status()

    data = respuesta.json()

    if not isinstance(data, dict):

        raise RuntimeError(
            "Respuesta inválida de Twelve Data."
        )

    if data.get("status") == "error":

        mensaje = data.get(
            "message",
            "Error desconocido de Twelve Data."
        )

        raise RuntimeError(
            f"Twelve Data: {mensaje}"
        )

    values = data.get("values")

    if not values:

        raise RuntimeError(
            "Twelve Data no devolvió velas."
        )

    return values


# ============================================================
# NORMALIZAR VELAS
# ============================================================

def normalizar_velas(values):

    df = pd.DataFrame(values)

    columnas = [
        "datetime",
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
            f"Faltan columnas: {faltantes}"
        )

    df = df[columnas].copy()

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        utc=True,
        errors="coerce"
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

    df = df.dropna()

    df = df.drop_duplicates(
        subset=["datetime"]
    )

    df = df.sort_values(
        "datetime"
    )

    df = df.reset_index(
        drop=True
    )

    return df


# ============================================================
# VALIDACIÓN TEMPORAL
# ============================================================

def validar_timestamps(
    df,
    intervalo,
    max_edad
):

    if df.empty:

        raise RuntimeError(
            f"No hay datos {intervalo}."
        )

    ahora = ahora_utc()

    ultima = df["datetime"].iloc[-1]

    if pd.isna(ultima):

        raise RuntimeError(
            f"Timestamp inválido {intervalo}."
        )

    edad_segundos = (
        ahora - ultima.to_pydatetime()
    ).total_seconds()

    print(
        f"🕐 Última vela {intervalo}: "
        f"{ultima}"
    )

    print(
        f"🕐 Edad vela {intervalo}: "
        f"{edad_segundos / 60:.1f} minutos"
    )

    # --------------------------------------------------------
    # DATOS FUTUROS
    # --------------------------------------------------------

    if edad_segundos < -MAX_FUTURO:

        raise RuntimeError(
            f"Datos {intervalo} futuros: "
            f"{abs(edad_segundos) / 60:.1f} minutos."
        )

    # --------------------------------------------------------
    # DATOS DEMASIADO ATRASADOS
    # --------------------------------------------------------

    if edad_segundos > max_edad:

        raise RuntimeError(
            f"Datos {intervalo} atrasados: "
            f"{edad_segundos / 60:.1f} minutos."
        )

    return edad_segundos


# ============================================================
# ELIMINAR VELA ABIERTA
# ============================================================

def obtener_velas_cerradas(df, intervalo):

    if df.empty:

        return df

    minutos = intervalo_minutos(
        intervalo
    )

    ahora = pd.Timestamp(
        ahora_utc()
    )

    inicio_vela_actual = ahora.floor(
        f"{minutos}min"
    )

    # Solo velas cuyo inicio sea anterior
    # al inicio de la vela actual.
    cerradas = df[
        df["datetime"] < inicio_vela_actual
    ].copy()

    cerradas = cerradas.sort_values(
        "datetime"
    )

    cerradas = cerradas.reset_index(
        drop=True
    )

    return cerradas


# ============================================================
# CARGAR MERCADO
# ============================================================

def cargar_datos():

    print(
        "📡 Descargando datos desde Twelve Data..."
    )

    valores_5m = descargar_serie(
        INTERVALO_5M,
        VELAS_5M
    )

    valores_15m = descargar_serie(
        INTERVALO_15M,
        VELAS_15M
    )

    df5 = normalizar_velas(
        valores_5m
    )

    df15 = normalizar_velas(
        valores_15m
    )

    print(
        f"✅ Twelve Data 5M: "
        f"{len(df5)} velas"
    )

    print(
        f"✅ Twelve Data 15M: "
        f"{len(df15)} velas"
    )

    # --------------------------------------------------------
    # VALIDAR ANTES DE TOCAR LOS DATOS
    # --------------------------------------------------------

    validar_timestamps(
        df5,
        INTERVALO_5M,
        MAX_EDAD_5M
    )

    validar_timestamps(
        df15,
        INTERVALO_15M,
        MAX_EDAD_15M
    )

    # --------------------------------------------------------
    # SOLO VELAS CERRADAS
    # --------------------------------------------------------

    df5 = obtener_velas_cerradas(
        df5,
        INTERVALO_5M
    )

    df15 = obtener_velas_cerradas(
        df15,
        INTERVALO_15M
    )

    if len(df5) < 80:

        raise RuntimeError(
            "Muy pocas velas cerradas 5M."
        )

    if len(df15) < 80:

        raise RuntimeError(
            "Muy pocas velas cerradas 15M."
        )

    return df5, df15


# ============================================================
# DATOS NUEVOS
# ============================================================

def hay_datos_nuevos(df5):

    global ultimo_cierre_analizado

    cierre_actual = df5[
        "datetime"
    ].iloc[-1]

    if (
        ultimo_cierre_analizado is not None
        and cierre_actual <= ultimo_cierre_analizado
    ):

        print(
            "ℹ️ No hay cierre 5M nuevo "
            "desde el análisis anterior."
        )

        return False

    ultimo_cierre_analizado = cierre_actual

    print(
        "🆕 Hay cierre 5M nuevo."
    )

    return True


# ============================================================
# INDICADORES
# ============================================================

def agregar_indicadores(df):

    df = df.copy()

    close = df["close"]
    high = df["high"]
    low = df["low"]

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = RSIIndicator(
        close=close,
        window=14
    )

    df["rsi"] = rsi.rsi()

    # --------------------------------------------------------
    # ADX
    # --------------------------------------------------------

    adx = ADXIndicator(
        high=high,
        low=low,
        close=close,
        window=14
    )

    df["adx"] = adx.adx()
    df["di_plus"] = adx.adx_pos()
    df["di_minus"] = adx.adx_neg()

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    atr = AverageTrueRange(
        high=high,
        low=low,
        close=close,
        window=14
    )

    df["atr"] = atr.average_true_range()

    # --------------------------------------------------------
    # CARACTERÍSTICAS DE VELA
    # --------------------------------------------------------

    df["range"] = (
        df["high"] -
        df["low"]
    )

    df["body"] = (
        df["close"] -
        df["open"]
    )

    df["body_abs"] = (
        df["body"].abs()
    )

    df["body_ratio"] = np.where(
        df["range"] > 0,
        df["body_abs"] /
        df["range"],
        0
    )

    # --------------------------------------------------------
    # DIRECCIÓN DE CIERRE
    # --------------------------------------------------------

    df["bull_candle"] = (
        df["close"] >
        df["open"]
    )

    df["bear_candle"] = (
        df["close"] <
        df["open"]
    )

    return df


# ============================================================
# PIVOTES
# ============================================================

def detectar_pivotes(df):

    high = df["high"].values
    low = df["low"].values

    pivots_high = []
    pivots_low = []

    left = PIVOT_LEFT
    right = PIVOT_RIGHT

    for i in range(
        left,
        len(df) - right
    ):

        ventana_high = high[
            i-left:i+right+1
        ]

        ventana_low = low[
            i-left:i+right+1
        ]

        if high[i] == np.max(
            ventana_high
        ):

            pivots_high.append({
                "index": i,
                "price": high[i]
            })

        if low[i] == np.min(
            ventana_low
        ):

            pivots_low.append({
                "index": i,
                "price": low[i]
            })

    return pivots_high, pivots_low


# ============================================================
# ESTRUCTURA
# ============================================================

def analizar_estructura(df):

    highs, lows = detectar_pivotes(
        df
    )

    if len(highs) < 2 or len(lows) < 2:

        return {
            "estado": "INSUFICIENTE",
            "highs": highs,
            "lows": lows,
            "bullish": False,
            "bearish": False
        }

    h1 = highs[-1]["price"]
    h2 = highs[-2]["price"]

    l1 = lows[-1]["price"]
    l2 = lows[-2]["price"]

    hh = h1 > h2
    lh = h1 < h2

    hl = l1 > l2
    ll = l1 < l2

    # --------------------------------------------------------
    # ESTRUCTURA CLARA
    # --------------------------------------------------------

    if hh and hl:

        estado = "HH + HL"

        bullish = True
        bearish = False

    elif lh and ll:

        estado = "LH + LL"

        bullish = False
        bearish = True

    else:

        estado = "MIXTA"

        bullish = False
        bearish = False

    return {
        "estado": estado,
        "highs": highs,
        "lows": lows,
        "bullish": bullish,
        "bearish": bearish,
        "hh": hh,
        "lh": lh,
        "hl": hl,
        "ll": ll
    }


# ============================================================
# BOS
# ============================================================

def detectar_bos(df, estructura):

    if len(df) < 5:

        return {
            "bullish": False,
            "bearish": False
        }

    cierre = df["close"].iloc[-1]

    highs = estructura.get(
        "highs",
        []
    )

    lows = estructura.get(
        "lows",
        []
    )

    bos_bullish = False
    bos_bearish = False

    if highs:

        ultimo_high = highs[-1]["price"]

        bos_bullish = (
            cierre > ultimo_high
        )

    if lows:

        ultimo_low = lows[-1]["price"]

        bos_bearish = (
            cierre < ultimo_low
        )

    return {
        "bullish": bos_bullish,
        "bearish": bos_bearish
        }


# ============================================================
# FUERZA DE IMPULSO
# ============================================================

def calcular_impulso(df):

    if len(df) < 12:

        return {
            "compra": False,
            "venta": False,
            "conflicto": True,
            "direccion": "NINGUNA",
            "fuerza_compra": 0,
            "fuerza_venta": 0
        }

    d = df.iloc[-8:].copy()

    atr = df["atr"].iloc[-1]

    if pd.isna(atr) or atr <= 0:

        return {
            "compra": False,
            "venta": False,
            "conflicto": True,
            "direccion": "NINGUNA",
            "fuerza_compra": 0,
            "fuerza_venta": 0
        }

    # --------------------------------------------------------
    # MOVIMIENTO NETO
    # --------------------------------------------------------

    movimiento = (
        d["close"].iloc[-1] -
        d["open"].iloc[0]
    )

    # --------------------------------------------------------
    # CUERPOS
    # --------------------------------------------------------

    cuerpos_alcistas = int(
        d["bull_candle"].sum()
    )

    cuerpos_bajistas = int(
        d["bear_candle"].sum()
    )

    # --------------------------------------------------------
    # TAMAÑO MEDIO
    # --------------------------------------------------------

    cuerpo_medio = (
        d["body_abs"].mean()
    )

    rango_medio = (
        d["range"].mean()
    )

    if rango_medio <= 0:

        rango_medio = 1

    ratio_cuerpo = (
        cuerpo_medio /
        rango_medio
    )

    # --------------------------------------------------------
    # VELOCIDAD
    # --------------------------------------------------------

    velocidad_alcista = (
        max(movimiento, 0) /
        atr
    )

    velocidad_bajista = (
        max(-movimiento, 0) /
        atr
    )

    # --------------------------------------------------------
    # FUERZA COMPRA
    # --------------------------------------------------------

    fuerza_compra = 0

    if movimiento > 0:

        fuerza_compra += 35

    if velocidad_alcista >= 0.60:

        fuerza_compra += 20

    if cuerpos_alcistas >= 5:

        fuerza_compra += 20

    if ratio_cuerpo >= 0.45:

        fuerza_compra += 15

    if d["range"].iloc[-1] >= rango_medio * 1.15:

        fuerza_compra += 10

    # --------------------------------------------------------
    # FUERZA VENTA
    # --------------------------------------------------------

    fuerza_venta = 0

    if movimiento < 0:

        fuerza_venta += 35

    if velocidad_bajista >= 0.60:

        fuerza_venta += 20

    if cuerpos_bajistas >= 5:

        fuerza_venta += 20

    if ratio_cuerpo >= 0.45:

        fuerza_venta += 15

    if d["range"].iloc[-1] >= rango_medio * 1.15:

        fuerza_venta += 10

    # --------------------------------------------------------
    # NORMALIZAR
    # --------------------------------------------------------

    fuerza_compra = min(
        fuerza_compra,
        100
    )

    fuerza_venta = min(
        fuerza_venta,
        100
    )

    # --------------------------------------------------------
    # REGLA IMPORTANTE
    #
    # COMPRA Y VENTA NUNCA PUEDEN SER TRUE A LA VEZ.
    # --------------------------------------------------------

    diferencia = abs(
        fuerza_compra -
        fuerza_venta
    )

    compra = False
    venta = False
    conflicto = False
    direccion = "NINGUNA"

    if (
        fuerza_compra >= 55
        and fuerza_compra >
        fuerza_venta + 10
    ):

        compra = True
        direccion = "COMPRA"

    elif (
        fuerza_venta >= 55
        and fuerza_venta >
        fuerza_compra + 10
    ):

        venta = True
        direccion = "VENTA"

    elif (
        fuerza_compra >= 55
        and fuerza_venta >= 55
    ):

        conflicto = True
        direccion = "CONFLICTO"

    return {
        "compra": compra,
        "venta": venta,
        "conflicto": conflicto,
        "direccion": direccion,
        "fuerza_compra": fuerza_compra,
        "fuerza_venta": fuerza_venta,
        "diferencia": diferencia
    }


# ============================================================
# MOMENTUM
# ============================================================

def analizar_momentum(df):

    rsi = df["rsi"].iloc[-1]
    adx = df["adx"].iloc[-1]

    di_plus = df["di_plus"].iloc[-1]
    di_minus = df["di_minus"].iloc[-1]

    compra = (
        rsi >= RSI_COMPRA
        and di_plus > di_minus
        and adx >= ADX_MINIMO
    )

    venta = (
        rsi <= RSI_VENTA
        and di_minus > di_plus
        and adx >= ADX_MINIMO
    )

    return {
        "rsi": rsi,
        "adx": adx,
        "di_plus": di_plus,
        "di_minus": di_minus,
        "compra": compra,
        "venta": venta
    }


# ============================================================
# PULLBACK
# ============================================================

def detectar_pullback(df, direccion):

    if len(df) < 12:

        return False

    atr = df["atr"].iloc[-1]

    if pd.isna(atr) or atr <= 0:

        return False

    recientes = df.iloc[-8:]

    cierre = df["close"].iloc[-1]

    maximo = recientes["high"].max()
    minimo = recientes["low"].min()

    # --------------------------------------------------------
    # COMPRA
    # --------------------------------------------------------

    if direccion == "COMPRA":

        impulso_prev = (
            df["close"].iloc[-6]
            <
            df["close"].iloc[-3]
        )

        retroceso = (
            maximo - cierre
        )

        retroceso_valido = (
            retroceso >= atr * 0.15
            and retroceso <= atr * 1.20
        )

        vela_actual_alcista = (
            df["close"].iloc[-1]
            >=
            df["open"].iloc[-1]
        )

        return (
            impulso_prev
            and retroceso_valido
            and vela_actual_alcista
        )

    # --------------------------------------------------------
    # VENTA
    # --------------------------------------------------------

    if direccion == "VENTA":

        impulso_prev = (
            df["close"].iloc[-6]
            >
            df["close"].iloc[-3]
        )

        retroceso = (
            cierre - minimo
        )

        retroceso_valido = (
            retroceso >= atr * 0.15
            and retroceso <= atr * 1.20
        )

        vela_actual_bajista = (
            df["close"].iloc[-1]
            <=
            df["open"].iloc[-1]
        )

        return (
            impulso_prev
            and retroceso_valido
            and vela_actual_bajista
        )

    return False


# ============================================================
# CONTINUACIÓN
# ============================================================

def detectar_continuacion(
    df,
    direccion,
    estructura
):

    if len(df) < 10:

        return False

    atr = df["atr"].iloc[-1]

    if pd.isna(atr) or atr <= 0:

        return False

    cierre = df["close"].iloc[-1]

    vela = df.iloc[-1]

    # --------------------------------------------------------
    # NIVELES DE REFERENCIA
    # --------------------------------------------------------

    highs = estructura.get(
        "highs",
        []
    )

    lows = estructura.get(
        "lows",
        []
    )

    if direccion == "COMPRA":

        if not highs:
            return False

        nivel = highs[-1]["price"]

        ruptura = (
            cierre > nivel
        )

        cuerpo_fuerte = (
            vela["body_abs"] >=
            atr * 0.25
        )

        vela_alcista = (
            vela["close"] >
            vela["open"]
        )

        return (
            ruptura
            and cuerpo_fuerte
            and vela_alcista
        )

    if direccion == "VENTA":

        if not lows:
            return False

        nivel = lows[-1]["price"]

        ruptura = (
            cierre < nivel
        )

        cuerpo_fuerte = (
            vela["body_abs"] >=
            atr * 0.25
        )

        vela_bajista = (
            vela["close"] <
            vela["open"]
        )

        return (
            ruptura
            and cuerpo_fuerte
            and vela_bajista
        )

    return False


# ============================================================
# REGIMEN 5M + 15M
# ============================================================

def obtener_regimen(
    estructura_5m,
    estructura_15m
):

    bull5 = estructura_5m["bullish"]
    bear5 = estructura_5m["bearish"]

    bull15 = estructura_15m["bullish"]
    bear15 = estructura_15m["bearish"]

    if bull5 and bull15:

        return "ALCISTA"

    if bear5 and bear15:

        return "BAJISTA"

    if (
        bull5
        and bear15
    ) or (
        bear5
        and bull15
    ):

        return "CONTRADICTORIO"

    return "LATERAL"


# ============================================================
# COMPATIBILIDAD DE DIRECCIÓN
# ============================================================

def direccion_compatible(
    direccion,
    regimen
):

    if direccion == "COMPRA":

        return regimen == "ALCISTA"

    if direccion == "VENTA":

        return regimen == "BAJISTA"

    return False


# ============================================================
# SCORE
# ============================================================

def calcular_score(
    direccion,
    estructura_5m,
    estructura_15m,
    impulso,
    momentum,
    pullback,
    continuacion,
    bos
):

    score = 0

    estructura5 = estructura_5m["estado"]
    estructura15 = estructura_15m["estado"]

    # --------------------------------------------------------
    # ESTRUCTURA 5M
    # --------------------------------------------------------

    if direccion == "COMPRA":

        if estructura5 == "HH + HL":
            score += 25

        if estructura15 == "HH + HL":
            score += 20

        if impulso["compra"]:
            score += 20

        if momentum["compra"]:
            score += 10

        if pullback:
            score += 10

        if continuacion:
            score += 15

        if bos["bullish"]:
            score += 10

    elif direccion == "VENTA":

        if estructura5 == "LH + LL":
            score += 25

        if estructura15 == "LH + LL":
            score += 20

        if impulso["venta"]:
            score += 20

        if momentum["venta"]:
            score += 10

        if pullback:
            score += 10

        if continuacion:
            score += 15

        if bos["bearish"]:
            score += 10

    return min(
        score,
        100
    )


# ============================================================
# SCORE CONTRARIO
# ============================================================

def calcular_scores(
    estructura_5m,
    estructura_15m,
    impulso,
    momentum
):

    score_compra = 0
    score_venta = 0

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    if estructura_5m["estado"] == "HH + HL":
        score_compra += 25

    if estructura_15m["estado"] == "HH + HL":
        score_compra += 20

    if estructura_5m["estado"] == "LH + LL":
        score_venta += 25

    if estructura_15m["estado"] == "LH + LL":
        score_venta += 20

    # --------------------------------------------------------
    # IMPULSO
    # --------------------------------------------------------

    if impulso["compra"]:
        score_compra += 20

    if impulso["venta"]:
        score_venta += 20

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    if momentum["compra"]:
        score_compra += 10

    if momentum["venta"]:
        score_venta += 10

    return (
        min(score_compra, 100),
        min(score_venta, 100)
    )


# ============================================================
# SL / TP
# ============================================================

def calcular_riesgo(
    precio,
    atr,
    direccion
):

    if pd.isna(atr) or atr <= 0:

        return None

    if direccion == "COMPRA":

        sl = (
            precio -
            atr * ATR_SL
        )

        tp = (
            precio +
            atr * ATR_TP
        )

    elif direccion == "VENTA":

        sl = (
            precio +
            atr * ATR_SL
        )

        tp = (
            precio -
            atr * ATR_TP
        )

    else:

        return None

    riesgo = abs(
        precio - sl
    )

    beneficio = abs(
        tp - precio
    )

    if riesgo <= 0:

        return None

    rr = (
        beneficio /
        riesgo
    )

    return {
        "sl": sl,
        "tp": tp,
        "riesgo": riesgo,
        "beneficio": beneficio,
        "rr": rr
    }


# ============================================================
# VALIDAR RR
# ============================================================

def riesgo_valido(riesgo):

    if not riesgo:

        return False

    return (
        riesgo["rr"] >= RR_MINIMO
    )


# ============================================================
# ID DE SEÑAL
# ============================================================

def generar_id(
    direccion,
    precio
):

    numero_id = int(
        time.time()
    )

    corto = uuid.uuid4().hex[:4]

    return (
        f"{direccion}-"
        f"{numero_id}-"
        f"{precio:.2f}-"
        f"{corto}"
    )


# ============================================================
# ESTADO DE PREALERTA
# ============================================================

def crear_prealerta(
    direccion,
    precio,
    score,
    riesgo
):

    global prealerta_activa

    identificador = generar_id(
        direccion,
        precio
    )

    prealerta_activa = {
        "id": identificador,
        "direccion": direccion,
        "precio": precio,
        "score": score,
        "sl": riesgo["sl"],
        "tp": riesgo["tp"],
        "rr": riesgo["rr"],
        "creada": ahora_utc()
    }

    return prealerta_activa


# ============================================================
# DESCARTAR PREALERTA
# ============================================================

def descartar_prealerta(
    motivo
):

    global prealerta_activa

    if prealerta_activa is None:

        return None

    p = prealerta_activa

    mensaje = (
        "❌ XAU SNIPER AI V4.2\n\n"
        "❌ SEÑAL DESCARTADA\n\n"
        f"🆔 ID: {p['id']}\n"
        f"📊 Dirección: {p['direccion']}\n"
        f"💰 Precio referencia: "
        f"{fmt(p['precio'])}\n\n"
        f"📌 Motivo:\n{motivo}"
    )

    prealerta_activa = None

    return {
        "tipo": "DESCARTADA",
        "id": p["id"],
        "mensaje": mensaje
    }


# ============================================================
# ERROR DE DATOS
# ============================================================

def resultado_error_datos(
    mensaje
):

    return {
        "tipo": "ERROR",
        "id": None,
        "mensaje": (
            "❌ XAU SNIPER AI V4.2\n\n"
            "⚠️ Error de datos / motor\n\n"
            f"{mensaje}\n\n"
            "📡 Proveedor: Twelve Data\n"
            "🛑 El bot continúa ejecutándose."
        )
    }


# ============================================================
# PREALERTA
# ============================================================

def construir_prealerta(
    p,
    estructura_5m,
    estructura_15m,
    momentum
):

    direccion = p["direccion"]

    texto = (
        "🟢 XAU SNIPER AI V4.2\n\n"
        f"⚠️ PREALERTA "
        f"{direccion}\n\n"
        f"🆔 ID: {p['id']}\n"
        f"📊 Score: {p['score']}/100\n"
        f"💰 Precio: {fmt(p['precio'])}\n\n"
        f"📈 5M: "
        f"{estructura_5m['estado']}\n"
        f"📊 15M: "
        f"{estructura_15m['estado']}\n\n"
        f"RSI 5M: "
        f"{fmt(momentum['rsi'])}\n"
        f"ADX 5M: "
        f"{fmt(momentum['adx'])}\n"
        f"DI+: "
        f"{fmt(momentum['di_plus'])}\n"
        f"DI-: "
        f"{fmt(momentum['di_minus'])}\n\n"
        f"🛑 SL referencia: "
        f"{fmt(p['sl'])}\n"
        f"🎯 TP referencia: "
        f"{fmt(p['tp'])}\n"
        f"📐 RR: 1:{fmt(p['rr'])}\n\n"
        "🧠 Estructura + movimiento "
        "detectados.\n"
        "🔄 Esperando continuación.\n"
        "⚠️ AÚN NO CONFIRMADA"
    )

    return texto


# ============================================================
# ESPERANDO
# ============================================================

def construir_esperando(
    p,
    faltantes
):

    texto = (
        "⏳ XAU SNIPER AI V4.2\n\n"
        f"• Dirección: "
        f"{p['direccion']}\n"
        f"• ID: {p['id']}\n"
        f"• Score actual: "
        f"{p['score']}/100\n\n"
        "⚠️ PREALERTA ACTIVA\n"
        "Esperando confirmación.\n\n"
    )

    for falta in faltantes:

        texto += (
            f"• {falta}\n"
        )

    return texto


# ============================================================
# CONFIRMACIÓN
# ============================================================

def construir_confirmada(
    p,
    estructura_5m,
    estructura_15m,
    momentum,
    continuacion
):

    direccion = p["direccion"]

    emoji = (
        "🟢"
        if direccion == "COMPRA"
        else "🔴"
    )

    texto = (
        "🚨 XAU SNIPER AI V4.2\n\n"
        f"{emoji} "
        f"SEÑAL CONFIRMADA "
        f"{direccion}\n\n"
        f"🆔 ID: {p['id']}\n"
        f"📊 Score: "
        f"{p['score']}/100\n"
        f"💰 Entrada referencia: "
        f"{fmt(p['precio'])}\n\n"
        f"📈 5M: "
        f"{estructura_5m['estado']}\n"
        f"📊 15M: "
        f"{estructura_15m['estado']}\n\n"
        f"RSI: "
        f"{fmt(momentum['rsi'])}\n"
        f"ADX: "
        f"{fmt(momentum['adx'])}\n"
        f"DI+: "
        f"{fmt(momentum['di_plus'])}\n"
        f"DI-: "
        f"{fmt(momentum['di_minus'])}\n\n"
        f"🛑 SL: "
        f"{fmt(p['sl'])}\n"
        f"🎯 TP: "
        f"{fmt(p['tp'])}\n"
        f"📐 RR: 1:{fmt(p['rr'])}\n\n"
        f"🚀 Continuación: "
        f"{'CONFIRMADA' if continuacion else 'NO'}\n"
        "🧠 Estructura + momentum "
        "alineados.\n\n"
        "⚠️ PAPER / ESCÁNER"
    )

    return texto


# ============================================================
# DIAGNÓSTICO
# ============================================================

def construir_diagnostico(
    estructura_5m,
    estructura_15m,
    momentum,
    impulso,
    pullback_compra,
    pullback_venta,
    continuacion_compra,
    continuacion_venta,
    score_compra,
    score_venta
):

    return (
        "📋 DIAGNÓSTICO XAU SNIPER\n"
        f"5M: {estructura_5m['estado']}\n"
        f"15M: {estructura_15m['estado']}\n"
        f"RSI: {fmt(momentum['rsi'])}\n"
        f"ADX: {fmt(momentum['adx'])}\n"
        f"DI+: {fmt(momentum['di_plus'])}\n"
        f"DI-: {fmt(momentum['di_minus'])}\n\n"
        f"💥 Impulso COMPRA: "
        f"{impulso['compra']}\n"
        f"💥 Impulso VENTA: "
        f"{impulso['venta']}\n"
        f"⚖️ Conflicto impulso: "
        f"{impulso['conflicto']}\n"
        f"🧭 Dirección impulso: "
        f"{impulso['direccion']}\n"
        f"💪 Fuerza compra: "
        f"{impulso['fuerza_compra']}\n"
        f"💪 Fuerza venta: "
        f"{impulso['fuerza_venta']}\n\n"
        f"🔄 Pullback compra: "
        f"{pullback_compra}\n"
        f"🔄 Pullback venta: "
        f"{pullback_venta}\n"
        f"🚀 Continuación compra: "
        f"{continuacion_compra}\n"
        f"🚀 Continuación venta: "
        f"{continuacion_venta}\n\n"
        f"🎯 Score COMPRA: "
        f"{score_compra}/100\n"
        f"🎯 Score VENTA: "
        f"{score_venta}/100"
    )


# ============================================================
# INVALIDAR PREALERTA
# ============================================================

def revisar_prealerta(
    estructura_5m,
    estructura_15m,
    impulso,
    momentum,
    continuacion_compra,
    continuacion_venta
):

    global prealerta_activa

    if prealerta_activa is None:

        return None

    direccion = (
        prealerta_activa["direccion"]
    )

    # --------------------------------------------------------
    # CONFLICTO
    # --------------------------------------------------------

    if impulso["conflicto"]:

        return descartar_prealerta(
            "El impulso perdió dirección clara."
        )

    # --------------------------------------------------------
    # COMPRA
    # --------------------------------------------------------

    if direccion == "COMPRA":

        if (
            estructura_5m["bearish"]
            and estructura_15m["bearish"]
        ):

            return descartar_prealerta(
                "La estructura pasó a bajista."
            )

        if (
            momentum["rsi"] < 48
        ):

            return descartar_prealerta(
                "El momentum dejó de favorecer la compra."
            )

    # --------------------------------------------------------
    # VENTA
    # --------------------------------------------------------

    if direccion == "VENTA":

        if (
            estructura_5m["bullish"]
            and estructura_15m["bullish"]
        ):

            return descartar_prealerta(
                "La estructura pasó a alcista."
            )

        if (
            momentum["rsi"] > 52
        ):

            return descartar_prealerta(
                "El momentum dejó de favorecer la venta."
            )

    return None


# ============================================================
# CONFIRMACIÓN REAL
# ============================================================

def puede_confirmar(
    p,
    estructura_5m,
    estructura_15m,
    momentum,
    continuacion
):

    direccion = p["direccion"]

    if p["score"] < SCORE_PREALERTA:

        return False

    if continuacion is not True:

        return False

    if direccion == "COMPRA":

        if not (
            estructura_5m["bullish"]
            and estructura_15m["bullish"]
        ):

            return False

        if momentum["rsi"] < RSI_CONFIRMACION_COMPRA:

            return False

        if momentum["di_plus"] <= momentum["di_minus"]:

            return False

    elif direccion == "VENTA":

        if not (
            estructura_5m["bearish"]
            and estructura_15m["bearish"]
        ):

            return False

        if momentum["rsi"] > RSI_CONFIRMACION_VENTA:

            return False

        if momentum["di_minus"] <= momentum["di_plus"]:

            return False

    else:

        return False

    return True


# ============================================================
# ANALIZAR
# ============================================================

def analizar():

    global prealerta_activa
    global ultima_vela_5m
    global ultima_vela_15m

    try:

        print("")
        print(
            "==================================="
        )
        print(
            "🔍 ANALIZANDO XAU/USD..."
        )
        print(
            "==================================="
        )

        # ----------------------------------------------------
        # DATOS
        # ----------------------------------------------------

        df5, df15 = cargar_datos()

        ultima_5 = (
            df5["datetime"].iloc[-1]
        )

        ultima_15 = (
            df15["datetime"].iloc[-1]
        )

        ultima_vela_5m = ultima_5
        ultima_vela_15m = ultima_15

        # ----------------------------------------------------
        # NUEVO CIERRE
        # ----------------------------------------------------

        if not hay_datos_nuevos(df5):

            return {
                "tipo": "SIN_SEÑAL",
                "id": None,
                "mensaje": (
                    "😴 SIN_SEÑAL\n"
                    "No existe nuevo cierre 5M."
                )
            }

        # ----------------------------------------------------
        # INDICADORES
        # ----------------------------------------------------

        df5 = agregar_indicadores(
            df5
        )

        df15 = agregar_indicadores(
            df15
        )

        # ----------------------------------------------------
        # ESTRUCTURA
        # ----------------------------------------------------

        estructura_5m = analizar_estructura(
            df5
        )

        estructura_15m = analizar_estructura(
            df15
        )

        regimen = obtener_regimen(
            estructura_5m,
            estructura_15m
        )

        print(
            f"📊 5M: "
            f"{estructura_5m['estado']}"
        )

        print(
            f"📊 15M: "
            f"{estructura_15m['estado']}"
        )

        print(
            f"🌐 Régimen: {regimen}"
        )

        # ----------------------------------------------------
        # MOMENTUM
        # ----------------------------------------------------

        momentum = analizar_momentum(
            df5
        )

        print(
            f"💰 Precio: "
            f"{fmt(df5['close'].iloc[-1])}"
        )

        print(
            f"RSI: "
            f"{fmt(momentum['rsi'])}"
        )

        print(
            f"ADX: "
            f"{fmt(momentum['adx'])}"
        )

        # ----------------------------------------------------
        # IMPULSO
        # ----------------------------------------------------

        impulso = calcular_impulso(
            df5
        )

        print(
            f"💥 Impulso compra: "
            f"{impulso['compra']}"
        )

        print(
            f"💥 Impulso venta: "
            f"{impulso['venta']}"
        )

        print(
            f"⚖️ Conflicto: "
            f"{impulso['conflicto']}"
        )

        print(
            f"🧭 Dirección: "
            f"{impulso['direccion']}"
        )

        # ----------------------------------------------------
        # BOS
        # ----------------------------------------------------

        bos = detectar_bos(
            df5,
            estructura_5m
        )

        # ----------------------------------------------------
        # PULLBACK
        # ----------------------------------------------------

        pullback_compra = detectar_pullback(
            df5,
            "COMPRA"
        )

        pullback_venta = detectar_pullback(
            df5,
            "VENTA"
        )

        # ----------------------------------------------------
        # CONTINUACIÓN
        # ----------------------------------------------------

        continuacion_compra = detectar_continuacion(
            df5,
            "COMPRA",
            estructura_5m
        )

        continuacion_venta = detectar_continuacion(
            df5,
            "VENTA",
            estructura_5m
        )

        print(
            f"🔄 Pullback compra: "
            f"{pullback_compra}"
        )

        print(
            f"🔄 Pullback venta: "
            f"{pullback_venta}"
        )

        print(
            f"🚀 Continuación compra: "
            f"{continuacion_compra}"
        )

        print(
            f"🚀 Continuación venta: "
            f"{continuacion_venta}"
        )

        # ----------------------------------------------------
        # SCORE BASE
        # ----------------------------------------------------

        score_compra, score_venta = calcular_scores(
            estructura_5m,
            estructura_15m,
            impulso,
            momentum
        )

        # Añadimos pullback / continuación
        if pullback_compra:
            score_compra += 10

        if continuacion_compra:
            score_compra += 15

        if bos["bullish"]:
            score_compra += 10

        if pullback_venta:
            score_venta += 10

        if continuacion_venta:
            score_venta += 15

        if bos["bearish"]:
            score_venta += 10

        score_compra = min(
            score_compra,
            100
        )

        score_venta = min(
            score_venta,
            100
        )

        print(
            f"🎯 Score COMPRA: "
            f"{score_compra}/100"
        )

        print(
            f"🎯 Score VENTA: "
            f"{score_venta}/100"
        )

        # ----------------------------------------------------
        # DIAGNÓSTICO
        # ----------------------------------------------------

        print(
            construir_diagnostico(
                estructura_5m,
                estructura_15m,
                momentum,
                impulso,
                pullback_compra,
                pullback_venta,
                continuacion_compra,
                continuacion_venta,
                score_compra,
                score_venta
            )
        )

        # ----------------------------------------------------
        # SI HAY CONFLICTO
        # ----------------------------------------------------

        if impulso["conflicto"]:

            if prealerta_activa:

                descartada = descartar_prealerta(
                    "Conflicto entre fuerzas de compra "
                    "y venta. Se cancela la prealerta."
                )

                if descartada:
                    return descartada

            return {
                "tipo": "SIN_SEÑAL",
                "id": None,
                "mensaje": (
                    "⚖️ SIN_SEÑAL\n\n"
                    "El mercado presenta "
                    "conflicto de impulso.\n"
                    "El motor no fuerza dirección."
                )
            }

        # ----------------------------------------------------
        # REVISAR PREALERTA EXISTENTE
        # ----------------------------------------------------

        descarte = revisar_prealerta(
            estructura_5m,
            estructura_15m,
            impulso,
            momentum,
            continuacion_compra,
            continuacion_venta
        )

        if descarte:

            return descarte

        # ----------------------------------------------------
        # SI YA EXISTE PREALERTA
        # ----------------------------------------------------

        if prealerta_activa:

            p = prealerta_activa

            direccion = p["direccion"]

            if direccion == "COMPRA":

                continuacion = (
                    continuacion_compra
                )

                score_actual = (
                    score_compra
                )

            else:

                continuacion = (
                    continuacion_venta
                )

                score_actual = (
                    score_venta
                )

            p["score"] = score_actual

            # ------------------------------------------------
            # CONFIRMACIÓN
            # ------------------------------------------------

            if puede_confirmar(
                p,
                estructura_5m,
                estructura_15m,
                momentum,
                continuacion
            ):

                if p["id"] not in confirmaciones_enviadas:

                    confirmaciones_enviadas.add(
                        p["id"]
                    )

                    mensaje = construir_confirmada(
                        p,
                        estructura_5m,
                        estructura_15m,
                        momentum,
                        continuacion
                    )

                    prealerta_activa = None

                    print(
                        "🚨 SEÑAL CONFIRMADA"
                    )

                    return {
                        "tipo": "CONFIRMADA",
                        "id": p["id"],
                        "mensaje": mensaje
                    }

            # ------------------------------------------------
            # TODAVÍA ESPERANDO
            # ------------------------------------------------

            faltantes = []

            if not continuacion:

                faltantes.append(
                    "falta continuación"
                )

            if direccion == "COMPRA":

                if momentum["rsi"] < RSI_CONFIRMACION_COMPRA:

                    faltantes.append(
                        "RSI aún no confirma"
                    )

                if momentum["di_plus"] <= momentum["di_minus"]:

                    faltantes.append(
                        "DI+ aún no domina"
                    )

            else:

                if momentum["rsi"] > RSI_CONFIRMACION_VENTA:

                    faltantes.append(
                        "RSI aún no confirma"
                    )

                if momentum["di_minus"] <= momentum["di_plus"]:

                    faltantes.append(
                        "DI- aún no domina"
                    )

            if not faltantes:

                faltantes.append(
                    "confirmación estructural"
                )

            print(
                "🔍 Todavía NO confirmada."
            )

            return {
                "tipo": "ESPERANDO",
                "id": p["id"],
                "mensaje": construir_esperando(
                    p,
                    faltantes
                )
            }

        # ----------------------------------------------------
        # NUEVA PREALERTA COMPRA
        # ----------------------------------------------------

        if (
            impulso["compra"]
            and score_compra >= SCORE_PREALERTA
            and estructura_5m["bullish"]
            and estructura_15m["bullish"]
            and regimen == "ALCISTA"
        ):

            riesgo = calcular_riesgo(
                df5["close"].iloc[-1],
                df5["atr"].iloc[-1],
                "COMPRA"
            )

            if riesgo and riesgo_valido(riesgo):

                p = crear_prealerta(
                    "COMPRA",
                    df5["close"].iloc[-1],
                    score_compra,
                    riesgo
                )

                print(
                    "⚠️ NUEVA PREALERTA COMPRA"
                )

                return {
                    "tipo": "PREALERTA",
                    "id": p["id"],
                    "mensaje": construir_prealerta(
                        p,
                        estructura_5m,
                        estructura_15m,
                        momentum
                    )
                }

        # ----------------------------------------------------
        # NUEVA PREALERTA VENTA
        # ----------------------------------------------------

        if (
            impulso["venta"]
            and score_venta >= SCORE_PREALERTA
            and estructura_5m["bearish"]
            and estructura_15m["bearish"]
            and regimen == "BAJISTA"
        ):

            riesgo = calcular_riesgo(
                df5["close"].iloc[-1],
                df5["atr"].iloc[-1],
                "VENTA"
            )

            if riesgo and riesgo_valido(riesgo):

                p = crear_prealerta(
                    "VENTA",
                    df5["close"].iloc[-1],
                    score_venta,
                    riesgo
                )

                print(
                    "⚠️ NUEVA PREALERTA VENTA"
                )

                return {
                    "tipo": "PREALERTA",
                    "id": p["id"],
                    "mensaje": construir_prealerta(
                        p,
                        estructura_5m,
                        estructura_15m,
                        momentum
                    )
                }

        # ----------------------------------------------------
        # SIN SEÑAL
        # ----------------------------------------------------

        print(
            "😴 SIN_SEÑAL"
        )

        return {
            "tipo": "SIN_SEÑAL",
            "id": None,
            "mensaje": "😴 SIN_SEÑAL"
        }

    except Exception as e:

        print(
            f"❌ ERROR STRATEGY: {e}"
        )

        return resultado_error_datos(
            str(e)
    )
