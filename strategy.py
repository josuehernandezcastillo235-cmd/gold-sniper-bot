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
# MOTOR DE:
#
# ESTRUCTURA
# MOVIMIENTO
# IMPULSO
# PULLBACK
# CONTINUACIÓN
# UBICACIÓN
# MOMENTUM
#
# EMA / RSI / ADX / DI = CONTEXTO SECUNDARIO
# ============================================================


API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"

INTERVALO_5M = "5min"
INTERVALO_15M = "15min"


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

MINUTOS_REPETICION = 15

MINUTOS_VIDA_PREALERTA = 30

ADX_MINIMO = 15

RSI_COMPRA_MIN = 50
RSI_VENTA_MAX = 50

RSI_CONFIRMACION_COMPRA = 53
RSI_CONFIRMACION_VENTA = 47

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

IMPULSO_ATR_MIN = 0.70
IMPULSO_VELAS = 8

MIN_VELAS_IMPULSO = 2


# ============================================================
# PULLBACK
# ============================================================

PULLBACK_MIN_ATR = 0.20
PULLBACK_MAX_ATR = 1.80

PULLBACK_VELAS = 6


# ============================================================
# CONTINUACIÓN
# ============================================================

CONTINUACION_ATR_MIN = 0.05

CONTINUACION_CUERPO_ATR = 0.12


# ============================================================
# ENTRADA TARDÍA
# ============================================================

MAX_DISTANCIA_ENTRADA_ATR = 1.50


# ============================================================
# SCORE
# ============================================================

SCORE_MIN_PREALERTA = 60
SCORE_MIN_CONFIRMACION = 70


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

    "estructura_prealerta": None,

    "nivel_continuacion": None,

    "extremo_impulso": None,

    "zona_pullback": None
}


# ============================================================
# OBTENER DATOS
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

    params = {
        "symbol": SYMBOL,
        "interval": intervalo,
        "outputsize": 5000,
        "apikey": API_KEY,
        "format": "JSON"
    }

    respuesta = requests.get(
        url,
        params=params,
        timeout=20
    )

    respuesta.raise_for_status()

    data = respuesta.json()

    if "values" not in data:
        raise Exception(
            f"Error Twelve Data: {data}"
        )

    df = pd.DataFrame(
        data["values"]
    )

    if df.empty:
        raise Exception(
            f"Datos vacíos para {intervalo}"
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
            "close"
        ]
    )

    df = df.sort_values(
        "datetime"
    )

    df = df.reset_index(
        drop=True
    )

    print(
        f"📥 {intervalo}: "
        f"{len(df)} velas recibidas"
    )

    return df


# ============================================================
# INDICADORES
# ============================================================

