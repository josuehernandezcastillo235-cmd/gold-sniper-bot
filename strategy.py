import requests
import pandas as pd
import os
import uuid
import time

from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


# ============================================================
# XAU SNIPER AI V4.2
# MOTOR DE ESTRUCTURA + MOMENTUM + LIQUIDEZ
#
# RÉGIMEN
# ↓
# ESTRUCTURA
# ↓
# BOS / CHoCH
# ↓
# IMPULSO REAL
# ↓
# PULLBACK REAL
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


API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"

INTERVALO_5M = "5min"
INTERVALO_15M = "15min"

INTERVALO_ANALISIS = 100


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

BREAK_BUFFER_ATR = 0.05


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
# OBTENER DATOS
# ============================================================

def obtener_datos(intervalo):

    if not API_KEY:
        raise Exception("API_KEY no configurada")

    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": SYMBOL,
        "interval": intervalo,
        "outputsize": 500,
        "apikey": API_KEY,
        "format": "JSON"
    }

    max_intentos = 4

    for intento in range(1, max_intentos + 1):

        try:

            respuesta = requests.get(
                url,
                params=params,
                timeout=20
            )

            if respuesta.status_code == 429:

                espera = min(
                    15,
                    3 * intento
                )

                print(
                    f"⚠️ Twelve Data 429 "
                    f"({intervalo}) | "
                    f"reintento {intento}/{max_intentos} "
                    f"en {espera}s"
                )

                time.sleep(espera)

                continue

            respuesta.raise_for_status()

            data = respuesta.json()

            if not isinstance(data, dict):

                raise Exception(
                    "Respuesta Twelve Data inválida."
                )

            if data.get("status") == "error":

                raise Exception(
                    "Twelve Data: " +
                    str(
                        data.get(
                            "message",
                            "Error desconocido"
                        )
                    )
                )

            if "values" not in data:

                raise Exception(
                    f"Twelve Data sin values: {data}"
                )

            values = data["values"]

            if not isinstance(values, list):

                raise Exception(
                    "Campo values inválido."
                )

            if len(values) < 50:

                raise Exception(
                    f"Datos insuficientes "
                    f"{intervalo}: {len(values)} velas."
                )

            df = pd.DataFrame(values)

            columnas = [
                "open",
                "high",
                "low",
                "close",
                "datetime"
            ]

            faltantes = [
                c for c in columnas
                if c not in df.columns
            ]

            if faltantes:

                raise Exception(
                    f"Faltan columnas: {faltantes}"
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

            df["datetime"] = pd.to_datetime(
                df["datetime"],
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

            df = df.sort_values("datetime")

            df = df.drop_duplicates(
                subset=["datetime"]
            )

            df = df.reset_index(drop=True)

            if len(df) < 50:

                raise Exception(
                    f"Después de limpiar quedaron "
                    f"{len(df)} velas."
                )

            print(
                f"📥 {intervalo}: "
                f"{len(df)} velas recibidas"
            )

            return df

        except requests.exceptions.Timeout:

            if intento >= max_intentos:

                raise Exception(
                    f"Timeout Twelve Data "
                    f"después de {max_intentos} intentos."
                )

            espera = 2 * intento

            print(
                f"⚠️ Timeout {intervalo}. "
                f"Reintentando en {espera}s..."
            )

            time.sleep(espera)

        except requests.exceptions.RequestException as e:

            if intento >= max_intentos:

                raise Exception(
                    f"Error HTTP Twelve Data: {e}"
                )

            espera = 2 * intento

            print(
                f"⚠️ Error HTTP {intervalo}: "
                f"{e}. Reintentando..."
            )

            time.sleep(espera)

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
        df["close"] - df["open"]
    ).abs()

    df["rango"] = (
        df["high"] - df["low"]
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

    print(
        f"📊 Velas útiles: {len(df)}"
    )

    return df


# ============================================================
# SOLO VELAS CERRADAS
# ============================================================

def velas_cerradas(df):

    if df is None:

        return pd.DataFrame()

    if len(df) < 5:

        return df.copy()

    return df.iloc[:-1].copy()


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

    for i in range(inicio, final):

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
# BUSCAR ÚLTIMOS SWINGS ANTERIORES
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

    # ========================================================
    # PRECIO ACTUAL
    # ========================================================

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
    #
    # Usamos swing confirmado.
    # Además exigimos cierre + buffer ATR.
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
    #
    # No basta con tocar el swing.
    # Necesitamos cierre estructural + desplazamiento mínimo.
    # ========================================================

    if resultado["direccion"] == "ALCISTA":

        if resultado["ultimo_low"] is not None:

            nivel = float(
                resultado["ultimo_low"]["precio"]
            )

            ruptura = (
                precio_actual <
                nivel -
                atr_actual * CHOCH_MIN_ATR
            )

            if ruptura:

                resultado["choch"] = True

                resultado["choch_nivel"] = nivel

    elif resultado["direccion"] == "BAJISTA":

        if resultado["ultimo_high"] is not None:

            nivel = float(
                resultado["ultimo_high"]["precio"]
            )

            ruptura = (
                precio_actual >
                nivel +
                atr_actual * CHOCH_MIN_ATR
            )

            if ruptura:

                resultado["choch"] = True

                resultado["choch_nivel"] = nivel

    return resultado


# ============================================================
# RÉGIMEN
# ============================================================

def detectar_regimen(df):

    if df is None or len(df) < 30:

        return "LATERAL"

    actual = df.iloc[-1]

    try:

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
        and
        ema20 > ema50
        and
        ema50 > ema200
        and
        pendiente20 > 0
        and
        pendiente50 >= 0
        and
        adx >= 18
    ):

        return "ALCISTA"

    if (
        precio < ema20
        and
        ema20 < ema50
        and
        ema50 < ema200
        and
        pendiente20 < 0
        and
        pendiente50 <= 0
        and
        adx >= 18
    ):

        return "BAJISTA"

    if (
        rango_atr < 3.0
        and
        adx < 18
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

        desplazamiento_atr = (
            desplazamiento / atr
        )

        if desplazamiento_atr < IMPULSO_ATR_MIN:

            return None

        velas_direccion = int(
            (
                ventana["direccion_vela"] ==
                (
                    1
                    if direccion == "ALCISTA"
                    else -1
                )
            ).sum()
        )

        expansion = int(
            ventana["expansion"].sum()
        )

        cambio = (
            float(ventana.iloc[-1]["close"]) -
            float(ventana.iloc[0]["close"])
        )

        if direccion == "BAJISTA":

            cambio = abs(cambio)

        else:

            cambio = abs(cambio)

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
#
# Busca primero un extremo.
# El impulso termina ANTES del pullback.
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

        # Dejamos mínimo 2 velas posteriores
        # al extremo para que exista pullback.
        rango_extremos = datos.iloc[
            : -PULLBACK_VELAS_MIN
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

        impulso["indice_extremo"] = int(
            pos
        )

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
            : -PULLBACK_VELAS_MIN
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

        impulso["indice_extremo"] = int(
            pos
        )

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
#
# IMPORTANTE:
# El pullback empieza DESPUÉS del extremo del impulso.
# Ya no se mezclan ambas fases.
# ============================================================

def detectar_pullback_alcista(
    df,
    impulso
):

    if (
        df is None
        or
        impulso is None
    ):

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

        # Como el índice viene de la ventana
        # local del impulso, calculamos la posición
        # absoluta aproximada.
        inicio_ventana = len(df) - IMPULSO_LOOKBACK

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

            # Usamos solamente las últimas
            # velas permitidas del pullback.
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

        # El precio no debe haber destruido
        # la base del impulso.
        if precio < (
            inicio -
            atr * 0.10
        ):

            return None

        # Para una prealerta todavía no queremos
        # que el precio haya confirmado la ruptura
        # del extremo.
        if precio > (
            extremo +
            atr * 0.50
        ):

            return None

        return {

            "direccion": "ALCISTA",

            "maximo_pullback":
                minimo_pullback,

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

    if (
        df is None
        or
        impulso is None
    ):

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

        inicio_ventana = len(df) - IMPULSO_LOOKBACK

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
                maximo_pullback,

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
# VALIDAR CALIDAD DEL PULLBACK
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
            pullback["retracement"] >
            PULLBACK_MAX_RETRACEMENT
        ):

            return False

        if (
            pullback["retroceso_atr"] >
            PULLBACK_MAX_ATR
        ):

            return False

        if direccion == "ALCISTA":

            return (
                float(df.iloc[-1]["close"])
                >=
                float(
                    pullback["inicio_impulso"]
                )
            )

        return (
            float(df.iloc[-1]["close"])
            <=
            float(
                pullback["inicio_impulso"]
            )
        )

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
        or
        pullback is None
        or
        len(df) < 2
    ):

        return False, None

    try:

        actual = df.iloc[-1]

        precio = float(
            actual["close"]
        )

        apertura = float(
            actual["open"]
        )

        cuerpo = float(
            actual["cuerpo"]
        )

        atr = float(
            actual["atr"]
        )

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
            precio >
            apertura
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
                and
                vela_alcista
                and
                cuerpo_ok
                and
                avance_ok
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
        or
        pullback is None
        or
        len(df) < 2
    ):

        return False, None

    try:

        actual = df.iloc[-1]

        precio = float(
            actual["close"]
        )

        apertura = float(
            actual["open"]
        )

        cuerpo = float(
            actual["cuerpo"]
        )

        atr = float(
            actual["atr"]
        )

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
            precio <
            apertura
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
                and
                vela_bajista
                and
                cuerpo_ok
                and
                avance_ok
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
        or
        atr is None
        or
        atr <= 0
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
        or
        atr is None
        or
        atr <= 0
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

        # Sweep de mínimos:
        # rompe abajo y recupera arriba.
        resultado["sweep_alcista"] = (
            low_actual <
            low_previo - buffer
            and
            close_actual >
            low_previo
        )

        # Sweep de máximos:
        # rompe arriba y recupera abajo.
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

                if precio not in zonas:

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
        or
        atr <= 0
    ):

        return 0

    if not zonas:

        return 1

    mejor_distancia = min(
        abs(
            precio -
            float(zona)
        )
        for zona in zonas
    )

    if mejor_distancia <= (
        atr * ZONA_MAX_ATR
    ):

        return 2

    return 1


