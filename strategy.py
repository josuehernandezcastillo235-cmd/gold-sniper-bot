# ============================================================
# XAU SNIPER AI V4.2
# MOTOR DE ESTRUCTURA + MOMENTUM + LIQUIDEZ
# PARTE 1/9
# ============================================================

import os
import time
import uuid
import logging
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

VELAS_5M = 300
VELAS_15M = 200

TIMEOUT_API = 15

# El bot corre cada 100 segundos desde bot.py.
INTERVALO_ANALISIS = 100

# ------------------------------------------------------------
# VALIDACIÓN TEMPORAL
# ------------------------------------------------------------

# Tolerancia máxima para datos realmente futuros.
# No se utiliza para considerar "vieja" una vela que simplemente
# todavía pertenece al intervalo actual de 15M.
FUTURO_TOLERANCIA_MIN = 2

# Una vela cerrada debe tener una antigüedad razonable.
# Se permite margen porque el proveedor puede tardar unos segundos.
MAX_EDAD_5M = 10
MAX_EDAD_15M = 20


# ============================================================
# ESTRUCTURA
# ============================================================

SWING_LOOKBACK = 3

MIN_BOS_DIST_ATR = 0.12
MIN_STRUCTURE_SCORE = 2


# ============================================================
# MOMENTUM
# ============================================================

RSI_COMPRA = 52
RSI_VENTA = 48

RSI_CONFIRMACION_COMPRA = 55
RSI_CONFIRMACION_VENTA = 45

ADX_MINIMO = 18
ADX_CONFIRMACION = 20


# ============================================================
# ATR / RIESGO
# ============================================================

ATR_SL = 1.30
ATR_TP = 2.20

RR_MINIMO = 1.50


# ============================================================
# SCORE
# ============================================================

SCORE_PREALERTA = 58
SCORE_CONFIRMACION = 72


# ============================================================
# COOLDOWNS
# ============================================================

MINUTOS_REPETICION = 15
MINUTOS_COOLDOWN_CONFIRMADA = 15

ultima_senal_id = None
ultima_direccion = None
ultima_confirmacion_ts = None

ultimo_error_ts = 0
ultimo_timestamp_5m = None
ultimo_timestamp_15m = None


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("xau_sniper_v42")

if not logger.handlers:

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s - "
            "%(levelname)s - "
            "%(message)s"
        )
    )


# ============================================================
# UTILIDADES BÁSICAS
# ============================================================

def ahora_utc():
    """
    Devuelve la hora UTC actual con timezone.
    """
    return datetime.now(timezone.utc)


def numero(valor, default=np.nan):
    """
    Convierte cualquier valor numérico a float de forma segura.
    """
    try:

        if valor is None:
            return default

        if isinstance(valor, str):
            valor = valor.replace(",", "").strip()

        resultado = float(valor)

        if not np.isfinite(resultado):
            return default

        return resultado

    except Exception:
        return default


def redondear_precio(valor):
    """
    Oro normalmente se muestra con 2 decimales en Telegram.
    """
    try:
        return round(float(valor), 2)
    except Exception:
        return 0.0


def fmt(valor, decimales=2):
    """
    Formato numérico seguro para mensajes.
    """
    try:
        return f"{float(valor):.{decimales}f}"
    except Exception:
        return "N/D"


def normalizar_timestamp(valor):
    """
    Convierte timestamps de Twelve Data a UTC.

    Regla importante:
    - Si vienen con timezone, se convierten a UTC.
    - Si vienen sin timezone, se interpretan como UTC porque
      la petición solicita timezone=UTC.
    """

    try:

        ts = pd.Timestamp(valor)

        if ts.tzinfo is None:

            ts = ts.tz_localize("UTC")

        else:

            ts = ts.tz_convert("UTC")

        return ts

    except Exception:

        return pd.NaT


def intervalo_minutos(intervalo):
    """
    Convierte 5min / 15min a minutos.
    """

    if intervalo == "5min":
        return 5

    if intervalo == "15min":
        return 15

    raise ValueError(
        f"Intervalo no soportado: {intervalo}"
    )


