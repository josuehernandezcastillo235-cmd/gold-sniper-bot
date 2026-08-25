import requests
import pandas as pd
import os
import uuid
import time

from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


# ============================================================
# XAU SNIPER AI V4.0
# PAPER TRADING / ANALIZADOR
# ============================================================
#
# FLUJO:
#
# CONTEXTO
#     ↓
# ESTRUCTURA
#     ↓
# IMPULSO
#     ↓
# PULLBACK
#     ↓
# CONTINUACIÓN
#     ↓
# SCORE
#     ↓
# PREALERTA
#     ↓
# CONFIRMACIÓN
#
# V4 prioriza estructura y movimiento del precio.
#
# EMA / RSI / ADX / DI = CONTEXTO SECUNDARIO
#
# ============================================================


API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"


# ============================================================
# TEMPORALIDADES
# ============================================================

INTERVALO_5M = "5min"
INTERVALO_15M = "15min"


# ============================================================
# CICLO DE ANÁLISIS
# ============================================================

# El bot externo debe ejecutar analizar()
# cada 100 segundos.

INTERVALO_ANALISIS = 100


# ============================================================
# ESTADOS
# ============================================================

TIPO_SIN_SEÑAL = "SIN_SEÑAL"
TIPO_PREALERTA_COMPRA = "POSIBLE_COMPRA"
TIPO_PREALERTA_VENTA = "POSIBLE_VENTA"
TIPO_COMPRA = "COMPRA"
TIPO_VENTA = "VENTA"
TIPO_DESCARTADA = "DESCARTADA"
TIPO_ERROR = "ERROR"


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

MINUTOS_REPETICION = 15

MINUTOS_VIDA_PREALERTA = 30


# ============================================================
# FILTROS SECUNDARIOS
# ============================================================

ADX_MINIMO = 15

RSI_COMPRA_MIN = 50
RSI_VENTA_MAX = 50

RSI_CONFIRMACION_COMPRA = 53
RSI_CONFIRMACION_VENTA = 47


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

SWING_ATR_MIN = 0.20


# ============================================================
# IMPULSO
# ============================================================

IMPULSO_VELAS = 10

# Antes era demasiado exigente.
IMPULSO_ATR_MIN = 0.45

IMPULSO_VELAS_MIN = 2


# ============================================================
# PULLBACK
# ============================================================

PULLBACK_MIN_ATR = 0.15
PULLBACK_MAX_ATR = 1.80


# ============================================================
# CONTINUACIÓN
# ============================================================

CONTINUACION_ATR_MIN = 0.05

CUERPO_CONTINUACION_ATR = 0.08


# ============================================================
# ENTRADA DEMASIADO ALEJADA
# ============================================================

MAX_DISTANCIA_ENTRADA_ATR = 1.50


# ============================================================
# SCORE
# ============================================================

# Relajados para evitar que V4 quede completamente muda.

SCORE_MIN_PREALERTA = 45

SCORE_MIN_CONFIRMACION = 60


# ============================================================
# ESTADO GLOBAL
# ============================================================

estado = {

    "direccion_pendiente": None,

    "id_pendiente": None,

    "ultima_prealerta": 0,

    "ultima_confirmacion": 0,

    "inicio_pendiente": 0,

    "precio_prealerta": None,

    "atr_prealerta": None,

    "impulso_inicio": None,

    "impulso_extremo": None,

    "pullback_nivel": None,

    "pullback_maximo": None,

    "nivel_continuacion": None,

}


# ============================================================
# OBTENER DATOS DE TWELVE DATA
# ============================================================