# ============================================================
# MOMENTUM COMPRA
# ============================================================

def evaluar_momentum_compra(actual):

    score = 0

    try:

        rsi = float(actual["rsi"])
        adx = float(actual["adx"])

        di_plus = float(
            actual["di_plus"]
        )

        di_minus = float(
            actual["di_minus"]
        )

        pendiente20 = float(
            actual["pendiente_ema20"]
        )

        rsi_slope = float(
            actual["rsi_slope"]
        )

        if rsi >= RSI_COMPRA_MIN:
            score += 1

        if rsi >= RSI_CONFIRMACION_COMPRA:
            score += 1

        if adx >= ADX_MINIMO:
            score += 1

        if adx >= ADX_FUERTE:
            score += 1

        if di_plus > di_minus:
            score += 1

        if pendiente20 > 0:
            score += 1

        if rsi_slope > 0:
            score += 1

    except Exception:

        return 0

    return score


# ============================================================
# MOMENTUM VENTA
# ============================================================

def evaluar_momentum_venta(actual):

    score = 0

    try:

        rsi = float(actual["rsi"])
        adx = float(actual["adx"])

        di_plus = float(
            actual["di_plus"]
        )

        di_minus = float(
            actual["di_minus"]
        )

        pendiente20 = float(
            actual["pendiente_ema20"]
        )

        rsi_slope = float(
            actual["rsi_slope"]
        )

        if rsi <= RSI_VENTA_MAX:
            score += 1

        if rsi <= RSI_CONFIRMACION_VENTA:
            score += 1

        if adx >= ADX_MINIMO:
            score += 1

        if adx >= ADX_FUERTE:
            score += 1

        if di_minus > di_plus:
            score += 1

        if pendiente20 < 0:
            score += 1

        if rsi_slope < 0:
            score += 1

    except Exception:

        return 0

    return score


