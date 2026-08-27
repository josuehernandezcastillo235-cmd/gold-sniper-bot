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


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 4/9
# RÉGIMEN + DIRECCIÓN + IMPULSO
# ============================================================


# ============================================================
# RÉGIMEN DEL MERCADO
# ============================================================

def determinar_regimen(
    estructura_5m,
    estructura_15m,
    df5,
    df15
):

    estado5 = estructura_5m["estado"]
    estado15 = estructura_15m["estado"]

    adx5 = numero(
        df5.iloc[-1]["adx"],
        0
    )

    adx15 = numero(
        df15.iloc[-1]["adx"],
        0
    )

    # --------------------------------------------------------
    # Tendencia clara en ambas temporalidades.
    # --------------------------------------------------------

    if (
        estado5 == "ALCISTA"
        and estado15 == "ALCISTA"
        and adx5 >= ADX_MINIMO
    ):

        return "ALCISTA"

    if (
        estado5 == "BAJISTA"
        and estado15 == "BAJISTA"
        and adx5 >= ADX_MINIMO
    ):

        return "BAJISTA"

    # --------------------------------------------------------
    # Si una temporalidad es MIXTA, no inventamos tendencia.
    # --------------------------------------------------------

    if (
        estado5 == "ALCISTA"
        and estado15 == "ALCISTA"
    ):

        return "ALCISTA"

    if (
        estado5 == "BAJISTA"
        and estado15 == "BAJISTA"
    ):

        return "BAJISTA"

    # --------------------------------------------------------
    # Lateral cuando no hay estructura suficientemente limpia.
    # --------------------------------------------------------

    if (
        adx5 < ADX_MINIMO
        and adx15 < ADX_MINIMO
    ):

        return "LATERAL"

    return "LATERAL"


# ============================================================
# IMPULSO
# ============================================================

def detectar_impulso(df):

    if len(df) < 8:

        return {
            "compra": False,
            "venta": False,
            "fuerza_compra": 0,
            "fuerza_venta": 0
        }

    ultimas = df.iloc[-5:].copy()

    atr = numero(
        df.iloc[-1]["atr"],
        0
    )

    if atr <= 0:

        return {
            "compra": False,
            "venta": False,
            "fuerza_compra": 0,
            "fuerza_venta": 0
        }

    # --------------------------------------------------------
    # Medimos movimiento neto, no simplemente si hubo una
    # vela verde y una roja.
    # --------------------------------------------------------

    cierre_inicio = float(
        ultimas.iloc[0]["open"]
    )

    cierre_final = float(
        ultimas.iloc[-1]["close"]
    )

    movimiento_neto = (
        cierre_final -
        cierre_inicio
    )

    # Movimiento máximo y mínimo de las últimas velas.
    maximo = float(
        ultimas["high"].max()
    )

    minimo = float(
        ultimas["low"].min()
    )

    rango_total = (
        maximo - minimo
    )

    # --------------------------------------------------------
    # Presión acumulada por cuerpos.
    # --------------------------------------------------------

    cuerpos_alcistas = 0.0
    cuerpos_bajistas = 0.0

    for _, fila in ultimas.iterrows():

        cuerpo = (
            float(fila["close"]) -
            float(fila["open"])
        )

        if cuerpo > 0:
            cuerpos_alcistas += cuerpo

        elif cuerpo < 0:
            cuerpos_bajistas += abs(cuerpo)

    # --------------------------------------------------------
    # Velas con cuerpo relativamente fuerte.
    # --------------------------------------------------------

    velas_fuertes_compra = 0
    velas_fuertes_venta = 0

    for _, fila in ultimas.iterrows():

        rango = numero(
            fila["range"],
            0
        )

        cuerpo = numero(
            fila["body"],
            0
        )

        if rango <= 0:
            continue

        ratio = cuerpo / rango

        if ratio >= 0.55:

            if fila["close"] > fila["open"]:
                velas_fuertes_compra += 1

            elif fila["close"] < fila["open"]:
                velas_fuertes_venta += 1

    # --------------------------------------------------------
    # Fuerza normalizada.
    # --------------------------------------------------------

    fuerza_compra = 0
    fuerza_venta = 0

    if movimiento_neto > atr * 0.25:
        fuerza_compra += 35

    if movimiento_neto < -atr * 0.25:
        fuerza_venta += 35

    if cuerpos_alcistas > cuerpos_bajistas * 1.20:
        fuerza_compra += 30

    elif cuerpos_bajistas > cuerpos_alcistas * 1.20:
        fuerza_venta += 30

    if velas_fuertes_compra >= 2:
        fuerza_compra += 20

    if velas_fuertes_venta >= 2:
        fuerza_venta += 20

    # --------------------------------------------------------
    # Rango total demasiado pequeño = no hay impulso real.
    # --------------------------------------------------------

    if rango_total < atr * 0.70:

        fuerza_compra = min(
            fuerza_compra,
            30
        )

        fuerza_venta = min(
            fuerza_venta,
            30
        )

    # --------------------------------------------------------
    # MUY IMPORTANTE:
    # no marcamos ambos impulsos True simplemente porque
    # existen velas de ambos colores.
    #
    # Se exige dominio.
    # --------------------------------------------------------

    diferencia = (
        fuerza_compra -
        fuerza_venta
    )

    compra = (
        fuerza_compra >= 60
        and diferencia >= 15
    )

    venta = (
        fuerza_venta >= 60
        and diferencia <= -15
    )

    return {
        "compra": compra,
        "venta": venta,
        "fuerza_compra": fuerza_compra,
        "fuerza_venta": fuerza_venta
    }


