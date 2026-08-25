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
# ============================================================
#
# RÉGIMEN
#    ↓
# ESTRUCTURA
#    ↓
# BOS / CHoCH
#    ↓
# IMPULSO
#    ↓
# PULLBACK
#    ↓
# LIQUIDEZ
#    ↓
# UBICACIÓN
#    ↓
# MOMENTUM
#    ↓
# CONTINUACIÓN
#    ↓
# SCORE
#    ↓
# PREALERTA
#    ↓
# CONFIRMACIÓN / DESCARTADA
#
# Las EMA / RSI / ADX son contexto.
# El núcleo es el precio.
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
# CONFIRMACIÓN
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
    estado["nivel_continuacion"] = None

    estado["swing_referencia"] = None

    estado["maximo_confirmacion"] = None
    estado["minimo_confirmacion"] = None

    estado["velas_pendiente"] = 0


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
            "close",
            "datetime"
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

    # ========================================================
    # DATOS DE VELA
    # ========================================================

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

    # ========================================================
    # RANGO MEDIO
    # ========================================================

    df["rango_medio"] = (
        df["rango"]
        .rolling(20)
        .mean()
    )

    df["expansion"] = (
        df["rango"] >
        df["rango_medio"] * 1.10
    )

    # ========================================================
    # PENDIENTE EMA
    # ========================================================

    df["pendiente_ema20"] = (
        df["ema20"] -
        df["ema20"].shift(3)
    )

    df["pendiente_ema50"] = (
        df["ema50"] -
        df["ema50"].shift(3)
    )

    # ========================================================
    # MOMENTUM RSI
    # ========================================================

    df["rsi_slope"] = (
        df["rsi"] -
        df["rsi"].shift(3)
    )

    # ========================================================
    # SEPARACIÓN DI
    # ========================================================

    df["di_separacion"] = (
        df["di_plus"] -
        df["di_minus"]
    ).abs()

    # ========================================================
    # EFICIENCIA DE MOVIMIENTO
    # ========================================================

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
        rango_total.replace(
            0,
            pd.NA
        )
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
# USAR SOLO VELAS CERRADAS
# ============================================================