# ============================================================
# SCORE COMPRA
# ============================================================

def calcular_score_compra_v4(
    estructura,
    contexto15,
    regimen,
    impulso,
    pullback,
    continuacion,
    liquidez,
    ubicacion,
    momentum,
    precio,
    ema20,
    ema50,
    rsi,
    adx,
    di_plus,
    di_minus
):

    score = 0

    # ESTRUCTURA
    if estructura.get("direccion") == "ALCISTA":
        score += 15

    if estructura.get("hh"):
        score += 5

    if estructura.get("hl"):
        score += 5

    if estructura.get("bos") == "ALCISTA":
        score += 8

    # 15M
    if contexto15 == "ALCISTA":
        score += 10

    elif contexto15 == "NEUTRAL":
        score += 4

    # RÉGIMEN
    if regimen == "ALCISTA":
        score += 8

    elif regimen == "TRANSICION":
        score += 4

    # IMPULSO
    if impulso is not None:

        score += 10

        if impulso.get("calidad", 0) >= 5:
            score += 3

    # PULLBACK
    if pullback is not None:
        score += 8

    # CONTINUACIÓN
    if continuacion:
        score += 8

    # LIQUIDEZ
    if liquidez.get(
        "sweep_alcista",
        False
    ):
        score += 5

    # UBICACIÓN
    if ubicacion >= 2:
        score += 3

    # MOMENTUM
    score += min(
        int(momentum),
        7
    )

    if rsi >= RSI_COMPRA_MIN:
        score += 2

    if di_plus > di_minus:
        score += 2

    if adx >= ADX_FUERTE:
        score += 2

    if ema20 > ema50:
        score += 2

    return min(
        int(score),
        100
    )


# ============================================================
# SCORE VENTA
# ============================================================

def calcular_score_venta_v4(
    estructura,
    contexto15,
    regimen,
    impulso,
    pullback,
    continuacion,
    liquidez,
    ubicacion,
    momentum,
    precio,
    ema20,
    ema50,
    rsi,
    adx,
    di_plus,
    di_minus
):

    score = 0

    if estructura.get("direccion") == "BAJISTA":
        score += 15

    if estructura.get("lh"):
        score += 5

    if estructura.get("ll"):
        score += 5

    if estructura.get("bos") == "BAJISTA":
        score += 8

    if contexto15 == "BAJISTA":
        score += 10

    elif contexto15 == "NEUTRAL":
        score += 4

    if regimen == "BAJISTA":
        score += 8

    elif regimen == "TRANSICION":
        score += 4

    if impulso is not None:

        score += 10

        if impulso.get("calidad", 0) >= 5:
            score += 3

    if pullback is not None:
        score += 8

    if continuacion:
        score += 8

    if liquidez.get(
        "sweep_bajista",
        False
    ):
        score += 5

    if ubicacion >= 2:
        score += 3

    score += min(
        int(momentum),
        7
    )

    if rsi <= RSI_VENTA_MAX:
        score += 2

    if di_minus > di_plus:
        score += 2

    if adx >= ADX_FUERTE:
        score += 2

    if ema20 < ema50:
        score += 2

    return min(
        int(score),
        100
    )


# ============================================================
# PREALERTA COMPRA
# ============================================================