# ============================================================
# FIN PARTE 1/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 2/9
# TWELVE DATA + VALIDACIÓN DE VELAS
# ============================================================


# ============================================================
# DESCARGA TWELVE DATA
# ============================================================

def descargar_velas(intervalo, outputsize):

    if not API_KEY:

        raise RuntimeError(
            "❌ Falta API_KEY. "
            "Agrega API_KEY en Railway."
        )

    url = "https://api.twelvedata.com/time_series"

    parametros = {
        "symbol": SYMBOL,
        "interval": intervalo,
        "outputsize": outputsize,
        "apikey": API_KEY,
        "format": "JSON",
        "timezone": "UTC"
    }

    try:

        respuesta = requests.get(
            url,
            params=parametros,
            timeout=TIMEOUT_API
        )

        respuesta.raise_for_status()

        datos = respuesta.json()

    except requests.RequestException as e:

        raise RuntimeError(
            f"Error conectando con Twelve Data: {e}"
        )

    except ValueError as e:

        raise RuntimeError(
            f"Respuesta JSON inválida de Twelve Data: {e}"
        )

    if not isinstance(datos, dict):

        raise RuntimeError(
            "Twelve Data devolvió una respuesta inválida."
        )

    if datos.get("status") == "error":

        mensaje = datos.get(
            "message",
            "Error desconocido"
        )

        raise RuntimeError(
            f"Twelve Data: {mensaje}"
        )

    valores = datos.get("values")

    if not valores:

        raise RuntimeError(
            f"Twelve Data no devolvió velas para {intervalo}."
        )

    filas = []

    for vela in valores:

        if not isinstance(vela, dict):
            continue

        timestamp = (
            vela.get("datetime")
            or vela.get("date")
            or vela.get("time")
        )

        if timestamp is None:
            continue

        filas.append({
            "datetime": timestamp,
            "open": numero(vela.get("open")),
            "high": numero(vela.get("high")),
            "low": numero(vela.get("low")),
            "close": numero(vela.get("close")),
            "volume": numero(
                vela.get("volume"),
                0
            )
        })

    if len(filas) < 50:

        raise RuntimeError(
            f"Datos insuficientes en {intervalo}: "
            f"{len(filas)} velas."
        )

    df = pd.DataFrame(filas)

    df["datetime"] = df["datetime"].apply(
        normalizar_timestamp
    )

    df = df.dropna(
        subset=[
            "datetime",
            "open",
            "high",
            "low",
            "close"
        ]
    )

    df = df.sort_values(
        "datetime"
    )

    df = df.drop_duplicates(
        subset=["datetime"],
        keep="last"
    )

    df = df.reset_index(
        drop=True
    )

    # ========================================================
    # VALIDACIÓN OHLC
    # ========================================================

    df = df[
        (df["high"] >= df["low"]) &
        (df["high"] >= df["open"]) &
        (df["high"] >= df["close"]) &
        (df["low"] <= df["open"]) &
        (df["low"] <= df["close"])
    ]

    df = df[
        (df["open"] > 0) &
        (df["high"] > 0) &
        (df["low"] > 0) &
        (df["close"] > 0)
    ]

    if len(df) < 50:

        raise RuntimeError(
            f"Después de validar OHLC quedan "
            f"muy pocas velas en {intervalo}."
        )

    return df


# ============================================================
# IDENTIFICAR VELA CERRADA
# ============================================================