# ============================================================
# DIRECCIÓN
# ============================================================

def determinar_direccion(
    regimen,
    estructura5,
    estructura15,
    impulso
):

    # --------------------------------------------------------
    # Primero estructura.
    # --------------------------------------------------------

    compra = 0
    venta = 0

    if regimen == "ALCISTA":
        compra += 2

    elif regimen == "BAJISTA":
        venta += 2

    if estructura5["estado"] == "ALCISTA":
        compra += 2

    elif estructura5["estado"] == "BAJISTA":
        venta += 2

    if estructura15["estado"] == "ALCISTA":
        compra += 2

    elif estructura15["estado"] == "BAJISTA":
        venta += 2

    # --------------------------------------------------------
    # Impulso dominante.
    # --------------------------------------------------------

    if impulso["compra"]:
        compra += 2

    if impulso["venta"]:
        venta += 2

    # --------------------------------------------------------
    # Si las puntuaciones son iguales, NEUTRAL.
    # --------------------------------------------------------

    if compra > venta:

        return "COMPRA"

    if venta > compra:

        return "VENTA"

    return "NEUTRAL"


# ============================================================
# FIN PARTE 4/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 5/9
# PULLBACK + CONTINUACIÓN + LIQUIDEZ
# ============================================================


# ============================================================
# PULLBACK REAL
# ============================================================

def detectar_pullback(
    df,
    direccion
):

    if len(df) < 12:

        return False

    atr = numero(
        df.iloc[-1]["atr"],
        0
    )

    if atr <= 0:
        return False

    # Últimas 8 velas.
    ventana = df.iloc[-8:].copy()

    # Movimiento previo.
    mitad = len(ventana) // 2

    tramo1 = ventana.iloc[
        :mitad
    ]

    tramo2 = ventana.iloc[
        mitad:
    ]

    movimiento1 = (
        tramo1.iloc[-1]["close"] -
        tramo1.iloc[0]["open"]
    )

    movimiento2 = (
        tramo2.iloc[-1]["close"] -
        tramo2.iloc[0]["open"]
    )

    # --------------------------------------------------------
    # COMPRA:
    # primero hubo desplazamiento alcista y después
    # retroceso controlado.
    # --------------------------------------------------------

    if direccion == "COMPRA":

        impulso_previo = (
            movimiento1 > atr * 0.35
        )

        retroceso = (
            movimiento2 < -atr * 0.12
        )

        retroceso_controlado = (
            abs(movimiento2)
            < abs(movimiento1) * 0.70
        )

        cierre_no_colapsa = (
            df.iloc[-1]["close"]
            >
            ventana["low"].min()
            + atr * 0.15
        )

        return bool(
            impulso_previo
            and retroceso
            and retroceso_controlado
            and cierre_no_colapsa
        )

    # --------------------------------------------------------
    # VENTA
    # --------------------------------------------------------

    if direccion == "VENTA":

        impulso_previo = (
            movimiento1 < -atr * 0.35
        )

        retroceso = (
            movimiento2 > atr * 0.12
        )

        retroceso_controlado = (
            abs(movimiento2)
            < abs(movimiento1) * 0.70
        )

        cierre_no_colapsa = (
            df.iloc[-1]["close"]
            <
            ventana["high"].max()
            - atr * 0.15
        )

        return bool(
            impulso_previo
            and retroceso
            and retroceso_controlado
            and cierre_no_colapsa
        )

    return False


# ============================================================
# CONTINUACIÓN
# ============================================================

def detectar_continuacion(
    df,
    direccion
):

    if len(df) < 8:
        return False

    atr = numero(
        df.iloc[-1]["atr"],
        0
    )

    if atr <= 0:
        return False

    ultimas = df.iloc[-3:]

    cuerpo_total = 0.0

    for _, fila in ultimas.iterrows():

        cuerpo = (
            float(fila["close"]) -
            float(fila["open"])
        )

        if direccion == "COMPRA" and cuerpo > 0:
            cuerpo_total += cuerpo

        elif direccion == "VENTA" and cuerpo < 0:
            cuerpo_total += abs(cuerpo)

    # --------------------------------------------------------
    # COMPRA
    # --------------------------------------------------------

    if direccion == "COMPRA":

        cierre = float(
            df.iloc[-1]["close"]
        )

        max_prev = float(
            df.iloc[-4:-1]["high"].max()
        )

        ruptura = (
            cierre >
            max_prev
        )

        desplazamiento = (
            cuerpo_total >= atr * 0.35
        )

        vela_final_alcista = (
            df.iloc[-1]["close"]
            >
            df.iloc[-1]["open"]
        )

        return bool(
            ruptura
            and desplazamiento
            and vela_final_alcista
        )

    # --------------------------------------------------------
    # VENTA
    # --------------------------------------------------------

    if direccion == "VENTA":

        cierre = float(
            df.iloc[-1]["close"]
        )

        min_prev = float(
            df.iloc[-4:-1]["low"].min()
        )

        ruptura = (
            cierre <
            min_prev
        )

        desplazamiento = (
            cuerpo_total >= atr * 0.35
        )

        vela_final_bajista = (
            df.iloc[-1]["close"]
            <
            df.iloc[-1]["open"]
        )

        return bool(
            ruptura
            and desplazamiento
            and vela_final_bajista
        )

    return False