def calcular_indicadores(df):

    df = df.copy()

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

    # --------------------------------------------------------
    # DATOS DE VELA
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # MEDIA DEL RANGO
    # --------------------------------------------------------

    df["rango_medio"] = (
        df["rango"]
        .rolling(20)
        .mean()
    )

    df["expansion"] = (
        df["rango"]
        >
        df["rango_medio"] * 1.10
    )

    # --------------------------------------------------------
    # VELOCIDAD DEL PRECIO
    # --------------------------------------------------------

    df["movimiento"] = (
        df["close"]
        .diff()
    )

    df["movimiento_atr"] = (
        df["movimiento"].abs()
        /
        df["atr"]
    )

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
    final = len(df) - SWING_RIGHT

    for i in range(inicio, final):

        high_actual = float(
            df.iloc[i]["high"]
        )

        low_actual = float(
            df.iloc[i]["low"]
        )

        atr = float(
            df.iloc[i]["atr"]
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

        swing_high = (
            high_actual >= altos_izq.max()
            and
            high_actual >= altos_der.max()
        )

        swing_low = (
            low_actual <= bajos_izq.min()
            and
            low_actual <= bajos_der.min()
        )

        if swing_high:

            highs.append({
                "index": i,
                "precio": high_actual,
                "atr": atr
            })

        if swing_low:

            lows.append({
                "index": i,
                "precio": low_actual,
                "atr": atr
            })

    return highs, lows


# ============================================================
# ANALIZAR ESTRUCTURA V4
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

        "fuerza": 0,

        "nivel_bos_alcista": None,
        "nivel_bos_bajista": None
    }

    if len(highs) >= 2:

        resultado["ultimo_high"] = highs[-1]

        resultado["prev_high"] = highs[-2]

    if len(lows) >= 2:

        resultado["ultimo_low"] = lows[-1]

        resultado["prev_low"] = lows[-2]

    # --------------------------------------------------------
    # HH / LH
    # --------------------------------------------------------

    if len(highs) >= 2:

        resultado["hh"] = (
            highs[-1]["precio"]
            >
            highs[-2]["precio"]
        )

        resultado["lh"] = (
            highs[-1]["precio"]
            <
            highs[-2]["precio"]
        )

    # --------------------------------------------------------
    # HL / LL
    # --------------------------------------------------------

    if len(lows) >= 2:

        resultado["hl"] = (
            lows[-1]["precio"]
            >
            lows[-2]["precio"]
        )

        resultado["ll"] = (
            lows[-1]["precio"]
            <
            lows[-2]["precio"]
        )

    precio = float(
        df.iloc[-1]["close"]
    )

    atr = float(
        df.iloc[-1]["atr"]
    )

    # --------------------------------------------------------
    # NIVELES IMPORTANTES
    # --------------------------------------------------------

    if resultado["ultimo_high"]:

        resultado["nivel_bos_alcista"] = (
            resultado["ultimo_high"]["precio"]
        )

    if resultado["ultimo_low"]:

        resultado["nivel_bos_bajista"] = (
            resultado["ultimo_low"]["precio"]
        )

    # --------------------------------------------------------
    # BOS
    # --------------------------------------------------------

    if (
        resultado["nivel_bos_alcista"]
        is not None
        and
        precio >
        resultado["nivel_bos_alcista"]
        + atr * 0.03
    ):

        resultado["bos"] = "ALCISTA"

    elif (
        resultado["nivel_bos_bajista"]
        is not None
        and
        precio <
        resultado["nivel_bos_bajista"]
        - atr * 0.03
    ):

        resultado["bos"] = "BAJISTA"

    # --------------------------------------------------------
    # ESTRUCTURA PRINCIPAL
    #
    # Ya NO exigimos obligatoriamente HH + HL.
    # --------------------------------------------------------

    puntos_alcistas = 0
    puntos_bajistas = 0

    if resultado["hh"]:
        puntos_alcistas += 2

    if resultado["hl"]:
        puntos_alcistas += 2

    if resultado["lh"]:
        puntos_bajistas += 2

    if resultado["ll"]:
        puntos_bajistas += 2

    if resultado["bos"] == "ALCISTA":
        puntos_alcistas += 2

    if resultado["bos"] == "BAJISTA":
        puntos_bajistas += 2

    # --------------------------------------------------------
    # PRECIO VS ÚLTIMOS SWINGS
    # --------------------------------------------------------

    if (
        resultado["ultimo_low"]
        is not None
        and
        precio >
        resultado["ultimo_low"]["precio"]
    ):

        puntos_alcistas += 1

    if (
        resultado["ultimo_high"]
        is not None
        and
        precio <
        resultado["ultimo_high"]["precio"]
    ):

        puntos_bajistas += 1

    # --------------------------------------------------------
    # DIRECCIÓN
    # --------------------------------------------------------

    if (
        puntos_alcistas >= 3
        and
        puntos_alcistas >
        puntos_bajistas
    ):

        resultado["direccion"] = "ALCISTA"

        resultado["fuerza"] = (
            puntos_alcistas
            -
            puntos_bajistas
        )

    elif (
        puntos_bajistas >= 3
        and
        puntos_bajistas >
        puntos_alcistas
    ):

        resultado["direccion"] = "BAJISTA"

        resultado["fuerza"] = (
            puntos_bajistas
            -
            puntos_alcistas
        )

    else:

        # ----------------------------------------------------
        # TRANSICIÓN
        # ----------------------------------------------------

        if (
            resultado["hh"]
            and
            not resultado["ll"]
        ):

            resultado["direccion"] = (
                "TRANSICION_ALCISTA"
            )

        elif (
            resultado["ll"]
            and
            not resultado["hh"]
        ):

            resultado["direccion"] = (
                "TRANSICION_BAJISTA"
            )

        resultado["fuerza"] = 0

    # --------------------------------------------------------
    # CHoCH
    # --------------------------------------------------------

    if (
        resultado["direccion"]
        in [
            "ALCISTA",
            "TRANSICION_ALCISTA"
        ]
        and
        resultado["bos"] == "BAJISTA"
    ):

        resultado["choch"] = True

    if (
        resultado["direccion"]
        in [
            "BAJISTA",
            "TRANSICION_BAJISTA"
        ]
        and
        resultado["bos"] == "ALCISTA"
    ):

        resultado["choch"] = True

    return resultado


# ============================================================
# IMPULSO ALCISTA
# ============================================================

