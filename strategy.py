import requests
import pandas as pd
import numpy as np

import os
import time
import uuid
import logging
from datetime import datetime, timezone


# =========================================================
# XAU SNIPER AI V4.2
# MOTOR:
#
# ESTRUCTURA + MOMENTUM + LIQUIDEZ
#
# PROVEEDOR:
# BiQuote
# =========================================================


# =========================================================
# CONFIGURACIÓN
# =========================================================

SYMBOL = "XAUUSD"

BIQUOTE_BASE = (
    "https://biquote.io/api"
)

INTERVALO_5M = "5m"
INTERVALO_15M = "15m"

VELAS_5M = 300
VELAS_15M = 200

TIMEOUT = 15

ATR_SL = 1.30
ATR_TP = 2.20

RR_MINIMO = 1.50

ADX_MINIMO = 15.0

RSI_COMPRA = 52.0
RSI_VENTA = 48.0

RSI_CONFIRMACION_COMPRA = 55.0
RSI_CONFIRMACION_VENTA = 45.0

MIN_SCORE_PREALERTA = 60
MIN_SCORE_CONFIRMACION = 75

MINUTOS_REPETICION = 15

SWING_LOOKBACK = 3

LOG_LEVEL = logging.INFO


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=LOG_LEVEL,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    )
)

logger = logging.getLogger(
    "XAU_SNIPER_V4"
)


# =========================================================
# SESIÓN HTTP
# =========================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent":
        "XAU-Sniper-AI-V4/4.2"
})


# =========================================================
# ESTADO GLOBAL DEL SETUP
# =========================================================
#
# Aquí está la corrección importante.
#
# Una PREALERTA no desaparece después de enviarla.
#
# Se conserva:
#
# {
#   id,
#   direccion,
#   estado,
#   precio_prealerta,
#   ...
# }
#
# y en los siguientes ciclos se intenta confirmar
# o invalidar.
# =========================================================

SETUP_ACTIVO = None


# =========================================================
# CACHE PARA EVITAR PETICIONES INNECESARIAS
# =========================================================

CACHE = {
    "5m": {
        "timestamp": 0,
        "df": None
    },
    "15m": {
        "timestamp": 0,
        "df": None
    }
}


CACHE_SEGUNDOS = 50


# =========================================================
# HELPERS BÁSICOS
# =========================================================

def ahora_utc():

    return datetime.now(
        timezone.utc
    )


def nuevo_id():

    return (
        datetime.now(
            timezone.utc
        ).strftime("%Y%m%d%H%M")
        + "-"
        + uuid.uuid4().hex[:6].upper()
    )


def numero(valor, default=np.nan):

    try:

        return float(valor)

    except (
        TypeError,
        ValueError
    ):

        return default


# =========================================================
# VALIDACIÓN DE DATAFRAME
# =========================================================

def validar_dataframe(df):

    if df is None:
        return False

    if df.empty:
        return False

    columnas = [
        "open",
        "high",
        "low",
        "close"
    ]

    for columna in columnas:

        if columna not in df.columns:
            return False

    if len(df) < 50:
        return False

    return True


# =========================================================
# DESCARGA DE OHLC DESDE BIQUOTE
# =========================================================