# ============================================================
# LIQUIDEZ / MÁXIMOS Y MÍNIMOS
# ============================================================

def analizar_liquidez(df):

    if len(df) < 20:

        return {
            "maximo": None,
            "minimo": None,
            "barrido_compra": False,
            "barrido_venta": False
        }

    # No usamos la última vela para construir el nivel.
    # Así evitamos que el propio precio actual "cree" el nivel.
    referencia = df.iloc[-11:-1]

    maximo = float(
        referencia["high"].max()
    )

    minimo = float(
        referencia["low"].min()
    )

    ultima = df.iloc[-1]

    # --------------------------------------------------------
    # Barrido de liquidez bajista:
    # rompe mínimo y recupera por encima.
    # --------------------------------------------------------

    barrido_compra = bool(
        ultima["low"] < minimo
        and ultima["close"] > minimo
    )

    # --------------------------------------------------------
    # Barrido de liquidez alcista:
    # rompe máximo y recupera por debajo.
    # --------------------------------------------------------

    barrido_venta = bool(
        ultima["high"] > maximo
        and ultima["close"] < maximo
    )

    return {
        "maximo": maximo,
        "minimo": minimo,
        "barrido_compra": barrido_compra,
        "barrido_venta": barrido_venta
    }


# ============================================================
# FIN PARTE 5/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 6/9
# MOMENTUM + SCORE
# ============================================================


# ============================================================
# MOMENTUM
# ============================================================

def analizar_momentum(df):

    fila = df.iloc[-1]

    rsi = numero(
        fila["rsi"],
        50
    )

    adx = numero(
        fila["adx"],
        0
    )

    di_plus = numero(
        fila["di_plus"],
        0
    )

    di_minus = numero(
        fila["di_minus"],
        0
    )

    # --------------------------------------------------------
    # COMPRA
    # --------------------------------------------------------

    compra = (
        rsi >= RSI_COMPRA
        and di_plus > di_minus
    )

    # --------------------------------------------------------
    # VENTA
    # --------------------------------------------------------

    venta = (
        rsi <= RSI_VENTA
        and di_minus > di_plus
    )

    return {
        "rsi": rsi,
        "adx": adx,
        "di_plus": di_plus,
        "di_minus": di_minus,
        "compra": bool(compra),
        "venta": bool(venta)
    }


# ============================================================
# SCORE
# ============================================================

def calcular_score(
    direccion,
    regimen,
    estructura5,
    estructura15,
    impulso,
    pullback,
    continuacion,
    liquidez,
    momentum
):

    score = 0
    razones = []

    # ========================================================
    # COMPRA
    # ========================================================

    if direccion == "COMPRA":

        # Régimen
        if regimen == "ALCISTA":
            score += 15
            razones.append(
                "régimen alcista"
            )

        # Estructura 5M
        if estructura5["estado"] == "ALCISTA":
            score += 15
            razones.append(
                "estructura 5M alcista"
            )

        # Estructura 15M
        if estructura15["estado"] == "ALCISTA":
            score += 15
            razones.append(
                "estructura 15M alcista"
            )

        # HH + HL
        if (
            estructura5["hh"]
            and estructura5["hl"]
        ):

            score += 10
            razones.append(
                "HH + HL"
            )

        # BOS
        if estructura5["bos_compra"]:
            score += 8
            razones.append(
                "BOS compra"
            )

        # Impulso
        if impulso["compra"]:
            score += 10
            razones.append(
                "impulso comprador"
            )

        # Pullback
        if pullback:
            score += 8
            razones.append(
                "pullback real"
            )

        # Continuación
        if continuacion:
            score += 10
            razones.append(
                "continuación"
            )

        # Momentum
        if momentum["rsi"] >= RSI_CONFIRMACION_COMPRA:
            score += 5
            razones.append(
                "RSI confirma"
            )

        if momentum["adx"] >= ADX_CONFIRMACION:
            score += 4
            razones.append(
                "ADX suficiente"
            )

        if (
            momentum["di_plus"]
            >
            momentum["di_minus"]
        ):

            score += 5
            razones.append(
                "DI+ dominante"
            )

        # Liquidez
        if liquidez["barrido_compra"]:
            score += 5
            razones.append(
                "barrido de liquidez"
            )

    # ========================================================
    # VENTA
    # ========================================================

    elif direccion == "VENTA":

        if regimen == "BAJISTA":
            score += 15
            razones.append(
                "régimen bajista"
            )

        if estructura5["estado"] == "BAJISTA":
            score += 15
            razones.append(
                "estructura 5M bajista"
            )

        if estructura15["estado"] == "BAJISTA":
            score += 15
            razones.append(
                "estructura 15M bajista"
            )

        if (
            estructura5["lh"]
            and estructura5["ll"]
        ):

            score += 10
            razones.append(
                "LH + LL"
            )

        if estructura5["bos_venta"]:
            score += 8
            razones.append(
                "BOS venta"
            )

        if impulso["venta"]:
            score += 10
            razones.append(
                "impulso vendedor"
            )

        if pullback:
            score += 8
            razones.append(
                "pullback real"
            )

        if continuacion:
            score += 10
            razones.append(
                "continuación"
            )

        if momentum["rsi"] <= RSI_CONFIRMACION_VENTA:
            score += 5
            razones.append(
                "RSI confirma"
            )

        if momentum["adx"] >= ADX_CONFIRMACION:
            score += 4
            razones.append(
                "ADX suficiente"
            )

        if (
            momentum["di_minus"]
            >
            momentum["di_plus"]
        ):

            score += 5
            razones.append(
                "DI- dominante"
            )

        if liquidez["barrido_venta"]:
            score += 5
            razones.append(
                "barrido de liquidez"
            )

    score = min(
        int(score),
        100
    )

    return score, razones