def crear_prealerta_compra(
    precio,
    atr,
    score,
    estructura,
    impulso,
    pullback,
    rsi,
    adx,
    di_plus,
    di_minus,
    ema20,
    ema50,
    regimen,
    contexto15
):

    identificador = generar_id()

    nivel = float(
        pullback["nivel_continuacion"]
    )

    sl = (
        precio -
        atr * ATR_SL
    )

    tp = (
        precio +
        atr * ATR_TP
    )

    return {

        "tipo":
            "POSIBLE_COMPRA_ANTICIPADA",

        "id":
            identificador,

        "mensaje":
            (
                f"🟡 POSIBLE COMPRA ANTICIPADA\n"
                f"🆔 ID: {identificador}\n\n"
                f"⭐ Score: {score}/100\n"
                f"💰 Precio: {precio:.2f}\n"
                f"🛑 SL ref: {sl:.2f}\n"
                f"🎯 TP ref: {tp:.2f}\n"
                f"📍 Nivel continuación: "
                f"{nivel:.2f}\n\n"
                f"🏗️ Estructura 5M: "
                f"{estructura.get('direccion')}\n"
                f"📊 Contexto 15M: "
                f"{contexto15}\n"
                f"📈 Régimen: {regimen}\n"
                f"RSI: {rsi:.1f}\n"
                f"ADX: {adx:.1f}\n"
                f"DI+: {di_plus:.1f}\n"
                f"DI-: {di_minus:.1f}\n\n"
                f"⚠️ Esperando continuación "
                f"alcista confirmada."
            ),

        "precio": precio,
        "sl": sl,
        "tp": tp,
        "score": score,
        "atr": atr
    }


# ============================================================
# PREALERTA VENTA
# ============================================================

def crear_prealerta_venta(
    precio,
    atr,
    score,
    estructura,
    impulso,
    pullback,
    rsi,
    adx,
    di_plus,
    di_minus,
    ema20,
    ema50,
    regimen,
    contexto15
):

    identificador = generar_id()

    nivel = float(
        pullback["nivel_continuacion"]
    )

    sl = (
        precio +
        atr * ATR_SL
    )

    tp = (
        precio -
        atr * ATR_TP
    )

    return {

        "tipo":
            "POSIBLE_VENTA_ANTICIPADA",

        "id":
            identificador,

        "mensaje":
            (
                f"🟡 POSIBLE VENTA ANTICIPADA\n"
                f"🆔 ID: {identificador}\n\n"
                f"⭐ Score: {score}/100\n"
                f"💰 Precio: {precio:.2f}\n"
                f"🛑 SL ref: {sl:.2f}\n"
                f"🎯 TP ref: {tp:.2f}\n"
                f"📍 Nivel continuación: "
                f"{nivel:.2f}\n\n"
                f"🏗️ Estructura 5M: "
                f"{estructura.get('direccion')}\n"
                f"📊 Contexto 15M: "
                f"{contexto15}\n"
                f"📉 Régimen: {regimen}\n"
                f"RSI: {rsi:.1f}\n"
                f"ADX: {adx:.1f}\n"
                f"DI+: {di_plus:.1f}\n"
                f"DI-: {di_minus:.1f}\n\n"
                f"⚠️ Esperando continuación "
                f"bajista confirmada."
            ),

        "precio": precio,
        "sl": sl,
        "tp": tp,
        "score": score,
        "atr": atr
    }


# ============================================================
# CONFIRMACIÓN COMPRA
# ============================================================

def crear_compra_confirmada(
    precio,
    atr,
    score,
    rsi,
    adx,
    di_plus,
    di_minus,
    ema20,
    ema50
):

    identificador = generar_id()

    sl = (
        precio -
        atr * ATR_SL
    )

    tp = (
        precio +
        atr * ATR_TP
    )

    return {

        "tipo":
            "COMPRA_CONFIRMADA",

        "id":
            identificador,

        "mensaje":
            (
                f"🟢 COMPRA CONFIRMADA\n"
                f"🆔 ID: {identificador}\n\n"
                f"⭐ Score: {score}/100\n"
                f"💰 Entrada: {precio:.2f}\n"
                f"🛑 SL: {sl:.2f}\n"
                f"🎯 TP: {tp:.2f}\n"
                f"📐 RR aprox: "
                f"{ATR_TP / ATR_SL:.2f}\n\n"
                f"RSI: {rsi:.1f}\n"
                f"ADX: {adx:.1f}\n"
                f"DI+: {di_plus:.1f}\n"
                f"DI-: {di_minus:.1f}"
            ),

        "precio": precio,
        "sl": sl,
        "tp": tp,
        "score": score,
        "atr": atr
    }


# ============================================================
# CONFIRMACIÓN VENTA
# ============================================================

def crear_venta_confirmada(
    precio,
    atr,
    score,
    rsi,
    adx,
    di_plus,
    di_minus,
    ema20,
    ema50
):

    identificador = generar_id()

    sl = (
        precio +
        atr * ATR_SL
    )

    tp = (
        precio -
        atr * ATR_TP
    )

    return {

        "tipo":
            "VENTA_CONFIRMADA",

        "id":
            identificador,

        "mensaje":
            (
                f"🔴 VENTA CONFIRMADA\n"
                f"🆔 ID: {identificador}\n\n"
                f"⭐ Score: {score}/100\n"
                f"💰 Entrada: {precio:.2f}\n"
                f"🛑 SL: {sl:.2f}\n"
                f"🎯 TP: {tp:.2f}\n"
                f"📐 RR aprox: "
                f"{ATR_TP / ATR_SL:.2f}\n\n"
                f"RSI: {rsi:.1f}\n"
                f"ADX: {adx:.1f}\n"
                f"DI+: {di_plus:.1f}\n"
                f"DI-: {di_minus:.1f}"
            ),

        "precio": precio,
        "sl": sl,
        "tp": tp,
        "score": score,
        "atr": atr
    }


# ============================================================
# DESCARTADA
# ============================================================