def obtener_datos(intervalo):

    if not API_KEY:
        raise Exception(
            "API_KEY no configurada"
        )

    url = (
        "https://api.twelvedata.com/"
        "time_series"
    )

    # ========================================================
    # IMPORTANTE
    # ========================================================
    #
    # Antes se pedían 5000 velas.
    #
    # Para este sistema no necesitamos semejante cantidad
    # en cada consulta.
    #
    # 500 es suficiente para indicadores + estructura.
    #
    # ========================================================

    params = {

        "symbol": SYMBOL,

        "interval": intervalo,

        "outputsize": 500,

        "apikey": API_KEY,

        "format": "JSON"

    }

    ultimo_error = None


    # ========================================================
    # REINTENTOS
    # ========================================================

    for intento in range(3):

        try:

            print(
                f"📡 Twelve Data "
                f"{intervalo} "
                f"intento {intento + 1}/3"
            )

            respuesta = requests.get(

                url,

                params=params,

                timeout=20

            )


            # ------------------------------------------------
            # ERROR 522
            # ------------------------------------------------

            if respuesta.status_code == 522:

                ultimo_error = (
                    "Twelve Data respondió "
                    "HTTP 522"
                )

                print(
                    "⚠️ Error 522 de Twelve Data"
                )

                if intento < 2:

                    espera = (
                        3 *
                        (intento + 1)
                    )

                    print(
                        f"⏳ Reintentando "
                        f"en {espera}s..."
                    )

                    time.sleep(
                        espera
                    )

                    continue


                break


            # ------------------------------------------------
            # OTROS ERRORES HTTP
            # ------------------------------------------------

            respuesta.raise_for_status()


            # ------------------------------------------------
            # JSON
            # ------------------------------------------------

            data = respuesta.json()


            # ------------------------------------------------
            # ERROR DEVUELTO POR TWELVE DATA
            # ------------------------------------------------

            if "values" not in data:

                ultimo_error = (
                    f"Twelve Data: {data}"
                )

                print(
                    f"⚠️ {ultimo_error}"
                )

                if intento < 2:

                    time.sleep(
                        2 *
                        (intento + 1)
                    )

                    continue

                break


            # ------------------------------------------------
            # DATAFRAME
            # ------------------------------------------------

            df = pd.DataFrame(
                data["values"]
            )


            if df.empty:

                ultimo_error = (
                    f"Datos vacíos "
                    f"para {intervalo}"
                )

                if intento < 2:

                    time.sleep(2)

                    continue

                break


            # ------------------------------------------------
            # CONVERSIÓN NUMÉRICA
            # ------------------------------------------------

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


            # ------------------------------------------------
            # FECHA
            # ------------------------------------------------

            df["datetime"] = pd.to_datetime(

                df["datetime"],

                errors="coerce"

            )


            # ------------------------------------------------
            # LIMPIEZA
            # ------------------------------------------------

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


            df = df.reset_index(

                drop=True

            )


            if len(df) < 50:

                raise Exception(

                    f"Insuficientes velas "
                    f"{intervalo}: "
                    f"{len(df)}"

                )


            print(

                f"📥 {intervalo}: "
                f"{len(df)} velas recibidas"

            )


            return df


        except requests.exceptions.Timeout as e:

            ultimo_error = (
                f"Timeout Twelve Data: {e}"
            )

            print(
                f"⚠️ {ultimo_error}"
            )

            if intento < 2:

                time.sleep(
                    3 *
                    (intento + 1)
                )

                continue


        except requests.exceptions.RequestException as e:

            ultimo_error = (
                f"Error HTTP Twelve Data: {e}"
            )

            print(
                f"⚠️ {ultimo_error}"
            )

            if intento < 2:

                time.sleep(
                    3 *
                    (intento + 1)
                )

                continue


        except Exception as e:

            ultimo_error = e

            print(
                f"⚠️ Error datos: "
                f"{repr(e)}"
            )

            if intento < 2:

                time.sleep(
                    2 *
                    (intento + 1)
                )

                continue


    raise Exception(

        f"No se pudieron obtener "
        f"datos {intervalo}. "
        f"Último error: "
        f"{ultimo_error}"

    )


# ============================================================
# INDICADORES
# ============================================================

def calcular_indicadores(df):

    df = df.copy()


    # --------------------------------------------------------
    # EMA
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    df["rsi"] = RSIIndicator(

        close=df["close"],

        window=14

    ).rsi()


    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    df["atr"] = AverageTrueRange(

        high=df["high"],

        low=df["low"],

        close=df["close"],

        window=14

    ).average_true_range()


    # --------------------------------------------------------
    # ADX
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
    # VELAS
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # RANGO MEDIO
    # --------------------------------------------------------

    df["rango_medio"] = (

        df["rango"]

        .rolling(20)

        .mean()

    )


    df["expansion"] = (

        df["rango"] >

        df["rango_medio"] * 1.10

    )


    # --------------------------------------------------------
    # PENDIENTE EMA
    # --------------------------------------------------------

    df["pendiente_ema20"] = (

        df["ema20"] -

        df["ema20"].shift(3)

    )


    df["pendiente_ema50"] = (

        df["ema50"] -

        df["ema50"].shift(3)

    )


    # --------------------------------------------------------
    # LIMPIAR NaN
    # --------------------------------------------------------

    df = df.dropna().reset_index(

        drop=True

    )


    print(

        f"📊 Velas útiles: "
        f"{len(df)}"

    )


    return df


# ============================================================
# DETECTAR SWINGS
# ============================================================

def detectar_swings(df):

    highs = []

    lows = []


    inicio = SWING_LEFT

    final = (

        len(df) -
        SWING_RIGHT

    )


    for i in range(

        inicio,
        final

    ):

        high_actual = float(

            df.iloc[i]["high"]

        )


        low_actual = float(

            df.iloc[i]["low"]

        )


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

            high_actual >=
            altos_izq.max()

            and

            high_actual >=
            altos_der.max()

        ):

            highs.append({

                "index": i,

                "precio": high_actual

            })


        if (

            low_actual <=
            bajos_izq.min()

            and

            low_actual <=
            bajos_der.min()

        ):

            lows.append({

                "index": i,

                "precio": low_actual

            })


    return highs, lows


# ============================================================
# ANALIZAR ESTRUCTURA
# ============================================================