# ============================================================
# FIN PARTE 6/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 7/9
# RIESGO + SL/TP + IDs + ESTADOS
# ============================================================


# ============================================================
# SL / TP DINÁMICOS
# ============================================================

def calcular_riesgo(
    precio,
    atr,
    direccion,
    estructura,
    liquidez
):

    atr = numero(
        atr,
        0
    )

    precio = numero(
        precio,
        0
    )

    if atr <= 0 or precio <= 0:

        return None

    distancia_sl = atr * ATR_SL

    distancia_tp = atr * ATR_TP

    # --------------------------------------------------------
    # Ajuste usando estructura.
    # No colocamos el SL exactamente sobre un swing.
    # --------------------------------------------------------

    if direccion == "COMPRA":

        sl = precio - distancia_sl
        tp = precio + distancia_tp

        ultimo_low = estructura.get(
            "ultimo_low"
        )

        if ultimo_low:

            nivel = float(
                ultimo_low["price"]
            )

            sl_estructural = (
                nivel - atr * 0.15
            )

            # Elegimos el nivel que dé espacio suficiente
            # sin exagerar la distancia.
            if (
                sl_estructural < precio
                and
                sl_estructural > precio - atr * 1.80
            ):

                sl = sl_estructural

        # Liquidez reciente
        minimo = liquidez.get(
            "minimo"
        )

        if minimo:

            if (
                minimo < precio
                and
                minimo > sl
            ):

                sl = (
                    minimo -
                    atr * 0.10
                )

    else:

        sl = precio + distancia_sl
        tp = precio - distancia_tp

        ultimo_high = estructura.get(
            "ultimo_high"
        )

        if ultimo_high:

            nivel = float(
                ultimo_high["price"]
            )

            sl_estructural = (
                nivel + atr * 0.15
            )

            if (
                sl_estructural > precio
                and
                sl_estructural < precio + atr * 1.80
            ):

                sl = sl_estructural

        maximo = liquidez.get(
            "maximo"
        )

        if maximo:

            if (
                maximo > precio
                and
                maximo < sl
            ):

                sl = (
                    maximo +
                    atr * 0.10
                )

    # --------------------------------------------------------
    # Recalcular TP para mantener como mínimo el RR deseado.
    # --------------------------------------------------------

    riesgo = abs(
        precio - sl
    )

    if riesgo <= 0:

        return None

    beneficio_minimo = (
        riesgo * RR_MINIMO
    )

    if direccion == "COMPRA":

        tp_minimo = (
            precio +
            beneficio_minimo
        )

        if tp < tp_minimo:
            tp = tp_minimo

    else:

        tp_minimo = (
            precio -
            beneficio_minimo
        )

        if tp > tp_minimo:
            tp = tp_minimo

    beneficio = abs(
        tp - precio
    )

    rr = (
        beneficio / riesgo
        if riesgo > 0
        else 0
    )

    if rr < RR_MINIMO:

        return None

    return {
        "sl": redondear_precio(sl),
        "tp": redondear_precio(tp),
        "rr": rr,
        "riesgo": riesgo
    }


# ============================================================
# ID DE SEÑAL
# ============================================================

def generar_id(
    direccion,
    precio
):

    ahora = int(
        time.time()
    )

    corto = uuid.uuid4().hex[:4]

    return (
        f"{direccion}-"
        f"{ahora}-"
        f"{redondear_precio(precio):.2f}-"
        f"{corto}"
    )


# ============================================================
# COOLDOWN
# ============================================================

def cooldown_activo(
    direccion
):

    global ultima_confirmacion_ts
    global ultima_direccion

    if (
        ultima_confirmacion_ts is None
        or ultima_direccion is None
    ):

        return False

    if direccion != ultima_direccion:

        return False

    transcurrido = (
        time.time() -
        ultima_confirmacion_ts
    ) / 60

    return (
        transcurrido
        <
        MINUTOS_COOLDOWN_CONFIRMADA
    )


def registrar_confirmacion(
    direccion
):

    global ultima_confirmacion_ts
    global ultima_direccion

    ultima_confirmacion_ts = time.time()
    ultima_direccion = direccion


# ============================================================
# ERROR CONTROLADO
# ============================================================