def obtener_velas_cerradas(df, intervalo):

    if df is None or df.empty:

        raise RuntimeError(
            f"DataFrame vacío en {intervalo}."
        )

    minutos = intervalo_minutos(
        intervalo
    )

    ahora = pd.Timestamp(
        ahora_utc()
    )

    ultimo = df.iloc[-1]["datetime"]

    if pd.isna(ultimo):

        raise RuntimeError(
            f"Timestamp inválido en {intervalo}."
        )

    # --------------------------------------------------------
    # Si la última vela está en el futuro de verdad,
    # NO intentamos "arreglarla" inventando una zona horaria.
    # --------------------------------------------------------

    diferencia_futuro = (
        ultimo - ahora
    ).total_seconds() / 60

    if diferencia_futuro > FUTURO_TOLERANCIA_MIN:

        raise RuntimeError(
            f"Datos {intervalo} futuros: "
            f"{diferencia_futuro:.1f} minutos."
        )

    # --------------------------------------------------------
    # Determinamos el inicio del bloque temporal actual.
    # Una vela cuyo inicio coincide con el bloque actual todavía
    # está abierta.
    # --------------------------------------------------------

    bloque_actual = ahora.floor(
        f"{minutos}min"
    )

    df = df.copy()

    df["datetime"] = df["datetime"].apply(
        normalizar_timestamp
    )

    # --------------------------------------------------------
    # Nos quedamos solamente con velas cuyo inicio sea anterior
    # al bloque actual.
    # --------------------------------------------------------

    cerradas = df[
        df["datetime"] < bloque_actual
    ].copy()

    if cerradas.empty:

        raise RuntimeError(
            f"No existe una vela cerrada válida "
            f"para {intervalo}."
        )

    cerradas = cerradas.sort_values(
        "datetime"
    )

    cerradas = cerradas.reset_index(
        drop=True
    )

    ultima = cerradas.iloc[-1]["datetime"]

    edad = (
        ahora - ultima
    ).total_seconds() / 60

    max_edad = (
        MAX_EDAD_5M
        if intervalo == "5min"
        else MAX_EDAD_15M
    )

    # --------------------------------------------------------
    # La edad se evalúa contra la vela cerrada más reciente.
    # Una 15M puede tener 10-14 minutos de edad y seguir siendo
    # perfectamente válida.
    # --------------------------------------------------------

    if edad < -FUTURO_TOLERANCIA_MIN:

        raise RuntimeError(
            f"Datos {intervalo} inconsistentes: "
            f"timestamp futuro."
        )

    if edad > max_edad:

        raise RuntimeError(
            f"Datos {intervalo} atrasados: "
            f"{edad:.1f} minutos."
        )

    return cerradas, ultima, edad


# ============================================================
# FIN PARTE 2/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 3/9
# INDICADORES + ESTRUCTURA
# ============================================================


# ============================================================
# INDICADORES
# ============================================================

def calcular_indicadores(df):

    df = df.copy()

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    atr = AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    df["atr"] = atr.average_true_range()

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = RSIIndicator(
        close=df["close"],
        window=14
    )

    df["rsi"] = rsi.rsi()

    # --------------------------------------------------------
    # ADX / DI
    # --------------------------------------------------------

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
    # EMA solo como CONTEXTO.
    # La estructura NO depende de ellas.
    # --------------------------------------------------------

    df["ema20"] = (
        df["close"]
        .ewm(span=20, adjust=False)
        .mean()
    )

    df["ema50"] = (
        df["close"]
        .ewm(span=50, adjust=False)
        .mean()
    )

    df["ema200"] = (
        df["close"]
        .ewm(span=200, adjust=False)
        .mean()
    )

    # --------------------------------------------------------
    # Tamaño de vela
    # --------------------------------------------------------

    df["range"] = (
        df["high"] -
        df["low"]
    )

    df["body"] = (
        df["close"] -
        df["open"]
    ).abs()

    df["body_ratio"] = np.where(
        df["range"] > 0,
        df["body"] / df["range"],
        0
    )

    # --------------------------------------------------------
    # Retorno
    # --------------------------------------------------------

    df["change"] = (
        df["close"]
        .pct_change()
    )

    return df


# ============================================================
# PUNTOS SWING
# ============================================================