def analizar_estructura(df):

    highs, lows = detectar_swings(df)


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


    # --------------------------------------------------------
    # HIGHS
    # --------------------------------------------------------

    if len(highs) >= 2:

        resultado["ultimo_high"] = highs[-1]

        resultado["prev_high"] = highs[-2]


        resultado["hh"] = (

            highs[-1]["precio"] >

            highs[-2]["precio"]

        )


        resultado["lh"] = (

            highs[-1]["precio"] <

            highs[-2]["precio"]

        )


    # --------------------------------------------------------
    # LOWS
    # --------------------------------------------------------

    if len(lows) >= 2:

        resultado["ultimo_low"] = lows[-1]

        resultado["prev_low"] = lows[-2]


        resultado["hl"] = (

            lows[-1]["precio"] >

            lows[-2]["precio"]

        )


        resultado["ll"] = (

            lows[-1]["precio"] <

            lows[-2]["precio"]

        )


    # --------------------------------------------------------
    # PUNTOS
    # --------------------------------------------------------

    puntos_alcistas = 0

    puntos_bajistas = 0


    if resultado["hh"]:

        puntos_alcistas += 1


    if resultado["hl"]:

        puntos_alcistas += 1


    if resultado["lh"]:

        puntos_bajistas += 1


    if resultado["ll"]:

        puntos_bajistas += 1


    # --------------------------------------------------------
    # DIRECCIÓN
    # --------------------------------------------------------

    if puntos_alcistas >= 2:

        resultado["direccion"] = "ALCISTA"

        resultado["fuerza"] = (
            puntos_alcistas
        )


    elif puntos_bajistas >= 2:

        resultado["direccion"] = "BAJISTA"

        resultado["fuerza"] = (
            puntos_bajistas
        )


    else:

        # ----------------------------------------------------
        # FALLBACK DE DESPLAZAMIENTO
        # ----------------------------------------------------

        cierre = float(

            df.iloc[-1]["close"]

        )


        cierre_anterior = float(

            df.iloc[-6]["close"]

        )


        atr = float(

            df.iloc[-1]["atr"]

        )


        desplazamiento = (

            cierre -
            cierre_anterior

        )


        if atr > 0:

            if (

                desplazamiento >
                atr * 0.30

            ):

                resultado["direccion"] = (
                    "ALCISTA"
                )

                resultado["fuerza"] = 1


            elif (

                desplazamiento <
                -atr * 0.30

            ):

                resultado["direccion"] = (
                    "BAJISTA"
                )

                resultado["fuerza"] = 1


    # --------------------------------------------------------
    # BOS
    #
    # Usamos swings confirmados anteriores.
    # --------------------------------------------------------

    precio_actual = float(

        df.iloc[-1]["close"]

    )


    if len(highs) >= 2:

        high_anterior = highs[-1]["precio"]

        if precio_actual > high_anterior:

            resultado["bos"] = "ALCISTA"


    if len(lows) >= 2:

        low_anterior = lows[-1]["precio"]

        if precio_actual < low_anterior:

            resultado["bos"] = "BAJISTA"


    # --------------------------------------------------------
    # CHoCH
    # --------------------------------------------------------

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
# IMPULSO ALCISTA
# ============================================================

def detectar_impulso_alcista(df):

    if len(df) < IMPULSO_VELAS + 2:

        return None


    ventana = df.iloc[

        -IMPULSO_VELAS:

    ]


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


    cierre_actual = float(

        ventana.iloc[-1]["close"]

    )


    avance = (

        cierre_actual -
        inicio

    )


    avance_atr = (

        avance /
        atr

    )


    if (

        desplazamiento_atr >=
        IMPULSO_ATR_MIN

        and

        velas_alcistas >=
        IMPULSO_VELAS_MIN

    ):

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
                expansion

        }


    return None


# ============================================================
# IMPULSO BAJISTA
# ============================================================

def detectar_impulso_bajista(df):

    if len(df) < IMPULSO_VELAS + 2:

        return None


    ventana = df.iloc[

        -IMPULSO_VELAS:

    ]


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


    cierre_actual = float(

        ventana.iloc[-1]["close"]

    )


    avance = (

        inicio -
        cierre_actual

    )


    avance_atr = (

        avance /
        atr

    )


    if (

        desplazamiento_atr >=
        IMPULSO_ATR_MIN

        and

        velas_bajistas >=
        IMPULSO_VELAS_MIN

    ):

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
                expansion

        }


    # ============================================================
# PULLBACK ALCISTA
# ============================================================

def detectar_pullback_alcista(
    df,
    impulso
):

    if impulso is None:

        return None


    atr = float(

        df.iloc[-1]["atr"]

    )


    if atr <= 0:

        return None


    extremo = float(

        impulso["extremo"]

    )


    inicio = float(

        impulso["inicio"]

    )


    ventana = df.iloc[-6:]


    minimo = float(

        ventana["low"].min()

    )


    precio = float(

        df.iloc[-1]["close"]

    )


    retroceso = (

        extremo -
        minimo

    )


    retroceso_atr = (

        retroceso /
        atr

    )


    estructura_valida = (

        minimo >

        inicio -
        atr * 0.50

    )


    if (

        retroceso_atr >=
        PULLBACK_MIN_ATR

        and

        retroceso_atr <=
        PULLBACK_MAX_ATR

        and

        estructura_valida

    ):

        nivel_continuacion = (

            extremo -
            atr * 0.05

        )


        return {

            "direccion": "ALCISTA",

            "extremo_impulso":
                extremo,

            "inicio_impulso":
                inicio,

            "minimo_pullback":
                minimo,

            "retroceso":
                retroceso,

            "retroceso_atr":
                retroceso_atr,

            "nivel_continuacion":
                nivel_continuacion,

            "precio_actual":
                precio

        }


    return None


# ============================================================
# PULLBACK BAJISTA
# ============================================================