def crear_descartada(
    direccion,
    motivo
):

    identificador = (
        estado["id_pendiente"]
        or
        generar_id()
    )

    estado["ultima_descartada"] = time.time()

    limpiar_pendiente()

    return {

        "tipo":
            "DESCARTADA",

        "id":
            identificador,

        "direccion":
            direccion,

        "mensaje":
            (
                f"❌ SEÑAL DESCARTADA\n"
                f"🆔 ID: {identificador}\n"
                f"📌 Dirección: {direccion}\n\n"
                f"{motivo}"
            )
    }


# ============================================================
# EXPIRACIÓN
# ============================================================

def comprobar_expiracion(
    ahora
):

    direccion = (
        estado["direccion_pendiente"]
    )

    if direccion is None:

        return None

    inicio = (
        estado["inicio_pendiente"]
    )

    if inicio <= 0:

        return None

    edad = (
        ahora -
        inicio
    )

    if edad < (
        MINUTOS_VIDA_PREALERTA * 60
    ):

        return None

    identificador = (
        estado["id_pendiente"]
        or
        generar_id()
    )

    estado["ultima_descartada"] = ahora

    limpiar_pendiente()

    return {

        "tipo":
            "DESCARTADA",

        "id":
            identificador,

        "mensaje":
            (
                f"❌ PREALERTA EXPIRADA\n"
                f"🆔 ID: {identificador}\n\n"
                f"⏱️ La prealerta superó "
                f"{MINUTOS_VIDA_PREALERTA} minutos "
                f"sin confirmación."
            )
    }


# ============================================================
# VALIDAR ESTADO
# ============================================================

def estado_valido():

    direccion = (
        estado["direccion_pendiente"]
    )

    if direccion is None:

        return True

    if direccion not in (
        "COMPRA",
        "VENTA"
    ):

        limpiar_pendiente()

        return False

    if estado["id_pendiente"] is None:

        limpiar_pendiente()

        return False

    if estado["inicio_pendiente"] <= 0:

        limpiar_pendiente()

        return False

    if estado["nivel_continuacion"] is None:

        limpiar_pendiente()

        return False

    return True


# ============================================================
# VALIDAR PREALERTA CONTRA ESTRUCTURA ACTUAL
# ============================================================

def validar_prealerta_compra(
    estructura,
    regimen,
    contexto15,
    precio,
    atr
):

    if estructura["choch"]:

        return False, (
            "📉 CHoCH bajista detectado. "
            "La estructura dejó de favorecer "
            "la compra."
        )

    if (
        regimen == "BAJISTA"
        and
        contexto15 == "BAJISTA"
    ):

        return False, (
            "📉 Régimen 5M y contexto 15M "
            "pasaron a bajista."
        )

    impulso_inicio = (
        estado["impulso_inicio"]
    )

    if impulso_inicio is not None:

        if precio < (
            float(impulso_inicio) -
            atr * 0.35
        ):

            return False, (
                "❌ El precio rompió la base "
                "del impulso alcista."
            )

    return True, None


# ============================================================
# VALIDAR PREALERTA VENTA
# ============================================================

def validar_prealerta_venta(
    estructura,
    regimen,
    contexto15,
    precio,
    atr
):

    if estructura["choch"]:

        return False, (
            "📈 CHoCH alcista detectado. "
            "La estructura dejó de favorecer "
            "la venta."
        )

    if (
        regimen == "ALCISTA"
        and
        contexto15 == "ALCISTA"
    ):

        return False, (
            "📈 Régimen 5M y contexto 15M "
            "pasaron a alcista."
        )

    impulso_inicio = (
        estado["impulso_inicio"]
    )

    if impulso_inicio is not None:

        if precio > (
            float(impulso_inicio) +
            atr * 0.35
        ):

            return False, (
                "❌ El precio rompió la base "
                "del impulso bajista."
            )

    return True, None


# ============================================================
# ANALIZAR V4.2
# ============================================================