def velas_cerradas(df):

    if len(df) < 5:
        return df.copy()

    # La última vela de Twelve Data puede estar
    # todavía formándose.
    return df.iloc[:-1].copy()


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

    if len(highs) >= 2:

        resultado["ultimo_high"] = highs[-1]
        resultado["prev_high"] = highs[-2]

        resultado["hh"] = (
            highs[-1]["precio"] >
            highs[-2]["precio"] +
            highs[-1]["atr"] * SWING_ATR_MIN
        )

        resultado["lh"] = (
            highs[-1]["precio"] <
            highs[-2]["precio"] -
            highs[-1]["atr"] * SWING_ATR_MIN
        )

    if len(lows) >= 2:

        resultado["ultimo_low"] = lows[-1]
        resultado["prev_low"] = lows[-2]

        resultado["hl"] = (
            lows[-1]["precio"] >
            lows[-2]["precio"] +
            lows[-1]["atr"] * SWING_ATR_MIN
        )

        resultado["ll"] = (
            lows[-1]["precio"] <
            lows[-2]["precio"] -
            lows[-1]["atr"] * SWING_ATR_MIN
        )

    # ========================================================
    # ESTRUCTURA
    # ========================================================

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

        # Movimiento reciente como contexto,
        # no como estructura completa.

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

            if desplazamiento > atr * 0.50:

                resultado["direccion"] = "ALCISTA"
                resultado["fuerza"] = 1

            elif desplazamiento < -atr * 0.50:

                resultado["direccion"] = "BAJISTA"
                resultado["fuerza"] = 1

    # ========================================================
    # BOS
    # ========================================================

    precio_actual = float(
        df.iloc[-1]["close"]
    )

    if (
        resultado["ultimo_high"] is not None
        and
        precio_actual >
        resultado["ultimo_high"]["precio"] +
        float(df.iloc[-1]["atr"]) *
        BREAK_BUFFER_ATR
    ):

        resultado["bos"] = "ALCISTA"

    elif (
        resultado["ultimo_low"] is not None
        and
        precio_actual <
        resultado["ultimo_low"]["precio"] -
        float(df.iloc[-1]["atr"]) *
        BREAK_BUFFER_ATR
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
# RÉGIMEN DEL MERCADO
# ============================================================

def detectar_regimen(df):

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

    rango20 = float(
        df["high"].iloc[-20:].max()
        -
        df["low"].iloc[-20:].min()
    )

    atr = float(actual["atr"])

    if atr <= 0:
        return "LATERAL"

    rango_atr = rango20 / atr

    # Tendencia alcista
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

    # Tendencia bajista
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

    # Mercado muy comprimido
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

    direccion = estructura15[
        "direccion"
    ]

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

    if len(df) < IMPULSO_VELAS + 5:
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

    avance = (
        float(ventana.iloc[-1]["close"])
        -
        inicio
    )

    avance_atr = (
        avance /
        atr
    )

    eficiencia = float(
        ventana["eficiencia"].mean()
    )

    cuerpos = (
        ventana["cuerpo"].sum()
    )

    rangos = (
        ventana["rango"].sum()
    )

    ratio_cuerpo = (
        cuerpos /
        rangos
        if rangos > 0
        else 0
    )

    calidad = 0

    if desplazamiento_atr >= IMPULSO_ATR_MIN:
        calidad += 1

    if desplazamiento_atr >= IMPULSO_FUERTE_ATR:
        calidad += 1

    if velas_alcistas >= IMPULSO_VELAS_MIN:
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

    if len(df) < IMPULSO_VELAS + 5:
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

    avance = (
        inicio -
        float(ventana.iloc[-1]["close"])
    )

    avance_atr = (
        avance /
        atr
    )

    eficiencia = float(
        ventana["eficiencia"].mean()
    )

    cuerpos = (
        ventana["cuerpo"].sum()
    )

    rangos = (
        ventana["rango"].sum()
    )

    ratio_cuerpo = (
        cuerpos /
        rangos
        if rangos > 0
        else 0
    )

    calidad = 0

    if desplazamiento_atr >= IMPULSO_ATR_MIN:
        calidad += 1

    if desplazamiento_atr >= IMPULSO_FUERTE_ATR:
        calidad += 1

    if velas_bajistas >= IMPULSO_VELAS_MIN:
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

    rango_impulso = (
        extremo -
        inicio
    )

    if rango_impulso <= 0:
        return None

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

    retracement = (
        retroceso /
        rango_impulso
    )

    # No debe destruir el impulso.
    estructura_valida = (
        minimo >
        inicio -
        atr * 0.35
    )

    # El pullback no debe ser demasiado profundo.
    retroceso_valido = (
        PULLBACK_MIN_RETRACEMENT
        <=
        retracement
        <=
        PULLBACK_MAX_RETRACEMENT
    )

    # Debe existir retroceso real.
    distancia_valida = (
        PULLBACK_MIN_ATR
        <=
        retroceso_atr
        <=
        PULLBACK_MAX_ATR
    )

    # No queremos una secuencia de caída demasiado agresiva.
    velas_bajistas = int(
        (
            ventana["direccion_vela"]
            == -1
        ).sum()
    )

    pullback_sano = (
        velas_bajistas <= 4
    )

    if not (
        estructura_valida
        and
        retroceso_valido
        and
        distancia_valida
        and
        pullback_sano
    ):
        return None

    nivel_continuacion = (
        extremo +
        atr * BREAK_BUFFER_ATR
    )

    return {

        "direccion":
            "ALCISTA",

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

        "retracement":
            retracement,

        "nivel_continuacion":
            nivel_continuacion,

        "precio_actual":
            precio
    }


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

    rango_impulso = (
        inicio -
        extremo
    )

    if rango_impulso <= 0:
        return None

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

    retracement = (
        retroceso /
        rango_impulso
    )

    estructura_valida = (
        maximo <
        inicio +
        atr * 0.35
    )

    retroceso_valido = (
        PULLBACK_MIN_RETRACEMENT
        <=
        retracement
        <=
        PULLBACK_MAX_RETRACEMENT
    )

    distancia_valida = (
        PULLBACK_MIN_ATR
        <=
        retroceso_atr
        <=
        PULLBACK_MAX_ATR
    )

    velas_alcistas = int(
        (
            ventana["direccion_vela"]
            == 1
        ).sum()
    )

    pullback_sano = (
        velas_alcistas <= 4
    )

    if not (
        estructura_valida
        and
        retroceso_valido
        and
        distancia_valida
        and
        pullback_sano
    ):
        return None

    nivel_continuacion = (
        extremo -
        atr * BREAK_BUFFER_ATR
    )

    return {

        "direccion":
            "BAJISTA",

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

        "retracement":
            retracement,

        "nivel_continuacion":
            nivel_continuacion,

        "precio_actual":
            precio
    }


# ============================================================
# ZONAS DE LIQUIDEZ
# ============================================================

def detectar_liquidez(df):

    atr = float(
        df.iloc[-1]["atr"]
    )

    if atr <= 0:
        return {
            "sweep_alcista": False,
            "sweep_bajista": False,
            "maximo": None,
            "minimo": None
        }

    ventana = df.iloc[
        -LIQUIDEZ_LOOKBACK:-1
    ]

    maximo_previo = float(
        ventana["high"].max()
    )

    minimo_previo = float(
        ventana["low"].min()
    )

    actual = df.iloc[-1]

    high = float(
        actual["high"]
    )

    low = float(
        actual["low"]
    )

    close = float(
        actual["close"]
    )

    # ========================================================
    # SWEEP DE LIQUIDEZ DE VENTA
    #
    # Rompe mínimo anterior y recupera.
    # Puede señalar rechazo bajista fallido.
    # ========================================================

    sweep_alcista = (
        low <
        minimo_previo -
        atr * LIQUIDEZ_BUFFER_ATR
        and
        close >
        minimo_previo
    )

    # ========================================================
    # SWEEP DE LIQUIDEZ DE COMPRA
    #
    # Rompe máximo anterior y cierra debajo.
    # ========================================================

    sweep_bajista = (
        high >
        maximo_previo +
        atr * LIQUIDEZ_BUFFER_ATR
        and
        close <
        maximo_previo
    )

    return {

        "sweep_alcista":
            sweep_alcista,

        "sweep_bajista":
            sweep_bajista,

        "maximo":
            maximo_previo,

        "minimo":
            minimo_previo
    }


# ============================================================
# SOPORTE / RESISTENCIA
# ============================================================

def obtener_zonas_sr(
    df,
    estructura
):

    soportes = []
    resistencias = []

    if estructura["ultimo_low"]:

        soportes.append(
            estructura["ultimo_low"]["precio"]
        )

    if estructura["prev_low"]:

        soportes.append(
            estructura["prev_low"]["precio"]
        )

    if estructura["ultimo_high"]:

        resistencias.append(
            estructura["ultimo_high"]["precio"]
        )

    if estructura["prev_high"]:

        resistencias.append(
            estructura["prev_high"]["precio"]
        )

    ventana = df.iloc[-30:]

    soportes.append(
        float(ventana["low"].min())
    )

    resistencias.append(
        float(ventana["high"].max())
    )

    return {
        "soportes": soportes,
        "resistencias": resistencias
    }


# ============================================================
# UBICACIÓN
# ============================================================

def evaluar_ubicacion(
    precio,
    atr,
    direccion,
    zonas
):

    if atr <= 0:
        return {
            "buena": False,
            "distancia_atr": None,
            "zona": None
        }

    if direccion == "ALCISTA":

        candidatos = zonas[
            "soportes"
        ]

        if not candidatos:
            return {
                "buena": False,
                "distancia_atr": None,
                "zona": None
            }

        zona = min(
            candidatos,
            key=lambda x:
            abs(precio - x)
        )

        distancia = (
            precio -
            zona
        )

        distancia_atr = (
            distancia /
            atr
        )

        buena = (
            0 <=
            distancia_atr
            <=
            ZONA_MAX_ATR
        )

        return {
            "buena": buena,
            "distancia_atr": distancia_atr,
            "zona": zona
        }

    if direccion == "BAJISTA":

        candidatos = zonas[
            "resistencias"
        ]

        if not candidatos:
            return {
                "buena": False,
                "distancia_atr": None,
                "zona": None
            }

        zona = min(
            candidatos,
            key=lambda x:
            abs(precio - x)
        )

        distancia = (
            zona -
            precio
        )

        distancia_atr = (
            distancia /
            atr
        )

        buena = (
            0 <=
            distancia_atr
            <=
            ZONA_MAX_ATR
        )

        return {
            "buena": buena,
            "distancia_atr": distancia_atr,
            "zona": zona
        }

    return {
        "buena": False,
        "distancia_atr": None,
        "zona": None
    }


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

    rango = float(
        actual["rango"]
    )

    if atr <= 0 or rango <= 0:
        return False, None

    nivel = float(
        pullback[
            "nivel_continuacion"
        ]
    )

    maximo_previo = float(
        df.iloc[-4:-1]["high"].max()
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

    cierre_fuerte = (
        (precio - actual["low"])
        /
        rango
        >=
        0.65
    )

    ruptura = (
        precio >
        nivel
    )

    ruptura_reciente = (
        precio >
        maximo_previo +
        atr * BREAK_BUFFER_ATR
    )

    confirmacion = (
        vela_alcista
        and
        cuerpo_fuerte
        and
        cierre_fuerte
        and
        (
            ruptura
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

    rango = float(
        actual["rango"]
    )

    if atr <= 0 or rango <= 0:
        return False, None

    nivel = float(
        pullback[
            "nivel_continuacion"
        ]
    )

    minimo_previo = float(
        df.iloc[-4:-1]["low"].min()
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

    cierre_fuerte = (
        (actual["high"] - precio)
        /
        rango
        >=
        0.65
    )

    ruptura = (
        precio <
        nivel
    )

    ruptura_reciente = (
        precio <
        minimo_previo -
        atr * BREAK_BUFFER_ATR
    )

    confirmacion = (
        vela_bajista
        and
        cuerpo_fuerte
        and
        cierre_fuerte
        and
        (
            ruptura
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

    if zona is None or atr <= 0:
        return True

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

    if zona is None or atr <= 0:
        return True

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
# CALIDAD DE MOMENTUM
# ============================================================

def evaluar_momentum_compra(
    actual
):

    rsi = float(
        actual["rsi"]
    )

    rsi_slope = float(
        actual["rsi_slope"]
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

    calidad = 0

    if rsi >= RSI_COMPRA_MIN:
        calidad += 1

    if rsi >= RSI_CONFIRMACION_COMPRA:
        calidad += 1

    if rsi_slope > 0:
        calidad += 1

    if adx >= ADX_MINIMO:
        calidad += 1

    if adx >= ADX_FUERTE:
        calidad += 1

    if di_plus > di_minus:
        calidad += 1

    if pendiente20 > 0:
        calidad += 1

    return calidad


def evaluar_momentum_venta(
    actual
):

    rsi = float(
        actual["rsi"]
    )

    rsi_slope = float(
        actual["rsi_slope"]
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

    calidad = 0

    if rsi <= RSI_VENTA_MAX:
        calidad += 1

    if rsi <= RSI_CONFIRMACION_VENTA:
        calidad += 1

    if rsi_slope < 0:
        calidad += 1

    if adx >= ADX_MINIMO:
        calidad += 1

    if adx >= ADX_FUERTE:
        calidad += 1

    if di_minus > di_plus:
        calidad += 1

    if pendiente20 < 0:
        calidad += 1

    return calidad


# ============================================================
# SCORE COMPRA
# ============================================================

def calcular_score_compra_v4(
    estructura,
    contexto15,
    regimen5,
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

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    if estructura["direccion"] == "ALCISTA":
        score += 18

    if estructura["hh"]:
        score += 6

    if estructura["hl"]:
        score += 6

    if estructura["bos"] == "ALCISTA":
        score += 10

    if estructura["choch"]:
        score -= 10

    # --------------------------------------------------------
    # RÉGIMEN
    # --------------------------------------------------------

    if regimen5 == "ALCISTA":
        score += 8

    elif regimen5 == "LATERAL":
        score -= 8

    elif regimen5 == "BAJISTA":
        score -= 10

    # --------------------------------------------------------
    # 15M
    # --------------------------------------------------------

    if contexto15 == "ALCISTA":
        score += 8

    elif contexto15 == "NEUTRAL":
        score += 2

    elif contexto15 == "BAJISTA":
        score -= 8

    # --------------------------------------------------------
    # IMPULSO
    # --------------------------------------------------------

    if impulso:

        score += 10

        if impulso["calidad"] >= 5:
            score += 4

        if impulso["desplazamiento_atr"] >= 1.20:
            score += 3

    # --------------------------------------------------------
    # PULLBACK
    # --------------------------------------------------------

    if pullback:

        score += 10

        if (
            0.25 <=
            pullback["retracement"]
            <= 0.65
        ):
            score += 4

    # --------------------------------------------------------
    # CONTINUACIÓN
    # --------------------------------------------------------

    if continuacion:
        score += 15

    # --------------------------------------------------------
    # LIQUIDEZ
    # --------------------------------------------------------

    if liquidez["sweep_alcista"]:
        score += 5

    if liquidez["sweep_bajista"]:
        score -= 5

    # --------------------------------------------------------
    # UBICACIÓN
    # --------------------------------------------------------

    if ubicacion["buena"]:
        score += 5

    else:
        score -= 4

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    score += momentum * 2

    # --------------------------------------------------------
    # INDICADORES SECUNDARIOS
    # --------------------------------------------------------

    if di_plus > di_minus:
        score += 3

    if adx >= 25:
        score += 3

    if rsi >= RSI_CONFIRMACION_COMPRA:
        score += 2

    if ema20 > ema50:
        score += 2

    if precio > ema20:
        score += 2

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
    regimen5,
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

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    if estructura["direccion"] == "BAJISTA":
        score += 18

    if estructura["lh"]:
        score += 6

    if estructura["ll"]:
        score += 6

    if estructura["bos"] == "BAJISTA":
        score += 10

    if estructura["choch"]:
        score -= 10

    # --------------------------------------------------------
    # RÉGIMEN
    # --------------------------------------------------------

    if regimen5 == "BAJISTA":
        score += 8

    elif regimen5 == "LATERAL":
        score -= 8

    elif regimen5 == "ALCISTA":
        score -= 10

    # --------------------------------------------------------
    # 15M
    # --------------------------------------------------------

    if contexto15 == "BAJISTA":
        score += 8

    elif contexto15 == "NEUTRAL":
        score += 2

    elif contexto15 == "ALCISTA":
        score -= 8

    # --------------------------------------------------------
    # IMPULSO
    # --------------------------------------------------------

    if impulso:

        score += 10

        if impulso["calidad"] >= 5:
            score += 4

        if impulso["desplazamiento_atr"] >= 1.20:
            score += 3

    # --------------------------------------------------------
    # PULLBACK
    # --------------------------------------------------------

    if pullback:

        score += 10

        if (
            0.25 <=
            pullback["retracement"]
            <= 0.65
        ):
            score += 4

    # --------------------------------------------------------
    # CONTINUACIÓN
    # --------------------------------------------------------

    if continuacion:
        score += 15

    # --------------------------------------------------------
    # LIQUIDEZ
    # --------------------------------------------------------

    if liquidez["sweep_bajista"]:
        score += 5

    if liquidez["sweep_alcista"]:
        score -= 5

    # --------------------------------------------------------
    # UBICACIÓN
    # --------------------------------------------------------

    if ubicacion["buena"]:
        score += 5

    else:
        score -= 4

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    score += momentum * 2

    # --------------------------------------------------------
    # INDICADORES SECUNDARIOS
    # --------------------------------------------------------

    if di_minus > di_plus:
        score += 3

    if adx >= 25:
        score += 3

    if rsi <= RSI_CONFIRMACION_VENTA:
        score += 2

    if ema20 < ema50:
        score += 2

    if precio < ema20:
        score += 2

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
    ema50,
    regimen5,
    contexto15
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
🥇 XAU SNIPER AI V4.1

ID: {identificador}

🟡 PREALERTA COMPRA

⚠️ MOVIMIENTO EN FORMACIÓN

⭐ Score: {score}/100

🏗️ Estructura:
{estructura["direccion"]}

🌐 Régimen 5M:
{regimen5}

🕐 Contexto 15M:
{contexto15}

🚀 Impulso:
DETECTADO

🔄 Pullback:
DETECTADO

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
Estructura → impulso → pullback

⏳ Esperando ruptura y continuación...

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
    ema50,
    regimen5,
    contexto15
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
🥇 XAU SNIPER AI V4.1

ID: {identificador}

🟡 PREALERTA VENTA

⚠️ MOVIMIENTO EN FORMACIÓN

⭐ Score: {score}/100

🏗️ Estructura:
{estructura["direccion"]}

🌐 Régimen 5M:
{regimen5}

🕐 Contexto 15M:
{contexto15}

🚀 Impulso:
DETECTADO

🔄 Pullback:
DETECTADO

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
Estructura → impulso → pullback

⏳ Esperando ruptura y continuación...

⏱️ Tiempo máximo:
{MINUTOS_VIDA_PREALERTA} minutos
""".strip()

    return {
        "tipo": "POSIBLE_VENTA",
        "mensaje": mensaje,
        "id": identificador
    }


# ============================================================
# COMPRA CONFIRMADA
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
        uuid.uuid4().hex[:6]
    )

    mensaje = f"""
🥇 XAU SNIPER AI V4.1

ID: {identificador}

🟢 COMPRA CONFIRMADA

⭐ Score: {score}/100

🚀 Impulso: DETECTADO
🔄 Pullback: CONFIRMADO
💥 Continuación: CONFIRMADA

📋 ENTRADA

Precio:
{entrada:.2f}

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

🧠 V4.1:
Estructura → impulso → pullback → ruptura

✅ Entrada confirmada
""".strip()

    return {
        "tipo": "COMPRA",
        "mensaje": mensaje,
        "id": identificador
    }


# ============================================================
# VENTA CONFIRMADA
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
        uuid.uuid4().hex[:6]
    )

    mensaje = f"""
🥇 XAU SNIPER AI V4.1

ID: {identificador}

🔴 VENTA CONFIRMADA

⭐ Score: {score}/100

🚀 Impulso: DETECTADO
🔄 Pullback: CONFIRMADO
💥 Continuación: CONFIRMADA

📋 ENTRADA

Precio:
{entrada:.2f}

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

🧠 V4.1:
Estructura → impulso → pullback → ruptura

✅ Entrada confirmada
""".strip()

    return {
        "tipo": "VENTA",
        "mensaje": mensaje,
        "id": identificador
    }


# ============================================================
# DESCARTADA
# ============================================================

def crear_descartada(
    direccion,
    razon
):

    identificador = (
        estado["id_pendiente"]
        or
        "------"
    )

    if direccion == "COMPRA":

        emoji = "🔴"
        texto = "PREALERTA COMPRA"

    else:

        emoji = "🟢"
        texto = "PREALERTA VENTA"

    mensaje = f"""
{emoji} {texto} DESCARTADA

🆔 ID:
{identificador}

❌ Motivo:
{razon}

⏱️ La señal salió de seguimiento.
No hubo confirmación válida.
""".strip()

    limpiar_pendiente()

    estado[
        "ultima_descartada"
    ] = time.time()

    return {
        "tipo": "DESCARTADA",
        "mensaje": mensaje,
        "id": identificador
    }


# ============================================================
# EXPIRACIÓN OBLIGATORIA
# ============================================================

def comprobar_expiracion(ahora):

    if (
        estado["direccion_pendiente"]
        is None
    ):
        return None

    inicio = float(
        estado["inicio_pendiente"]
    )

    if inicio <= 0:

        return crear_descartada(
            estado[
                "direccion_pendiente"
            ],
            "⚠️ Estado inválido. "
            "Se reinició el temporizador."
        )

    segundos = (
        ahora -
        inicio
    )

    limite = (
        MINUTOS_VIDA_PREALERTA *
        60
    )

    print(
        f"⏱️ Tiempo prealerta: "
        f"{segundos / 60:.1f}/"
        f"{MINUTOS_VIDA_PREALERTA} min"
    )

    if segundos >= limite:

        return crear_descartada(

            estado[
                "direccion_pendiente"
            ],

            "⏳ Se agotaron los "
            f"{MINUTOS_VIDA_PREALERTA} minutos "
            "sin una continuación válida."
        )

    return None


# ============================================================
# ANALIZAR V4.1
# ============================================================

def analizar():

    try:

        print("")
        print("===================================")
        print("🔍 ANALIZANDO XAU/USD...")
        print("===================================")

        ahora = time.time()

        # ====================================================
        # 1. EXPIRACIÓN PRIMERO
        #
        # ESTO ES IMPORTANTE.
        #
        # Antes de crear otra señal, antes de devolver
        # SIN_SEÑAL y antes de cualquier otra cosa,
        # se comprueba si la prealerta ya murió.
        # ====================================================

        expiracion = comprobar_expiracion(
            ahora
        )

        if expiracion is not None:

            print(
                "🔴 PREALERTA DESCARTADA "
                "POR TIEMPO"
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
                "Datos 5M insuficientes"
            )

        if len(df15) < 100:

            raise Exception(
                "Datos 15M insuficientes"
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
        # SOPORTES / RESISTENCIAS
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
        # SI HAY PREALERTA, CONGELAMOS SU NIVEL
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "COMPRA"
            and
            estado["nivel_continuacion"]
            is not None
        ):

            zona_compra = (
                estado[
                    "nivel_continuacion"
                ]
            )

        if (
            estado["direccion_pendiente"]
            == "VENTA"
            and
            estado["nivel_continuacion"]
            is not None
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
        # SI HAY PREALERTA ACTIVA
        # ====================================================

        if (
            estado["direccion_pendiente"]
            is not None
        ):

            estado[
                "velas_pendiente"
            ] += 1

            # =================================================
            # COMPRA PENDIENTE
            # =================================================

            if (
                estado["direccion_pendiente"]
                == "COMPRA"
            ):

                # Cambio estructural fuerte
                if (
                    estructura5["choch"]
                    and
                    estructura5["direccion"]
                    == "BAJISTA"
                ):

                    return crear_descartada(
                        "COMPRA",

                        "📉 CHoCH bajista detectado. "
                        "La estructura dejó de favorecer "
                        "la continuación alcista."
                    )

                # Régimen claramente contrario
                if (
                    regimen5 == "BAJISTA"
                    and
                    contexto15 == "BAJISTA"
                ):

                    return crear_descartada(
                        "COMPRA",

                        "📉 Régimen 5M y contexto 15M "
                        "pasaron a bajista."
                    )

                # Pullback destruido
                if (
                    estado[
                        "impulso_inicio"
                    ] is not None
                    and
                    precio <
                    estado[
                        "impulso_inicio"
                    ] -
                    atr * 0.35
                ):

                    return crear_descartada(
                        "COMPRA",

                        "❌ El precio rompió la base "
                        "del impulso alcista."
                    )

                # =================================================
                # CONFIRMACIÓN
                # =================================================

                if (
                    continuacion_compra
                    and
                    score_compra
                    >=
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
                    "⏳ COMPRA PENDIENTE..."
                )

                return {
                    "tipo":
                        "SIN_SEÑAL",

                    "mensaje":
                        "🔎 Compra pendiente. "
                        "Esperando ruptura confirmada."
                }

            # =================================================
            # VENTA PENDIENTE
            # =================================================

            if (
                estado["direccion_pendiente"]
                == "VENTA"
            ):

                if (
                    estructura5["choch"]
                    and
                    estructura5["direccion"]
                    == "ALCISTA"
                ):

                    return crear_descartada(
                        "VENTA",

                        "📈 CHoCH alcista detectado. "
                        "La estructura dejó de favorecer "
                        "la continuación bajista."
                    )

                if (
                    regimen5 == "ALCISTA"
                    and
                    contexto15 == "ALCISTA"
                ):

                    return crear_descartada(
                        "VENTA",

                        "📈 Régimen 5M y contexto 15M "
                        "pasaron a alcista."
                    )

                if (
                    estado[
                        "impulso_inicio"
                    ] is not None
                    and
                    precio >
                    estado[
                        "impulso_inicio"
                    ] +
                    atr * 0.35
                ):

                    return crear_descartada(
                        "VENTA",

                        "❌ El precio rompió la base "
                        "del impulso bajista."
                    )

                # =================================================
                # CONFIRMACIÓN
                # =================================================

                if (
                    continuacion_venta
                    and
                    score_venta
                    >=
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
                    "⏳ VENTA PENDIENTE..."
                )

                return {
                    "tipo":
                        "SIN_SEÑAL",

                    "mensaje":
                        "🔎 Venta pendiente. "
                        "Esperando ruptura confirmada."
                }

        # ====================================================
        # NUEVA PREALERTA COMPRA
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

            score_compra
            >=
            SCORE_MIN_PREALERTA
        )

        # ====================================================
        # NUEVA PREALERTA VENTA
        # ====================================================

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

            score_venta
            >=
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
                    "😴 Cooldown después de "
                    "señal descartada."
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
        print(
            "❌ ERROR EN ANALIZAR:"
        )

        print(
            repr(e)
        )

        return {
            "tipo":
                "ERROR",

            "mensaje":
                f"❌ Error V4.1:\n{e}"
        }