def detectar_pullback_bajista(
    df,
    impulso
):

    if impulso is None:

        return None


    atr = float(

        df.iloc[-1]["atr"]

    )


    if atr <= 0:

        return None


    extremo = float(

        impulso["extremo"]

    )


    inicio = float(

        impulso["inicio"]

    )


    ventana = df.iloc[-6:]


    maximo = float(

        ventana["high"].max()

    )


    precio = float(

        df.iloc[-1]["close"]

    )


    retroceso = (

        maximo -
        extremo

    )


    retroceso_atr = (

        retroceso /
        atr

    )


    estructura_valida = (

        maximo <

        inicio +
        atr * 0.50

    )


    if (

        retroceso_atr >=
        PULLBACK_MIN_ATR

        and

        retroceso_atr <=
        PULLBACK_MAX_ATR

        and

        estructura_valida

    ):

        nivel_continuacion = (

            extremo +
            atr * 0.05

        )


        return {

            "direccion": "BAJISTA",

            "extremo_impulso":
                extremo,

            "inicio_impulso":
                inicio,

            "maximo_pullback":
                maximo,

            "retroceso":
                retroceso,

            "retroceso_atr":
                retroceso_atr,

            "nivel_continuacion":
                nivel_continuacion,

            "precio_actual":
                precio

        }


    return None


# ============================================================
# CONTINUACIÓN ALCISTA
# ============================================================

def detectar_continuacion_alcista(
    df,
    pullback
):

    if pullback is None:

        return False, None


    atr = float(

        df.iloc[-1]["atr"]

    )


    if atr <= 0:

        return False, None


    actual = df.iloc[-1]


    precio = float(

        actual["close"]

    )


    apertura = float(

        actual["open"]

    )


    cuerpo = abs(

        precio -
        apertura

    )


    vela_alcista = (

        precio >
        apertura

    )


    cuerpo_fuerte = (

        cuerpo >=

        atr *
        CUERPO_CONTINUACION_ATR

    )


    nivel = float(

        pullback[
            "nivel_continuacion"
        ]

    )


    maximo_ultimas = float(

        df.iloc[-4:-1]["high"].max()

    )


    ruptura_nivel = (

        precio >
        nivel

    )


    ruptura_reciente = (

        precio >
        maximo_ultimas

    )


    confirmacion = (

        vela_alcista

        and

        cuerpo_fuerte

        and

        (

            ruptura_nivel

            or

            ruptura_reciente

        )

    )


    return (

        confirmacion,

        nivel

    )


# ============================================================
# CONTINUACIÓN BAJISTA
# ============================================================

def detectar_continuacion_bajista(
    df,
    pullback
):

    if pullback is None:

        return False, None


    atr = float(

        df.iloc[-1]["atr"]

    )


    if atr <= 0:

        return False, None


    actual = df.iloc[-1]


    precio = float(

        actual["close"]

    )


    apertura = float(

        actual["open"]

    )


    cuerpo = abs(

        precio -
        apertura

    )


    vela_bajista = (

        precio <
        apertura

    )


    cuerpo_fuerte = (

        cuerpo >=

        atr *
        CUERPO_CONTINUACION_ATR

    )


    nivel = float(

        pullback[
            "nivel_continuacion"
        ]

    )


    minimo_ultimas = float(

        df.iloc[-4:-1]["low"].min()

    )


    ruptura_nivel = (

        precio <
        nivel

    )


    ruptura_reciente = (

        precio <
        minimo_ultimas

    )


    confirmacion = (

        vela_bajista

        and

        cuerpo_fuerte

        and

        (

            ruptura_nivel

            or

            ruptura_reciente

        )

    )


    return (

        confirmacion,

        nivel

    )


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

        atr <= 0

    ):

        return False


    distancia = (

        precio -
        zona

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

        atr <= 0

    ):

        return False


    distancia = (

        zona -
        precio

    )


    return (

        distancia >

        atr *
        MAX_DISTANCIA_ENTRADA_ATR

    )


# ============================================================
# CONTEXTO 15M
# ============================================================

def obtener_contexto_15m(
    estructura15,
    df15
):

    direccion = (

        estructura15[
            "direccion"
        ]

    )


    actual = df15.iloc[-1]


    ema20 = float(

        actual["ema20"]

    )


    ema50 = float(

        actual["ema50"]

    )


    precio = float(

        actual["close"]

    )


    if (

        direccion == "ALCISTA"

        or

        (

            precio > ema20

            and

            ema20 > ema50

        )

    ):

        return "ALCISTA"


    if (

        direccion == "BAJISTA"

        or

        (

            precio < ema20

            and

            ema20 < ema50

        )

    ):

        return "BAJISTA"


    return "NEUTRAL"


    # ============================================================
# SCORE COMPRA
# ============================================================

