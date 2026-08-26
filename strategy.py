import requests
import pandas as pd
import os
import uuid
import time
from datetime import datetime, timezone

from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


# ============================================================
# XAU SNIPER AI V4.2.1
# MOTOR DE ESTRUCTURA + MOMENTUM + LIQUIDEZ
#
# DATOS:
# BIQUOTE
#
# RÉGIMEN
# ↓
# ESTRUCTURA
# ↓
# BOS / CHoCH
# ↓
# IMPULSO
# ↓
# PULLBACK
# ↓
# LIQUIDEZ
# ↓
# UBICACIÓN
# ↓
# MOMENTUM
# ↓
# CONTINUACIÓN
# ↓
# SCORE
# ↓
# PREALERTA
# ↓
# CONFIRMACIÓN / DESCARTADA
# ============================================================


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

SYMBOL = "XAUUSD"

INTERVALO_5M = "5m"
INTERVALO_15M = "15m"

BIQUOTE_BASE_URL = "https://biquote.io/api"


# ============================================================
# DATOS
# ============================================================

OUTPUTSIZE_5M = 250
OUTPUTSIZE_15M = 250

INTERVALO_ANALISIS = 300

TIMEOUT_API = 15
MAX_INTENTOS_API = 2


# ============================================================
# CACHE DE DATOS
# ============================================================

CACHE_5M = {
    "df": None,
    "timestamp": 0
}

CACHE_15M = {
    "df": None,
    "timestamp": 0
}

CACHE_MAX_5M = 240
CACHE_MAX_15M = 840


# ============================================================
# CICLO DE SEÑAL
# ============================================================

MINUTOS_REPETICION = 15

MINUTOS_VIDA_PREALERTA = 30

COOLDOWN_DESCARTADA = 10


# ============================================================
# SCORE
# ============================================================

SCORE_MIN_PREALERTA = 68

SCORE_MIN_CONFIRMACION = 76


# ============================================================
# RSI / ADX
# ============================================================

RSI_COMPRA_MIN = 50
RSI_VENTA_MAX = 50

RSI_CONFIRMACION_COMPRA = 53
RSI_CONFIRMACION_VENTA = 47

ADX_MINIMO = 15
ADX_FUERTE = 25


# ============================================================
# ATR
# ============================================================

ATR_SL = 1.30
ATR_TP = 2.20

RR_MINIMO = 1.50


# ============================================================
# ESTRUCTURA
# ============================================================

SWING_LEFT = 2
SWING_RIGHT = 2

SWING_ATR_MIN = 0.25

BREAK_BUFFER_ATR = 0.05

CHOCH_MIN_ATR = 0.15


# ============================================================
# IMPULSO
# ============================================================

IMPULSO_LOOKBACK = 20

IMPULSO_MIN_VELAS = 4

IMPULSO_MAX_VELAS = 12

IMPULSO_ATR_MIN = 0.80

IMPULSO_FUERTE_ATR = 1.20

IMPULSO_VELAS_MIN = 3

EFICIENCIA_MINIMA = 0.45

RATIO_CUERPO_MIN = 0.40


# ============================================================
# PULLBACK
# ============================================================

PULLBACK_VELAS_MIN = 2

PULLBACK_VELAS_MAX = 7

PULLBACK_MIN_ATR = 0.20

PULLBACK_MAX_ATR = 1.60

PULLBACK_MAX_RETRACEMENT = 0.75

PULLBACK_MIN_RETRACEMENT = 0.20


# ============================================================
# CONTINUACIÓN
# ============================================================

CUERPO_CONTINUACION_ATR = 0.18

CONTINUACION_ATR_MIN = 0.05


# ============================================================
# ENTRADA TARDÍA
# ============================================================

MAX_DISTANCIA_ENTRADA_ATR = 1.20


# ============================================================
# LIQUIDEZ
# ============================================================

LIQUIDEZ_LOOKBACK = 20

LIQUIDEZ_BUFFER_ATR = 0.08


# ============================================================
# UBICACIÓN
# ============================================================

ZONA_MAX_ATR = 0.80


# ============================================================
# ESTADO GLOBAL
# ============================================================

estado = {

    "direccion_pendiente": None,

    "id_pendiente": None,

    "inicio_pendiente": 0,

    "ultima_prealerta": 0,

    "ultima_confirmacion": 0,

    "ultima_descartada": 0,

    "precio_prealerta": None,

    "atr_prealerta": None,

    "impulso_inicio": None,

    "impulso_extremo": None,

    "impulso_indice_extremo": None,

    "pullback_nivel": None,

    "nivel_continuacion": None,

    "swing_referencia": None,

    "maximo_confirmacion": None,

    "minimo_confirmacion": None,

    "velas_pendiente": 0
}


# ============================================================
# LIMPIAR PENDIENTE
# ============================================================

def limpiar_pendiente():

    estado["direccion_pendiente"] = None
    estado["id_pendiente"] = None
    estado["inicio_pendiente"] = 0

    estado["precio_prealerta"] = None
    estado["atr_prealerta"] = None

    estado["impulso_inicio"] = None
    estado["impulso_extremo"] = None
    estado["impulso_indice_extremo"] = None

    estado["pullback_nivel"] = None
    estado["nivel_continuacion"] = None
    estado["swing_referencia"] = None

    estado["maximo_confirmacion"] = None
    estado["minimo_confirmacion"] = None

    estado["velas_pendiente"] = 0


# ============================================================
# ID
# ============================================================

def generar_id():

    return uuid.uuid4().hex[:8].upper()


# ============================================================
# NORMALIZAR RESPUESTA BIQUOTE
# ============================================================

def normalizar_biquote(values):

    if not isinstance(values, list):

        raise Exception(
            "Biquote: bars no es una lista."
        )

    if len(values) < 50:

        raise Exception(
            f"Biquote devolvió pocas velas: {len(values)}"
        )

    df = pd.DataFrame(values)

    # Biquote normalmente usa:
    # openTime, open, high, low, close, volume, isOpen

    mapa = {}

    if "openTime" in df.columns:
        mapa["openTime"] = "datetime"

    elif "datetime" in df.columns:
        mapa["datetime"] = "datetime"

    elif "time" in df.columns:
        mapa["time"] = "datetime"

    elif "timestamp" in df.columns:
        mapa["timestamp"] = "datetime"

    else:

        raise Exception(
            "Biquote: no se encontró columna temporal."
        )

    for original, nuevo in mapa.items():

        df[nuevo] = df[original]

    requeridas = [
        "open",
        "high",
        "low",
        "close",
        "datetime"
    ]

    faltantes = [
        c for c in requeridas
        if c not in df.columns
    ]

    if faltantes:

        raise Exception(
            f"Biquote: faltan columnas {faltantes}"
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

    # ========================================================
    # FECHA
    # ========================================================

    fecha = df["datetime"]

    if pd.api.types.is_numeric_dtype(fecha):

        valores = pd.to_numeric(
            fecha,
            errors="coerce"
        )

        maximo = valores.max()

        if maximo > 10_000_000_000:

            df["datetime"] = pd.to_datetime(
                valores,
                unit="ms",
                utc=True,
                errors="coerce"
            )

        else:

            df["datetime"] = pd.to_datetime(
                valores,
                unit="s",
                utc=True,
                errors="coerce"
            )

    else:

        df["datetime"] = pd.to_datetime(
            fecha,
            utc=True,
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "open",
            "high",
            "low",
            "close",
            "datetime"
        ]
    )

    df = df.sort_values(
        "datetime"
    )

    df = df.drop_duplicates(
        subset=["datetime"]
    )

    df = df.reset_index(
        drop=True
    )

    # ========================================================
    # IDENTIFICAR VELA ABIERTA
    # ========================================================

    if "isOpen" in df.columns:

        df["isOpen"] = (
            df["isOpen"]
            .astype(str)
            .str.lower()
            .isin([
                "true",
                "1",
                "yes"
            ])
        )

    else:

        df["isOpen"] = False

    return df


# ============================================================
# OBTENER DATOS DESDE BIQUOTE
# ============================================================