def obtener_ohlc(
    intervalo,
    limite
):

    ahora = time.time()

    cache = CACHE.get(
        intervalo
    )

    # -----------------------------------------------------
    # CACHE
    # -----------------------------------------------------

    if cache:

        edad = (
            ahora
            - cache["timestamp"]
        )

        if (
            cache["df"] is not None
            and edad < CACHE_SEGUNDOS
        ):

            return cache["df"].copy()

    url = (
        f"{BIQUOTE_BASE}/"
        f"{SYMBOL}/ohlc"
    )

    params = {
        "interval": intervalo,
        "limit": limite
    }

    ultimo_error = None

    # -----------------------------------------------------
    # RETRY SUAVE
    # -----------------------------------------------------

    for intento in range(3):

        try:

            response = SESSION.get(
                url,
                params=params,
                timeout=TIMEOUT
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(
                data,
                dict
            ):

                raise ValueError(
                    "Respuesta BiQuote inválida"
                )

            bars = data.get(
                "bars"
            )

            if not bars:

                raise ValueError(
                    "BiQuote no devolvió velas"
                )

            df = pd.DataFrame(
                bars
            )

            if df.empty:

                raise ValueError(
                    "DataFrame vacío"
                )

            # -------------------------------------------------
            # TIMESTAMP
            # -------------------------------------------------

            df["openTime"] = (
                pd.to_datetime(
                    df["openTime"],
                    utc=True,
                    errors="coerce"
                )
            )

            df = df.dropna(
                subset=["openTime"]
            )

            # -------------------------------------------------
            # ELIMINAR VELA ABIERTA
            # -------------------------------------------------

            if "isOpen" in df.columns:

                df = df[
                    df["isOpen"] != True
                ]

            # -------------------------------------------------
            # NUMÉRICOS
            # -------------------------------------------------

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

            if "tickVolume" in df.columns:

                df["tickVolume"] = (
                    pd.to_numeric(
                        df["tickVolume"],
                        errors="coerce"
                    ).fillna(0)
                )

            else:

                df["tickVolume"] = 0

            df = df.dropna(
                subset=[
                    "open",
                    "high",
                    "low",
                    "close"
                ]
            )

            # -------------------------------------------------
            # ORDEN CRONOLÓGICO
            # -------------------------------------------------

            df = (
                df
                .sort_values(
                    "openTime"
                )
                .drop_duplicates(
                    subset=["openTime"]
                )
                .reset_index(
                    drop=True
                )
            )

            if not validar_dataframe(
                df
            ):

                raise ValueError(
                    f"Datos insuficientes "
                    f"para {intervalo}: "
                    f"{len(df)} velas"
                )

            CACHE[intervalo] = {
                "timestamp": ahora,
                "df": df.copy()
            }

            logger.info(
                "BiQuote %s: %s velas",
                intervalo,
                len(df)
            )

            return df

        except Exception as e:

            ultimo_error = e

            logger.warning(
                "BiQuote %s intento %s/3: %s",
                intervalo,
                intento + 1,
                e
            )

            if intento < 2:

                time.sleep(
                    1.5 * (intento + 1)
                )

    raise RuntimeError(
        f"BiQuote {intervalo} falló: "
        f"{ultimo_error}"
    )


# =========================================================
# CARGAR MERCADO
# =========================================================

def cargar_mercado():

    df5 = obtener_ohlc(
        INTERVALO_5M,
        VELAS_5M
    )

    df15 = obtener_ohlc(
        INTERVALO_15M,
        VELAS_15M
    )

    return df5, df15


# =========================================================
# INDICADORES
# =========================================================

def calcular_indicadores(df):

    df = df.copy()

    close = df["close"]
    high = df["high"]
    low = df["low"]

    # -----------------------------------------------------
    # EMA
    # -----------------------------------------------------

    df["ema20"] = (
        close.ewm(
            span=20,
            adjust=False
        ).mean()
    )

    df["ema50"] = (
        close.ewm(
            span=50,
            adjust=False
        ).mean()
    )

    df["ema200"] = (
        close.ewm(
            span=200,
            adjust=False
        ).mean()
    )

    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    delta = close.diff()

    gain = (
        delta.clip(lower=0)
        .ewm(
            alpha=1 / 14,
            adjust=False
        )
        .mean()
    )

    loss = (
        (-delta.clip(upper=0))
        .ewm(
            alpha=1 / 14,
            adjust=False
        )
        .mean()
    )

    rs = gain / loss.replace(
        0,
        np.nan
    )

    df["rsi"] = (
        100
        - (
            100
            / (1 + rs)
        )
    )

    # -----------------------------------------------------
    # TRUE RANGE
    # -----------------------------------------------------

    prev_close = close.shift(1)

    tr1 = high - low

    tr2 = (
        high - prev_close
    ).abs()

    tr3 = (
        low - prev_close
    ).abs()

    tr = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(axis=1)

    df["atr"] = (
        tr.ewm(
            alpha=1 / 14,
            adjust=False
        ).mean()
    )

    # -----------------------------------------------------
    # ADX
    # -----------------------------------------------------

    up_move = (
        high.diff()
    )

    down_move = (
        -low.diff()
    )

    plus_dm = np.where(
        (
            (up_move > down_move)
            & (up_move > 0)
        ),
        up_move,
        0
    )

    minus_dm = np.where(
        (
            (down_move > up_move)
            & (down_move > 0)
        ),
        down_move,
        0
    )

    atr14 = (
        tr.ewm(
            alpha=1 / 14,
            adjust=False
        ).mean()
    )

    plus_di = (
        100
        * pd.Series(
            plus_dm,
            index=df.index
        )
        .ewm(
            alpha=1 / 14,
            adjust=False
        )
        .mean()
        / atr14.replace(
            0,
            np.nan
        )
    )

    minus_di = (
        100
        * pd.Series(
            minus_dm,
            index=df.index
        )
        .ewm(
            alpha=1 / 14,
            adjust=False
        )
        .mean()
        / atr14.replace(
            0,
            np.nan
        )
    )

    dx = (
        100
        * (plus_di - minus_di).abs()
        / (
            plus_di + minus_di
        ).replace(
            0,
            np.nan
        )
    )

    df["plus_di"] = plus_di
    df["minus_di"] = minus_di

    df["adx"] = (
        dx.ewm(
            alpha=1 / 14,
            adjust=False
        ).mean()
    )

    # -----------------------------------------------------
    # VELOCIDAD DE LA VELA
    # -----------------------------------------------------

    df["body"] = (
        df["close"]
        - df["open"]
    )

    df["body_abs"] = (
        df["body"].abs()
    )

    df["range"] = (
        df["high"]
        - df["low"]
    )

    df["body_ratio"] = (
        df["body_abs"]
        / df["range"].replace(
            0,
            np.nan
        )
    )

    # -----------------------------------------------------
    # RETORNO
    # -----------------------------------------------------

    df["return_3"] = (
        close
        .pct_change(3)
        * 100
    )

    df["return_6"] = (
        close
        .pct_change(6)
        * 100
    )

    return df


# =========================================================
# ÚLTIMA FILA VÁLIDA
# =========================================================

def ultima_fila(df):

    if df is None or df.empty:
        return None

    fila = df.iloc[-1]

    return fila


# =========================================================
# ESTRUCTURA DE MERCADO
# =========================================================

def detectar_swings(
    df,
    izquierda=SWING_LOOKBACK,
    derecha=SWING_LOOKBACK
):

    highs = []
    lows = []

    if len(df) < (
        izquierda
        + derecha
        + 5
    ):

        return highs, lows

    high_values = (
        df["high"].values
    )

    low_values = (
        df["low"].values
    )

    for i in range(
        izquierda,
        len(df) - derecha
    ):

        ventana_high = (
            high_values[
                i - izquierda:
                i + derecha + 1
            ]
        )

        ventana_low = (
            low_values[
                i - izquierda:
                i + derecha + 1
            ]
        )

        if (
            high_values[i]
            == max(ventana_high)
        ):

            highs.append({
                "index": i,
                "price": float(
                    high_values[i]
                )
            })

        if (
            low_values[i]
            == min(ventana_low)
        ):

            lows.append({
                "index": i,
                "price": float(
                    low_values[i]
                )
            })

    return highs, lows


# =========================================================
# CLASIFICAR HH / LH
# =========================================================

def clasificar_maximos(highs):

    resultado = []

    anteriores = []

    for swing in highs:

        precio = swing["price"]

        if not anteriores:

            etiqueta = "H"

        else:

            anterior = (
                anteriores[-1]["price"]
            )

            if precio > anterior:
                etiqueta = "HH"

            else:
                etiqueta = "LH"

        resultado.append({
            **swing,
            "tipo": etiqueta
        })

        anteriores.append(
            swing
        )

    return resultado


# =========================================================
# CLASIFICAR HL / LL
# =========================================================

def clasificar_minimos(lows):

    resultado = []

    anteriores = []

    for swing in lows:

        precio = swing["price"]

        if not anteriores:

            etiqueta = "L"

        else:

            anterior = (
                anteriores[-1]["price"]
            )

            if precio > anterior:
                etiqueta = "HL"

            else:
                etiqueta = "LL"

        resultado.append({
            **swing,
            "tipo": etiqueta
        })

        anteriores.append(
            swing
        )

    return resultado


# =========================================================
# ESTRUCTURA COMPLETA
# =========================================================

def analizar_estructura(df):

    highs, lows = detectar_swings(
        df
    )

    highs = clasificar_maximos(
        highs
    )

    lows = clasificar_minimos(
        lows
    )

    if not highs or not lows:

        return {
            "direccion": "NEUTRAL",
            "estructura": "SIN_DATOS",
            "bos": None,
            "choch": None,
            "highs": highs,
            "lows": lows
        }

    ultimos_highs = highs[-4:]
    ultimos_lows = lows[-4:]

    tipos_high = [
        x["tipo"]
        for x in ultimos_highs
    ]

    tipos_low = [
        x["tipo"]
        for x in ultimos_lows
    ]

    alcista = (
        "HH" in tipos_high
        and
        "HL" in tipos_low
    )

    bajista = (
        "LH" in tipos_high
        and
        "LL" in tipos_low
    )

    if alcista:
        direccion = "ALCISTA"

    elif bajista:
        direccion = "BAJISTA"

    else:
        direccion = "LATERAL"

    precio = float(
        df["close"].iloc[-1]
    )

    ultimo_high = (
        highs[-1]["price"]
    )

    ultimo_low = (
        lows[-1]["price"]
    )

    penultimo_high = (
        highs[-2]["price"]
        if len(highs) >= 2
        else ultimo_high
    )

    penultimo_low = (
        lows[-2]["price"]
        if len(lows) >= 2
        else ultimo_low
    )

    # -----------------------------------------------------
    # BOS
    # -----------------------------------------------------

    bos = None

    if precio > ultimo_high:

        bos = "BOS_ALCISTA"

    elif precio < ultimo_low:

        bos = "BOS_BAJISTA"

    # -----------------------------------------------------
    # CHOCH
    # -----------------------------------------------------

    choch = None

    if (
        precio > penultimo_high
        and direccion == "BAJISTA"
    ):

        choch = "CHOCH_ALCISTA"

    elif (
        precio < penultimo_low
        and direccion == "ALCISTA"
    ):

        choch = "CHOCH_BAJISTA"

    estructura = (
        f"Highs:{tipos_high[-3:]} "
        f"Lows:{tipos_low[-3:]}"
    )

    return {
        "direccion": direccion,
        "estructura": estructura,
        "bos": bos,
        "choch": choch,
        "highs": highs,
        "lows": lows
    }


# =========================================================
# ZONAS DE LIQUIDEZ
# =========================================================

def detectar_liquidez(df):

    highs, lows = detectar_swings(
        df,
        izquierda=2,
        derecha=2
    )

    if not highs and not lows:

        return {
            "liquidez_alta": [],
            "liquidez_baja": []
        }

    ultimos_highs = [
        x["price"]
        for x in highs[-6:]
    ]

    ultimos_lows = [
        x["price"]
        for x in lows[-6:]
    ]

    return {
        "liquidez_alta": ultimos_highs,
        "liquidez_baja": ultimos_lows
        }


# =========================================================
# CONTEXTO DE MOMENTUM
# =========================================================

def analizar_momentum(df):

    fila = ultima_fila(
        df
    )

    if fila is None:

        return {
            "rsi": np.nan,
            "adx": np.nan,
            "plus_di": np.nan,
            "minus_di": np.nan,
            "ema20": np.nan,
            "ema50": np.nan,
            "ema200": np.nan,
            "atr": np.nan,
            "momentum": "NEUTRAL"
        }

    rsi = numero(
        fila.get("rsi")
    )

    adx = numero(
        fila.get("adx")
    )

    plus_di = numero(
        fila.get("plus_di")
    )

    minus_di = numero(
        fila.get("minus_di")
    )

    ema20 = numero(
        fila.get("ema20")
    )

    ema50 = numero(
        fila.get("ema50")
    )

    ema200 = numero(
        fila.get("ema200")
    )

    close = numero(
        fila.get("close")
    )

    # -----------------------------------------------------
    # MOMENTUM
    # -----------------------------------------------------

    if (
        rsi >= RSI_CONFIRMACION_COMPRA
        and plus_di > minus_di
    ):

        momentum = "ALCISTA"

    elif (
        rsi <= RSI_CONFIRMACION_VENTA
        and minus_di > plus_di
    ):

        momentum = "BAJISTA"

    else:

        momentum = "NEUTRAL"

    return {
        "rsi": rsi,
        "adx": adx,
        "plus_di": plus_di,
        "minus_di": minus_di,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "atr": numero(
            fila.get("atr")
        ),
        "close": close,
        "momentum": momentum
    }


# =========================================================
# RÉGIMEN 15M
# =========================================================

def obtener_regimen(
    df15
):

    estructura = analizar_estructura(
        df15
    )

    momentum = analizar_momentum(
        df15
    )

    direccion = (
        estructura["direccion"]
    )

    mom = (
        momentum["momentum"]
    )

    if (
        direccion == "ALCISTA"
        and mom == "ALCISTA"
    ):

        return "ALCISTA"

    if (
        direccion == "BAJISTA"
        and mom == "BAJISTA"
    ):

        return "BAJISTA"

    return "LATERAL"


# =========================================================
# DETECTAR IMPULSO
# =========================================================

def detectar_impulso(
    df,
    direccion
):

    if len(df) < 8:

        return False

    recientes = df.iloc[-6:]

    atr = numero(
        df["atr"].iloc[-1]
    )

    if not np.isfinite(atr) or atr <= 0:

        return False

    movimiento = (
        recientes["close"].iloc[-1]
        -
        recientes["open"].iloc[0]
    )

    cuerpos = (
        recientes["body_abs"]
        .tail(4)
        .mean()
    )

    if direccion == "COMPRA":

        return (
            movimiento > atr * 0.80
            and
            cuerpos > atr * 0.15
        )

    if direccion == "VENTA":

        return (
            movimiento < -atr * 0.80
            and
            cuerpos > atr * 0.15
        )

    return False


# =========================================================
# DETECTAR PULLBACK
# =========================================================

def detectar_pullback(
    df,
    direccion
):

    if len(df) < 8:

        return False

    recientes = df.iloc[-5:]

    atr = numero(
        df["atr"].iloc[-1]
    )

    if not np.isfinite(atr) or atr <= 0:

        return False

    maximo = (
        recientes["high"].max()
    )

    minimo = (
        recientes["low"].min()
    )

    cierre = (
        recientes["close"].iloc[-1]
    )

    if direccion == "COMPRA":

        distancia = (
            maximo - cierre
        )

        return (
            distancia > atr * 0.15
            and
            distancia < atr * 1.20
        )

    if direccion == "VENTA":

        distancia = (
            cierre - minimo
        )

        return (
            distancia > atr * 0.15
            and
            distancia < atr * 1.20
        )

    return False


# =========================================================
# VELA DE CONTINUACIÓN
# =========================================================

def detectar_continuacion(
    df,
    direccion
):

    if len(df) < 3:

        return False

    ultima = df.iloc[-1]

    anterior = df.iloc[-2]

    atr = numero(
        ultima["atr"]
    )

    if not np.isfinite(atr) or atr <= 0:

        return False

    cuerpo = abs(
        ultima["close"]
        - ultima["open"]
    )

    if cuerpo < atr * 0.20:

        return False

    if direccion == "COMPRA":

        return (
            ultima["close"]
            > ultima["open"]
            and
            ultima["close"]
            > anterior["high"]
        )

    if direccion == "VENTA":

        return (
            ultima["close"]
            < ultima["open"]
            and
            ultima["close"]
            < anterior["low"]
        )

    return False


# =========================================================
# SCORE
# =========================================================

def calcular_score(
    direccion,
    estructura5,
    estructura15,
    momentum5,
    momentum15,
    impulso,
    pullback,
    continuacion
):

    score = 0

    razones = []

    # -----------------------------------------------------
    # ESTRUCTURA 5M
    # -----------------------------------------------------

    if direccion == "COMPRA":

        if estructura5["direccion"] == "ALCISTA":

            score += 20
            razones.append(
                "Estructura 5M alcista"
            )

        if estructura5["bos"] == "BOS_ALCISTA":

            score += 12
            razones.append(
                "BOS alcista"
            )

        if estructura5["choch"] == "CHOCH_ALCISTA":

            score += 8
            razones.append(
                "CHoCH alcista"
            )

    elif direccion == "VENTA":

        if estructura5["direccion"] == "BAJISTA":

            score += 20
            razones.append(
                "Estructura 5M bajista"
            )

        if estructura5["bos"] == "BOS_BAJISTA":

            score += 12
            razones.append(
                "BOS bajista"
            )

        if estructura5["choch"] == "CHOCH_BAJISTA":

            score += 8
            razones.append(
                "CHoCH bajista"
            )

    # -----------------------------------------------------
    # CONTEXTO 15M
    # -----------------------------------------------------

    if (
        direccion == "COMPRA"
        and
        estructura15["direccion"]
        == "ALCISTA"
    ):

        score += 15

        razones.append(
            "Contexto 15M alcista"
        )

    elif (
        direccion == "VENTA"
        and
        estructura15["direccion"]
        == "BAJISTA"
    ):

        score += 15

        razones.append(
            "Contexto 15M bajista"
        )

    # -----------------------------------------------------
    # MOMENTUM
    # -----------------------------------------------------

    if (
        direccion == "COMPRA"
        and
        momentum5["momentum"]
        == "ALCISTA"
    ):

        score += 12

        razones.append(
            "Momentum 5M alcista"
        )

    elif (
        direccion == "VENTA"
        and
        momentum5["momentum"]
        == "BAJISTA"
    ):

        score += 12

        razones.append(
            "Momentum 5M bajista"
        )

    # -----------------------------------------------------
    # ADX
    # -----------------------------------------------------

    adx = momentum5["adx"]

    if np.isfinite(adx):

        if adx >= ADX_MINIMO:

            score += 6

            razones.append(
                f"ADX {adx:.1f}"
            )

    # -----------------------------------------------------
    # IMPULSO
    # -----------------------------------------------------

    if impulso:

        score += 10

        razones.append(
            "Impulso detectado"
        )

    # -----------------------------------------------------
    # PULLBACK
    # -----------------------------------------------------

    if pullback:

        score += 10

        razones.append(
            "Pullback detectado"
        )

    # -----------------------------------------------------
    # CONTINUACIÓN
    # -----------------------------------------------------

    if continuacion:

        score += 15

        razones.append(
            "Continuación detectada"
        )

    return min(
        score,
        100
    ), razones


# =========================================================
# DIRECCIÓN CANDIDATA
# =========================================================

def determinar_direccion(
    estructura5,
    estructura15,
    momentum5
):

    # -----------------------------------------------------
    # COMPRA
    # -----------------------------------------------------

    compra = 0

    if (
        estructura5["direccion"]
        == "ALCISTA"
    ):

        compra += 2

    if (
        estructura15["direccion"]
        == "ALCISTA"
    ):

        compra += 2

    if (
        momentum5["momentum"]
        == "ALCISTA"
    ):

        compra += 1

    # -----------------------------------------------------
    # VENTA
    # -----------------------------------------------------

    venta = 0

    if (
        estructura5["direccion"]
        == "BAJISTA"
    ):

        venta += 2

    if (
        estructura15["direccion"]
        == "BAJISTA"
    ):

        venta += 2

    if (
        momentum5["momentum"]
        == "BAJISTA"
    ):

        venta += 1

    if compra >= 3 and compra > venta:

        return "COMPRA"

    if venta >= 3 and venta > compra:

        return "VENTA"

    return None


# =========================================================
# NIVELES SL / TP
# =========================================================

def calcular_niveles(
    df,
    direccion
):

    precio = float(
        df["close"].iloc[-1]
    )

    atr = float(
        df["atr"].iloc[-1]
    )

    if not np.isfinite(atr) or atr <= 0:

        return None

    if direccion == "COMPRA":

        sl = (
            precio
            - atr * ATR_SL
        )

        tp = (
            precio
            + atr * ATR_TP
        )

    elif direccion == "VENTA":

        sl = (
            precio
            + atr * ATR_SL
        )

        tp = (
            precio
            - atr * ATR_TP
        )

    else:

        return None

    riesgo = abs(
        precio - sl
    )

    recompensa = abs(
        tp - precio
    )

    if riesgo <= 0:

        return None

    rr = (
        recompensa
        / riesgo
    )

    return {
        "precio": precio,
        "sl": sl,
        "tp": tp,
        "atr": atr,
        "rr": rr
    }


# =========================================================
# VALIDAR RR
# =========================================================

def validar_rr(
    niveles
):

    if not niveles:

        return False

    return (
        niveles["rr"]
        >= RR_MINIMO
    )


# =========================================================
# CREAR SETUP
# =========================================================

def crear_setup(
    direccion,
    df5,
    estructura5,
    estructura15,
    momentum5,
    momentum15,
    score,
    razones
):

    niveles = calcular_niveles(
        df5,
        direccion
    )

    if not niveles:

        return None

    if not validar_rr(
        niveles
    ):

        return None

    precio = niveles["precio"]

    return {
        "id": nuevo_id(),
        "estado": "PREALERTA",
        "direccion": direccion,

        "creado": ahora_utc().isoformat(),

        "precio_prealerta": precio,

        "sl": niveles["sl"],
        "tp": niveles["tp"],
        "atr": niveles["atr"],
        "rr": niveles["rr"],

        "score_prealerta": score,

        "razones": razones,

        "estructura5": (
            estructura5["direccion"]
        ),

        "estructura15": (
            estructura15["direccion"]
        ),

        "momentum5": (
            momentum5["momentum"]
        ),

        "momentum15": (
            momentum15["momentum"]
        ),

        "rsi": momentum5["rsi"],
        "adx": momentum5["adx"],

        "ultimo_precio": precio
    }


# =========================================================
# FORMATEAR PREALERTA
# =========================================================

def mensaje_prealerta(
    setup
):

    direccion = setup[
        "direccion"
    ]

    emoji = (
        "🟢"
        if direccion == "COMPRA"
        else "🔴"
    )

    razones = setup.get(
        "razones",
        []
    )

    razones_texto = "\n".join(
        f"• {r}"
        for r in razones[-6:]
    )

    return (
        f"🟡 PREALERTA XAU/USD\n\n"

        f"{emoji} POSIBLE "
        f"{direccion}\n\n"

        f"🆔 ID: "
        f"{setup['id']}\n"

        f"⭐ Score: "
        f"{setup['score_prealerta']}/100\n\n"

        f"💰 Precio: "
        f"{setup['precio_prealerta']:.2f}\n"

        f"🛑 SL referencia: "
        f"{setup['sl']:.2f}\n"

        f"🎯 TP referencia: "
        f"{setup['tp']:.2f}\n"

        f"📐 RR: "
        f"{setup['rr']:.2f}\n\n"

        f"📊 5M: "
        f"{setup['estructura5']}\n"

        f"📊 15M: "
        f"{setup['estructura15']}\n"

        f"⚡ Momentum: "
        f"{setup['momentum5']}\n"

        f"RSI: "
        f"{setup['rsi']:.1f}\n"

        f"ADX: "
        f"{setup['adx']:.1f}\n\n"

        f"🧠 Factores:\n"
        f"{razones_texto}\n\n"

        f"⚠️ PREALERTA\n"
        f"La oportunidad todavía "
        f"NO está confirmada.\n\n"

        f"🔍 El motor seguirá vigilando "
        f"este mismo setup."
    )


# =========================================================
# FORMATEAR CONFIRMACIÓN
# =========================================================

def mensaje_confirmada(
    setup,
    niveles,
    score
):

    direccion = setup[
        "direccion"
    ]

    emoji = (
        "🟢"
        if direccion == "COMPRA"
        else "🔴"
    )

    return (
        f"🟢 SEÑAL CONFIRMADA XAU/USD\n\n"

        f"{emoji} {direccion}\n\n"

        f"🆔 ID: "
        f"{setup['id']}\n"

        f"⭐ Score: "
        f"{score}/100\n\n"

        f"💰 Precio confirmación: "
        f"{niveles['precio']:.2f}\n"

        f"🛑 SL referencia: "
        f"{niveles['sl']:.2f}\n"

        f"🎯 TP referencia: "
        f"{niveles['tp']:.2f}\n"

        f"📐 RR: "
        f"{niveles['rr']:.2f}\n\n"

        f"📊 Estructura 5M: "
        f"{setup['estructura5']}\n"

        f"📊 Contexto 15M: "
        f"{setup['estructura15']}\n"

        f"⚡ Momentum: "
        f"{setup['momentum5']}\n\n"

        f"💥 Continuación confirmada.\n"
        f"🧠 Setup evolucionó desde "
        f"la prealerta."
    )


# =========================================================
# FORMATEAR DESCARTADA
# =========================================================

def mensaje_descartada(
    setup,
    precio,
    motivo
):

    direccion = setup[
        "direccion"
    ]

    emoji = (
        "🟢"
        if direccion == "COMPRA"
        else "🔴"
    )

    return (
        f"🔴 PREALERTA DESCARTADA\n\n"

        f"{emoji} {direccion}\n"

        f"🆔 ID: "
        f"{setup['id']}\n\n"

        f"💰 Precio actual: "
        f"{precio:.2f}\n\n"

        f"❌ Motivo:\n"
        f"{motivo}\n\n"

        f"🧠 El setup quedó invalidado.\n"
        f"No se convertirá en confirmación."
    )


# =========================================================
# VALIDAR SETUP ACTIVO
# =========================================================

def evaluar_setup_activo(
    setup,
    df5,
    df15,
    estructura5,
    estructura15,
    momentum5,
    momentum15
):

    precio = float(
        df5["close"].iloc[-1]
    )

    direccion = setup[
        "direccion"
    ]

    # -----------------------------------------------------
    # ACTUALIZAR PRECIO
    # -----------------------------------------------------

    setup[
        "ultimo_precio"
    ] = precio

    # -----------------------------------------------------
    # INVALIDACIÓN POR SL
    # -----------------------------------------------------

    if direccion == "COMPRA":

        if precio <= setup["sl"]:

            return {
                "estado": "DESCARTADA",
                "motivo":
                    "El precio alcanzó "
                    "la zona de invalidación."
            }

    elif direccion == "VENTA":

        if precio >= setup["sl"]:

            return {
                "estado": "DESCARTADA",
                "motivo":
                    "El precio alcanzó "
                    "la zona de invalidación."
            }

    # -----------------------------------------------------
    # CONTEXTO 15M INVALIDADO
    # -----------------------------------------------------

    if direccion == "COMPRA":

        if (
            estructura15["direccion"]
            == "BAJISTA"
        ):

            return {
                "estado": "DESCARTADA",
                "motivo":
                    "El contexto 15M "
                    "cambió a bajista."
            }

    if direccion == "VENTA":

        if (
            estructura15["direccion"]
            == "ALCISTA"
        ):

            return {
                "estado": "DESCARTADA",
                "motivo":
                    "El contexto 15M "
                    "cambió a alcista."
            }

    # -----------------------------------------------------
    # MOMENTUM
    # -----------------------------------------------------

    rsi = momentum5["rsi"]

    if direccion == "COMPRA":

        if (
            np.isfinite(rsi)
            and
            rsi < RSI_VENTA
        ):

            return {
                "estado": "DESCARTADA",
                "motivo":
                    f"RSI cayó a "
                    f"{rsi:.1f}."
            }

    if direccion == "VENTA":

        if (
            np.isfinite(rsi)
            and
            rsi > RSI_COMPRA
        ):

            return {
                "estado": "DESCARTADA",
                "motivo":
                    f"RSI subió a "
                    f"{rsi:.1f}."
            }

    # -----------------------------------------------------
    # CONFIRMACIÓN
    # -----------------------------------------------------

    continuacion = (
        detectar_continuacion(
            df5,
            direccion
        )
    )

    adx = momentum5["adx"]

    adx_ok = (
        np.isfinite(adx)
        and
        adx >= ADX_MINIMO
    )

    rsi_ok = False

    if direccion == "COMPRA":

        rsi_ok = (
            np.isfinite(rsi)
            and
            rsi >=
            RSI_CONFIRMACION_COMPRA
        )

    elif direccion == "VENTA":

        rsi_ok = (
            np.isfinite(rsi)
            and
            rsi <=
            RSI_CONFIRMACION_VENTA
        )

    contexto_ok = False

    if direccion == "COMPRA":

        contexto_ok = (
            estructura15["direccion"]
            == "ALCISTA"
        )

    elif direccion == "VENTA":

        contexto_ok = (
            estructura15["direccion"]
            == "BAJISTA"
        )

    estructura_ok = False

    if direccion == "COMPRA":

        estructura_ok = (
            estructura5["direccion"]
            == "ALCISTA"
            or
            estructura5["bos"]
            == "BOS_ALCISTA"
            or
            estructura5["choch"]
            == "CHOCH_ALCISTA"
        )

    elif direccion == "VENTA":

        estructura_ok = (
            estructura5["direccion"]
            == "BAJISTA"
            or
            estructura5["bos"]
            == "BOS_BAJISTA"
            or
            estructura5["choch"]
            == "CHOCH_BAJISTA"
        )

    # -----------------------------------------------------
    # SCORE DE CONFIRMACIÓN
    # -----------------------------------------------------

    score = 0

    if estructura_ok:
        score += 25

    if contexto_ok:
        score += 20

    if continuacion:
        score += 25

    if rsi_ok:
        score += 15

    if adx_ok:
        score += 15

    score = min(
        score,
        100
    )

    # -----------------------------------------------------
    # CONFIRMADA
    # -----------------------------------------------------

    if (
        score >= MIN_SCORE_CONFIRMACION
        and
        continuacion
        and
        contexto_ok
        and
        rsi_ok
    ):

        niveles = calcular_niveles(
            df5,
            direccion
        )

        if niveles and validar_rr(
            niveles
        ):

            return {
                "estado": "CONFIRMADA",
                "niveles": niveles,
                "score": score
            }

    # -----------------------------------------------------
    # TODAVÍA VÁLIDA
    # -----------------------------------------------------

    return {
        "estado": "PENDIENTE",
        "score": score
    }


# =========================================================
# CONSTRUIR PREALERTA
# =========================================================

def buscar_prealerta(
    df5,
    df15
):

    estructura5 = (
        analizar_estructura(
            df5
        )
    )

    estructura15 = (
        analizar_estructura(
            df15
        )
    )

    momentum5 = (
        analizar_momentum(
            df5
        )
    )

    momentum15 = (
        analizar_momentum(
            df15
        )
    )

    direccion = (
        determinar_direccion(
            estructura5,
            estructura15,
            momentum5
        )
    )

    if direccion is None:

        return None

    impulso = (
        detectar_impulso(
            df5,
            direccion
        )
    )

    pullback = (
        detectar_pullback(
            df5,
            direccion
        )
    )

    continuacion = (
        detectar_continuacion(
            df5,
            direccion
        )
    )

    score, razones = (
        calcular_score(
            direccion,
            estructura5,
            estructura15,
            momentum5,
            momentum15,
            impulso,
            pullback,
            continuacion
        )
    )

    # -----------------------------------------------------
    # UNA PREALERTA REQUIERE ALGO MÁS QUE "EMA ARRIBA"
    # -----------------------------------------------------

    setup_valido = (
        score >= MIN_SCORE_PREALERTA
        and
        (
            impulso
            or
            pullback
            or
            estructura5["bos"]
            is not None
            or
            estructura5["choch"]
            is not None
        )
    )

    if not setup_valido:

        return None

    setup = crear_setup(
        direccion,
        df5,
        estructura5,
        estructura15,
        momentum5,
        momentum15,
        score,
        razones
    )

    return setup


# =========================================================
# DIAGNÓSTICO
# =========================================================

def diagnostico(
    df5,
    df15
):

    estructura5 = (
        analizar_estructura(
            df5
        )
    )

    estructura15 = (
        analizar_estructura(
            df15
        )
    )

    momentum5 = (
        analizar_momentum(
            df5
        )
    )

    momentum15 = (
        analizar_momentum(
            df15
        )
    )

    precio = float(
        df5["close"].iloc[-1]
    )

    print(
        "-----------------------------------"
    )

    print(
        f"💰 Precio: {precio:.2f}"
    )

    print(
        "📊 5M:",
        estructura5["direccion"]
    )

    print(
        "📊 15M:",
        estructura15["direccion"]
    )

    print(
        "⚡ Momentum 5M:",
        momentum5["momentum"]
    )

    print(
        f"RSI 5M: "
        f"{momentum5['rsi']:.2f}"
    )

    print(
        f"ADX 5M: "
        f"{momentum5['adx']:.2f}"
    )

    print(
        "⚡ Momentum 15M:",
        momentum15["momentum"]
    )

    print(
        f"RSI 15M: "
        f"{momentum15['rsi']:.2f}"
    )

    print(
        f"ADX 15M: "
        f"{momentum15['adx']:.2f}"
    )

    print(
        "-----------------------------------"
    )


# =========================================================
# FUNCIÓN PRINCIPAL
# =========================================================
#
# ESTA ES LA FUNCIÓN QUE BOT.PY IMPORTA:
#
# from strategy import analizar
#
# =========================================================

def analizar():

    global SETUP_ACTIVO

    try:

        print(
            "📡 Obteniendo datos desde BiQuote..."
        )

        # -------------------------------------------------
        # MERCADO
        # -------------------------------------------------

        df5, df15 = (
            cargar_mercado()
        )

        # -------------------------------------------------
        # INDICADORES
        # -------------------------------------------------

        df5 = calcular_indicadores(
            df5
        )

        df15 = calcular_indicadores(
            df15
        )

        if not validar_dataframe(
            df5
        ):

            return {
                "tipo": "ERROR",
                "id": None,
                "mensaje":
                    "❌ BiQuote: "
                    "datos 5M insuficientes."
            }

        if not validar_dataframe(
            df15
        ):

            return {
                "tipo": "ERROR",
                "id": None,
                "mensaje":
                    "❌ BiQuote: "
                    "datos 15M insuficientes."
            }

        # -------------------------------------------------
        # DIAGNÓSTICO
        # -------------------------------------------------

        diagnostico(
            df5,
            df15
        )

        # =================================================
        # SI YA EXISTE PREALERTA
        # =================================================

        if SETUP_ACTIVO is not None:

            print(
                "🟡 Setup activo:",
                SETUP_ACTIVO["id"]
            )

            estructura5 = (
                analizar_estructura(
                    df5
                )
            )

            estructura15 = (
                analizar_estructura(
                    df15
                )
            )

            momentum5 = (
                analizar_momentum(
                    df5
                )
            )

            momentum15 = (
                analizar_momentum(
                    df15
                )

            )

            evaluacion = (
                evaluar_setup_activo(
                    SETUP_ACTIVO,
                    df5,
                    df15,
                    estructura5,
                    estructura15,
                    momentum5,
                    momentum15
                )
            )

            estado = (
                evaluacion["estado"]
            )

            # ---------------------------------------------
            # CONFIRMADA
            # ---------------------------------------------

            if estado == "CONFIRMADA":

                niveles = (
                    evaluacion["niveles"]
                )

                score = (
                    evaluacion["score"]
                )

                mensaje = (
                    mensaje_confirmada(
                        SETUP_ACTIVO,
                        niveles,
                        score
                    )
                )

                identificador = (
                    SETUP_ACTIVO["id"]
                )

                SETUP_ACTIVO = None

                print(
                    "🟢 PREALERTA CONFIRMADA"
                )

                return {
                    "tipo": "CONFIRMADA",
                    "id": identificador,
                    "mensaje": mensaje
                }

            # ---------------------------------------------
            # DESCARTADA
            # ---------------------------------------------

            if estado == "DESCARTADA":

                precio = float(
                    df5["close"].iloc[-1]
                )

                motivo = (
                    evaluacion.get(
                        "motivo",
                        "Estructura invalidada."
                    )
                )

                identificador = (
                    SETUP_ACTIVO["id"]
                )

                mensaje = (
                    mensaje_descartada(
                        SETUP_ACTIVO,
                        precio,
                        motivo
                    )
                )

                SETUP_ACTIVO = None

                print(
                    "🔴 PREALERTA DESCARTADA"
                )

                return {
                    "tipo": "DESCARTADA",
                    "id": identificador,
                    "mensaje": mensaje
                }

            # ---------------------------------------------
            # TODAVÍA PENDIENTE
            # ---------------------------------------------

            print(
                "🟡 Setup sigue pendiente:"
                f" {SETUP_ACTIVO['id']}"
            )

            return {
                "tipo": "SIN_SEÑAL",
                "id": SETUP_ACTIVO["id"],
                "mensaje":
                    "🟡 Setup activo. "
                    "Esperando confirmación."
            }

        # =================================================
        # NO EXISTE SETUP
        # BUSCAR PREALERTA
        # =================================================

        setup = (
            buscar_prealerta(
                df5,
                df15
            )
        )

        if setup is None:

            print(
                "😴 SIN SEÑAL"
            )

            return {
                "tipo": "SIN_SEÑAL",
                "id": None,
                "mensaje":
                    "😴 Sin señal."
            }

        # -------------------------------------------------
        # GUARDAR PREALERTA
        # -------------------------------------------------

        SETUP_ACTIVO = setup

        print(
            "🟡 NUEVA PREALERTA:",
            setup["id"]
        )

        return {
            "tipo": "PREALERTA",
            "id": setup["id"],
            "mensaje":
                mensaje_prealerta(
                    setup
                )
        }

    except Exception as e:

        logger.exception(
            "❌ ERROR EN STRATEGY"
        )

        return {
            "tipo": "ERROR",
            "id": None,
            "mensaje":
                (
                    "❌ Error V4.2\n\n"
                    f"{type(e).__name__}: "
                    f"{e}"
                )
        }