def detectar_swings(df, lookback=SWING_LOOKBACK):

    highs = []
    lows = []

    if len(df) < (
        lookback * 2 + 5
    ):

        return highs, lows

    for i in range(
        lookback,
        len(df) - lookback
    ):

        high_actual = df.iloc[i]["high"]
        low_actual = df.iloc[i]["low"]

        ventana_high = df.iloc[
            i - lookback:
            i + lookback + 1
        ]["high"]

        ventana_low = df.iloc[
            i - lookback:
            i + lookback + 1
        ]["low"]

        if high_actual >= ventana_high.max():

            highs.append({
                "index": i,
                "price": float(high_actual),
                "time": df.iloc[i]["datetime"]
            })

        if low_actual <= ventana_low.min():

            lows.append({
                "index": i,
                "price": float(low_actual),
                "time": df.iloc[i]["datetime"]
            })

    return highs, lows


# ============================================================
# ESTRUCTURA HH / HL / LH / LL
# ============================================================

def analizar_estructura(df):

    highs, lows = detectar_swings(
        df
    )

    resultado = {
        "estado": "MIXTA",
        "ultimo_high": None,
        "penultimo_high": None,
        "ultimo_low": None,
        "penultimo_low": None,
        "hh": False,
        "hl": False,
        "lh": False,
        "ll": False,
        "bos_compra": False,
        "bos_venta": False,
        "choch_compra": False,
        "choch_venta": False,
        "score_compra": 0,
        "score_venta": 0
    }

    if len(highs) >= 2:

        ultimo_high = highs[-1]
        penultimo_high = highs[-2]

        resultado["ultimo_high"] = ultimo_high
        resultado["penultimo_high"] = penultimo_high

        if (
            ultimo_high["price"]
            > penultimo_high["price"]
        ):

            resultado["hh"] = True
            resultado["score_compra"] += 1

        elif (
            ultimo_high["price"]
            < penultimo_high["price"]
        ):

            resultado["lh"] = True
            resultado["score_venta"] += 1

    if len(lows) >= 2:

        ultimo_low = lows[-1]
        penultimo_low = lows[-2]

        resultado["ultimo_low"] = ultimo_low
        resultado["penultimo_low"] = penultimo_low

        if (
            ultimo_low["price"]
            > penultimo_low["price"]
        ):

            resultado["hl"] = True
            resultado["score_compra"] += 1

        elif (
            ultimo_low["price"]
            < penultimo_low["price"]
        ):

            resultado["ll"] = True
            resultado["score_venta"] += 1

    # --------------------------------------------------------
    # Estado estructural
    # --------------------------------------------------------

    if (
        resultado["hh"]
        and resultado["hl"]
    ):

        resultado["estado"] = "ALCISTA"

    elif (
        resultado["lh"]
        and resultado["ll"]
    ):

        resultado["estado"] = "BAJISTA"

    elif (
        resultado["hh"]
        or resultado["hl"]
    ) and not (
        resultado["lh"]
        or resultado["ll"]
    ):

        resultado["estado"] = "ALCISTA"

    elif (
        resultado["lh"]
        or resultado["ll"]
    ) and not (
        resultado["hh"]
        or resultado["hl"]
    ):

        resultado["estado"] = "BAJISTA"

    # --------------------------------------------------------
    # BOS / CHoCH
    # --------------------------------------------------------

    cierre = float(
        df.iloc[-1]["close"]
    )

    atr_actual = numero(
        df.iloc[-1]["atr"],
        0
    )

    distancia_minima = (
        atr_actual *
        MIN_BOS_DIST_ATR
    )

    if (
        resultado["ultimo_high"]
        and cierre >
        resultado["ultimo_high"]["price"]
        + distancia_minima
    ):

        resultado["bos_compra"] = True

    if (
        resultado["ultimo_low"]
        and cierre <
        resultado["ultimo_low"]["price"]
        - distancia_minima
    ):

        resultado["bos_venta"] = True

    # --------------------------------------------------------
    # CHoCH:
    # cambio estructural que rompe la dirección anterior.
    # --------------------------------------------------------

    if (
        resultado["estado"] == "BAJISTA"
        and resultado["bos_compra"]
    ):

        resultado["choch_compra"] = True

    if (
        resultado["estado"] == "ALCISTA"
        and resultado["bos_venta"]
    ):

        resultado["choch_venta"] = True

    return resultado


# ============================================================
# FIN PARTE 3/9
# ============================================================