def obtener_datos(intervalo):

    if intervalo == INTERVALO_5M:

        cache = CACHE_5M
        outputsize = OUTPUTSIZE_5M
        max_cache = CACHE_MAX_5M

    elif intervalo == INTERVALO_15M:

        cache = CACHE_15M
        outputsize = OUTPUTSIZE_15M
        max_cache = CACHE_MAX_15M

    else:

        raise Exception(
            f"Intervalo no soportado: {intervalo}"
        )

    ahora = time.time()

    # ========================================================
    # CACHE
    # ========================================================

    if (
        cache["df"] is not None
        and
        ahora - cache["timestamp"] < max_cache
    ):

        return cache["df"].copy()

    url = (
        f"{BIQUOTE_BASE_URL}/"
        f"{SYMBOL}/ohlc"
    )

    params = {
        "interval": intervalo,
        "limit": outputsize
    }

    for intento in range(
        1,
        MAX_INTENTOS_API + 1
    ):

        try:

            respuesta = requests.get(
                url,
                params=params,
                timeout=TIMEOUT_API
            )

            respuesta.raise_for_status()

            data = respuesta.json()

            if not isinstance(data, dict):

                raise Exception(
                    "Respuesta Biquote inválida."
                )

            if "bars" not in data:

                raise Exception(
                    f"Biquote sin bars: {data}"
                )

            df = normalizar_biquote(
                data["bars"]
            )

            if len(df) < 220:

                raise Exception(
                    f"Datos insuficientes "
                    f"{intervalo}: "
                    f"{len(df)} velas."
                )

            cache["df"] = df.copy()
            cache["timestamp"] = time.time()

            print(
                f"📥 Biquote {intervalo}: "
                f"{len(df)} velas"
            )

            return df

        except requests.exceptions.Timeout:

            print(
                f"⚠️ Timeout Biquote "
                f"{intervalo} "
                f"| {intento}/{MAX_INTENTOS_API}"
            )

            if intento >= MAX_INTENTOS_API:

                raise Exception(
                    f"Timeout Biquote {intervalo}"
                )

            time.sleep(
                2 * intento
            )

        except requests.exceptions.RequestException as e:

            print(
                f"⚠️ Error HTTP Biquote "
                f"{intervalo}: {e}"
            )

            if intento >= MAX_INTENTOS_API:

                raise Exception(
                    f"Error HTTP Biquote: {e}"
                )

            time.sleep(
                2 * intento
            )

        except Exception:

            raise

    raise Exception(
        f"No se pudieron obtener datos {intervalo}"
    )


# ============================================================
# INDICADORES
# ============================================================