def mensaje_error(mensaje):

    global ultimo_error_ts

    ahora = time.time()

    # El strategy devuelve ERROR, pero evita que una falla
    # temporal mande spam continuamente.
    if (
        ahora - ultimo_error_ts
        < 300
    ):

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": (
                "😴 SIN_SEÑAL\n\n"
                "⚠️ Error temporal de datos "
                "ya notificado."
            ),
            "id": None
        }

    ultimo_error_ts = ahora

    return {
        "tipo": "ERROR",
        "mensaje": (
            "❌ XAU SNIPER AI V4.2\n\n"
            "⚠️ Error de datos / motor\n\n"
            f"{mensaje}\n\n"
            "📡 Proveedor: Twelve Data\n"
            "🛑 El bot continúa ejecutándose."
        ),
        "id": None
    }


# ============================================================
# FIN PARTE 7/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 8/9
# MOTOR DE DECISIÓN
# ============================================================


# ============================================================
# CONSTRUIR DIAGNÓSTICO
# ============================================================

def construir_diagnostico(
    precio,
    estructura5,
    estructura15,
    regimen,
    direccion,
    impulso,
    pullback,
    continuacion,
    momentum,
    score_compra,
    score_venta
):

    estructura5_texto = (
        estructura5["estado"]
    )

    estructura15_texto = (
        estructura15["estado"]
    )

    return (
        "📋 DIAGNÓSTICO XAU SNIPER\n"
        f"5M: {estructura5_texto}\n"
        f"15M: {estructura15_texto}\n"
        f"🌐 Régimen: {regimen}\n"
        f"🧭 Dirección: {direccion}\n\n"
        f"💰 Precio: {fmt(precio)}\n"
        f"RSI: {fmt(momentum['rsi'])}\n"
        f"ADX: {fmt(momentum['adx'])}\n"
        f"DI+: {fmt(momentum['di_plus'])}\n"
        f"DI-: {fmt(momentum['di_minus'])}\n\n"
        f"🏗 Estructura 5M: "
        f"{estructura5_texto}\n"
        f"🏗 Estructura 15M: "
        f"{estructura15_texto}\n\n"
        f"💥 Impulso compra: "
        f"{impulso['compra']}\n"
        f"💥 Impulso venta: "
        f"{impulso['venta']}\n"
        f"💪 Fuerza compra: "
        f"{impulso['fuerza_compra']}\n"
        f"💪 Fuerza venta: "
        f"{impulso['fuerza_venta']}\n\n"
        f"🔄 Pullback: {pullback}\n"
        f"🚀 Continuación: "
        f"{continuacion}\n\n"
        f"🎯 Score COMPRA: "
        f"{score_compra}/100\n"
        f"🎯 Score VENTA: "
        f"{score_venta}/100"
    )


# ============================================================
# ANALIZAR
# ============================================================