def calcular_score_compra_v4(
    estructura,
    contexto15,
    impulso,
    pullback,
    continuacion,
    precio,
    ema20,
    ema50,
    rsi,
    adx,
    di_plus,
    di_minus,
    atr,
    zona
):

    score = 0


    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    if estructura["direccion"] == "ALCISTA":

        score += 20

    elif estructura["direccion"] == "NEUTRAL":

        score += 8


    if estructura["hh"]:

        score += 5


    if estructura["hl"]:

        score += 5


    if estructura["bos"] == "ALCISTA":

        score += 8


    # --------------------------------------------------------
    # CHoCH CONTRARIO
    # --------------------------------------------------------

    if estructura["choch"]:

        score -= 10


    # --------------------------------------------------------
    # CONTEXTO 15M
    # --------------------------------------------------------

    if contexto15 == "ALCISTA":

        score += 10

    elif contexto15 == "NEUTRAL":

        score += 5

    elif contexto15 == "BAJISTA":

        score -= 6


    # --------------------------------------------------------
    # IMPULSO
    # --------------------------------------------------------

    if impulso is not None:

        score += 12


        if (

            impulso[
                "desplazamiento_atr"
            ] >= 1.20

        ):

            score += 4


    # --------------------------------------------------------
    # PULLBACK
    # --------------------------------------------------------

    if pullback is not None:

        score += 12


        if (

            pullback[
                "retroceso_atr"
            ] <= 1.20

        ):

            score += 4


    # --------------------------------------------------------
    # CONTINUACIÓN
    # --------------------------------------------------------

    if continuacion:

        score += 15


    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if rsi >= RSI_COMPRA_MIN:

        score += 3


    if rsi >= RSI_CONFIRMACION_COMPRA:

        score += 2


    # --------------------------------------------------------
    # ADX
    # --------------------------------------------------------

    if adx >= ADX_MINIMO:

        score += 3


    if adx >= 25:

        score += 2


    # --------------------------------------------------------
    # DI
    # --------------------------------------------------------

    if di_plus > di_minus:

        score += 4


    # --------------------------------------------------------
    # EMA CONTEXTO
    # --------------------------------------------------------

    if ema20 > ema50:

        score += 3


    if precio > ema20:

        score += 2


    # --------------------------------------------------------
    # UBICACIÓN
    # --------------------------------------------------------

    if (

        zona is not None

        and

        atr > 0

    ):

        distancia = (

            precio -
            zona

        )


        distancia_atr = (

            distancia /
            atr

        )


        if (

            0 <=
            distancia_atr <=
            0.80

        ):

            score += 3


    return max(

        0,

        min(

            int(score),

            100

        )

    )


# ============================================================
# SCORE VENTA
# ============================================================