def calcular_indicadores(df):

    if df is None or df.empty:

        raise Exception(
            "DataFrame vacío en indicadores."
        )

    df = df.copy()

    if len(df) < 220:

        raise Exception(
            f"Se requieren al menos 220 velas. "
            f"Recibidas: {len(df)}"
        )

    df["ema20"] = EMAIndicator(
        close=df["close"],
        window=20
    ).ema_indicator()

    df["ema50"] = EMAIndicator(
        close=df["close"],
        window=50
    ).ema_indicator()

    df["ema200"] = EMAIndicator(
        close=df["close"],
        window=200
    ).ema_indicator()

    df["rsi"] = RSIIndicator(
        close=df["close"],
        window=14
    ).rsi()

    df["atr"] = AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    ).average_true_range()

    adx = ADXIndicator(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    df["adx"] = adx.adx()

    df["di_plus"] = adx.adx_pos()

    df["di_minus"] = adx.adx_neg()

    df["cuerpo"] = (
        df["close"] -
        df["open"]
    ).abs()

    df["rango"] = (
        df["high"] -
        df["low"]
    )

    df["direccion_vela"] = 0

    df.loc[
        df["close"] > df["open"],
        "direccion_vela"
    ] = 1

    df.loc[
        df["close"] < df["open"],
        "direccion_vela"
    ] = -1

    df["mecha_superior"] = (
        df["high"] -
        df[["open", "close"]].max(axis=1)
    )

    df["mecha_inferior"] = (
        df[["open", "close"]].min(axis=1) -
        df["low"]
    )

    df["rango_medio"] = (
        df["rango"]
        .rolling(20)
        .mean()
    )

    df["expansion"] = (
        df["rango"] >
        df["rango_medio"] * 1.10
    )

    df["pendiente_ema20"] = (
        df["ema20"] -
        df["ema20"].shift(3)
    )

    df["pendiente_ema50"] = (
        df["ema50"] -
        df["ema50"].shift(3)
    )

    df["rsi_slope"] = (
        df["rsi"] -
        df["rsi"].shift(3)
    )

    df["di_separacion"] = (
        df["di_plus"] -
        df["di_minus"]
    ).abs()

    cambio = (
        df["close"] -
        df["close"].shift(5)
    ).abs()

    rango_total = (
        df["rango"]
        .rolling(5)
        .sum()
    )

    df["eficiencia"] = (
        cambio /
        rango_total.replace(0, pd.NA)
    )

    df = df.replace(
        [float("inf"), float("-inf")],
        pd.NA
    )

    df = df.dropna().reset_index(
        drop=True
    )

    if len(df) < 100:

        raise Exception(
            f"Después de indicadores quedaron "
            f"{len(df)} velas útiles."
        )

    return df


# ============================================================
# SOLO VELAS CERRADAS
# ============================================================

def velas_cerradas(df):

    if df is None:

        return pd.DataFrame()

    if df.empty:

        return df.copy()

    # Biquote marca explícitamente la vela abierta.
    if "isOpen" in df.columns:

        cerradas = df[
            ~df["isOpen"]
        ].copy()

        if len(cerradas) >= 5:

            return cerradas.reset_index(
                drop=True
            )

    # Fallback:
    # quitamos la última si no hay bandera.
    if len(df) >= 5:

        return df.iloc[:-1].copy()

    return df.copy()


# ============================================================
# DETECTAR SWINGS
# ============================================================

def detectar_swings(df):

    highs = []
    lows = []

    if df is None or len(df) < 10:

        return highs, lows

    inicio = SWING_LEFT

    final = len(df) - SWING_RIGHT

    for i in range(
        inicio,
        final
    ):

        try:

            high_actual = float(
                df.iloc[i]["high"]
            )

            low_actual = float(
                df.iloc[i]["low"]
            )

            atr = float(
                df.iloc[i]["atr"]
            )

            if atr <= 0:

                continue

            altos_izq = df.iloc[
                i - SWING_LEFT:i
            ]["high"]

            altos_der = df.iloc[
                i + 1:
                i + 1 + SWING_RIGHT
            ]["high"]

            bajos_izq = df.iloc[
                i - SWING_LEFT:i
            ]["low"]

            bajos_der = df.iloc[
                i + 1:
                i + 1 + SWING_RIGHT
            ]["low"]

            es_high = (
                high_actual >= altos_izq.max()
                and
                high_actual >= altos_der.max()
            )

            es_low = (
                low_actual <= bajos_izq.min()
                and
                low_actual <= bajos_der.min()
            )

            if es_high:

                highs.append({
                    "index": i,
                    "precio": high_actual,
                    "atr": atr
                })

            if es_low:

                lows.append({
                    "index": i,
                    "precio": low_actual,
                    "atr": atr
                })

        except Exception:

            continue

    return highs, lows


# ============================================================
# SWINGS ANTERIORES
# ============================================================

def obtener_swings_anteriores(
    swings,
    cantidad=4
):

    if not swings:

        return []

    return swings[-cantidad:]


# ============================================================
# ANALIZAR ESTRUCTURA
# ============================================================

def analizar_estructura(df):

    resultado = {

        "direccion": "NEUTRAL",

        "ultimo_high": None,
        "prev_high": None,

        "ultimo_low": None,
        "prev_low": None,

        "bos": None,
        "choch": False,

        "bos_nivel": None,
        "choch_nivel": None,

        "hh": False,
        "hl": False,
        "lh": False,
        "ll": False,

        "fuerza": 0
    }

    if df is None or len(df) < 20:

        return resultado

    highs, lows = detectar_swings(df)

    if len(highs) >= 2:

        resultado["ultimo_high"] = highs[-1]
        resultado["prev_high"] = highs[-2]

        resultado["hh"] = (
            highs[-1]["precio"] >
            highs[-2]["precio"] +
            highs[-1]["atr"] *
            SWING_ATR_MIN
        )

        resultado["lh"] = (
            highs[-1]["precio"] <
            highs[-2]["precio"] -
            highs[-1]["atr"] *
            SWING_ATR_MIN
        )

    if len(lows) >= 2:

        resultado["ultimo_low"] = lows[-1]
        resultado["prev_low"] = lows[-2]

        resultado["hl"] = (
            lows[-1]["precio"] >
            lows[-2]["precio"] +
            lows[-1]["atr"] *
            SWING_ATR_MIN
        )

        resultado["ll"] = (
            lows[-1]["precio"] <
            lows[-2]["precio"] -
            lows[-1]["atr"] *
            SWING_ATR_MIN
        )

    alcistas = 0
    bajistas = 0

    if resultado["hh"]:
        alcistas += 1

    if resultado["hl"]:
        alcistas += 1

    if resultado["lh"]:
        bajistas += 1

    if resultado["ll"]:
        bajistas += 1

    if alcistas >= 2:

        resultado["direccion"] = "ALCISTA"
        resultado["fuerza"] = alcistas

    elif bajistas >= 2:

        resultado["direccion"] = "BAJISTA"
        resultado["fuerza"] = bajistas

    else:

        cierre = float(
            df.iloc[-1]["close"]
        )

        cierre_anterior = float(
            df.iloc[-6]["close"]
        )

        atr = float(
            df.iloc[-1]["atr"]
        )

        if atr > 0:

            desplazamiento = (
                cierre -
                cierre_anterior
            )

            if desplazamiento > atr * 0.50:

                resultado["direccion"] = "ALCISTA"
                resultado["fuerza"] = 1

            elif desplazamiento < -atr * 0.50:

                resultado["direccion"] = "BAJISTA"
                resultado["fuerza"] = 1

    precio_actual = float(
        df.iloc[-1]["close"]
    )

    atr_actual = float(
        df.iloc[-1]["atr"]
    )

    if atr_actual <= 0:

        return resultado

    # ========================================================
    # BOS
    # ========================================================

    if resultado["ultimo_high"] is not None:

        nivel_high = float(
            resultado["ultimo_high"]["precio"]
        )

        if precio_actual > (
            nivel_high +
            atr_actual * BREAK_BUFFER_ATR
        ):

            resultado["bos"] = "ALCISTA"
            resultado["bos_nivel"] = nivel_high

    if resultado["ultimo_low"] is not None:

        nivel_low = float(
            resultado["ultimo_low"]["precio"]
        )

        if precio_actual < (
            nivel_low -
            atr_actual * BREAK_BUFFER_ATR
        ):

            resultado["bos"] = "BAJISTA"
            resultado["bos_nivel"] = nivel_low

    # ========================================================
    # CHoCH
    # ========================================================

    if resultado["direccion"] == "ALCISTA":

        if resultado["ultimo_low"] is not None:

            nivel = float(
                resultado["ultimo_low"]["precio"]
            )

            if precio_actual < (
                nivel -
                atr_actual * CHOCH_MIN_ATR
            ):

                resultado["choch"] = True
                resultado["choch_nivel"] = nivel

    elif resultado["direccion"] == "BAJISTA":

        if resultado["ultimo_high"] is not None:

            nivel = float(
                resultado["ultimo_high"]["precio"]
            )

            if precio_actual > (
                nivel +
                atr_actual * CHOCH_MIN_ATR
            ):

                resultado["choch"] = True
                resultado["choch_nivel"] = nivel

    return resultado


# ============================================================
# RÉGIMEN
# ============================================================

def detectar_regimen(df):

    if df is None or len(df) < 30:

        return "LATERAL"

    try:

        actual = df.iloc[-1]

        precio = float(actual["close"])
        ema20 = float(actual["ema20"])
        ema50 = float(actual["ema50"])
        ema200 = float(actual["ema200"])
        adx = float(actual["adx"])

        pendiente20 = float(
            actual["pendiente_ema20"]
        )

        pendiente50 = float(
            actual["pendiente_ema50"]
        )

        rango20 = (
            float(df["high"].iloc[-20:].max())
            -
            float(df["low"].iloc[-20:].min())
        )

        atr = float(actual["atr"])

    except Exception:

        return "LATERAL"

    if atr <= 0:

        return "LATERAL"

    rango_atr = rango20 / atr

    if (
        precio > ema20
        and ema20 > ema50
        and ema50 > ema200
        and pendiente20 > 0
        and pendiente50 >= 0
        and adx >= 18
    ):

        return "ALCISTA"

    if (
        precio < ema20
        and ema20 < ema50
        and ema50 < ema200
        and pendiente20 < 0
        and pendiente50 <= 0
        and adx >= 18
    ):

        return "BAJISTA"

    if (
        rango_atr < 3.0
        and adx < 18
    ):

        return "LATERAL"

    return "TRANSICION"


# ============================================================
# CONTEXTO 15M
# ============================================================

def obtener_contexto_15m(
    estructura15,
    df15
):

    regimen15 = detectar_regimen(df15)

    direccion = estructura15.get(
        "direccion",
        "NEUTRAL"
    )

    if (
        direccion == "ALCISTA"
        and
        regimen15 != "BAJISTA"
    ):

        return "ALCISTA"

    if (
        direccion == "BAJISTA"
        and
        regimen15 != "ALCISTA"
    ):

        return "BAJISTA"

    if regimen15 == "ALCISTA":

        return "ALCISTA"

    if regimen15 == "BAJISTA":

        return "BAJISTA"

    return "NEUTRAL"


# ============================================================
# CALIDAD DEL IMPULSO
# ============================================================

def evaluar_calidad_impulso(
    ventana,
    direccion,
    inicio,
    extremo,
    atr
):

    if ventana is None or len(ventana) < 2:

        return None

    try:

        desplazamiento = (
            extremo - inicio
            if direccion == "ALCISTA"
            else
            inicio - extremo
        )

        if desplazamiento <= 0 or atr <= 0:

            return None

        desplazamiento_atr = (
            desplazamiento / atr
        )

        if desplazamiento_atr < IMPULSO_ATR_MIN:

            return None

        direccion_num = (
            1
            if direccion == "ALCISTA"
            else -1
        )

        velas_direccion = int(
            (
                ventana["direccion_vela"] ==
                direccion_num
            ).sum()
        )

        expansion = int(
            ventana["expansion"].sum()
        )

        cambio = abs(
            float(ventana.iloc[-1]["close"])
            -
            float(ventana.iloc[0]["close"])
        )

        rango_total = float(
            ventana["rango"].sum()
        )

        eficiencia = (
            cambio / rango_total
            if rango_total > 0
            else 0
        )

        cuerpos = float(
            ventana["cuerpo"].sum()
        )

        rangos = float(
            ventana["rango"].sum()
        )

        ratio_cuerpo = (
            cuerpos / rangos
            if rangos > 0
            else 0
        )

        calidad = 0

        if desplazamiento_atr >= IMPULSO_ATR_MIN:
            calidad += 1

        if desplazamiento_atr >= IMPULSO_FUERTE_ATR:
            calidad += 1

        if velas_direccion >= IMPULSO_VELAS_MIN:
            calidad += 1

        if expansion >= 1:
            calidad += 1

        if eficiencia >= EFICIENCIA_MINIMA:
            calidad += 1

        if ratio_cuerpo >= RATIO_CUERPO_MIN:
            calidad += 1

        if calidad < 4:

            return None

        return {

            "direccion": direccion,

            "inicio": float(inicio),

            "extremo": float(extremo),

            "desplazamiento":
                float(desplazamiento),

            "desplazamiento_atr":
                float(desplazamiento_atr),

            "velas_direccion":
                velas_direccion,

            "expansion":
                expansion,

            "eficiencia":
                float(eficiencia),

            "ratio_cuerpo":
                float(ratio_cuerpo),

            "calidad":
                calidad
        }

    except Exception:

        return None


# ============================================================
# IMPULSO ALCISTA
# ============================================================

def detectar_impulso_alcista(df):

    if df is None:

        return None

    if len(df) < IMPULSO_LOOKBACK + 5:

        return None

    datos = df.iloc[
        -IMPULSO_LOOKBACK:
    ].copy()

    try:

        atr_actual = float(
            df.iloc[-1]["atr"]
        )

        if atr_actual <= 0:

            return None

        rango_extremos = datos.iloc[
            :-PULLBACK_VELAS_MIN
        ]

        if len(rango_extremos) < 6:

            return None

        posicion_extremo = (
            rango_extremos["high"].idxmax()
        )

        pos = datos.index.get_loc(
            posicion_extremo
        )

        if pos < IMPULSO_MIN_VELAS:

            return None

        if pos > (
            len(datos) -
            PULLBACK_VELAS_MIN -
            1
        ):

            return None

        inicio_pos = max(
            0,
            pos - IMPULSO_MAX_VELAS + 1
        )

        if (
            pos -
            inicio_pos +
            1
        ) < IMPULSO_MIN_VELAS:

            return None

        ventana = datos.iloc[
            inicio_pos:
            pos + 1
        ]

        inicio = float(
            ventana.iloc[0]["close"]
        )

        extremo = float(
            ventana["high"].max()
        )

        impulso = evaluar_calidad_impulso(
            ventana,
            "ALCISTA",
            inicio,
            extremo,
            atr_actual
        )

        if impulso is None:

            return None

        impulso["indice_extremo"] = int(pos)

        impulso["indice_inicio"] = int(
            inicio_pos
        )

        impulso["timestamp_extremo"] = (
            datos.iloc[pos]["datetime"]
        )

        return impulso

    except Exception:

        return None


# ============================================================
# IMPULSO BAJISTA
# ============================================================

def detectar_impulso_bajista(df):

    if df is None:

        return None

    if len(df) < IMPULSO_LOOKBACK + 5:

        return None

    datos = df.iloc[
        -IMPULSO_LOOKBACK:
    ].copy()

    try:

        atr_actual = float(
            df.iloc[-1]["atr"]
        )

        if atr_actual <= 0:

            return None

        rango_extremos = datos.iloc[
            :-PULLBACK_VELAS_MIN
        ]

        if len(rango_extremos) < 6:

            return None

        posicion_extremo = (
            rango_extremos["low"].idxmin()
        )

        pos = datos.index.get_loc(
            posicion_extremo
        )

        if pos < IMPULSO_MIN_VELAS:

            return None

        if pos > (
            len(datos) -
            PULLBACK_VELAS_MIN -
            1
        ):

            return None

        inicio_pos = max(
            0,
            pos - IMPULSO_MAX_VELAS + 1
        )

        if (
            pos -
            inicio_pos +
            1
        ) < IMPULSO_MIN_VELAS:

            return None

        ventana = datos.iloc[
            inicio_pos:
            pos + 1
        ]

        inicio = float(
            ventana.iloc[0]["close"]
        )

        extremo = float(
            ventana["low"].min()
        )

        impulso = evaluar_calidad_impulso(
            ventana,
            "BAJISTA",
            inicio,
            extremo,
            atr_actual
        )

        if impulso is None:

            return None

        impulso["indice_extremo"] = int(pos)

        impulso["indice_inicio"] = int(
            inicio_pos
        )

        impulso["timestamp_extremo"] = (
            datos.iloc[pos]["datetime"]
        )

        return impulso

    except Exception:

        return None


# ============================================================
# PULLBACK ALCISTA
# ============================================================

def detectar_pullback_alcista(
    df,
    impulso
):

    if df is None or impulso is None:

        return None

    try:

        atr = float(
            df.iloc[-1]["atr"]
        )

        if atr <= 0:

            return None

        indice_extremo = int(
            impulso["indice_extremo"]
        )

        inicio_ventana = (
            len(df) -
            IMPULSO_LOOKBACK
        )

        indice_absoluto = (
            inicio_ventana +
            indice_extremo
        )

        inicio_pullback = (
            indice_absoluto + 1
        )

        fin = len(df)

        cantidad = (
            fin -
            inicio_pullback
        )

        if cantidad < PULLBACK_VELAS_MIN:

            return None

        if cantidad > PULLBACK_VELAS_MAX:

            inicio_pullback = (
                fin -
                PULLBACK_VELAS_MAX
            )

        pullback_df = df.iloc[
            inicio_pullback:
        ]

        if len(pullback_df) < PULLBACK_VELAS_MIN:

            return None

        extremo = float(
            impulso["extremo"]
        )

        inicio = float(
            impulso["inicio"]
        )

        desplazamiento = (
            extremo -
            inicio
        )

        if desplazamiento <= 0:

            return None

        precio = float(
            df.iloc[-1]["close"]
        )

        minimo_pullback = float(
            pullback_df["low"].min()
        )

        maximo_pullback = float(
            pullback_df["high"].max()
        )

        retroceso = (
            extremo -
            minimo_pullback
        )

        retroceso_atr = (
            retroceso /
            atr
        )

        retracement = (
            retroceso /
            desplazamiento
        )

        if retroceso_atr < PULLBACK_MIN_ATR:
            return None

        if retroceso_atr > PULLBACK_MAX_ATR:
            return None

        if retracement < PULLBACK_MIN_RETRACEMENT:
            return None

        if retracement > PULLBACK_MAX_RETRACEMENT:
            return None

        if precio < (
            inicio -
            atr * 0.10
        ):

            return None

        if precio > (
            extremo +
            atr * 0.50
        ):

            return None

        return {

            "direccion": "ALCISTA",

            "maximo_pullback":
                maximo_pullback,

            "minimo_pullback":
                minimo_pullback,

            "nivel_continuacion":
                extremo,

            "extremo_impulso":
                extremo,

            "inicio_impulso":
                inicio,

            "retracement":
                float(retracement),

            "retroceso_atr":
                float(retroceso_atr),

            "velas":
                len(pullback_df)
        }

    except Exception:

        return None


# ============================================================
# PULLBACK BAJISTA
# ============================================================

def detectar_pullback_bajista(
    df,
    impulso
):

    if df is None or impulso is None:

        return None

    try:

        atr = float(
            df.iloc[-1]["atr"]
        )

        if atr <= 0:

            return None

        indice_extremo = int(
            impulso["indice_extremo"]
        )

        inicio_ventana = (
            len(df) -
            IMPULSO_LOOKBACK
        )

        indice_absoluto = (
            inicio_ventana +
            indice_extremo
        )

        inicio_pullback = (
            indice_absoluto + 1
        )

        fin = len(df)

        cantidad = (
            fin -
            inicio_pullback
        )

        if cantidad < PULLBACK_VELAS_MIN:

            return None

        if cantidad > PULLBACK_VELAS_MAX:

            inicio_pullback = (
                fin -
                PULLBACK_VELAS_MAX
            )

        pullback_df = df.iloc[
            inicio_pullback:
        ]

        if len(pullback_df) < PULLBACK_VELAS_MIN:

            return None

        extremo = float(
            impulso["extremo"]
        )

        inicio = float(
            impulso["inicio"]
        )

        desplazamiento = (
            inicio -
            extremo
        )

        if desplazamiento <= 0:

            return None

        precio = float(
            df.iloc[-1]["close"]
        )

        maximo_pullback = float(
            pullback_df["high"].max()
        )

        minimo_pullback = float(
            pullback_df["low"].min()
        )

        retroceso = (
            maximo_pullback -
            extremo
        )

        retroceso_atr = (
            retroceso /
            atr
        )

        retracement = (
            retroceso /
            desplazamiento
        )

        if retroceso_atr < PULLBACK_MIN_ATR:
            return None

        if retroceso_atr > PULLBACK_MAX_ATR:
            return None

        if retracement < PULLBACK_MIN_RETRACEMENT:
            return None

        if retracement > PULLBACK_MAX_RETRACEMENT:
            return None

        if precio > (
            inicio +
            atr * 0.10
        ):

            return None

        if precio < (
            extremo -
            atr * 0.50
        ):

            return None

        return {

            "direccion": "BAJISTA",

            "maximo_pullback":
                maximo_pullback,

            "minimo_pullback":
                minimo_pullback,

            "nivel_continuacion":
                extremo,

            "extremo_impulso":
                extremo,

            "inicio_impulso":
                inicio,

            "retracement":
                float(retracement),

            "retroceso_atr":
                float(retroceso_atr),

            "velas":
                len(pullback_df)
        }

    except Exception:

        return None


# ============================================================
# VALIDAR PULLBACK
# ============================================================

def pullback_sano(
    df,
    pullback,
    direccion
):

    if pullback is None:

        return False

    try:

        if (
            pullback["retracement"]
            > PULLBACK_MAX_RETRACEMENT
        ):

            return False

        if (
            pullback["retroceso_atr"]
            > PULLBACK_MAX_ATR
        ):

            return False

        precio = float(
            df.iloc[-1]["close"]
        )

        inicio = float(
            pullback["inicio_impulso"]
        )

        if direccion == "ALCISTA":

            return precio >= inicio

        return precio <= inicio

    except Exception:

        return False


# ============================================================
# CONTINUACIÓN ALCISTA
# ============================================================

def detectar_continuacion_alcista(
    df,
    pullback
):

    if (
        df is None
        or pullback is None
        or len(df) < 2
    ):

        return False, None

    try:

        actual = df.iloc[-1]

        precio = float(actual["close"])
        apertura = float(actual["open"])
        cuerpo = float(actual["cuerpo"])
        atr = float(actual["atr"])

        nivel = float(
            pullback["nivel_continuacion"]
        )

        if atr <= 0:

            return False, nivel

        ruptura = (
            precio >
            nivel +
            atr * BREAK_BUFFER_ATR
        )

        vela_alcista = (
            precio > apertura
        )

        cuerpo_ok = (
            cuerpo >=
            atr * CUERPO_CONTINUACION_ATR
        )

        avance_ok = (
            precio >
            nivel +
            atr * CONTINUACION_ATR_MIN
        )

        return (
            bool(
                ruptura
                and vela_alcista
                and cuerpo_ok
                and avance_ok
            ),
            nivel
        )

    except Exception:

        return False, None


# ============================================================
# CONTINUACIÓN BAJISTA
# ============================================================

def detectar_continuacion_bajista(
    df,
    pullback
):

    if (
        df is None
        or pullback is None
        or len(df) < 2
    ):

        return False, None

    try:

        actual = df.iloc[-1]

        precio = float(actual["close"])
        apertura = float(actual["open"])
        cuerpo = float(actual["cuerpo"])
        atr = float(actual["atr"])

        nivel = float(
            pullback["nivel_continuacion"]
        )

        if atr <= 0:

            return False, nivel

        ruptura = (
            precio <
            nivel -
            atr * BREAK_BUFFER_ATR
        )

        vela_bajista = (
            precio < apertura
        )

        cuerpo_ok = (
            cuerpo >=
            atr * CUERPO_CONTINUACION_ATR
        )

        avance_ok = (
            precio <
            nivel -
            atr * CONTINUACION_ATR_MIN
        )

        return (
            bool(
                ruptura
                and vela_bajista
                and cuerpo_ok
                and avance_ok
            ),
            nivel
        )

    except Exception:

        return False, None


# ============================================================
# ENTRADA TARDÍA
# ============================================================

def entrada_tardia_compra(
    precio,
    zona,
    atr
):

    if (
        zona is None
        or atr is None
        or atr <= 0
    ):

        return False

    distancia = (
        precio -
        float(zona)
    )

    return (
        distancia >
        atr *
        MAX_DISTANCIA_ENTRADA_ATR
    )


def entrada_tardia_venta(
    precio,
    zona,
    atr
):

    if (
        zona is None
        or atr is None
        or atr <= 0
    ):

        return False

    distancia = (
        float(zona) -
        precio
    )

    return (
        distancia >
        atr *
        MAX_DISTANCIA_ENTRADA_ATR
    )


# ============================================================
# LIQUIDEZ
# ============================================================

def detectar_liquidez(df):

    resultado = {

        "sweep_alcista": False,

        "sweep_bajista": False,

        "nivel_alcista": None,

        "nivel_bajista": None
    }

    if (
        df is None
        or
        len(df) < LIQUIDEZ_LOOKBACK + 2
    ):

        return resultado

    try:

        actual = df.iloc[-1]

        atr = float(
            actual["atr"]
        )

        if atr <= 0:

            return resultado

        high_previo = float(
            df["high"].iloc[
                -LIQUIDEZ_LOOKBACK-1:-1
            ].max()
        )

        low_previo = float(
            df["low"].iloc[
                -LIQUIDEZ_LOOKBACK-1:-1
            ].min()
        )

        high_actual = float(
            actual["high"]
        )

        low_actual = float(
            actual["low"]
        )

        close_actual = float(
            actual["close"]
        )

        buffer = (
            atr *
            LIQUIDEZ_BUFFER_ATR
        )

        resultado["nivel_alcista"] = (
            low_previo
        )

        resultado["nivel_bajista"] = (
            high_previo
        )

        resultado["sweep_alcista"] = (
            low_actual <
            low_previo - buffer
            and
            close_actual >
            low_previo
        )

        resultado["sweep_bajista"] = (
            high_actual >
            high_previo + buffer
            and
            close_actual <
            high_previo
        )

    except Exception:

        pass

    return resultado


# ============================================================
# SOPORTES / RESISTENCIAS
# ============================================================

def obtener_zonas_sr(
    df,
    estructura
):

    zonas = []

    if df is None or len(df) < 20:

        return zonas

    try:

        for clave in [
            "ultimo_high",
            "prev_high",
            "ultimo_low",
            "prev_low"
        ]:

            swing = estructura.get(
                clave
            )

            if swing is not None:

                precio = float(
                    swing["precio"]
                )

                if not any(
                    abs(precio - z)
                    < float(df.iloc[-1]["atr"]) * 0.10
                    for z in zonas
                ):

                    zonas.append(precio)

    except Exception:

        pass

    return zonas


# ============================================================
# UBICACIÓN
# ============================================================

def evaluar_ubicacion(
    precio,
    atr,
    direccion,
    zonas
):

    if (
        atr is None
        or atr <= 0
    ):

        return 0

    if not zonas:

        return 1

    distancias = [
        abs(
            precio -
            float(zona)
        )
        for zona in zonas
    ]

    mejor_distancia = min(
        distancias
    )

    if mejor_distancia <= (
        atr * ZONA_MAX_ATR
    ):

        return 2

    return 1


# ============================================================
# MOMENTUM
# ============================================================

def evaluar_momentum(
    df,
    direccion
):

    resultado = {

        "puntos": 0,

        "rsi": 50,

        "adx": 0,

        "di_plus": 0,

        "di_minus": 0,

        "pendiente_ema20": 0,

        "rsi_slope": 0
    }

    if df is None or len(df) < 5:

        return resultado

    try:

        actual = df.iloc[-1]

        rsi = float(actual["rsi"])
        adx = float(actual["adx"])

        di_plus = float(
            actual["di_plus"]
        )

        di_minus = float(
            actual["di_minus"]
        )

        pendiente = float(
            actual["pendiente_ema20"]
        )

        rsi_slope = float(
            actual["rsi_slope"]
        )

        resultado.update({

            "rsi": rsi,

            "adx": adx,

            "di_plus": di_plus,

            "di_minus": di_minus,

            "pendiente_ema20":
                pendiente,

            "rsi_slope":
                rsi_slope
        })

        puntos = 0

        if direccion == "ALCISTA":

            if rsi >= RSI_COMPRA_MIN:
                puntos += 1

            if rsi >= RSI_CONFIRMACION_COMPRA:
                puntos += 1

            if di_plus > di_minus:
                puntos += 1

            if pendiente > 0:
                puntos += 1

            if rsi_slope > 0:
                puntos += 1

        else:

            if rsi <= RSI_VENTA_MAX:
                puntos += 1

            if rsi <= RSI_CONFIRMACION_VENTA:
                puntos += 1

            if di_minus > di_plus:
                puntos += 1

            if pendiente < 0:
                puntos += 1

            if rsi_slope < 0:
                puntos += 1

        if adx >= ADX_MINIMO:
            puntos += 1

        if adx >= ADX_FUERTE:
            puntos += 1

        resultado["puntos"] = puntos

    except Exception:

        pass

    return resultado


# ============================================================
# EVALUAR ESTRUCTURA + DIRECCIÓN
# ============================================================

def evaluar_direccion(
    estructura5,
    contexto15,
    regimen5,
    direccion
):

    puntos = 0
    razones = []

    if direccion == "ALCISTA":

        if estructura5.get("direccion") == "ALCISTA":

            puntos += 2
            razones.append("estructura 5M alcista")

        if contexto15 == "ALCISTA":

            puntos += 2
            razones.append("contexto 15M alcista")

        if regimen5 == "ALCISTA":

            puntos += 2
            razones.append("régimen 5M alcista")

        if estructura5.get("bos") == "ALCISTA":

            puntos += 2
            razones.append("BOS alcista")

        if estructura5.get("choch"):

            puntos -= 2
            razones.append("CHoCH contrario")

    else:

        if estructura5.get("direccion") == "BAJISTA":

            puntos += 2
            razones.append("estructura 5M bajista")

        if contexto15 == "BAJISTA":

            puntos += 2
            razones.append("contexto 15M bajista")

        if regimen5 == "BAJISTA":

            puntos += 2
            razones.append("régimen 5M bajista")

        if estructura5.get("bos") == "BAJISTA":

            puntos += 2
            razones.append("BOS bajista")

        if estructura5.get("choch"):

            puntos -= 2
            razones.append("CHoCH contrario")

    return puntos, razones


# ============================================================
# EVALUAR LIQUIDEZ
# ============================================================

def evaluar_liquidez(
    liquidez,
    direccion
):

    puntos = 0
    razones = []

    if direccion == "ALCISTA":

        if liquidez.get("sweep_alcista"):

            puntos += 3
            razones.append(
                "sweep de liquidez inferior"
            )

        elif liquidez.get("nivel_alcista") is not None:

            puntos += 1
            razones.append(
                "liquidez inferior identificada"
            )

    else:

        if liquidez.get("sweep_bajista"):

            puntos += 3
            razones.append(
                "sweep de liquidez superior"
            )

        elif liquidez.get("nivel_bajista") is not None:

            puntos += 1
            razones.append(
                "liquidez superior identificada"
            )

    return puntos, razones


# ============================================================
# SCORE
# ============================================================

def calcular_score(
    direccion,
    estructura5,
    contexto15,
    regimen5,
    impulso,
    pullback,
    liquidez,
    ubicacion,
    momentum,
    continuacion=False
):

    score = 0
    razones = []

    # ========================================================
    # DIRECCIÓN / CONTEXTO
    # ========================================================

    puntos, motivos = evaluar_direccion(
        estructura5,
        contexto15,
        regimen5,
        direccion
    )

    score += puntos
    razones.extend(motivos)

    # ========================================================
    # IMPULSO
    # ========================================================

    if impulso is not None:

        score += 8
        razones.append("impulso válido")

        if impulso.get(
            "desplazamiento_atr", 0
        ) >= IMPULSO_FUERTE_ATR:

            score += 4
            razones.append(
                "impulso fuerte"
            )

        if impulso.get(
            "eficiencia", 0
        ) >= 0.60:

            score += 2
            razones.append(
                "impulso eficiente"
            )

    # ========================================================
    # PULLBACK
    # ========================================================

    if pullback is not None:

        score += 8
        razones.append("pullback válido")

        retracement = pullback.get(
            "retracement",
            1
        )

        if (
            0.30 <=
            retracement <=
            0.60
        ):

            score += 3
            razones.append(
                "retroceso saludable"
            )

    # ========================================================
    # LIQUIDEZ
    # ========================================================

    puntos, motivos = evaluar_liquidez(
        liquidez,
        direccion
    )

    score += puntos
    razones.extend(motivos)

    # ========================================================
    # UBICACIÓN
    # ========================================================

    if ubicacion >= 2:

        score += 5
        razones.append(
            "buena ubicación"
        )

    elif ubicacion == 1:

        score += 2
        razones.append(
            "ubicación aceptable"
        )

    # ========================================================
    # MOMENTUM
    # ========================================================

    puntos_momentum = int(
        momentum.get(
            "puntos",
            0
        )
    )

    score += min(
        puntos_momentum * 2,
        12
    )

    if puntos_momentum >= 5:

        razones.append(
            "momentum favorable"
        )

    # ========================================================
    # CONTINUACIÓN
    # ========================================================

    if continuacion:

        score += 8
        razones.append(
            "continuación confirmada"
        )

    # ========================================================
    # LIMITAR
    # ========================================================

    score = max(
        0,
        min(
            100,
            int(score)
        )
    )

    return score, razones


# ============================================================
# VALIDAR DIRECCIÓN DE MOMENTUM
# ============================================================

def momentum_valido(
    momentum,
    direccion
):

    if momentum is None:

        return False

    rsi = float(
        momentum.get("rsi", 50)
    )

    di_plus = float(
        momentum.get("di_plus", 0)
    )

    di_minus = float(
        momentum.get("di_minus", 0)
    )

    adx = float(
        momentum.get("adx", 0)
    )

    if adx < ADX_MINIMO:

        return False

    if direccion == "ALCISTA":

        return (
            rsi >= RSI_COMPRA_MIN
            and
            di_plus >= di_minus
        )

    return (
        rsi <= RSI_VENTA_MAX
        and
        di_minus >= di_plus
    )


# ============================================================
# VALIDAR CONFIRMACIÓN DE MOMENTUM
# ============================================================

def momentum_confirmado(
    momentum,
    direccion
):

    if momentum is None:

        return False

    rsi = float(
        momentum.get("rsi", 50)
    )

    adx = float(
        momentum.get("adx", 0)
    )

    di_plus = float(
        momentum.get("di_plus", 0)
    )

    di_minus = float(
        momentum.get("di_minus", 0)
    )

    if adx < ADX_MINIMO:

        return False

    if direccion == "ALCISTA":

        return (
            rsi >= RSI_CONFIRMACION_COMPRA
            and
            di_plus > di_minus
        )

    return (
        rsi <= RSI_CONFIRMACION_VENTA
        and
        di_minus > di_plus
    )


# ============================================================
# VALIDAR RÉGIMEN
# ============================================================

def regimen_compatible(
    regimen,
    direccion
):

    if direccion == "ALCISTA":

        return regimen in [
            "ALCISTA",
            "TRANSICION"
        ]

    return regimen in [
        "BAJISTA",
        "TRANSICION"
    ]


# ============================================================
# SL / TP
# ============================================================

def calcular_sl_tp(
    precio,
    atr,
    direccion,
    estructura=None,
    pullback=None
):

    if atr is None or atr <= 0:

        return None

    precio = float(precio)
    atr = float(atr)

    if direccion == "ALCISTA":

        sl_atr = (
            precio -
            atr * ATR_SL
        )

        tp_atr = (
            precio +
            atr * ATR_TP
        )

        sl_estructura = None

        if pullback is not None:

            try:

                sl_estructura = (
                    float(
                        pullback[
                            "minimo_pullback"
                        ]
                    )
                    -
                    atr * 0.10
                )

            except Exception:

                pass

        if sl_estructura is not None:

            sl = min(
                sl_atr,
                sl_estructura
            )

        else:

            sl = sl_atr

        riesgo = precio - sl

        if riesgo <= 0:

            return None

        tp_minimo = (
            precio +
            riesgo * RR_MINIMO
        )

        tp = max(
            tp_atr,
            tp_minimo
        )

    else:

        sl_atr = (
            precio +
            atr * ATR_SL
        )

        tp_atr = (
            precio -
            atr * ATR_TP
        )

        sl_estructura = None

        if pullback is not None:

            try:

                sl_estructura = (
                    float(
                        pullback[
                            "maximo_pullback"
                        ]
                    )
                    +
                    atr * 0.10
                )

            except Exception:

                pass

        if sl_estructura is not None:

            sl = max(
                sl_atr,
                sl_estructura
            )

        else:

            sl = sl_atr

        riesgo = sl - precio

        if riesgo <= 0:

            return None

        tp_minimo = (
            precio -
            riesgo * RR_MINIMO
        )

        tp = min(
            tp_atr,
            tp_minimo
        )

    riesgo = abs(
        precio - sl
    )

    recompensa = abs(
        tp - precio
    )

    if riesgo <= 0:

        return None

    rr = (
        recompensa /
        riesgo
    )

    if rr < RR_MINIMO:

        return None

    return {

        "entrada": precio,

        "sl": float(sl),

        "tp": float(tp),

        "riesgo": float(riesgo),

        "recompensa": float(recompensa),

        "rr": float(rr)
    }


# ============================================================
# VALIDAR ENTRADA TARDÍA
# ============================================================

def validar_entrada(
    precio,
    nivel,
    atr,
    direccion
):

    if (
        nivel is None
        or
        atr is None
        or
        atr <= 0
    ):

        return False

    if direccion == "ALCISTA":

        distancia = (
            precio -
            float(nivel)
        )

    else:

        distancia = (
            float(nivel) -
            precio
        )

    if distancia < 0:

        return False

    return (
        distancia <=
        atr *
        MAX_DISTANCIA_ENTRADA_ATR
    )


# ============================================================
# PREALERTA
# ============================================================

def crear_prealerta(
    direccion,
    precio,
    atr,
    score,
    estructura,
    impulso,
    pullback,
    momentum
):

    ahora = time.time()

    id_senal = generar_id()

    estado["direccion_pendiente"] = (
        direccion
    )

    estado["id_pendiente"] = (
        id_senal
    )

    estado["inicio_pendiente"] = (
        ahora
    )

    estado["ultima_prealerta"] = (
        ahora
    )

    estado["precio_prealerta"] = (
        precio
    )

    estado["atr_prealerta"] = (
        atr
    )

    estado["impulso_inicio"] = (
        impulso.get("inicio")
        if impulso
        else None
    )

    estado["impulso_extremo"] = (
        impulso.get("extremo")
        if impulso
        else None
    )

    estado["impulso_indice_extremo"] = (
        impulso.get("indice_extremo")
        if impulso
        else None
    )

    estado["pullback_nivel"] = (
        pullback.get(
            "nivel_continuacion"
        )
        if pullback
        else None
    )

    estado["nivel_continuacion"] = (
        estado["pullback_nivel"]
    )

    if direccion == "ALCISTA":

        estado["swing_referencia"] = (
            estructura.get(
                "ultimo_high"
            )
        )

    else:

        estado["swing_referencia"] = (
            estructura.get(
                "ultimo_low"
            )
        )

    return {

        "tipo": "PREALERTA",

        "estado": "PENDIENTE",

        "id": id_senal,

        "direccion": direccion,

        "precio": float(precio),

        "atr": float(atr),

        "score": int(score),

        "rsi": float(
            momentum.get(
                "rsi",
                0
            )
        ),

        "adx": float(
            momentum.get(
                "adx",
                0
            )
        ),

        "timestamp": ahora
    }


# ============================================================
# EXPIRAR PREALERTA
# ============================================================

def prealerta_expirada():

    if (
        estado["id_pendiente"] is None
    ):

        return False

    vida = (
        time.time()
        -
        estado["inicio_pendiente"]
    )

    return (
        vida >
        MINUTOS_VIDA_PREALERTA * 60
    )


# ============================================================
# COOLDOWN
# ============================================================

def cooldown_activo(
    timestamp,
    minutos
):

    if timestamp <= 0:

        return False

    return (
        time.time() -
        timestamp
        <
        minutos * 60
    )


# ============================================================
# VALIDAR PREALERTA EXISTENTE
# ============================================================

def prealerta_valida_para_confirmar(
    direccion
):

    if estado["id_pendiente"] is None:

        return False

    if (
        estado["direccion_pendiente"]
        !=
        direccion
    ):

        return False

    if prealerta_expirada():

        limpiar_pendiente()

        return False

    return True


# ============================================================
# CONFIRMACIÓN
# ============================================================

def crear_confirmacion(
    direccion,
    precio,
    sltp,
    score,
    momentum,
    id_senal
):

    ahora = time.time()

    estado["ultima_confirmacion"] = (
        ahora
    )

    estado["maximo_confirmacion"] = (
        precio
    )

    estado["minimo_confirmacion"] = (
        precio
    )

    return {

        "tipo": "CONFIRMADA",

        "estado": "CONFIRMADA",

        "id": id_senal,

        "direccion": direccion,

        "precio": float(precio),

        "sl": float(
            sltp["sl"]
        ),

        "tp": float(
            sltp["tp"]
        ),

        "rr": float(
            sltp["rr"]
        ),

        "score": int(score),

        "rsi": float(
            momentum.get(
                "rsi",
                0
            )
        ),

        "adx": float(
            momentum.get(
                "adx",
                0
            )
        ),

        "timestamp": ahora
    }


# ============================================================
# DESCARTAR
# ============================================================

def crear_descartada(
    motivo
):

    ahora = time.time()

    estado["ultima_descartada"] = (
        ahora
    )

    id_senal = (
        estado["id_pendiente"]
    )

    resultado = {

        "tipo": "DESCARTADA",

        "estado": "DESCARTADA",

        "id": id_senal,

        "direccion":
            estado["direccion_pendiente"],

        "motivo": motivo,

        "timestamp": ahora
    }

    limpiar_pendiente()

    return resultado


# ============================================================
# ANALIZAR MERCADO COMPLETO
# ============================================================

def analizar_mercado():

    inicio = time.time()

    try:

        print(
            "\n==================================="
        )

        print(
            "🔍 ANALIZANDO XAU/USD..."
        )

        print(
            "==================================="
        )

        # ====================================================
        # 5M
        # ====================================================

        raw5 = obtener_datos(
            INTERVALO_5M
        )

        df5 = velas_cerradas(
            raw5
        )

        df5 = calcular_indicadores(
            df5
        )

        # ====================================================
        # 15M
        # ====================================================

        raw15 = obtener_datos(
            INTERVALO_15M
        )

        df15 = velas_cerradas(
            raw15
        )

        df15 = calcular_indicadores(
            df15
        )

        if len(df5) < 100:

            return {
                "estado": "SIN_SEÑAL",
                "motivo":
                    "Pocas velas 5M"
            }

        if len(df15) < 100:

            return {
                "estado": "SIN_SEÑAL",
                "motivo":
                    "Pocas velas 15M"
            }

        # ====================================================
        # ESTRUCTURA
        # ====================================================

        estructura5 = analizar_estructura(
            df5
        )

        estructura15 = analizar_estructura(
            df15
        )

        regimen5 = detectar_regimen(
            df5
        )

        contexto15 = obtener_contexto_15m(
            estructura15,
            df15
        )

        # ====================================================
        # PRECIO / ATR
        # ====================================================

        actual = df5.iloc[-1]

        precio = float(
            actual["close"]
        )

        atr = float(
            actual["atr"]
        )

        # ====================================================
        # LIQUIDEZ
        # ====================================================

        liquidez = detectar_liquidez(
            df5
        )

        zonas = obtener_zonas_sr(
            df5,
            estructura5
        )

        # ====================================================
        # DIRECCIONES A ESTUDIAR
        # ====================================================

        candidatos = []

        if regimen5 in [
            "ALCISTA",
            "TRANSICION"
        ]:

            candidatos.append(
                "ALCISTA"
            )

        if regimen5 in [
            "BAJISTA",
            "TRANSICION"
        ]:

            candidatos.append(
                "BAJISTA"
            )

        # Si estructura es muy clara,
        # priorizamos esa dirección.

        if estructura5["direccion"] in [
            "ALCISTA",
            "BAJISTA"
        ]:

            direccion_estructura = (
                estructura5["direccion"]
            )

            if (
                direccion_estructura
                in candidatos
            ):

                candidatos = [
                    direccion_estructura
                ]

        # ====================================================
        # EVALUAR CANDIDATOS
        # ====================================================

        mejor = None

        for direccion in candidatos:

            if not regimen_compatible(
                regimen5,
                direccion
            ):

                continue

            # -----------------------------------------------
            # IMPULSO
            # -----------------------------------------------

            if direccion == "ALCISTA":

                impulso = (
                    detectar_impulso_alcista(
                        df5
                    )
                )

                pullback = (
                    detectar_pullback_alcista(
                        df5,
                        impulso
                    )
                    if impulso
                    else None
                )

                continuacion, nivel = (
                    detectar_continuacion_alcista(
                        df5,
                        pullback
                    )
                    if pullback
                    else (False, None)
                )

            else:

                impulso = (
                    detectar_impulso_bajista(
                        df5
                    )
                )

                pullback = (
                    detectar_pullback_bajista(
                        df5,
                        impulso
                    )
                    if impulso
                    else None
                )

                continuacion, nivel = (
                    detectar_continuacion_bajista(
                        df5,
                        pullback
                    )
                    if pullback
                    else (False, None)
                )

            # -----------------------------------------------
            # PULLBACK SANO
            # -----------------------------------------------

            if pullback is not None:

                if not pullback_sano(
                    df5,
                    pullback,
                    direccion
                ):

                    pullback = None
                    continuacion = False

            # -----------------------------------------------
            # MOMENTUM
            # -----------------------------------------------

            momentum = evaluar_momentum(
                df5,
                direccion
            )

            if not momentum_valido(
                momentum,
                direccion
            ):

                continue

            # -----------------------------------------------
            # UBICACIÓN
            # -----------------------------------------------

            ubicacion = evaluar_ubicacion(
                precio,
                atr,
                direccion,
                zonas
            )

            # -----------------------------------------------
            # SCORE
            # -----------------------------------------------

            score, razones = calcular_score(
                direccion,
                estructura5,
                contexto15,
                regimen5,
                impulso,
                pullback,
                liquidez,
                ubicacion,
                momentum,
                continuacion
            )

            candidato = {

                "direccion": direccion,

                "score": score,

                "razones": razones,

                "impulso": impulso,

                "pullback": pullback,

                "continuacion": continuacion,

                "nivel": nivel,

                "momentum": momentum,

                "ubicacion": ubicacion
            }

            if (
                mejor is None
                or
                candidato["score"]
                >
                mejor["score"]
            ):

                mejor = candidato

        # ====================================================
        # SIN CANDIDATO
        # ====================================================

        if mejor is None:

            return {

                "estado": "SIN_SEÑAL",

                "motivo":
                    "No existe configuración válida",

                "precio": precio,

                "regimen5": regimen5,

                "contexto15": contexto15,

                "estructura5":
                    estructura5,

                "estructura15":
                    estructura15,

                "rsi":
                    float(actual["rsi"]),

                "adx":
                    float(actual["adx"])
            }

        direccion = mejor["direccion"]

        score = mejor["score"]

        impulso = mejor["impulso"]

        pullback = mejor["pullback"]

        momentum = mejor["momentum"]

        continuacion = (
            mejor["continuacion"]
        )

        # ====================================================
        # ENTRADA TARDÍA
        # ====================================================

        nivel_entrada = (
            mejor["nivel"]
            or
            (
                pullback.get(
                    "nivel_continuacion"
                )
                if pullback
                else None
            )
        )

        if entrada_tardia_compra(
            precio,
            nivel_entrada,
            atr
        ) if direccion == "ALCISTA" else entrada_tardia_venta(
            precio,
            nivel_entrada,
            atr
        ):

            return {

                "estado": "DESCARTADA",

                "motivo":
                    "Entrada demasiado extendida",

                "direccion":
                    direccion,

                "precio":
                    precio,

                "score":
                    score
            }

        # ====================================================
        # SCORE DEMASIADO BAJO
        # ====================================================

        if score < SCORE_MIN_PREALERTA:

            return {

                "estado": "SIN_SEÑAL",

                "motivo":
                    "Score insuficiente",

                "direccion":
                    direccion,

                "precio":
                    precio,

                "score":
                    score,

                "razones":
                    mejor["razones"]
            }

        # ====================================================
        # PREALERTA EXISTENTE
        # ====================================================

        if (
            estado["id_pendiente"]
            is not None
        ):

            if not prealerta_valida_para_confirmar(
                direccion
            ):

                if prealerta_expirada():

                    limpiar_pendiente()

                else:

                    return {

                        "estado":
                            "SIN_SEÑAL",

                        "motivo":
                            "Ya existe otra dirección pendiente",

                        "direccion":
                            direccion,

                        "score":
                            score
                    }

        # ====================================================
        # CONFIRMACIÓN
        # ====================================================

        if (
            estado["id_pendiente"]
            is not None
            and
            prealerta_valida_para_confirmar(
                direccion
            )
        ):

            confirmacion_momentum = (
                momentum_confirmado(
                    momentum,
                    direccion
                )
            )

            if (
                continuacion
                and
                confirmacion_momentum
                and
                score >=
                SCORE_MIN_CONFIRMACION
            ):

                sltp = calcular_sl_tp(
                    precio,
                    atr,
                    direccion,
                    estructura5,
                    pullback
                )

                if sltp is None:

                    return crear_descartada(
                        "SL/TP inválido"
                    )

                resultado = crear_confirmacion(
                    direccion,
                    precio,
                    sltp,
                    score,
                    momentum,
                    estado["id_pendiente"]
                )

                limpiar_pendiente()

                resultado.update({

                    "regimen5":
                        regimen5,

                    "contexto15":
                        contexto15,

                    "estructura5":
                        estructura5,

                    "estructura15":
                        estructura15,

                    "razones":
                        mejor["razones"]
                })

                return resultado

        # ====================================================
        # CREAR PREALERTA
        # ====================================================

        if (
            estado["id_pendiente"]
            is None
            and
            not cooldown_activo(
                estado["ultima_descartada"],
                COOLDOWN_DESCARTADA
            )
        ):

            prealerta = crear_prealerta(
                direccion,
                precio,
                atr,
                score,
                estructura5,
                impulso,
                pullback,
                momentum
            )

            prealerta.update({

                "regimen5":
                    regimen5,

                "contexto15":
                    contexto15,

                "estructura5":
                    estructura5,

                "estructura15":
                    estructura15,

                "razones":
                    mejor["razones"]
            })

            return prealerta

        # ====================================================
        # RESULTADO NORMAL
        # ====================================================

        return {

            "estado":
                "SIN_SEÑAL",

            "motivo":
                "Configuración detectada pero esperando confirmación",

            "direccion":
                direccion,

            "precio":
                precio,

            "score":
                score,

            "regimen5":
                regimen5,

            "contexto15":
                contexto15,

            "rsi":
                float(momentum["rsi"]),

            "adx":
                float(momentum["adx"]),

            "razones":
                mejor["razones"]
        }

    except Exception as e:

        print(
            f"❌ Error analizando mercado: {e}"
        )

        return {

            "estado":
                "ERROR",

            "motivo":
                str(e),

            "timestamp":
                time.time()
        }

    finally:

        duracion = (
            time.time() -
            inicio
        )

        print(
            f"⏱️ Análisis terminado "
            f"en {duracion:.2f}s"
    )


# ============================================================
# DIAGNÓSTICO
# ============================================================

def obtener_diagnostico():

    try:

        raw5 = obtener_datos(
            INTERVALO_5M
        )

        df5 = calcular_indicadores(
            velas_cerradas(raw5)
        )

        raw15 = obtener_datos(
            INTERVALO_15M
        )

        df15 = calcular_indicadores(
            velas_cerradas(raw15)
        )

        estructura5 = analizar_estructura(
            df5
        )

        estructura15 = analizar_estructura(
            df15
        )

        regimen5 = detectar_regimen(
            df5
        )

        regimen15 = detectar_regimen(
            df15
        )

        contexto15 = obtener_contexto_15m(
            estructura15,
            df15
        )

        actual = df5.iloc[-1]

        return {

            "ok": True,

            "symbol": SYMBOL,

            "precio": float(
                actual["close"]
            ),

            "atr": float(
                actual["atr"]
            ),

            "rsi": float(
                actual["rsi"]
            ),

            "adx": float(
                actual["adx"]
            ),

            "di_plus": float(
                actual["di_plus"]
            ),

            "di_minus": float(
                actual["di_minus"]
            ),

            "ema20": float(
                actual["ema20"]
            ),

            "ema50": float(
                actual["ema50"]
            ),

            "ema200": float(
                actual["ema200"]
            ),

            "regimen5":
                regimen5,

            "regimen15":
                regimen15,

            "contexto15":
                contexto15,

            "estructura5":
                estructura5,

            "estructura15":
                estructura15,

            "prealerta":
                estado["id_pendiente"]
        }

    except Exception as e:

        return {

            "ok": False,

            "error": str(e)
        }


# ============================================================
# FORMATEAR ESTRUCTURA
# ============================================================

def texto_estructura(
    estructura
):

    if not estructura:

        return "NEUTRAL"

    partes = []

    direccion = estructura.get(
        "direccion",
        "NEUTRAL"
    )

    partes.append(
        f"Dirección: {direccion}"
    )

    if estructura.get("hh"):
        partes.append("HH")

    if estructura.get("hl"):
        partes.append("HL")

    if estructura.get("lh"):
        partes.append("LH")

    if estructura.get("ll"):
        partes.append("LL")

    bos = estructura.get(
        "bos"
    )

    if bos:

        partes.append(
            f"BOS {bos}"
        )

    if estructura.get("choch"):

        partes.append(
            "⚠️ CHoCH"
        )

    return " | ".join(partes)


# ============================================================
# FORMATO TELEGRAM
# ============================================================

def formatear_resultado(
    resultado
):

    if not resultado:

        return "❌ Resultado vacío."

    estado_resultado = resultado.get(
        "estado",
        "SIN_SEÑAL"
    )

    if estado_resultado == "ERROR":

        return (
            "❌ ERROR V4.2.1\n\n"
            f"{resultado.get('motivo', 'Error desconocido')}"
        )

    if estado_resultado == "SIN_SEÑAL":

        direccion = resultado.get(
            "direccion",
            "NEUTRAL"
        )

        precio = resultado.get(
            "precio"
        )

        score = resultado.get(
            "score"
        )

        texto = (
            "🔎 XAU SNIPER AI V4.2.1\n\n"
            "⚪ SIN SEÑAL\n\n"
            f"Dirección: {direccion}\n"
        )

        if precio is not None:

            texto += (
                f"Precio: {precio:.2f}\n"
            )

        if score is not None:

            texto += (
                f"Score: {score}/100\n"
            )

        texto += (
            f"Motivo: "
            f"{resultado.get('motivo', '-')}"
        )

        return texto

    if estado_resultado == "DESCARTADA":

        return (
            "🗑️ XAU SNIPER AI V4.2.1\n\n"
            "❌ DESCARTADA\n\n"
            f"ID: {resultado.get('id', '-')}\n"
            f"Dirección: "
            f"{resultado.get('direccion', '-')}\n"
            f"Score: "
            f"{resultado.get('score', '-')}\n\n"
            f"Motivo: "
            f"{resultado.get('motivo', '-')}"
        )

    if estado_resultado == "PREALERTA":

        direccion = resultado.get(
            "direccion",
            "-"
        )

        emoji = (
            "🟢"
            if direccion == "ALCISTA"
            else "🔴"
        )

        return (
            f"{emoji} POSIBLE "
            f"{'COMPRA' if direccion == 'ALCISTA' else 'VENTA'} "
            f"ANTICIPADA\n\n"
            f"🆔 ID: "
            f"{resultado.get('id', '-')}\n"
            f"📊 Score: "
            f"{resultado.get('score', 0)}/100\n"
            f"💰 Precio: "
            f"{resultado.get('precio', 0):.2f}\n"
            f"📈 RSI: "
            f"{resultado.get('rsi', 0):.1f}\n"
            f"💪 ADX: "
            f"{resultado.get('adx', 0):.1f}\n\n"
            "⚠️ PREALERTA\n"
            "Esperando continuación + "
            "confirmación de momentum."
        )

    if estado_resultado == "CONFIRMADA":

        direccion = resultado.get(
            "direccion",
            "-"
        )

        emoji = (
            "🟢 COMPRA"
            if direccion == "ALCISTA"
            else "🔴 VENTA"
        )

        return (
            "🚨 XAU SNIPER AI V4.2.1\n\n"
            f"✅ SEÑAL CONFIRMADA\n\n"
            f"{emoji}\n\n"
            f"🆔 ID: "
            f"{resultado.get('id', '-')}\n"
            f"💰 Entrada: "
            f"{resultado.get('precio', 0):.2f}\n"
            f"🛑 SL: "
            f"{resultado.get('sl', 0):.2f}\n"
            f"🎯 TP: "
            f"{resultado.get('tp', 0):.2f}\n"
            f"📐 RR: "
            f"{resultado.get('rr', 0):.2f}\n"
            f"📊 Score: "
            f"{resultado.get('score', 0)}/100\n"
            f"📈 RSI: "
            f"{resultado.get('rsi', 0):.1f}\n"
            f"💪 ADX: "
            f"{resultado.get('adx', 0):.1f}\n\n"
            "⚠️ Señal generada para "
            "prueba/paper trading."
        )

    return (
        "🔎 XAU SNIPER AI V4.2.1\n\n"
        f"Estado: {estado_resultado}"
    )


# ============================================================
# RESUMEN DE DIAGNÓSTICO
# ============================================================

def formatear_diagnostico(
    diagnostico
):

    if not diagnostico.get("ok"):

        return (
            "❌ DIAGNÓSTICO\n\n"
            f"{diagnostico.get('error')}"
        )

    estructura5 = texto_estructura(
        diagnostico["estructura5"]
    )

    estructura15 = texto_estructura(
        diagnostico["estructura15"]
    )

    return (
        "🔍 DIAGNÓSTICO XAU/USD\n\n"

        f"💰 Precio: "
        f"{diagnostico['precio']:.2f}\n"

        f"📏 ATR: "
        f"{diagnostico['atr']:.2f}\n"

        f"📈 RSI: "
        f"{diagnostico['rsi']:.1f}\n"

        f"💪 ADX: "
        f"{diagnostico['adx']:.1f}\n\n"

        f"5M: "
        f"{diagnostico['regimen5']}\n"

        f"15M: "
        f"{diagnostico['regimen15']}\n"

        f"Contexto: "
        f"{diagnostico['contexto15']}\n\n"

        f"🏗️ Estructura 5M:\n"
        f"{estructura5}\n\n"

        f"🏗️ Estructura 15M:\n"
        f"{estructura15}\n\n"

        f"🆔 Pendiente: "
        f"{diagnostico.get('prealerta') or 'ninguna'}"
    )


# ============================================================
# PRUEBA DE CONEXIÓN BIQUOTE
# ============================================================

def probar_biquote():

    try:

        df5 = obtener_datos(
            INTERVALO_5M
        )

        df15 = obtener_datos(
            INTERVALO_15M
        )

        return {

            "ok": True,

            "5m": len(df5),

            "15m": len(df15),

            "proveedor": "Biquote",

            "symbol": SYMBOL
        }

    except Exception as e:

        return {

            "ok": False,

            "error": str(e),

            "proveedor": "Biquote"
        }


# ============================================================
# LIMPIAR CACHE
# ============================================================

def limpiar_cache():

    CACHE_5M["df"] = None
    CACHE_5M["timestamp"] = 0

    CACHE_15M["df"] = None
    CACHE_15M["timestamp"] = 0

    print(
        "🧹 Cache de mercado limpiada."
        )


# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================

if __name__ == "__main__":

    print(
        "\n"
        "============================================\n"
        "   XAU SNIPER AI V4.2.1\n"
        "   BIQUOTE DATA ENGINE\n"
        "============================================\n"
    )

    print(
        "🌐 Proveedor: Biquote"
    )

    print(
        f"🥇 Símbolo: {SYMBOL}"
    )

    print(
        "⏱️ 5M + 15M"
    )

    print(
        "🔒 Modo: análisis / paper trading"
    )

    print()

    # ========================================================
    # TEST DE CONEXIÓN
    # ========================================================

    prueba = probar_biquote()

    if not prueba.get("ok"):

        print(
            "❌ ERROR CONECTANDO CON BIQUOTE"
        )

        print(
            prueba.get(
                "error",
                "Error desconocido"
            )
        )

        raise SystemExit(1)

    print(
        "✅ BIQUOTE CONECTADO"
    )

    print(
        f"📊 5M: {prueba['5m']} velas"
    )

    print(
        f"📊 15M: {prueba['15m']} velas"
    )

    print()

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    diagnostico = obtener_diagnostico()

    print(
        formatear_diagnostico(
            diagnostico
        )
    )

    print()

    # ========================================================
    # PRIMER ANÁLISIS
    # ========================================================

    resultado = analizar_mercado()

    print()

    print(
        formatear_resultado(
            resultado
        )
    )

    print()

    print(
        "============================================"
    )

    print(
        "Fin de prueba."
    )