def analizar():

    try:

        print("")
        print("===================================")
        print("🔍 ANALIZANDO XAU/USD V4.2")
        print("===================================")

        ahora = time.time()

        # ====================================================
        # VALIDAR ESTADO
        # ====================================================

        estado_valido()

        # ====================================================
        # EXPIRACIÓN
        # ====================================================

        expiracion = comprobar_expiracion(
            ahora
        )

        if expiracion is not None:

            print(
                "🔴 PREALERTA EXPIRADA"
            )

            return expiracion

        # ====================================================
        # DATOS
        # ====================================================

        df5 = obtener_datos(
            INTERVALO_5M
        )

        df15 = obtener_datos(
            INTERVALO_15M
        )

        # ====================================================
        # INDICADORES
        # ====================================================

        df5 = calcular_indicadores(
            df5
        )

        df15 = calcular_indicadores(
            df15
        )

        # ====================================================
        # SOLO VELAS CERRADAS
        # ====================================================

        df5 = velas_cerradas(
            df5
        )

        df15 = velas_cerradas(
            df15
        )

        if len(df5) < 100:

            raise Exception(
                f"Datos 5M insuficientes: "
                f"{len(df5)}"
            )

        if len(df15) < 100:

            raise Exception(
                f"Datos 15M insuficientes: "
                f"{len(df15)}"
            )

        # ====================================================
        # ACTUAL
        # ====================================================

        actual = df5.iloc[-1]

        precio = float(
            actual["close"]
        )

        ema20 = float(
            actual["ema20"]
        )

        ema50 = float(
            actual["ema50"]
        )

        rsi = float(
            actual["rsi"]
        )

        atr = float(
            actual["atr"]
        )

        adx = float(
            actual["adx"]
        )

        di_plus = float(
            actual["di_plus"]
        )

        di_minus = float(
            actual["di_minus"]
        )

        if atr <= 0:

            raise Exception(
                "ATR inválido."
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

        regimen5 = detectar_regimen(
            df5
        )

        contexto15 = obtener_contexto_15m(
            estructura15,
            df15
        )

        # ====================================================
        # IMPULSOS
        # ====================================================

        impulso_compra = (
            detectar_impulso_alcista(
                df5
            )
        )

        impulso_venta = (
            detectar_impulso_bajista(
                df5
            )
        )

        # ====================================================
        # PULLBACKS
        # ====================================================

        pullback_compra = (
            detectar_pullback_alcista(
                df5,
                impulso_compra
            )
        )

        pullback_venta = (
            detectar_pullback_bajista(
                df5,
                impulso_venta
            )
        )

        # ====================================================
        # CONTINUACIÓN
        # ====================================================

        continuacion_compra, zona_compra = (
            detectar_continuacion_alcista(
                df5,
                pullback_compra
            )
        )

        continuacion_venta, zona_venta = (
            detectar_continuacion_bajista(
                df5,
                pullback_venta
            )
        )

        # ====================================================
        # PREALERTA ACTIVA
        #
        # CONGELAMOS EL NIVEL ORIGINAL
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "COMPRA"
            and
            estado["nivel_continuacion"]
            is not None
        ):

            zona_compra = float(
                estado["nivel_continuacion"]
            )

        if (
            estado["direccion_pendiente"]
            == "VENTA"
            and
            estado["nivel_continuacion"]
            is not None
        ):

            zona_venta = float(
                estado["nivel_continuacion"]
            )

        # ====================================================
        # ENTRADA TARDÍA
        # ====================================================

        tardia_compra = (
            entrada_tardia_compra(
                precio,
                zona_compra,
                atr
            )
        )

        tardia_venta = (
            entrada_tardia_venta(
                precio,
                zona_venta,
                atr
            )
        )

        # ====================================================
        # LIQUIDEZ
        # ====================================================

        liquidez = detectar_liquidez(
            df5
        )

        # ====================================================
        # S/R
        # ====================================================

        zonas = obtener_zonas_sr(
            df5,
            estructura5
        )

        ubicacion_compra = evaluar_ubicacion(
            precio,
            atr,
            "ALCISTA",
            zonas
        )

        ubicacion_venta = evaluar_ubicacion(
            precio,
            atr,
            "BAJISTA",
            zonas
        )

        # ====================================================
        # MOMENTUM
        # ====================================================

        momentum_compra = (
            evaluar_momentum_compra(
                actual
            )
        )

        momentum_venta = (
            evaluar_momentum_venta(
                actual
            )
        )

        # ====================================================
        # SCORE
        # ====================================================

        score_compra = (
            calcular_score_compra_v4(
                estructura5,
                contexto15,
                regimen5,
                impulso_compra,
                pullback_compra,
                continuacion_compra,
                liquidez,
                ubicacion_compra,
                momentum_compra,
                precio,
                ema20,
                ema50,
                rsi,
                adx,
                di_plus,
                di_minus
            )
        )

        score_venta = (
            calcular_score_venta_v4(
                estructura5,
                contexto15,
                regimen5,
                impulso_venta,
                pullback_venta,
                continuacion_venta,
                liquidez,
                ubicacion_venta,
                momentum_venta,
                precio,
                ema20,
                ema50,
                rsi,
                adx,
                di_plus,
                di_minus
            )
        )

        # ====================================================
        # DIAGNÓSTICO
        # ====================================================

        print("")
        print("🏗️ ESTRUCTURA")
        print("-----------------------------------")

        print(
            f"5M: {estructura5['direccion']}"
        )

        print(
            f"15M: {estructura15['direccion']}"
        )

        print(
            f"Régimen 5M: {regimen5}"
        )

        print(
            f"Contexto 15M: {contexto15}"
        )

        print(
            f"BOS: {estructura5['bos']}"
        )

        print(
            f"Nivel BOS: "
            f"{estructura5['bos_nivel']}"
        )

        print(
            f"CHoCH: {estructura5['choch']}"
        )

        print(
            f"Nivel CHoCH: "
            f"{estructura5['choch_nivel']}"
        )

        print(
            f"HH: {estructura5['hh']} | "
            f"HL: {estructura5['hl']}"
        )

        print(
            f"LH: {estructura5['lh']} | "
            f"LL: {estructura5['ll']}"
        )

        print("")
        print("🚀 MOVIMIENTO")
        print("-----------------------------------")

        print(
            f"Impulso compra: "
            f"{impulso_compra is not None}"
        )

        if impulso_compra:

            print(
                f"  ↳ Calidad: "
                f"{impulso_compra['calidad']}/6"
            )

            print(
                f"  ↳ Desplazamiento: "
                f"{impulso_compra['desplazamiento_atr']:.2f} ATR"
            )

        print(
            f"Impulso venta: "
            f"{impulso_venta is not None}"
        )

        if impulso_venta:

            print(
                f"  ↳ Calidad: "
                f"{impulso_venta['calidad']}/6"
            )

            print(
                f"  ↳ Desplazamiento: "
                f"{impulso_venta['desplazamiento_atr']:.2f} ATR"
            )

        print(
            f"Pullback compra: "
            f"{pullback_compra is not None}"
        )

        if pullback_compra:

            print(
                f"  ↳ Retroceso: "
                f"{pullback_compra['retracement'] * 100:.1f}%"
            )

        print(
            f"Pullback venta: "
            f"{pullback_venta is not None}"
        )

        if pullback_venta:

            print(
                f"  ↳ Retroceso: "
                f"{pullback_venta['retracement'] * 100:.1f}%"
            )

        print(
            f"Continuación compra: "
            f"{continuacion_compra}"
        )

        print(
            f"Continuación venta: "
            f"{continuacion_venta}"
        )

        print("")
        print("💧 LIQUIDEZ")
        print("-----------------------------------")

        print(
            f"Sweep alcista: "
            f"{liquidez['sweep_alcista']}"
        )

        print(
            f"Sweep bajista: "
            f"{liquidez['sweep_bajista']}"
        )

        print("")
        print("📊 MOMENTUM")
        print("-----------------------------------")

        print(
            f"RSI: {rsi:.1f}"
        )

        print(
            f"ADX: {adx:.1f}"
        )

        print(
            f"DI+: {di_plus:.1f}"
        )

        print(
            f"DI-: {di_minus:.1f}"
        )

        print(
            f"Momentum compra: "
            f"{momentum_compra}/7"
        )

        print(
            f"Momentum venta: "
            f"{momentum_venta}/7"
        )

        print("")
        print("⭐ SCORE")
        print("-----------------------------------")

        print(
            f"Compra: "
            f"{score_compra}/100"
        )

        print(
            f"Venta: "
            f"{score_venta}/100"
        )

        # ====================================================
        # PREALERTA ACTIVA
        # ====================================================

        if (
            estado["direccion_pendiente"]
            is not None
        ):

            estado["velas_pendiente"] += 1

            direccion = (
                estado[
                    "direccion_pendiente"
                ]
            )

            # =================================================
            # COMPRA PENDIENTE
            # =================================================

            if direccion == "COMPRA":

                valida, motivo = (
                    validar_prealerta_compra(
                        estructura5,
                        regimen5,
                        contexto15,
                        precio,
                        atr
                    )
                )

                if not valida:

                    return crear_descartada(
                        "COMPRA",
                        motivo
                    )

                # ---------------------------------------------
                # CONFIRMACIÓN
                # ---------------------------------------------

                nivel = float(
                    estado[
                        "nivel_continuacion"
                    ]
                )

                confirmacion_valida = (
                    continuacion_compra
                    and
                    precio >
                    nivel +
                    atr * BREAK_BUFFER_ATR
                    and
                    score_compra >=
                    SCORE_MIN_CONFIRMACION
                    and
                    not tardia_compra
                    and
                    rsi >=
                    RSI_CONFIRMACION_COMPRA
                    and
                    di_plus > di_minus
                )

                if confirmacion_valida:

                    resultado = (
                        crear_compra_confirmada(
                            precio,
                            atr,
                            score_compra,
                            rsi,
                            adx,
                            di_plus,
                            di_minus,
                            ema20,
                            ema50
                        )
                    )

                    limpiar_pendiente()

                    estado[
                        "ultima_confirmacion"
                    ] = ahora

                    return resultado

                print(
                    "⏳ COMPRA PENDIENTE..."
                )

                return {

                    "tipo":
                        "SIN_SEÑAL",

                    "mensaje":
                        (
                            "🔎 Compra pendiente. "
                            "Esperando ruptura "
                            "confirmada."
                        )
                }

            # =================================================
            # VENTA PENDIENTE
            # =================================================

            if direccion == "VENTA":

                valida, motivo = (
                    validar_prealerta_venta(
                        estructura5,
                        regimen5,
                        contexto15,
                        precio,
                        atr
                    )
                )

                if not valida:

                    return crear_descartada(
                        "VENTA",
                        motivo
                    )

                nivel = float(
                    estado[
                        "nivel_continuacion"
                    ]
                )

                confirmacion_valida = (
                    continuacion_venta
                    and
                    precio <
                    nivel -
                    atr * BREAK_BUFFER_ATR
                    and
                    score_venta >=
                    SCORE_MIN_CONFIRMACION
                    and
                    not tardia_venta
                    and
                    rsi <=
                    RSI_CONFIRMACION_VENTA
                    and
                    di_minus > di_plus
                )

                if confirmacion_valida:

                    resultado = (
                        crear_venta_confirmada(
                            precio,
                            atr,
                            score_venta,
                            rsi,
                            adx,
                            di_plus,
                            di_minus,
                            ema20,
                            ema50
                        )
                    )

                    limpiar_pendiente()

                    estado[
                        "ultima_confirmacion"
                    ] = ahora

                    return resultado

                print(
                    "⏳ VENTA PENDIENTE..."
                )

                return {

                    "tipo":
                        "SIN_SEÑAL",

                    "mensaje":
                        (
                            "🔎 Venta pendiente. "
                            "Esperando ruptura "
                            "confirmada."
                        )
                }

        # ====================================================
        # NUEVAS PREALERTAS
        #
        # La continuación NO es requisito aquí.
        # ====================================================

        posible_compra = (

            estructura5["direccion"]
            == "ALCISTA"

            and

            impulso_compra is not None

            and

            pullback_compra is not None

            and

            pullback_sano(
                df5,
                pullback_compra,
                "ALCISTA"
            )

            and

            not tardia_compra

            and

            not estructura5["choch"]

            and

            regimen5 != "BAJISTA"

            and

            contexto15 != "BAJISTA"

            and

            score_compra >=
            SCORE_MIN_PREALERTA
        )

        posible_venta = (

            estructura5["direccion"]
            == "BAJISTA"

            and

            impulso_venta is not None

            and

            pullback_venta is not None

            and

            pullback_sano(
                df5,
                pullback_venta,
                "BAJISTA"
            )

            and

            not tardia_venta

            and

            not estructura5["choch"]

            and

            regimen5 != "ALCISTA"

            and

            contexto15 != "ALCISTA"

            and

            score_venta >=
            SCORE_MIN_PREALERTA
        )

        # ====================================================
        # COOLDOWN
        # ====================================================

        if (
            ahora -
            estado["ultima_descartada"]
            <
            COOLDOWN_DESCARTADA * 60
        ):

            return {

                "tipo":
                    "SIN_SEÑAL",

                "mensaje":
                    (
                        "😴 Cooldown después "
                        "de señal descartada."
                    )
            }

        # ====================================================
        # PREALERTA COMPRA
        # ====================================================

        if posible_compra:

            if (
                ahora -
                estado["ultima_prealerta"]
                >=
                MINUTOS_REPETICION * 60
            ):

                resultado = (
                    crear_prealerta_compra(
                        precio,
                        atr,
                        score_compra,
                        estructura5,
                        impulso_compra,
                        pullback_compra,
                        rsi,
                        adx,
                        di_plus,
                        di_minus,
                        ema20,
                        ema50,
                        regimen5,
                        contexto15
                    )
                )

                estado[
                    "direccion_pendiente"
                ] = "COMPRA"

                estado[
                    "id_pendiente"
                ] = resultado["id"]

                estado[
                    "inicio_pendiente"
                ] = ahora

                estado[
                    "ultima_prealerta"
                ] = ahora

                estado[
                    "precio_prealerta"
                ] = precio

                estado[
                    "atr_prealerta"
                ] = atr

                estado[
                    "impulso_inicio"
                ] = impulso_compra[
                    "inicio"
                ]

                estado[
                    "impulso_extremo"
                ] = impulso_compra[
                    "extremo"
                ]

                estado[
                    "impulso_indice_extremo"
                ] = impulso_compra[
                    "indice_extremo"
                ]

                estado[
                    "pullback_nivel"
                ] = pullback_compra[
                    "minimo_pullback"
                ]

                estado[
                    "nivel_continuacion"
                ] = pullback_compra[
                    "nivel_continuacion"
                ]

                estado[
                    "swing_referencia"
                ] = pullback_compra[
                    "extremo_impulso"
                ]

                estado[
                    "velas_pendiente"
                ] = 0

                print(
                    "🟡 NUEVA PREALERTA COMPRA"
                )

                return resultado

        # ====================================================
        # PREALERTA VENTA
        # ====================================================

        if posible_venta:

            if (
                ahora -
                estado["ultima_prealerta"]
                >=
                MINUTOS_REPETICION * 60
            ):

                resultado = (
                    crear_prealerta_venta(
                        precio,
                        atr,
                        score_venta,
                        estructura5,
                        impulso_venta,
                        pullback_venta,
                        rsi,
                        adx,
                        di_plus,
                        di_minus,
                        ema20,
                        ema50,
                        regimen5,
                        contexto15
                    )
                )

                estado[
                    "direccion_pendiente"
                ] = "VENTA"

                estado[
                    "id_pendiente"
                ] = resultado["id"]

                estado[
                    "inicio_pendiente"
                ] = ahora

                estado[
                    "ultima_prealerta"
                ] = ahora

                estado[
                    "precio_prealerta"
                ] = precio

                estado[
                    "atr_prealerta"
                ] = atr

                estado[
                    "impulso_inicio"
                ] = impulso_venta[
                    "inicio"
                ]

                estado[
                    "impulso_extremo"
                ] = impulso_venta[
                    "extremo"
                ]

                estado[
                    "impulso_indice_extremo"
                ] = impulso_venta[
                    "indice_extremo"
                ]

                estado[
                    "pullback_nivel"
                ] = pullback_venta[
                    "maximo_pullback"
                ]

                estado[
                    "nivel_continuacion"
                ] = pullback_venta[
                    "nivel_continuacion"
                ]

                estado[
                    "swing_referencia"
                ] = pullback_venta[
                    "extremo_impulso"
                ]

                estado[
                    "velas_pendiente"
                ] = 0

                print(
                    "🟡 NUEVA PREALERTA VENTA"
                )

                return resultado

        # ====================================================
        # SIN SEÑAL
        # ====================================================

        return {

            "tipo":
                "SIN_SEÑAL",

            "mensaje":
                "😴 Sin señal V4.2"
        }

    except Exception as e:

        print("")
        print("❌ ERROR EN ANALIZAR V4.2:")
        print(repr(e))

        return {

            "tipo":
                "ERROR",

            "mensaje":
                f"❌ Error V4.2:\n{e}"
    }
              