def calcular_score_venta_v4(
    estructura,
    contexto15,
    impulso,
    pullback,
    continuacion,
    precio,
    ema20,
    ema50,
    rsi,
    adx,
    di_plus,
    di_minus,
    atr,
    zona
):

    score = 0


    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    if estructura["direccion"] == "BAJISTA":

        score += 20

    elif estructura["direccion"] == "NEUTRAL":

        score += 8


    if estructura["lh"]:

        score += 5


    if estructura["ll"]:

        score += 5


    if estructura["bos"] == "BAJISTA":

        score += 8


    # --------------------------------------------------------
    # CHoCH
    # --------------------------------------------------------

    if estructura["choch"]:

        score -= 10


    # --------------------------------------------------------
    # CONTEXTO 15M
    # --------------------------------------------------------

    if contexto15 == "BAJISTA":

        score += 10

    elif contexto15 == "NEUTRAL":

        score += 5

    elif contexto15 == "ALCISTA":

        score -= 6


    # --------------------------------------------------------
    # IMPULSO
    # --------------------------------------------------------

    if impulso is not None:

        score += 12


        if (

            impulso[
                "desplazamiento_atr"
            ] >= 1.20

        ):

            score += 4


    # --------------------------------------------------------
    # PULLBACK
    # --------------------------------------------------------

    if pullback is not None:

        score += 12


        if (

            pullback[
                "retroceso_atr"
            ] <= 1.20

        ):

            score += 4


    # --------------------------------------------------------
    # CONTINUACIÓN
    # --------------------------------------------------------

    if continuacion:

        score += 15


    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if rsi <= RSI_VENTA_MAX:

        score += 3


    if rsi <= RSI_CONFIRMACION_VENTA:

        score += 2


    # --------------------------------------------------------
    # ADX
    # --------------------------------------------------------

    if adx >= ADX_MINIMO:

        score += 3


    if adx >= 25:

        score += 2


    # --------------------------------------------------------
    # DI
    # --------------------------------------------------------

    if di_minus > di_plus:

        score += 4


    # --------------------------------------------------------
    # EMA
    # --------------------------------------------------------

    if ema20 < ema50:

        score += 3


    if precio < ema20:

        score += 2


    # --------------------------------------------------------
    # UBICACIÓN
    # --------------------------------------------------------

    if (

        zona is not None

        and

        atr > 0

    ):

        distancia = (

            zona -
            precio

        )


        distancia_atr = (

            distancia /
            atr

        )


        if (

            0 <=
            distancia_atr <=
            0.80

        ):

            score += 3


    return max(

        0,

        min(

            int(score),

            100

        )

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
    ema50
):

    entrada = round(
        precio,
        2
    )


    sl = round(

        entrada -
        atr * ATR_SL,

        2

    )


    tp = round(

        entrada +
        atr * ATR_TP,

        2

    )


    identificador = (

        uuid.uuid4()
        .hex[:6]

    )


    mensaje = f"""
🥇 XAU SNIPER AI V4.0

ID: {identificador}

🟡 PREALERTA COMPRA

⚠️ MOVIMIENTO EN FORMACIÓN

⭐ Score: {score}/100

🏗️ Estructura:
{estructura["direccion"]}

🚀 Impulso:
{"DETECTADO" if impulso else "NO DETECTADO"}

🔄 Pullback:
{"DETECTADO" if pullback else "NO DETECTADO"}

📊 Precio:
{entrada:.2f}

🛑 SL referencia:
{sl:.2f}

🎯 TP referencia:
{tp:.2f}

📈 RSI: {rsi:.1f}
📊 ADX: {adx:.1f}

DI+: {di_plus:.1f}
DI-: {di_minus:.1f}

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}

🧠 V4:
Estructura → impulso → pullback

⏳ Esperando continuación...

⏱️ Vida máxima:
{MINUTOS_VIDA_PREALERTA} minutos
""".strip()


    return {

        "tipo":
            TIPO_PREALERTA_COMPRA,

        "mensaje":
            mensaje,

        "id":
            identificador

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
    ema50
):

    entrada = round(
        precio,
        2
    )


    sl = round(

        entrada +
        atr * ATR_SL,

        2

    )


    tp = round(

        entrada -
        atr * ATR_TP,

        2

    )


    identificador = (

        uuid.uuid4()
        .hex[:6]

    )


    mensaje = f"""
🥇 XAU SNIPER AI V4.0

ID: {identificador}

🟡 PREALERTA VENTA

⚠️ MOVIMIENTO EN FORMACIÓN

⭐ Score: {score}/100

🏗️ Estructura:
{estructura["direccion"]}

🚀 Impulso:
{"DETECTADO" if impulso else "NO DETECTADO"}

🔄 Pullback:
{"DETECTADO" if pullback else "NO DETECTADO"}

📊 Precio:
{entrada:.2f}

🛑 SL referencia:
{sl:.2f}

🎯 TP referencia:
{tp:.2f}

📈 RSI: {rsi:.1f}
📊 ADX: {adx:.1f}

DI+: {di_plus:.1f}
DI-: {di_minus:.1f}

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}

🧠 V4:
Estructura → impulso → pullback

⏳ Esperando continuación...

⏱️ Vida máxima:
{MINUTOS_VIDA_PREALERTA} minutos
""".strip()


    return {

        "tipo":
            TIPO_PREALERTA_VENTA,

        "mensaje":
            mensaje,

        "id":
            identificador

    }


    return None


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

    entrada = round(
        precio,
        2
    )


    sl = round(

        entrada -
        atr * ATR_SL,

        2

    )


    tp = round(

        entrada +
        atr * ATR_TP,

        2

    )


    identificador = (

        estado["id_pendiente"]

        or

        uuid.uuid4()
        .hex[:6]

    )


    mensaje = f"""
🥇 XAU SNIPER AI V4.0

ID: {identificador}

🟢 COMPRA CONFIRMADA

⭐ Score: {score}/100

🚀 Impulso: DETECTADO
🔄 Pullback: CONFIRMADO
💥 Continuación: CONFIRMADA

📋 PAPER TRADING

Precio:
{entrada:.2f}

🛑 SL simulado:
{sl:.2f}

🎯 TP simulado:
{tp:.2f}

📈 RSI: {rsi:.1f}
📊 ADX: {adx:.1f}

DI+: {di_plus:.1f}
DI-: {di_minus:.1f}

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}

🧠 V4:
Estructura → impulso → pullback → continuación

🧪 Operación simulada
""".strip()


    return {

        "tipo":
            TIPO_COMPRA,

        "mensaje":
            mensaje,

        "id":
            identificador

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

    entrada = round(
        precio,
        2
    )


    sl = round(

        entrada +
        atr * ATR_SL,

        2

    )


    tp = round(

        entrada -
        atr * ATR_TP,

        2

    )


    identificador = (

        estado["id_pendiente"]

        or

        uuid.uuid4()
        .hex[:6]

    )


    mensaje = f"""
🥇 XAU SNIPER AI V4.0

ID: {identificador}

🔴 VENTA CONFIRMADA

⭐ Score: {score}/100

🚀 Impulso: DETECTADO
🔄 Pullback: CONFIRMADO
💥 Continuación: CONFIRMADA

📋 PAPER TRADING

Precio:
{entrada:.2f}

🛑 SL simulado:
{sl:.2f}

🎯 TP simulado:
{tp:.2f}

📈 RSI: {rsi:.1f}
📊 ADX: {adx:.1f}

DI+: {di_plus:.1f}
DI-: {di_minus:.1f}

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}

🧠 V4:
Estructura → impulso → pullback → continuación

🧪 Operación simulada
""".strip()


    return {

        "tipo":
            TIPO_VENTA,

        "mensaje":
            mensaje,

        "id":
            identificador

    }


# ============================================================
# LIMPIAR ESTADO
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

    estado["pullback_maximo"] = None

    estado["nivel_continuacion"] = None


# ============================================================
# DESCARTADA COMPRA
# ============================================================

def descartada_compra(razon):

    identificador = (

        estado["id_pendiente"]

        or

        "------"

    )


    mensaje = (

        "🔴 PREALERTA COMPRA "
        "DESCARTADA\n\n"

        f"🆔 ID: {identificador}\n\n"

        f"{razon}"

    )


    limpiar_pendiente()


    return {

        "tipo":
            TIPO_DESCARTADA,

        "id":
            identificador,

        "mensaje":
            mensaje

    }


# ============================================================
# DESCARTADA VENTA
# ============================================================

def descartada_venta(razon):

    identificador = (

        estado["id_pendiente"]

        or

        "------"

    )


    mensaje = (

        "🟢 PREALERTA VENTA "
        "DESCARTADA\n\n"

        f"🆔 ID: {identificador}\n\n"

        f"{razon}"

    )


    limpiar_pendiente()


    return {

        "tipo":
            TIPO_DESCARTADA,

        "id":
            identificador,

        "mensaje":
            mensaje

    }


# ============================================================
# DIAGNÓSTICO
# ============================================================

def imprimir_diagnostico(
    estructura5,
    estructura15,
    contexto15,
    impulso_compra,
    impulso_venta,
    pullback_compra,
    pullback_venta,
    continuacion_compra,
    continuacion_venta,
    tardia_compra,
    tardia_venta,
    score_compra,
    score_venta,
    rsi,
    adx,
    di_plus,
    di_minus
):

    print("")
    print("===================================")
    print("📋 DIAGNÓSTICO XAU SNIPER V4")
    print("===================================")

    print(
        f"🏗️ 5M: "
        f"{estructura5['direccion']}"
    )

    print(
        f"🏗️ 15M: "
        f"{estructura15['direccion']}"
    )

    print(
        f"🧭 Contexto 15M: "
        f"{contexto15}"
    )

    print(
        f"📈 BOS: "
        f"{estructura5['bos']}"
    )

    print(
        f"🔄 CHoCH: "
        f"{estructura5['choch']}"
    )

    print(
        f"HH: {estructura5['hh']} | "
        f"HL: {estructura5['hl']}"
    )

    print(
        f"LH: {estructura5['lh']} | "
        f"LL: {estructura5['ll']}"
    )

    print(
        f"🚀 Impulso compra: "
        f"{impulso_compra is not None}"
    )

    print(
        f"🚀 Impulso venta: "
        f"{impulso_venta is not None}"
    )

    print(
        f"🔄 Pullback compra: "
        f"{pullback_compra is not None}"
    )

    print(
        f"🔄 Pullback venta: "
        f"{pullback_venta is not None}"
    )

    print(
        f"💥 Continuación compra: "
        f"{continuacion_compra}"
    )

    print(
        f"💥 Continuación venta: "
        f"{continuacion_venta}"
    )

    print(
        f"🚫 Compra tardía: "
        f"{tardia_compra}"
    )

    print(
        f"🚫 Venta tardía: "
        f"{tardia_venta}"
    )

    print(
        f"⭐ Score compra: "
        f"{score_compra}/100"
    )

    print(
        f"⭐ Score venta: "
        f"{score_venta}/100"
    )

    print(
        f"📈 RSI: {rsi:.1f}"
    )

    print(
        f"📊 ADX: {adx:.1f}"
    )

    print(
        f"DI+: {di_plus:.1f}"
    )

    print(
        f"DI-: {di_minus:.1f}"
    )

    print(
        f"⏳ Pendiente: "
        f"{estado['direccion_pendiente']}"
    )

    print("===================================")


# ============================================================
# ANALIZAR V4
# ============================================================

def analizar():

    try:

        print("")
        print("===================================")
        print("🔍 XAU SNIPER AI V4.0")
        print("🧠 ESTRUCTURA + MOVIMIENTO")
        print("===================================")


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


        if len(df5) < 100:

            raise Exception(

                "Datos 5M insuficientes"

            )


        if len(df15) < 100:

            raise Exception(

                "Datos 15M insuficientes"

            )


        # ====================================================
        # ACTUAL
        # ====================================================

        actual5 = df5.iloc[-1]


        precio = float(

            actual5["close"]

        )


        ema20 = float(

            actual5["ema20"]

        )


        ema50 = float(

            actual5["ema50"]

        )


        rsi = float(

            actual5["rsi"]

        )


        atr = float(

            actual5["atr"]

        )


        adx = float(

            actual5["adx"]

        )


        di_plus = float(

            actual5["di_plus"]

        )


        di_minus = float(

            actual5["di_minus"]

        )


        ahora = time.time()


        # ====================================================
        # ESTRUCTURA
        # ====================================================

        estructura5 = analizar_estructura(

            df5

        )


        estructura15 = analizar_estructura(

            df15

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
        # CONTINUACIONES
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
        # SI HAY PREALERTA PENDIENTE,
        # CONSERVAMOS SU NIVEL
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
        # SCORE
        # ====================================================

        score_compra = (

            calcular_score_compra_v4(

                estructura5,

                contexto15,

                impulso_compra,

                pullback_compra,

                continuacion_compra,

                precio,

                ema20,

                ema50,

                rsi,

                adx,

                di_plus,

                di_minus,

                atr,

                zona_compra

            )

        )


        score_venta = (

            calcular_score_venta_v4(

                estructura5,

                contexto15,

                impulso_venta,

                pullback_venta,

                continuacion_venta,

                precio,

                ema20,

                ema50,

                rsi,

                adx,

                di_plus,

                di_minus,

                atr,

                zona_venta

            )

        )


        # ====================================================
        # DIAGNÓSTICO
        # ====================================================

        imprimir_diagnostico(

            estructura5,

            estructura15,

            contexto15,

            impulso_compra,

            impulso_venta,

            pullback_compra,

            pullback_venta,

            continuacion_compra,

            continuacion_venta,

            tardia_compra,

            tardia_venta,

            score_compra,

            score_venta,

            rsi,

            adx,

            di_plus,

            di_minus

        )


        # ====================================================
        # SETUPS POSIBLES
        #
        # YA NO REQUERIMOS QUE 5M Y 15M SEAN IGUALES.
        # ====================================================

        posible_compra = (

            impulso_compra is not None

            and

            pullback_compra is not None

            and

            not tardia_compra

            and

            score_compra >=
            SCORE_MIN_PREALERTA

        )


        posible_venta = (

            impulso_venta is not None

            and

            pullback_venta is not None

            and

            not tardia_venta

            and

            score_venta >=
            SCORE_MIN_PREALERTA

        )


        # ====================================================
        # PREALERTA YA EXISTENTE
        # ====================================================

        if (

            estado[
                "direccion_pendiente"
            ] is not None

        ):

            tiempo_viva = (

                ahora -
                estado[
                    "inicio_pendiente"
                ]

            )


            # =================================================
            # EXPIRACIÓN
            # =================================================

            if (

                tiempo_viva >=

                MINUTOS_VIDA_PREALERTA * 60

            ):

                print(
                    "⏳ PREALERTA EXPIRADA"
                )


                if (

                    estado[
                        "direccion_pendiente"
                    ] == "COMPRA"

                ):

                    return descartada_compra(

                        "⏳ Tiempo de "
                        "confirmación agotado.\n\n"
                        "El movimiento no produjo "
                        "continuación válida dentro "
                        f"de {MINUTOS_VIDA_PREALERTA} "
                        "minutos."

                    )


                return descartada_venta(

                    "⏳ Tiempo de "
                    "confirmación agotado.\n\n"
                    "El movimiento no produjo "
                    "continuación válida dentro "
                    f"de {MINUTOS_VIDA_PREALERTA} "
                    "minutos."

                )


            # =================================================
            # PREALERTA COMPRA
            # =================================================

            if (

                estado[
                    "direccion_pendiente"
                ] == "COMPRA"

            ):

                contexto_contrario = (

                    estructura5[
                        "direccion"
                    ] == "BAJISTA"

                    and

                    estructura5[
                        "fuerza"
                    ] >= 2

                    and

                    contexto15 == "BAJISTA"

                )


                if contexto_contrario:

                    return descartada_compra(

                        "📉 La estructura cambió "
                        "claramente a bajista en "
                        "5M y 15M."

                    )


                if (

                    continuacion_compra

                    and

                    score_compra >=
                    SCORE_MIN_CONFIRMACION

                    and

                    not tardia_compra

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
                    "⏳ Compra V4 pendiente..."
                )


                return {

                    "tipo":
                        TIPO_SIN_SEÑAL,

                    "mensaje":
                        "🔎 Compra V4 "
                        "pendiente de confirmación..."

                }


            # =================================================
            # PREALERTA VENTA
            # =================================================

            if (

                estado[
                    "direccion_pendiente"
                ] == "VENTA"

            ):

                contexto_contrario = (

                    estructura5[
                        "direccion"
                    ] == "ALCISTA"

                    and

                    estructura5[
                        "fuerza"
                    ] >= 2

                    and

                    contexto15 == "ALCISTA"

                )


                if contexto_contrario:

                    return descartada_venta(

                        "📈 La estructura cambió "
                        "claramente a alcista en "
                        "5M y 15M."

                    )


                if (

                    continuacion_venta

                    and

                    score_venta >=
                    SCORE_MIN_CONFIRMACION

                    and

                    not tardia_venta

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
                    "⏳ Venta V4 pendiente..."
                )


                return {

                    "tipo":
                        TIPO_SIN_SEÑAL,

                    "mensaje":
                        "🔎 Venta V4 "
                        "pendiente de confirmación..."

                }


        # ====================================================
        # NUEVA PREALERTA COMPRA
        # ====================================================

        if posible_compra:

            cooldown_ok = (

                ahora -
                estado[
                    "ultima_prealerta"
                ]

                >=

                MINUTOS_REPETICION * 60

            )


            if cooldown_ok:

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

                        ema50

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
                ] = (

                    impulso_compra[
                        "inicio"
                    ]

                )


                estado[
                    "impulso_extremo"
                ] = (

                    impulso_compra[
                        "extremo"
                    ]

                )


                estado[
                    "pullback_nivel"
                ] = (

                    pullback_compra[
                        "minimo_pullback"
                    ]

                )


                estado[
                    "pullback_maximo"
                ] = None


                estado[
                    "nivel_continuacion"
                ] = (

                    pullback_compra[
                        "nivel_continuacion"
                    ]

                )


                print(
                    "🟡 NUEVA PREALERTA COMPRA"
                )


                return resultado


        # ====================================================
        # NUEVA PREALERTA VENTA
        # ====================================================

        if posible_venta:

            cooldown_ok = (

                ahora -
                estado[
                    "ultima_prealerta"
                ]

                >=

                MINUTOS_REPETICION * 60

            )


            if cooldown_ok:

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

                        ema50

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
                ] = (

                    impulso_venta[
                        "inicio"
                    ]

                )


                estado[
                    "impulso_extremo"
                ] = (

                    impulso_venta[
                        "extremo"
                    ]

                )


                # =========================================
                # CORREGIDO
                # =========================================
                #
                # El campo correcto del pullback bajista
                # es maximo_pullback.
                #
                # =========================================

                estado[
                    "pullback_maximo"
                ] = (

                    pullback_venta[
                        "maximo_pullback"
                    ]

                )


                estado[
                    "pullback_nivel"
                ] = (

                    pullback_venta[
                        "maximo_pullback"
                    ]

                )


                estado[
                    "nivel_continuacion"
                ] = (

                    pullback_venta[
                        "nivel_continuacion"
                    ]

                )


                print(
                    "🟡 NUEVA PREALERTA VENTA"
                )


                return resultado


        # ====================================================
        # SIN SEÑAL
        # ====================================================

        return {

            "tipo":
                TIPO_SIN_SEÑAL,

            "mensaje":
                "😴 Sin señal V4"

        }


    # ========================================================
    # ERROR GENERAL
    # ========================================================

    except Exception as e:

        print("")

        print(
            "❌ ERROR EN ANALIZAR V4:"
        )

        print(
            repr(e)
        )


        return {

            "tipo":
                TIPO_ERROR,

            "mensaje":
                f"❌ Error V4:\n{e}"

    }
