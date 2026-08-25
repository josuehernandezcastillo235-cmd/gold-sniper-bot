import requests
import pandas as pd
import os
import uuid
import time

from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


# ============================================================
# XAU SNIPER AI V4.1
# MOTOR DE LECTURA DE MERCADO
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


# ============================================================
# IMPULSO
# ============================================================

IMPULSO_VELAS = 10

IMPULSO_ATR_MIN = 0.80

IMPULSO_FUERTE_ATR = 1.20

IMPULSO_VELAS_MIN = 3

EFICIENCIA_MINIMA = 0.45


# ============================================================
# PULLBACK
# ============================================================

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

    estado["pullback_nivel"] = None

    estado["nivel_continuacion"] = None

    estado["swing_referencia"] = None

    estado["maximo_confirmacion"] = None

    estado["minimo_confirmacion"] = None

    estado["velas_pendiente"] = 0


# ============================================================
# NUEVO ID
# ============================================================

def generar_id():

    return uuid.uuid4().hex[:8].upper()


# ============================================================
# OBTENER DATOS DE TWELVE DATA
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

                espera = 3 * intento

                print(
                    f"⚠️ Twelve Data 429 "
                    f"({intervalo}) | "
                    f"reintento {intento}/{max_intentos} "
                    f"en {espera}s"
                )

                time.sleep(espera)

                continue

            respuesta.raise_for_status()

            try:

                data = respuesta.json()

            except Exception:

                raise Exception(
                    "Twelve Data devolvió una respuesta "
                    "que no es JSON válido."
                )

            if not isinstance(data, dict):

                raise Exception(
                    "Respuesta Twelve Data inválida."
                )

            if "status" in data:

                if data.get("status") == "error":

                    mensaje = data.get(
                        "message",
                        "Error desconocido"
                    )

                    raise Exception(
                        f"Twelve Data: {mensaje}"
                    )

            if "values" not in data:

                raise Exception(
                    f"Twelve Data sin 'values': {data}"
                )

            values = data["values"]

            if not isinstance(values, list):

                raise Exception(
                    "Campo 'values' inválido."
                )

            if len(values) < 50:

                raise Exception(
                    f"Datos insuficientes de "
                    f"Twelve Data ({intervalo}): "
                    f"{len(values)} velas."
                )

            df = pd.DataFrame(values)

            if df.empty:

                raise Exception(
                    f"DataFrame vacío para {intervalo}"
                )

            columnas_necesarias = [
                "open",
                "high",
                "low",
                "close",
                "datetime"
            ]

            faltantes = [
                c
                for c in columnas_necesarias
                if c not in df.columns
            ]

            if faltantes:

                raise Exception(
                    f"Faltan columnas Twelve Data: "
                    f"{faltantes}"
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

            df = df.sort_values(
                "datetime"
            )

            df = df.drop_duplicates(
                subset=["datetime"]
            )

            df = df.reset_index(
                drop=True
            )

            if len(df) < 50:

                raise Exception(
                    f"Después de limpiar datos "
                    f"quedaron solo {len(df)} velas."
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
            f"Se requieren al menos 220 velas "
            f"para indicadores. "
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
            f"solo {len(df)} velas útiles."
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

            if (
                high_actual >= altos_izq.max()
                and
                high_actual >= altos_der.max()
            ):

                highs.append({
                    "index": i,
                    "precio": high_actual,
                    "atr": atr
                })

            if (
                low_actual <= bajos_izq.min()
                and
                low_actual <= bajos_der.min()
            ):

                lows.append({
                    "index": i,
                    "precio": low_actual,
                    "atr": atr
                })

        except Exception:

            continue

    return highs, lows


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

    # ========================================================
    # BOS
    # ========================================================

    if (
        resultado["ultimo_high"] is not None
        and
        precio_actual >
        resultado["ultimo_high"]["precio"] +
        atr_actual * BREAK_BUFFER_ATR
    ):

        resultado["bos"] = "ALCISTA"

    elif (
        resultado["ultimo_low"] is not None
        and
        precio_actual <
        resultado["ultimo_low"]["precio"] -
        atr_actual * BREAK_BUFFER_ATR
    ):

        resultado["bos"] = "BAJISTA"

    # ========================================================
    # CHoCH
    # ========================================================

    if resultado["direccion"] == "ALCISTA":

        if (
            resultado["ultimo_low"] is not None
            and
            precio_actual <
            resultado["ultimo_low"]["precio"]
        ):

            resultado["choch"] = True

    elif resultado["direccion"] == "BAJISTA":

        if (
            resultado["ultimo_high"] is not None
            and
            precio_actual >
            resultado["ultimo_high"]["precio"]
        ):

            resultado["choch"] = True

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

    regimen15 = detectar_regimen(
        df15
    )

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
# IMPULSO ALCISTA
# ============================================================

def detectar_impulso_alcista(df):

    if df is None:

        return None

    if len(df) < IMPULSO_VELAS + 5:

        return None

    ventana = df.iloc[
        -IMPULSO_VELAS:
    ]

    try:

        atr = float(
            df.iloc[-1]["atr"]
        )

        if atr <= 0:

            return None

        inicio = float(
            ventana.iloc[0]["close"]
        )

        extremo = float(
            ventana["high"].max()
        )

        desplazamiento = (
            extremo -
            inicio
        )

        desplazamiento_atr = (
            desplazamiento /
            atr
        )

        velas_alcistas = int(
            (
                ventana["direccion_vela"]
                == 1
            ).sum()
        )

        expansion = int(
            ventana["expansion"].sum()
        )

        avance = (
            float(
                ventana.iloc[-1]["close"]
            )
            -
            inicio
        )

        avance_atr = (
            avance /
            atr
        )

        eficiencia = float(
            ventana["eficiencia"]
            .mean()
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

    except Exception:

        return None

    calidad = 0

    if (
        desplazamiento_atr >=
        IMPULSO_ATR_MIN
    ):

        calidad += 1

    if (
        desplazamiento_atr >=
        IMPULSO_FUERTE_ATR
    ):

        calidad += 1

    if (
        velas_alcistas >=
        IMPULSO_VELAS_MIN
    ):

        calidad += 1

    if expansion >= 1:

        calidad += 1

    if eficiencia >= EFICIENCIA_MINIMA:

        calidad += 1

    if ratio_cuerpo >= 0.45:

        calidad += 1

    if calidad < 4:

        return None

    return {

        "direccion": "ALCISTA",

        "inicio": inicio,

        "extremo": extremo,

        "desplazamiento":
            desplazamiento,

        "desplazamiento_atr":
            desplazamiento_atr,

        "avance":
            avance,

        "avance_atr":
            avance_atr,

        "velas_alcistas":
            velas_alcistas,

        "expansion":
            expansion,

        "eficiencia":
            eficiencia,

        "ratio_cuerpo":
            ratio_cuerpo,

        "calidad":
            calidad
    }


# ============================================================
# IMPULSO BAJISTA
# ============================================================

def detectar_impulso_bajista(df):

    if df is None:

        return None

    if len(df) < IMPULSO_VELAS + 5:

        return None

    ventana = df.iloc[
        -IMPULSO_VELAS:
    ]

    try:

        atr = float(
            df.iloc[-1]["atr"]
        )

        if atr <= 0:

            return None

        inicio = float(
            ventana.iloc[0]["close"]
        )

        extremo = float(
            ventana["low"].min()
        )

        desplazamiento = (
            inicio -
            extremo
        )

        desplazamiento_atr = (
            desplazamiento /
            atr
        )

        velas_bajistas = int(
            (
                ventana["direccion_vela"]
                == -1
            ).sum()
        )

        expansion = int(
            ventana["expansion"].sum()
        )

        avance = (
            inicio -
            float(
                ventana.iloc[-1]["close"]
            )
        )

        avance_atr = (
            avance /
            atr
        )

        eficiencia = float(
            ventana["eficiencia"]
            .mean()
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

    except Exception:

        return None

    calidad = 0

    if (
        desplazamiento_atr >=
        IMPULSO_ATR_MIN
    ):

        calidad += 1

    if (
        desplazamiento_atr >=
        IMPULSO_FUERTE_ATR
    ):

        calidad += 1

    if (
        velas_bajistas >=
        IMPULSO_VELAS_MIN
    ):

        calidad += 1

    if expansion >= 1:

        calidad += 1

    if eficiencia >= EFICIENCIA_MINIMA:

        calidad += 1

    if ratio_cuerpo >= 0.45:

        calidad += 1

    if calidad < 4:

        return None

    return {

        "direccion": "BAJISTA",

        "inicio": inicio,

        "extremo": extremo,

        "desplazamiento":
            desplazamiento,

        "desplazamiento_atr":
            desplazamiento_atr,

        "avance":
            avance,

        "avance_atr":
            avance_atr,

        "velas_bajistas":
            velas_bajistas,

        "expansion":
            expansion,

        "eficiencia":
            eficiencia,

        "ratio_cuerpo":
            ratio_cuerpo,

        "calidad":
            calidad
    }


# ============================================================
# PULLBACK ALCISTA
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

        inicio = float(
            impulso["inicio"]
        )

        extremo = float(
            impulso["extremo"]
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

        max_pullback = float(
            df["low"].iloc[-5:].min()
        )

        retroceso = (
            extremo -
            max_pullback
        )

        retroceso_atr = (
            retroceso /
            atr
        )

        retracement = (
            retroceso /
            desplazamiento
        )

        if (
            retroceso_atr <
            PULLBACK_MIN_ATR
        ):

            return None

        if (
            retroceso_atr >
            PULLBACK_MAX_ATR
        ):

            return None

        if (
            retracement <
            PULLBACK_MIN_RETRACEMENT
        ):

            return None

        if (
            retracement >
            PULLBACK_MAX_RETRACEMENT
        ):

            return None

        nivel_continuacion = (
            extremo
        )

        if precio < (
            inicio -
            atr * 0.10
        ):

            return None

        return {

            "direccion": "ALCISTA",

            "maximo_pullback":
                max_pullback,

            "nivel_continuacion":
                nivel_continuacion,

            "extremo_impulso":
                extremo,

            "retracement":
                retracement,

            "retroceso_atr":
                retroceso_atr
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

        inicio = float(
            impulso["inicio"]
        )

        extremo = float(
            impulso["extremo"]
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

        max_pullback = float(
            df["high"].iloc[-5:].max()
        )

        retroceso = (
            max_pullback -
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

        if (
            retroceso_atr <
            PULLBACK_MIN_ATR
        ):

            return None

        if (
            retroceso_atr >
            PULLBACK_MAX_ATR
        ):

            return None

        if (
            retracement <
            PULLBACK_MIN_RETRACEMENT
        ):

            return None

        if (
            retracement >
            PULLBACK_MAX_RETRACEMENT
        ):

            return None

        nivel_continuacion = (
            extremo
        )

        if precio > (
            inicio +
            atr * 0.10
        ):

            return None

        return {

            "direccion": "BAJISTA",

            "maximo_pullback":
                max_pullback,

            "nivel_continuacion":
                nivel_continuacion,

            "extremo_impulso":
                extremo,

            "retracement":
                retracement,

            "retroceso_atr":
                retroceso_atr
        }

    except Exception:

        return None


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
        len(df) < 3
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

        high = float(
            actual["high"]
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
        len(df) < 3
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
        # rompe abajo y recupera arriba
        resultado["sweep_alcista"] = (
            low_actual <
            low_previo - buffer
            and
            close_actual >
            low_previo
        )

        # Sweep de máximos:
        # rompe arriba y recupera abajo
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

        if estructura.get(
            "ultimo_high"
        ):

            zonas.append(
                float(
                    estructura[
                        "ultimo_high"
                    ]["precio"]
                )
            )

        if estructura.get(
            "prev_high"
        ):

            zonas.append(
                float(
                    estructura[
                        "prev_high"
                    ]["precio"]
                )
            )

        if estructura.get(
            "ultimo_low"
        ):

            zonas.append(
                float(
                    estructura[
                        "ultimo_low"
                    ]["precio"]
                )
            )

        if estructura.get(
            "prev_low"
        ):

            zonas.append(
                float(
                    estructura[
                        "prev_low"
                    ]["precio"]
                )
            )

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

        rsi = float(
            actual["rsi"]
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

        pendiente20 = float(
            actual["pendiente_ema20"]
        )

        pendiente50 = float(
            actual["pendiente_ema50"]
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

        rsi = float(
            actual["rsi"]
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

    if estructura.get(
        "direccion"
    ) == "ALCISTA":

        score += 15

    if estructura.get("hh"):

        score += 5

    if estructura.get("hl"):

        score += 5

    if estructura.get("bos") == "ALCISTA":

        score += 8

    if (
        contexto15 ==
        "ALCISTA"
    ):

        score += 10

    elif contexto15 == "NEUTRAL":

        score += 4

    if regimen == "ALCISTA":

        score += 8

    elif regimen == "TRANSICION":

        score += 4

    if impulso is not None:

        score += 10

        if impulso.get(
            "calidad",
            0
        ) >= 5:

            score += 3

    if pullback is not None:

        score += 8

    if continuacion:

        score += 8

    if liquidez.get(
        "sweep_alcista",
        False
    ):

        score += 5

    if ubicacion >= 2:

        score += 3

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

    if estructura.get(
        "direccion"
    ) == "BAJISTA":

        score += 15

    if estructura.get("lh"):

        score += 5

    if estructura.get("ll"):

        score += 5

    if estructura.get("bos") == "BAJISTA":

        score += 8

    if (
        contexto15 ==
        "BAJISTA"
    ):

        score += 10

    elif contexto15 == "NEUTRAL":

        score += 4

    if regimen == "BAJISTA":

        score += 8

    elif regimen == "TRANSICION":

        score += 4

    if impulso is not None:

        score += 10

        if impulso.get(
            "calidad",
            0
        ) >= 5:

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
# CREAR PREALERTA COMPRA
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

    nivel = (
        pullback.get(
            "nivel_continuacion"
        )
        if pullback
        else None
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
# CREAR PREALERTA VENTA
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

    nivel = (
        pullback.get(
            "nivel_continuacion"
        )
        if pullback
        else None
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

    estado[
        "ultima_descartada"
    ] = time.time()

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
        estado[
            "direccion_pendiente"
        ]
    )

    if direccion is None:

        return None

    inicio = (
        estado[
            "inicio_pendiente"
        ]
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

    estado[
        "ultima_descartada"
    ] = ahora

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
# VALIDAR ESTADO INTERNO
# ============================================================

def estado_valido():

    direccion = (
        estado[
            "direccion_pendiente"
        ]
    )

    if direccion is None:

        return True

    if direccion not in (
        "COMPRA",
        "VENTA"
    ):

        limpiar_pendiente()

        return False

    if estado[
        "id_pendiente"
    ] is None:

        limpiar_pendiente()

        return False

    return True


# ============================================================
# ANALIZAR V4.1
# ============================================================

def analizar():

    try:

        print("")
        print("===================================")
        print("🔍 ANALIZANDO XAU/USD V4.1")
        print("===================================")

        ahora = time.time()

        # ====================================================
        # VALIDAR ESTADO
        # ====================================================

        estado_valido()

        # ====================================================
        # EXPIRACIÓN PRIMERO
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
        # PREALERTA ACTIVA
        #
        # CONGELAMOS SU NIVEL ORIGINAL
        # ====================================================

        if (
            estado[
                "direccion_pendiente"
            ] == "COMPRA"
            and
            estado[
                "nivel_continuacion"
            ] is not None
        ):

            zona_compra = (
                estado[
                    "nivel_continuacion"
                ]
            )

        if (
            estado[
                "direccion_pendiente"
            ] == "VENTA"
            and
            estado[
                "nivel_continuacion"
            ] is not None
        ):

            zona_venta = (
                estado[
                    "nivel_continuacion"
                ]
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
            f"CHoCH: {estructura5['choch']}"
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

        print(
            f"Impulso venta: "
            f"{impulso_venta is not None}"
        )

        print(
            f"Pullback compra: "
            f"{pullback_compra is not None}"
        )

        print(
            f"Pullback venta: "
            f"{pullback_venta is not None}"
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
            estado[
                "direccion_pendiente"
            ] is not None
        ):

            estado[
                "velas_pendiente"
            ] += 1

            direccion = (
                estado[
                    "direccion_pendiente"
                ]
            )

            # =================================================
            # COMPRA PENDIENTE
            # =================================================

            if direccion == "COMPRA":

                if (
                    estructura5["choch"]
                    and
                    estructura5["direccion"]
                    == "BAJISTA"
                ):

                    return crear_descartada(
                        "COMPRA",
                        (
                            "📉 CHoCH bajista detectado. "
                            "La estructura dejó de favorecer "
                            "la continuación alcista."
                        )
                    )

                if (
                    regimen5 == "BAJISTA"
                    and
                    contexto15 == "BAJISTA"
                ):

                    return crear_descartada(
                        "COMPRA",
                        (
                            "📉 Régimen 5M y contexto "
                            "15M pasaron a bajista."
                        )
                    )

                impulso_base = (
                    estado[
                        "impulso_inicio"
                    ]
                )

                if (
                    impulso_base is not None
                    and
                    precio <
                    impulso_base -
                    atr * 0.35
                ):

                    return crear_descartada(
                        "COMPRA",
                        (
                            "❌ El precio rompió la "
                            "base del impulso alcista."
                        )
                    )

                if (
                    continuacion_compra
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
                ):

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

                if (
                    estructura5["choch"]
                    and
                    estructura5["direccion"]
                    == "ALCISTA"
                ):

                    return crear_descartada(
                        "VENTA",
                        (
                            "📈 CHoCH alcista detectado. "
                            "La estructura dejó de favorecer "
                            "la continuación bajista."
                        )
                    )

                if (
                    regimen5 == "ALCISTA"
                    and
                    contexto15 == "ALCISTA"
                ):

                    return crear_descartada(
                        "VENTA",
                        (
                            "📈 Régimen 5M y contexto "
                            "15M pasaron a alcista."
                        )
                    )

                impulso_base = (
                    estado[
                        "impulso_inicio"
                    ]
                )

                if (
                    impulso_base is not None
                    and
                    precio >
                    impulso_base +
                    atr * 0.35
                ):

                    return crear_descartada(
                        "VENTA",
                        (
                            "❌ El precio rompió la "
                            "base del impulso bajista."
                        )
                    )

                if (
                    continuacion_venta
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
                ):

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
        # IMPORTANTE:
        # NO exigimos continuación aquí.
        # La prealerta existe para esperar la continuación.
        # ====================================================

        posible_compra = (

            estructura5["direccion"]
            == "ALCISTA"

            and

            impulso_compra is not None

            and

            pullback_compra is not None

            and

            not tardia_compra

            and

            not estructura5["choch"]

            and

            regimen5 != "BAJISTA"

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

            not tardia_venta

            and

            not estructura5["choch"]

            and

            regimen5 != "ALCISTA"

            and

            score_venta >=
            SCORE_MIN_PREALERTA
        )

        # ====================================================
        # COOLDOWN
        # ====================================================

        if (
            ahora -
            estado[
                "ultima_descartada"
            ]
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
                estado[
                    "ultima_prealerta"
                ]
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

                # =================================================
                # AQUÍ ESTABA EL BUG DE TU CÓDIGO
                #
                # TODO ES DE COMPRA.
                # YA NO HAY impulso_venta NI pullback_venta.
                # =================================================

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
                    "pullback_nivel"
                ] = pullback_compra[
                    "maximo_pullback"
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
                estado[
                    "ultima_prealerta"
                ]
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

                # =================================================
                # TODO ES DE VENTA
                # =================================================

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
                "😴 Sin señal V4.1"
        }

    except Exception as e:

        print("")
        print("❌ ERROR EN ANALIZAR V4.1:")
        print(repr(e))

        return {

            "tipo":
                "ERROR",

            "mensaje":
                f"❌ Error V4.1:\n{e}"
        }