def analizar():

    global ultima_senal_id
    global ultimo_timestamp_5m
    global ultimo_timestamp_15m

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

        # ====================================================
        # API
        # ====================================================

        print(
            "📡 Descargando datos desde "
            "Twelve Data..."
        )

        bruto5 = descargar_velas(
            INTERVALO_5M,
            VELAS_5M
        )

        bruto15 = descargar_velas(
            INTERVALO_15M,
            VELAS_15M
        )

        print(
            f"✅ Twelve Data 5M: "
            f"{len(bruto5)} velas"
        )

        print(
            f"✅ Twelve Data 15M: "
            f"{len(bruto15)} velas"
        )

        # ====================================================
        # SOLO VELAS CERRADAS
        # ====================================================

        df5, ts5, edad5 = (
            obtener_velas_cerradas(
                bruto5,
                INTERVALO_5M
            )
        )

        df15, ts15, edad15 = (
            obtener_velas_cerradas(
                bruto15,
                INTERVALO_15M
            )
        )

        print(
            f"🕐 Última vela 5M: "
            f"{ts5}"
        )

        print(
            f"🕐 Edad vela 5M: "
            f"{edad5:.1f} minutos"
        )

        print(
            f"🕐 Última vela 15M: "
            f"{ts15}"
        )

        print(
            f"🕐 Edad vela 15M: "
            f"{edad15:.1f} minutos"
        )

        # ====================================================
        # DETECTAR NUEVAS VELAS
        # ====================================================

        datos_nuevos = (
            ts5 != ultimo_timestamp_5m
            or
            ts15 != ultimo_timestamp_15m
        )

        if datos_nuevos:

            print(
                "🆕 Hay cierre de vela nuevo."
            )

        else:

            print(
                "ℹ️ No hay velas cerradas "
                "nuevas desde el análisis anterior."
            )

        ultimo_timestamp_5m = ts5
        ultimo_timestamp_15m = ts15

        # ====================================================
        # INDICADORES
        # ====================================================

        df5 = calcular_indicadores(
            df5
        )

        df15 = calcular_indicadores(
            df15
        )

        # Eliminamos filas donde todavía no existen
        # indicadores suficientes.

        df5 = df5.dropna(
            subset=[
                "atr",
                "rsi",
                "adx",
                "di_plus",
                "di_minus"
            ]
        ).reset_index(
            drop=True
        )

        df15 = df15.dropna(
            subset=[
                "atr",
                "rsi",
                "adx",
                "di_plus",
                "di_minus"
            ]
        ).reset_index(
            drop=True
        )

        if len(df5) < 50:

            raise RuntimeError(
                "Muy pocos datos útiles en 5M."
            )

        if len(df15) < 50:

            raise RuntimeError(
                "Muy pocos datos útiles en 15M."
            )

        # ====================================================
        # ESTRUCTURA
        # ====================================================

        estructura5 = analizar_estructura(
            df5
        )

        estructura15 = analizar_estructura(
            df15
        )

        # ====================================================
        # RÉGIMEN
        # ====================================================

        regimen = determinar_regimen(
            estructura5,
            estructura15,
            df5,
            df15
        )

        # ====================================================
        # IMPULSO
        # ====================================================

        impulso = detectar_impulso(
            df5
        )

        # ====================================================
        # DIRECCIÓN
        # ====================================================

        direccion = determinar_direccion(
            regimen,
            estructura5,
            estructura15,
            impulso
        )

        # ====================================================
        # PRECIO
        # ====================================================

        precio = float(
            df5.iloc[-1]["close"]
        )

        # ====================================================
        # PULLBACK
        # ====================================================

        pullback = detectar_pullback(
            df5,
            direccion
        )

        # ====================================================
        # CONTINUACIÓN
        # ====================================================

        continuacion = detectar_continuacion(
            df5,
            direccion
        )

        # ====================================================
        # LIQUIDEZ
        # ====================================================

        liquidez = analizar_liquidez(
            df5
        )

        # ====================================================
        # MOMENTUM
        # ====================================================

        momentum = analizar_momentum(
            df5
        )

        # ====================================================
        # SCORES
        # ====================================================

        score_compra, razones_compra = (
            calcular_score(
                "COMPRA",
                regimen,
                estructura5,
                estructura15,
                impulso,
                detectar_pullback(
                    df5,
                    "COMPRA"
                ),
                detectar_continuacion(
                    df5,
                    "COMPRA"
                ),
                liquidez,
                momentum
            )
        )

        score_venta, razones_venta = (
            calcular_score(
                "VENTA",
                regimen,
                estructura5,
                estructura15,
                impulso,
                detectar_pullback(
                    df5,
                    "VENTA"
                ),
                detectar_continuacion(
                    df5,
                    "VENTA"
                ),
                liquidez,
                momentum
            )
        )

        # ====================================================
        # PRINT LIMPIO
        # ====================================================

        print(
            f"📊 5M: "
            f"{estructura5['estado']}"
        )

        print(
            f"📊 15M: "
            f"{estructura15['estado']}"
        )

        print(
            f"🌐 Régimen: {regimen}"
        )

        print(
            f"💰 Precio: {fmt(precio)}"
        )

        print(
            f"RSI: {fmt(momentum['rsi'])}"
        )

        print(
            f"ADX: {fmt(momentum['adx'])}"
        )

        print(
            f"💥 Impulso COMPRA: "
            f"{impulso['compra']}"
        )

        print(
            f"💥 Impulso VENTA: "
            f"{impulso['venta']}"
        )

        print(
            f"⚖️ Conflicto impulso: "
            f"{impulso['compra'] and impulso['venta']}"
        )

        print(
            f"🧭 Dirección: {direccion}"
        )

        print(
            f"🔄 Pullback: {pullback}"
        )

        print(
            f"🚀 Continuación: "
            f"{continuacion}"
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
        # DIAGNÓSTICO
        # ====================================================

        print(
            construir_diagnostico(
                precio,
                estructura5,
                estructura15,
                regimen,
                direccion,
                impulso,
                pullback,
                continuacion,
                momentum,
                score_compra,
                score_venta
            )
        )

        # ====================================================
        # FIN PARTE 8
        # ====================================================

        return _decidir_senal(
            precio=precio,
            df5=df5,
            estructura5=estructura5,
            estructura15=estructura15,
            regimen=regimen,
            direccion=direccion,
            impulso=impulso,
            pullback=pullback,
            continuacion=continuacion,
            liquidez=liquidez,
            momentum=momentum,
            score_compra=score_compra,
            score_venta=score_venta,
            datos_nuevos=datos_nuevos
        )

    except Exception as e:

        logger.exception(
            "❌ Error en analizar()"
        )

        return mensaje_error(
            str(e)
        )


# ============================================================
# FIN PARTE 8/9
# ============================================================


# ============================================================
# XAU SNIPER AI V4.2
# PARTE 9/9
# DECISIÓN FINAL + PREALERTA + CONFIRMACIÓN
# ============================================================


# ============================================================
# DECISIÓN FINAL
# ============================================================

def _decidir_senal(
    precio,
    df5,
    estructura5,
    estructura15,
    regimen,
    direccion,
    impulso,
    pullback,
    continuacion,
    liquidez,
    momentum,
    score_compra,
    score_venta,
    datos_nuevos
):

    global ultima_senal_id

    # ========================================================
    # CONFLICTO REAL
    # ========================================================

    # El conflicto YA NO se define simplemente porque hubo
    # velas verdes y rojas.
    #
    # Solo existe si los dos lados realmente superan el
    # umbral de impulso y además tienen fuerzas cercanas.

    diferencia_fuerza = abs(
        impulso["fuerza_compra"] -
        impulso["fuerza_venta"]
    )

    conflicto_impulso = (
        impulso["compra"]
        and
        impulso["venta"]
        and
        diferencia_fuerza < 20
    )

    if conflicto_impulso:

        print(
            "⚖️ CONFLICTO REAL: "
            "fuerzas demasiado parejas."
        )

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": (
                "😴 SIN_SEÑAL\n\n"
                "⚖️ Conflicto real de presión.\n"
                "El mercado no tiene un "
                "dominante suficientemente claro.\n\n"
                "🧠 Se evita forzar operación."
            ),
            "id": None
        }

    # ========================================================
    # DIRECCIÓN NEUTRAL
    # ========================================================

    if direccion == "NEUTRAL":

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": (
                "😴 SIN_SEÑAL\n\n"
                "🧭 Dirección neutral.\n"
                "No existe ventaja suficiente."
            ),
            "id": None
        }

    # ========================================================
    # RÉGIMEN LATERAL
    # ========================================================

    # No prohibimos absolutamente una señal en lateral,
    # pero exigimos una configuración mucho más fuerte.
    # Esto evita repetir el caso de score 55 en mercado lateral.

    score_actual = (
        score_compra
        if direccion == "COMPRA"
        else score_venta
    )

    if regimen == "LATERAL":

        if score_actual < 70:

            print(
                "🌐 Mercado lateral. "
                "Score insuficiente."
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "😴 SIN_SEÑAL\n\n"
                    "🌐 Régimen: LATERAL\n"
                    f"🎯 Score: {score_actual}/100\n\n"
                    "🛑 No se fuerza entrada "
                    "contra un mercado sin "
                    "estructura limpia."
                ),
                "id": None
            }

    # ========================================================
    # FILTRO ESTRUCTURAL
    # ========================================================

    estructura_direccion = (
        estructura5["estado"]
        if direccion == "COMPRA"
        else estructura5["estado"]
    )

    if direccion == "COMPRA":

        estructura_ok = (
            estructura5["estado"] == "ALCISTA"
            or
            estructura5["bos_compra"]
            or
            estructura5["choch_compra"]
        )

    else:

        estructura_ok = (
            estructura5["estado"] == "BAJISTA"
            or
            estructura5["bos_venta"]
            or
            estructura5["choch_venta"]
        )

    if not estructura_ok:

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": (
                "😴 SIN_SEÑAL\n\n"
                f"🧭 Dirección: {direccion}\n"
                f"🏗 Estructura 5M: "
                f"{estructura5['estado']}\n\n"
                "🛑 Estructura insuficiente "
                "para operar."
            ),
            "id": None
        }

    # ========================================================
    # MOMENTUM
    # ========================================================

    if direccion == "COMPRA":

        momentum_basico = (
            momentum["rsi"] >= RSI_COMPRA
            and
            momentum["di_plus"]
            >= momentum["di_minus"]
        )

    else:

        momentum_basico = (
            momentum["rsi"] <= RSI_VENTA
            and
            momentum["di_minus"]
            >= momentum["di_plus"]
        )

    # ========================================================
    # SCORE PREALERTA
    # ========================================================

    if score_actual < SCORE_PREALERTA:

        print(
            "😴 Score por debajo de "
            "prealerta."
        )

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": (
                "😴 SIN_SEÑAL\n\n"
                f"🧭 Dirección: {direccion}\n"
                f"🎯 Score: "
                f"{score_actual}/100\n"
                f"📈 Régimen: {regimen}\n\n"
                "No existe suficiente ventaja "
                "estadística para generar "
                "prealerta."
            ),
            "id": None
        }

    # ========================================================
    # ID
    # ========================================================

    # Mientras una configuración siga viva, se mantiene el
    # mismo ID. Esto permite que bot.py controle correctamente
    # ESPERANDO y evite spam.

    if ultima_senal_id is None:

        ultima_senal_id = generar_id(
            direccion,
            precio
        )

    identificador = (
        ultima_senal_id
    )

    # ========================================================
    # RIESGO
    # ========================================================

    riesgo = calcular_riesgo(
        precio,
        df5.iloc[-1]["atr"],
        direccion,
        estructura5,
        liquidez
    )

    if riesgo is None:

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": (
                "😴 SIN_SEÑAL\n\n"
                "🛑 No se pudo construir "
                "un SL/TP válido con "
                f"RR mínimo {RR_MINIMO:.2f}."
            ),
            "id": None
        }

    # ========================================================
    # CONFIRMACIÓN
    # ========================================================

    if direccion == "COMPRA":

        confirmacion_rsi = (
            momentum["rsi"]
            >= RSI_CONFIRMACION_COMPRA
        )

        confirmacion_di = (
            momentum["di_plus"]
            >
            momentum["di_minus"]
        )

    else:

        confirmacion_rsi = (
            momentum["rsi"]
            <= RSI_CONFIRMACION_VENTA
        )

        confirmacion_di = (
            momentum["di_minus"]
            >
            momentum["di_plus"]
        )

    confirmacion_adx = (
        momentum["adx"]
        >= ADX_CONFIRMACION
    )

    # La confirmación exige:
    #
    # 1. score alto
    # 2. impulso dominante
    # 3. continuación
    # 4. RSI
    # 5. DI
    # 6. ADX
    #
    # No basta con una sola variable.

    confirmada = (
        score_actual >= SCORE_CONFIRMACION
        and
        (
            impulso["compra"]
            if direccion == "COMPRA"
            else impulso["venta"]
        )
        and
        continuacion
        and
        confirmacion_rsi
        and
        confirmacion_di
        and
        confirmacion_adx
        and
        momentum_basico
    )

    # ========================================================
    # CONFIRMADA
    # ========================================================

    if confirmada:

        if cooldown_activo(
            direccion
        ):

            print(
                "⏳ Cooldown activo para "
                f"{direccion}."
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "😴 SIN_SEÑAL\n\n"
                    "⏳ Cooldown activo.\n"
                    f"🧭 Dirección: {direccion}"
                ),
                "id": None
            }

        registrar_confirmacion(
            direccion
        )

        mensaje = (
            "🥇 XAU SNIPER AI V4.2\n\n"
            f"🚨 CONFIRMADA {direccion}\n\n"
            f"🆔 ID: {identificador}\n"
            f"🎯 Score: {score_actual}/100\n"
            f"💰 Precio: {fmt(precio)}\n\n"
            f"📈 5M: {estructura5['estado']}\n"
            f"📊 15M: {estructura15['estado']}\n"
            f"🌐 Régimen: {regimen}\n\n"
            f"RSI: {fmt(momentum['rsi'])}\n"
            f"ADX: {fmt(momentum['adx'])}\n"
            f"DI+: {fmt(momentum['di_plus'])}\n"
            f"DI-: {fmt(momentum['di_minus'])}\n\n"
            f"🛑 SL: {fmt(riesgo['sl'])}\n"
            f"🎯 TP: {fmt(riesgo['tp'])}\n"
            f"📐 RR: 1:{riesgo['rr']:.2f}\n\n"
            "🧠 Estructura + movimiento "
            "confirmados.\n"
            "🚀 Continuación confirmada.\n"
            "⚠️ PAPER / ESCÁNER"
        )

        print(
            "🚨 CONFIRMADA: "
            f"{direccion}"
        )

        return {
            "tipo": "CONFIRMADA",
            "mensaje": mensaje,
            "id": identificador
        }

    # ========================================================
    # ESPERANDO CONFIRMACIÓN
    # ========================================================

    faltantes = []

    if not (
        impulso["compra"]
        if direccion == "COMPRA"
        else impulso["venta"]
    ):

        faltantes.append(
            "impulso dominante"
        )

    if not pullback:

        faltantes.append(
            "pullback"
        )

    if not continuacion:

        faltantes.append(
            "continuación"
        )

    if not confirmacion_rsi:

        faltantes.append(
            "RSI"
        )

    if not confirmacion_di:

        faltantes.append(
            "DI dominante"
        )

    if not confirmacion_adx:

        faltantes.append(
            "ADX"
        )

    # ========================================================
    # PREALERTA
    # ========================================================

    if (
        score_actual >= SCORE_PREALERTA
        and
        not confirmada
    ):

        texto_faltantes = (
            "\n".join(
                f"• {x}"
                for x in faltantes
            )
            if faltantes
            else
            "• Confirmación final"
        )

        mensaje = (
            "🟢 XAU SNIPER AI V4.2\n\n"
            f"⚠️ PREALERTA {direccion}\n\n"
            f"🆔 ID: {identificador}\n"
            f"🎯 Score: "
            f"{score_actual}/100\n"
            f"💰 Precio: "
            f"{fmt(precio)}\n\n"
            f"📈 5M: "
            f"{estructura5['estado']}\n"
            f"📊 15M: "
            f"{estructura15['estado']}\n"
            f"🌐 Régimen: {regimen}\n\n"
            f"RSI: "
            f"{fmt(momentum['rsi'])}\n"
            f"ADX: "
            f"{fmt(momentum['adx'])}\n"
            f"DI+: "
            f"{fmt(momentum['di_plus'])}\n"
            f"DI-: "
            f"{fmt(momentum['di_minus'])}\n\n"
            f"🛑 SL referencia: "
            f"{fmt(riesgo['sl'])}\n"
            f"🎯 TP referencia: "
            f"{fmt(riesgo['tp'])}\n"
            f"📐 RR: "
            f"1:{riesgo['rr']:.2f}\n\n"
            "⏳ Esperando confirmación.\n\n"
            "Falta:\n"
            f"{texto_faltantes}\n\n"
            "⚠️ AÚN NO CONFIRMADA"
        )

        print(
            f"⚠️ NUEVA PREALERTA {direccion}"
        )

        return {
            "tipo": "PREALERTA",
            "mensaje": mensaje,
            "id": identificador
        }

    # ========================================================
    # SIN SEÑAL
    # ========================================================

    return {
        "tipo": "SIN_SEÑAL",
        "mensaje": (
            "😴 SIN_SEÑAL\n\n"
            f"🧭 Dirección: {direccion}\n"
            f"🎯 Score: {score_actual}/100\n"
            f"🌐 Régimen: {regimen}\n\n"
            "No existe confirmación "
            "suficiente."
        ),
        "id": None
    }


# ============================================================
# FIN XAU SNIPER AI V4.2
# ============================================================