def detectar_impulso_alcista(df):

    if len(df) < IMPULSO_VELAS + 2:
        return None

    atr = float(
        df.iloc[-1]["atr"]
    )

    if atr <= 0:
        return None

    ventana = df.iloc[
        -IMPULSO_VELAS:
    ]

    inicio = float(
        ventana.iloc[0]["close"]
    )

    extremo = float(
        ventana["high"].max()
    )

    desplazamiento = (
        extremo - inicio
    )

    desplazamiento_atr = (
        desplazamiento / atr
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

    # El precio no debe estar muy lejos del extremo
    distancia_extremo = (
        extremo - cierre_actual
    )

    distancia_extremo_atr = (
        distancia_extremo / atr
    )

    if (
        desplazamiento_atr
        >=
        IMPULSO_ATR_MIN
        and
        velas_alcistas
        >=
        MIN_VELAS_IMPULSO
        and
        distancia_extremo_atr
        <=
        1.50
    ):

        return {

            "direccion": "ALCISTA",

            "inicio": inicio,

            "extremo": extremo,

            "desplazamiento":
                desplazamiento,

            "desplazamiento_atr":
                desplazamiento_atr,

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

    atr = float(
        df.iloc[-1]["atr"]
    )

    if atr <= 0:
        return None

    ventana = df.iloc[
        -IMPULSO_VELAS:
    ]

    inicio = float(
        ventana.iloc[0]["close"]
    )

    extremo = float(
        ventana["low"].min()
    )

    desplazamiento = (
        inicio - extremo
    )

    desplazamiento_atr = (
        desplazamiento / atr
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

    distancia_extremo = (
        cierre_actual - extremo
    )

    distancia_extremo_atr = (
        distancia_extremo / atr
    )

    if (
        desplazamiento_atr
        >=
        IMPULSO_ATR_MIN
        and
        velas_bajistas
        >=
        MIN_VELAS_IMPULSO
        and
        distancia_extremo_atr
        <=
        1.50
    ):

        return {

            "direccion": "BAJISTA",

            "inicio": inicio,

            "extremo": extremo,

            "desplazamiento":
                desplazamiento,

            "desplazamiento_atr":
                desplazamiento_atr,

            "velas_bajistas":
                velas_bajistas,

            "expansion":
                expansion
        }

    return None


# ============================================================
# PULLBACK ALCISTA V4
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

    ventana = df.iloc[
        -PULLBACK_VELAS:
    ]

    minimo = float(
        ventana["low"].min()
    )

    retroceso = (
        extremo - minimo
    )

    retroceso_atr = (
        retroceso / atr
    )

    precio = float(
        df.iloc[-1]["close"]
    )

    # --------------------------------------------------------
    # El precio debe seguir razonablemente cerca del impulso.
    # --------------------------------------------------------

    distancia_extremo = (
        extremo - precio
    )

    distancia_extremo_atr = (
        distancia_extremo / atr
    )

    if (
        retroceso_atr
        >=
        PULLBACK_MIN_ATR
        and
        retroceso_atr
        <=
        PULLBACK_MAX_ATR
        and
        distancia_extremo_atr
        <=
        PULLBACK_MAX_ATR
    ):

        return {

            "direccion": "ALCISTA",

            "extremo_impulso":
                extremo,

            "minimo_pullback":
                minimo,

            "retroceso":
                retroceso,

            "retroceso_atr":
                retroceso_atr
        }

    return None


# ============================================================
# PULLBACK BAJISTA V4
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

    ventana = df.iloc[
        -PULLBACK_VELAS:
    ]

    maximo = float(
        ventana["high"].max()
    )

    retroceso = (
        maximo - extremo
    )

    retroceso_atr = (
        retroceso / atr
    )

    precio = float(
        df.iloc[-1]["close"]
    )

    distancia_extremo = (
        precio - extremo
    )

    distancia_extremo_atr = (
        distancia_extremo / atr
    )

    if (
        retroceso_atr
        >=
        PULLBACK_MIN_ATR
        and
        retroceso_atr
        <=
        PULLBACK_MAX_ATR
        and
        distancia_extremo_atr
        <=
        PULLBACK_MAX_ATR
    ):

        return {

            "direccion": "BAJISTA",

            "extremo_impulso":
                extremo,

            "maximo_pullback":
                maximo,

            "retroceso":
                retroceso,

            "retroceso_atr":
                retroceso_atr
        }

    return None


# ============================================================
# CONTINUACIÓN ALCISTA V4
#
# YA NO EXIGE ROMPER TODO EL EXTREMO DEL IMPULSO.
#
# Busca:
# - vela alcista
# - recuperación del pullback
# - aceleración
# - ruptura del máximo reciente
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

    maximo = float(
        actual["high"]
    )

    cuerpo = abs(
        precio - apertura
    )

    vela_alcista = (
        precio > apertura
    )

    cuerpo_valido = (
        cuerpo
        >=
        atr * CONTINUACION_CUERPO_ATR
    )

    # --------------------------------------------------------
    # Máximo reciente antes de la vela actual.
    # --------------------------------------------------------

    if len(df) >= 4:

        maximo_reciente = float(
            df.iloc[-4:-1]["high"].max()
        )

    else:

        maximo_reciente = (
            float(
                df["high"].iloc[-2]
            )
        )

    ruptura_reciente = (
        precio
        >
        maximo_reciente
        +
        atr * CONTINUACION_ATR_MIN
    )

    # --------------------------------------------------------
    # Recuperación del pullback
    # --------------------------------------------------------

    minimo_pullback = float(
        pullback["minimo_pullback"]
    )

    distancia_pullback = (
        precio - minimo_pullback
    )

    recuperacion = (
        distancia_pullback
        >=
        atr * 0.15
    )

    # --------------------------------------------------------
    # Movimiento positivo actual
    # --------------------------------------------------------

    movimiento = (
        precio - float(
            df.iloc[-2]["close"]
        )
    )

    movimiento_valido = (
        movimiento
        >=
        atr * 0.05
    )

    confirmada = (

        vela_alcista

        and

        cuerpo_valido

        and

        recuperacion

        and

        (
            ruptura_reciente
            or
            movimiento_valido
        )
    )

    # Nivel de continuación
    nivel = maximo_reciente

    return (
        confirmada,
        nivel
    )


# ============================================================
# CONTINUACIÓN BAJISTA V4
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

    minimo = float(
        actual["low"]
    )

    cuerpo = abs(
        precio - apertura
    )

    vela_bajista = (
        precio < apertura
    )

    cuerpo_valido = (
        cuerpo
        >=
        atr * CONTINUACION_CUERPO_ATR
    )

    if len(df) >= 4:

        minimo_reciente = float(
            df.iloc[-4:-1]["low"].min()
        )

    else:

        minimo_reciente = (
            float(
                df["low"].iloc[-2]
            )
        )

    ruptura_reciente = (
        precio
        <
        minimo_reciente
        -
        atr * CONTINUACION_ATR_MIN
    )

    maximo_pullback = float(
        pullback["maximo_pullback"]
    )

    distancia_pullback = (
        maximo_pullback - precio
    )

    recuperacion = (
        distancia_pullback
        >=
        atr * 0.15
    )

    movimiento = (
        float(
            df.iloc[-2]["close"]
        )
        -
        precio
    )

    movimiento_valido = (
        movimiento
        >=
        atr * 0.05
    )

    confirmada = (

        vela_bajista

        and

        cuerpo_valido

        and

        recuperacion

        and

        (
            ruptura_reciente
            or
            movimiento_valido
        )
    )

    nivel = minimo_reciente

    return (
        confirmada,
        nivel
    )


# ============================================================
# ENTRADA TARDÍA COMPRA
# ============================================================

def entrada_tardia_compra(
    precio,
    zona,
    atr
):

    if zona is None or atr <= 0:
        return False

    distancia = (
        precio - zona
    )

    if distancia <= 0:
        return False

    distancia_atr = (
        distancia / atr
    )

    return (
        distancia_atr
        >
        MAX_DISTANCIA_ENTRADA_ATR
    )


# ============================================================
# ENTRADA TARDÍA VENTA
# ============================================================

def entrada_tardia_venta(
    precio,
    zona,
    atr
):

    if zona is None or atr <= 0:
        return False

    distancia = (
        zona - precio
    )

    if distancia <= 0:
        return False

    distancia_atr = (
        distancia / atr
    )

    return (
        distancia_atr
        >
        MAX_DISTANCIA_ENTRADA_ATR
    )


# ============================================================
# SCORE COMPRA V4
# ============================================================

def calcular_score_compra_v4(
    estructura,
    estructura15,
    impulso,
    pullback,
    continuacion,
    precio,
    ema20,
    ema50,
    ema200,
    rsi,
    adx,
    di_plus,
    di_minus,
    atr,
    zona
):

    score = 0

    # --------------------------------------------------------
    # ESTRUCTURA 5M
    # --------------------------------------------------------

    if estructura["direccion"] == "ALCISTA":
        score += 20

    elif estructura["direccion"] == "TRANSICION_ALCISTA":
        score += 12

    if estructura["hh"]:
        score += 4

    if estructura["hl"]:
        score += 4

    if estructura["bos"] == "ALCISTA":
        score += 7

    # --------------------------------------------------------
    # CONTEXTO 15M
    #
    # YA NO ES OBLIGATORIO.
    # --------------------------------------------------------

    if estructura15["direccion"] == "ALCISTA":
        score += 10

    elif estructura15["direccion"] == "TRANSICION_ALCISTA":
        score += 5

    elif estructura15["direccion"] == "BAJISTA":
        score -= 6

    # --------------------------------------------------------
    # IMPULSO
    # --------------------------------------------------------

    if impulso is not None:

        score += 12

        if (
            impulso["desplazamiento_atr"]
            >=
            1.20
        ):

            score += 4

        if impulso["expansion"] >= 1:
            score += 2

    # --------------------------------------------------------
    # PULLBACK
    # --------------------------------------------------------

    if pullback is not None:

        score += 12

        if (
            pullback["retroceso_atr"]
            <=
            1.20
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
        score += 2

    if adx >= 20:
        score += 2

    # --------------------------------------------------------
    # DI
    # --------------------------------------------------------

    if di_plus > di_minus:
        score += 4

    # --------------------------------------------------------
    # EMA COMO CONTEXTO
    # --------------------------------------------------------

    if ema20 > ema50:
        score += 2

    if precio > ema20:
        score += 2

    if ema20 > ema200:
        score += 1

    # --------------------------------------------------------
    # UBICACIÓN
    # --------------------------------------------------------

    if zona is not None and atr > 0:

        distancia = (
            precio - zona
        )

        distancia_atr = (
            distancia / atr
        )

        if (
            0 <= distancia_atr <= 0.70
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
# SCORE VENTA V4
# ============================================================

def calcular_score_venta_v4(
    estructura,
    estructura15,
    impulso,
    pullback,
    continuacion,
    precio,
    ema20,
    ema50,
    ema200,
    rsi,
    adx,
    di_plus,
    di_minus,
    atr,
    zona
):

    score = 0

    # --------------------------------------------------------
    # ESTRUCTURA 5M
    # --------------------------------------------------------

    if estructura["direccion"] == "BAJISTA":
        score += 20

    elif estructura["direccion"] == "TRANSICION_BAJISTA":
        score += 12

    if estructura["lh"]:
        score += 4

    if estructura["ll"]:
        score += 4

    if estructura["bos"] == "BAJISTA":
        score += 7

    # --------------------------------------------------------
    # CONTEXTO 15M
    # --------------------------------------------------------

    if estructura15["direccion"] == "BAJISTA":
        score += 10

    elif estructura15["direccion"] == "TRANSICION_BAJISTA":
        score += 5

    elif estructura15["direccion"] == "ALCISTA":
        score -= 6

    # --------------------------------------------------------
    # IMPULSO
    # --------------------------------------------------------

    if impulso is not None:

        score += 12

        if (
            impulso["desplazamiento_atr"]
            >=
            1.20
        ):

            score += 4

        if impulso["expansion"] >= 1:
            score += 2

    # --------------------------------------------------------
    # PULLBACK
    # --------------------------------------------------------

    if pullback is not None:

        score += 12

        if (
            pullback["retroceso_atr"]
            <=
            1.20
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
        score += 2

    if adx >= 20:
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
        score += 2

    if precio < ema20:
        score += 2

    if ema20 < ema200:
        score += 1

    # --------------------------------------------------------
    # UBICACIÓN
    # --------------------------------------------------------

    if zona is not None and atr > 0:

        distancia = (
            zona - precio
        )

        distancia_atr = (
            distancia / atr
        )

        if (
            0 <= distancia_atr <= 0.70
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
        entrada - atr * ATR_SL,
        2
    )

    tp = round(
        entrada + atr * ATR_TP,
        2
    )

    identificador = (
        uuid.uuid4().hex[:6]
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

🧠 Lectura:
Precio → estructura → movimiento

⏳ Esperando continuación...

⏱️ Tiempo máximo:
{MINUTOS_VIDA_PREALERTA} minutos
""".strip()

    return {
        "tipo": "POSIBLE_COMPRA",
        "mensaje": mensaje,
        "id": identificador
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
        entrada + atr * ATR_SL,
        2
    )

    tp = round(
        entrada - atr * ATR_TP,
        2
    )

    identificador = (
        uuid.uuid4().hex[:6]
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

🧠 Lectura:
Precio → estructura → movimiento

⏳ Esperando continuación...

⏱️ Tiempo máximo:
{MINUTOS_VIDA_PREALERTA} minutos
""".strip()

    return {
        "tipo": "POSIBLE_VENTA",
        "mensaje": mensaje,
        "id": identificador
    }


# ============================================================
# CREAR COMPRA CONFIRMADA
# ============================================================

def crear_compra_confirmada(
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
        entrada - atr * ATR_SL,
        2
    )

    tp = round(
        entrada + atr * ATR_TP,
        2
    )

    identificador = (
        estado["id_pendiente"]
        or uuid.uuid4().hex[:6]
    )

    mensaje = f"""
🥇 XAU SNIPER AI V4.0

ID: {identificador}

🟢 COMPRA CONFIRMADA

⭐ Score: {score}/100

🏗️ Estructura:
{estructura["direccion"]}

🚀 Impulso: DETECTADO
🔄 Pullback: CONFIRMADO
💥 Continuación: CONFIRMADA

📋 ENTRADA

Precio: {entrada:.2f}

🛑 SL:
{sl:.2f}

🎯 TP:
{tp:.2f}

📈 RSI: {rsi:.1f}
📊 ADX: {adx:.1f}

DI+: {di_plus:.1f}
DI-: {di_minus:.1f}

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}

✅ Movimiento alcista
✅ Impulso detectado
✅ Pullback válido
✅ Continuación confirmada
✅ Entrada dentro de zona válida
""".strip()

    return {
        "tipo": "COMPRA",
        "mensaje": mensaje,
        "id": identificador
    }


# ============================================================
# CREAR VENTA CONFIRMADA
# ============================================================

def crear_venta_confirmada(
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
        entrada + atr * ATR_SL,
        2
    )

    tp = round(
        entrada - atr * ATR_TP,
        2
    )

    identificador = (
        estado["id_pendiente"]
        or uuid.uuid4().hex[:6]
    )

    mensaje = f"""
🥇 XAU SNIPER AI V4.0

ID: {identificador}

🔴 VENTA CONFIRMADA

⭐ Score: {score}/100

🏗️ Estructura:
{estructura["direccion"]}

🚀 Impulso: DETECTADO
🔄 Pullback: CONFIRMADO
💥 Continuación: CONFIRMADA

📋 ENTRADA

Precio: {entrada:.2f}

🛑 SL:
{sl:.2f}

🎯 TP:
{tp:.2f}

📈 RSI: {rsi:.1f}
📊 ADX: {adx:.1f}

DI+: {di_plus:.1f}
DI-: {di_minus:.1f}

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}

✅ Movimiento bajista
✅ Impulso detectado
✅ Pullback válido
✅ Continuación confirmada
✅ Entrada dentro de zona válida
""".strip()

    return {
        "tipo": "VENTA",
        "mensaje": mensaje,
        "id": identificador
        }


# ============================================================
# LIMPIAR ESTADO
# ============================================================

def limpiar_pendiente():

    estado["direccion_pendiente"] = None
    estado["id_pendiente"] = None
    estado["inicio_pendiente"] = 0
    estado["precio_prealerta"] = None
    estado["estructura_prealerta"] = None
    estado["nivel_continuacion"] = None
    estado["extremo_impulso"] = None
    estado["zona_pullback"] = None


# ============================================================
# ANALIZAR V4
# ============================================================

def analizar():

    try:

        print("")
        print("===================================")
        print("🧠 XAU SNIPER AI V4.0")
        print("🔍 Analizando movimiento...")
        print("===================================")

        # ----------------------------------------------------
        # DATOS
        # ----------------------------------------------------

        df5 = obtener_datos(
            INTERVALO_5M
        )

        df15 = obtener_datos(
            INTERVALO_15M
        )

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

        # ----------------------------------------------------
        # DATOS ACTUALES
        # ----------------------------------------------------

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

        ema200 = float(
            actual5["ema200"]
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

        # ----------------------------------------------------
        # ESTRUCTURA
        # ----------------------------------------------------

        estructura5 = analizar_estructura(
            df5
        )

        estructura15 = analizar_estructura(
            df15
        )

        print("")
        print("🏗️ ESTRUCTURA")
        print("-----------------------------------")

        print(
            f"5M: "
            f"{estructura5['direccion']}"
        )

        print(
            f"15M: "
            f"{estructura15['direccion']}"
        )

        print(
            f"BOS 5M: "
            f"{estructura5['bos']}"
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
            f"Fuerza estructura: "
            f"{estructura5['fuerza']}"
        )

        # ----------------------------------------------------
        # IMPULSOS
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # PULLBACKS
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # CONTINUACIONES
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # ENTRADAS TARDÍAS
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # POSIBLE COMPRA
        #
        # 15M YA NO BLOQUEA.
        # ----------------------------------------------------

        estructura_compra_valida = (
            estructura5["direccion"]
            in [
                "ALCISTA",
                "TRANSICION_ALCISTA"
            ]
        )

        estructura_venta_valida = (
            estructura5["direccion"]
            in [
                "BAJISTA",
                "TRANSICION_BAJISTA"
            ]
        )

        posible_compra = (
            estructura_compra_valida
            and
            impulso_compra is not None
            and
            pullback_compra is not None
            and
            not tardia_compra
        )

        posible_venta = (
            estructura_venta_valida
            and
            impulso_venta is not None
            and
            pullback_venta is not None
            and
            not tardia_venta
        )

        # ----------------------------------------------------
        # CONFIRMACIÓN
        # ----------------------------------------------------

        confirmada_compra = (
            posible_compra
            and
            continuacion_compra
            and
            rsi >= RSI_CONFIRMACION_COMPRA
            and
            di_plus >= di_minus
        )

        confirmada_venta = (
            posible_venta
            and
            continuacion_venta
            and
            rsi <= RSI_CONFIRMACION_VENTA
            and
            di_minus >= di_plus
        )

        # ----------------------------------------------------
        # SCORES
        # ----------------------------------------------------

        score_compra = (
            calcular_score_compra_v4(
                estructura5,
                estructura15,
                impulso_compra,
                pullback_compra,
                continuacion_compra,
                precio,
                ema20,
                ema50,
                ema200,
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
                estructura15,
                impulso_venta,
                pullback_venta,
                continuacion_venta,
                precio,
                ema20,
                ema50,
                ema200,
                rsi,
                adx,
                di_plus,
                di_minus,
                atr,
                zona_venta
            )
        )

        # ----------------------------------------------------
        # DIAGNÓSTICO
        # ----------------------------------------------------

        print("")
        print("📋 CONDICIONES V4")
        print("-----------------------------------")

        print(
            f"🟡 Posible compra: "
            f"{posible_compra}"
        )

        print(
            f"🟡 Posible venta: "
            f"{posible_venta}"
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
            f"🚫 Entrada compra tardía: "
            f"{tardia_compra}"
        )

        print(
            f"🚫 Entrada venta tardía: "
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

        # ====================================================
        # TIEMPO DE PREALERTA
        # ====================================================

        ahora = time.time()

        if (
            estado["direccion_pendiente"]
            is not None
            and
            estado["inicio_pendiente"] > 0
        ):

            tiempo_viva = (
                ahora
                -
                estado["inicio_pendiente"]
            )

            if (
                tiempo_viva
                >=
                MINUTOS_VIDA_PREALERTA * 60
            ):

                direccion = (
                    estado[
                        "direccion_pendiente"
                    ]
                )

                identificador = (
                    estado[
                        "id_pendiente"
                    ]
                )

                limpiar_pendiente()

                if direccion == "COMPRA":

                    return {
                        "tipo": "DESCARTADA",
                        "id": identificador,
                        "mensaje": (
                            "🔴 PREALERTA COMPRA "
                            "DESCARTADA\n\n"
                            f"🆔 ID: {identificador}\n\n"
                            "⏳ Tiempo de "
                            "confirmación agotado.\n\n"
                            "El movimiento no produjo "
                            "una continuación válida "
                            f"dentro de "
                            f"{MINUTOS_VIDA_PREALERTA} "
                            "minutos."
                        )
                    }

                return {
                    "tipo": "DESCARTADA",
                    "id": identificador,
                    "mensaje": (
                        "🟢 PREALERTA VENTA "
                        "DESCARTADA\n\n"
                        f"🆔 ID: {identificador}\n\n"
                        "⏳ Tiempo de "
                        "confirmación agotado.\n\n"
                        "El movimiento no produjo "
                        "una continuación válida "
                        f"dentro de "
                        f"{MINUTOS_VIDA_PREALERTA} "
                        "minutos."
                    )
                }

        # ====================================================
        # CONFIRMACIÓN COMPRA
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "COMPRA"
            and
            confirmada_compra
            and
            score_compra
            >=
            SCORE_MIN_CONFIRMACION
        ):

            resultado = (
                crear_compra_confirmada(
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

            limpiar_pendiente()

            estado[
                "ultima_confirmacion"
            ] = ahora

            return resultado

        # ====================================================
        # CONFIRMACIÓN VENTA
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "VENTA"
            and
            confirmada_venta
            and
            score_venta
            >=
            SCORE_MIN_CONFIRMACION
        ):

            resultado = (
                crear_venta_confirmada(
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

            limpiar_pendiente()

            estado[
                "ultima_confirmacion"
            ] = ahora

            return resultado

        # ====================================================
        # COMPRA PENDIENTE
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "COMPRA"
        ):

            # -----------------------------------------------
            # DESCARTAR SOLO CON CAMBIO REALMENTE CONTRARIO
            # -----------------------------------------------

            contexto_contrario = (
                estructura5["direccion"]
                == "BAJISTA"
                and
                estructura15["direccion"]
                == "BAJISTA"
            )

            choque_fuerte = (
                estructura5["bos"]
                == "BAJISTA"
            )

            if (
                contexto_contrario
                or
                choque_fuerte
            ):

                identificador = (
                    estado["id_pendiente"]
                )

                limpiar_pendiente()

                return {
                    "tipo": "DESCARTADA",
                    "id": identificador,
                    "mensaje": (
                        "🔴 PREALERTA COMPRA "
                        "DESCARTADA\n\n"
                        f"🆔 ID: {identificador}\n\n"
                        "📉 El movimiento "
                        "alcista perdió validez.\n\n"
                        "Se detectó estructura "
                        "contraria."
                    )
                }

            # -----------------------------------------------
            # SOLO DESCARTAR TARDÍA SI REALMENTE SE ALEJÓ
            # -----------------------------------------------

            if (
                tardia_compra
                and
                continuacion_compra
            ):

                identificador = (
                    estado["id_pendiente"]
                )

                limpiar_pendiente()

                return {
                    "tipo": "DESCARTADA",
                    "id": identificador,
                    "mensaje": (
                        "🔴 PREALERTA COMPRA "
                        "DESCARTADA\n\n"
                        f"🆔 ID: {identificador}\n\n"
                        "🚫 Entrada demasiado "
                        "extendida."
                    )
                }

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "🔎 Compra V4 pendiente..."
                )
            }

        # ====================================================
        # VENTA PENDIENTE
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "VENTA"
        ):

            contexto_contrario = (
                estructura5["direccion"]
                == "ALCISTA"
                and
                estructura15["direccion"]
                == "ALCISTA"
            )

            choque_fuerte = (
                estructura5["bos"]
                == "ALCISTA"
            )

            if (
                contexto_contrario
                or
                choque_fuerte
            ):

                identificador = (
                    estado["id_pendiente"]
                )

                limpiar_pendiente()

                return {
                    "tipo": "DESCARTADA",
                    "id": identificador,
                    "mensaje": (
                        "🟢 PREALERTA VENTA "
                        "DESCARTADA\n\n"
                        f"🆔 ID: {identificador}\n\n"
                        "📈 El movimiento "
                        "bajista perdió validez.\n\n"
                        "Se detectó estructura "
                        "contraria."
                    )
                }

            if (
                tardia_venta
                and
                continuacion_venta
            ):

                identificador = (
                    estado["id_pendiente"]
                )

                limpiar_pendiente()

                return {
                    "tipo": "DESCARTADA",
                    "id": identificador,
                    "mensaje": (
                        "🟢 PREALERTA VENTA "
                        "DESCARTADA\n\n"
                        f"🆔 ID: {identificador}\n\n"
                        "🚫 Entrada demasiado "
                        "extendida."
                    )
                }

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "🔎 Venta V4 pendiente..."
                )
            }

        # ====================================================
        # NUEVA PREALERTA COMPRA
        # ====================================================

        if (
            posible_compra
            and
            score_compra
            >=
            SCORE_MIN_PREALERTA
        ):

            if (
                ahora
                -
                estado["ultima_prealerta"]
                <
                MINUTOS_REPETICION * 60
            ):

                return {
                    "tipo": "SIN_SEÑAL",
                    "mensaje": (
                        "⏳ Cooldown V4..."
                    )
                }

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
                "precio_prealerta"
            ] = precio

            estado[
                "estructura_prealerta"
            ] = estructura5[
                "direccion"
            ]

            estado[
                "extremo_impulso"
            ] = (
                impulso_compra["extremo"]
                if impulso_compra
                else None
            )

            estado[
                "zona_pullback"
            ] = (
                pullback_compra[
                    "minimo_pullback"
                ]
                if pullback_compra
                else None
            )

            estado[
                "nivel_continuacion"
            ] = zona_compra

            estado[
                "ultima_prealerta"
            ] = ahora

            return resultado

        # ====================================================
        # NUEVA PREALERTA VENTA
        # ====================================================

        if (
            posible_venta
            and
            score_venta
            >=
            SCORE_MIN_PREALERTA
        ):

            if (
                ahora
                -
                estado["ultima_prealerta"]
                <
                MINUTOS_REPETICION * 60
            ):

                return {
                    "tipo": "SIN_SEÑAL",
                    "mensaje": (
                        "⏳ Cooldown V4..."
                    )
                }

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
                "precio_prealerta"
            ] = precio

            estado[
                "estructura_prealerta"
            ] = estructura5[
                "direccion"
            ]

            estado[
                "extremo_impulso"
            ] = (
                impulso_venta["extremo"]
                if impulso_venta
                else None
            )

            estado[
                "zona_pullback"
            ] = (
                pullback_venta[
                    "maximo_pullback"
                ]
                if pullback_venta
                else None
            )

            estado[
                "nivel_continuacion"
            ] = zona_venta

            estado[
                "ultima_prealerta"
            ] = ahora

            return resultado

        # ====================================================
        # SIN SEÑAL
        # ====================================================

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": (
                "😴 Sin señal V4"
            )
        }

    except Exception as e:

        print(
            "❌ ERROR EN ANALIZADOR V4:"
        )

        print(
            str(e)
        )

        return {
            "tipo": "ERROR",
            "mensaje": (
                f"❌ Error V4:\n{str(e)}"
            )
    }
              
