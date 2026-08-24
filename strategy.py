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
# MOTOR DE ESTRUCTURA + MOVIMIENTO + LIQUIDEZ
# ============================================================

API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"

INTERVALO_5M = "5min"
INTERVALO_15M = "15min"


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

MINUTOS_REPETICION = 15

ADX_MINIMO = 15

ATR_SL = 1.30
ATR_TP = 2.20

SCORE_MIN_PREALERTA = 55
SCORE_MIN_CONFIRMACION = 70


# ============================================================
# ESTRUCTURA
# ============================================================

SWING_LEFT = 2
SWING_RIGHT = 2

SWING_ATR_MIN = 0.25


# ============================================================
# IMPULSO
# ============================================================

IMPULSO_ATR_MIN = 1.0
IMPULSO_ATR_FUERTE = 1.5

IMPULSO_VELAS = 8
IMPULSO_MIN_VELAS_DIRECCION = 3


# ============================================================
# PULLBACK
# ============================================================

PULLBACK_MIN_ATR = 0.30
PULLBACK_MAX_ATR = 1.80


# ============================================================
# CONTINUACIÓN
# ============================================================

CONTINUACION_ATR_MIN = 0.10


# ============================================================
# ANTI-ENTRADA TARDÍA
# ============================================================

MAX_DISTANCIA_ENTRADA_ATR = 1.20


# ============================================================
# ESTADO
# ============================================================

estado = {
    "direccion_pendiente": None,
    "id_pendiente": None,

    "ultima_prealerta": 0,
    "ultima_confirmacion": 0,

    "estructura": None,
    "impulso": None,
    "zona_pullback": None,
    "nivel_continuacion": None,
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
        "https://api.twelvedata.com/time_series"
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
    # RANGO MEDIO
    # --------------------------------------------------------

    df["rango_medio"] = (
        df["rango"]
        .rolling(20)
        .mean()
    )

    df["expansion"] = (
        df["rango"]
        >
        df["rango_medio"] * 1.15
    )

    # --------------------------------------------------------
    # VELOCIDAD DEL PRECIO
    # --------------------------------------------------------

    df["cambio_1"] = (
        df["close"]
        .diff()
    )

    df["cambio_3"] = (
        df["close"]
        .diff(3)
    )

    df = df.dropna().reset_index(
        drop=True
    )

    print(
        f"📊 Velas útiles: {len(df)}"
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

    if final <= inicio:
        return highs, lows

    atr_actual = float(
        df.iloc[-1]["atr"]
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

        if len(altos_der) < SWING_RIGHT:
            continue

        if len(bajos_der) < SWING_RIGHT:
            continue

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

        # ----------------------------------------------------
        # FILTRO DE SEPARACIÓN
        # ----------------------------------------------------

        if es_high:

            if (
                not highs
                or
                abs(
                    high_actual
                    -
                    highs[-1]["precio"]
                )
                >= atr_actual * SWING_ATR_MIN
            ):

                highs.append({
                    "index": i,
                    "precio": high_actual
                })

        if es_low:

            if (
                not lows
                or
                abs(
                    low_actual
                    -
                    lows[-1]["precio"]
                )
                >= atr_actual * SWING_ATR_MIN
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
    # SWINGS HIGH
    # --------------------------------------------------------

    if len(highs) >= 1:

        resultado["ultimo_high"] = (
            highs[-1]
        )

    if len(highs) >= 2:

        resultado["prev_high"] = (
            highs[-2]
        )

    # --------------------------------------------------------
    # SWINGS LOW
    # --------------------------------------------------------

    if len(lows) >= 1:

        resultado["ultimo_low"] = (
            lows[-1]
        )

    if len(lows) >= 2:

        resultado["prev_low"] = (
            lows[-2]
        )

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

    precio_actual = float(
        df.iloc[-1]["close"]
    )

    # --------------------------------------------------------
    # BOS
    # --------------------------------------------------------

    if (
        resultado["ultimo_high"]
        is not None
        and
        precio_actual
        >
        resultado["ultimo_high"]["precio"]
    ):

        resultado["bos"] = "ALCISTA"

    elif (
        resultado["ultimo_low"]
        is not None
        and
        precio_actual
        <
        resultado["ultimo_low"]["precio"]
    ):

        resultado["bos"] = "BAJISTA"

    # --------------------------------------------------------
    # DIRECCIÓN
    # --------------------------------------------------------

    if (
        resultado["hh"]
        and
        resultado["hl"]
    ):

        resultado["direccion"] = "ALCISTA"

    elif (
        resultado["lh"]
        and
        resultado["ll"]
    ):

        resultado["direccion"] = "BAJISTA"

    elif (
        resultado["bos"]
        == "ALCISTA"
    ):

        resultado["direccion"] = "ALCISTA"

    elif (
        resultado["bos"]
        == "BAJISTA"
    ):

        resultado["direccion"] = "BAJISTA"

    else:

        # ----------------------------------------------------
        # ESTRUCTURA PARCIAL
        #
        # Esto evita que 5M se quede NEUTRAL demasiado fácil.
        # ----------------------------------------------------

        if resultado["hh"] and not resultado["ll"]:

            resultado["direccion"] = "ALCISTA"

        elif resultado["hl"] and not resultado["lh"]:

            resultado["direccion"] = "ALCISTA"

        elif resultado["lh"] and not resultado["hl"]:

            resultado["direccion"] = "BAJISTA"

        elif resultado["ll"] and not resultado["hh"]:

            resultado["direccion"] = "BAJISTA"

    # --------------------------------------------------------
    # FUERZA ESTRUCTURAL
    # --------------------------------------------------------

    fuerza = 0

    if resultado["hh"]:
        fuerza += 1

    if resultado["hl"]:
        fuerza += 1

    if resultado["lh"]:
        fuerza -= 1

    if resultado["ll"]:
        fuerza -= 1

    if resultado["bos"] == "ALCISTA":
        fuerza += 2

    if resultado["bos"] == "BAJISTA":
        fuerza -= 2

    resultado["fuerza"] = fuerza

    # --------------------------------------------------------
    # CHoCH
    # --------------------------------------------------------

    if (
        resultado["direccion"]
        == "ALCISTA"
        and
        resultado["ll"]
    ):

        resultado["choch"] = True

    if (
        resultado["direccion"]
        == "BAJISTA"
        and
        resultado["hh"]
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

    maximo = float(
        ventana["high"].max()
    )

    desplazamiento = (
        maximo - inicio
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

    desplazamiento_atr = (
        desplazamiento / atr
    )

    if (
        desplazamiento_atr
        >= IMPULSO_ATR_MIN
        and
        velas_alcistas
        >= IMPULSO_MIN_VELAS_DIRECCION
    ):

        indice_extremo = (
            ventana["high"].idxmax()
        )

        return {
            "direccion": "ALCISTA",
            "inicio": inicio,
            "extremo": maximo,
            "indice_extremo": int(
                indice_extremo
            ),
            "desplazamiento": desplazamiento,
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

    minimo = float(
        ventana["low"].min()
    )

    desplazamiento = (
        inicio - minimo
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

    desplazamiento_atr = (
        desplazamiento / atr
    )

    if (
        desplazamiento_atr
        >= IMPULSO_ATR_MIN
        and
        velas_bajistas
        >= IMPULSO_MIN_VELAS_DIRECCION
    ):

        indice_extremo = (
            ventana["low"].idxmin()
        )

        return {
            "direccion": "BAJISTA",
            "inicio": inicio,
            "extremo": minimo,
            "indice_extremo": int(
                indice_extremo
            ),
            "desplazamiento": desplazamiento,
            "desplazamiento_atr":
                desplazamiento_atr,
            "velas_bajistas":
                velas_bajistas,
            "expansion":
                expansion
        }

    return None


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

    extremo = impulso["extremo"]

    indice_extremo = (
        impulso["indice_extremo"]
    )

    # Buscamos retroceso después
    # del máximo del impulso.

    posteriores = df[
        df.index > indice_extremo
    ]

    if posteriores.empty:
        return None

    posteriores = posteriores.tail(5)

    minimo_reciente = float(
        posteriores["low"].min()
    )

    retroceso = (
        extremo
        -
        minimo_reciente
    )

    retroceso_atr = (
        retroceso / atr
    )

    if (
        retroceso_atr
        >= PULLBACK_MIN_ATR
        and
        retroceso_atr
        <= PULLBACK_MAX_ATR
    ):

        indice_pullback = int(
            posteriores["low"].idxmin()
        )

        return {
            "direccion": "ALCISTA",
            "extremo_impulso":
                extremo,
            "minimo_pullback":
                minimo_reciente,
            "indice_pullback":
                indice_pullback,
            "retroceso":
                retroceso,
            "retroceso_atr":
                retroceso_atr
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

    extremo = impulso["extremo"]

    indice_extremo = (
        impulso["indice_extremo"]
    )

    posteriores = df[
        df.index > indice_extremo
    ]

    if posteriores.empty:
        return None

    posteriores = posteriores.tail(5)

    maximo_reciente = float(
        posteriores["high"].max()
    )

    retroceso = (
        maximo_reciente
        -
        extremo
    )

    retroceso_atr = (
        retroceso / atr
    )

    if (
        retroceso_atr
        >= PULLBACK_MIN_ATR
        and
        retroceso_atr
        <= PULLBACK_MAX_ATR
    ):

        indice_pullback = int(
            posteriores["high"].idxmax()
        )

        return {
            "direccion": "BAJISTA",
            "extremo_impulso":
                extremo,
            "maximo_pullback":
                maximo_reciente,
            "indice_pullback":
                indice_pullback,
            "retroceso":
                retroceso,
            "retroceso_atr":
                retroceso_atr
        }

    return None


# ============================================================
# CONTINUACIÓN ALCISTA
# ============================================================

def detectar_continuacion_alcista(
    df,
    impulso,
    pullback
):

    if (
        impulso is None
        or
        pullback is None
    ):

        return False, None

    atr = float(
        df.iloc[-1]["atr"]
    )

    if atr <= 0:
        return False, None

    nivel = float(
        impulso["extremo"]
    )

    precio = float(
        df.iloc[-1]["close"]
    )

    apertura = float(
        df.iloc[-1]["open"]
    )

    # --------------------------------------------------------
    # RUPTURA DEL MÁXIMO DEL IMPULSO
    # --------------------------------------------------------

    ruptura = (
        precio
        >
        nivel + atr * CONTINUACION_ATR_MIN
    )

    # --------------------------------------------------------
    # FUERZA DE LA VELA
    # --------------------------------------------------------

    fuerza = (
        precio > apertura
    )

    # --------------------------------------------------------
    # DISTANCIA
    # --------------------------------------------------------

    distancia = (
        precio - nivel
    )

    distancia_atr = (
        distancia / atr
    )

    confirmada = (
        ruptura
        and
        fuerza
        and
        distancia_atr
        >= CONTINUACION_ATR_MIN
    )

    return confirmada, nivel


# ============================================================
# CONTINUACIÓN BAJISTA
# ============================================================

def detectar_continuacion_bajista(
    df,
    impulso,
    pullback
):

    if (
        impulso is None
        or
        pullback is None
    ):

        return False, None

    atr = float(
        df.iloc[-1]["atr"]
    )

    if atr <= 0:
        return False, None

    nivel = float(
        impulso["extremo"]
    )

    precio = float(
        df.iloc[-1]["close"]
    )

    apertura = float(
        df.iloc[-1]["open"]
    )

    ruptura = (
        precio
        <
        nivel - atr * CONTINUACION_ATR_MIN
    )

    fuerza = (
        precio < apertura
    )

    distancia = (
        nivel - precio
    )

    distancia_atr = (
        distancia / atr
    )

    confirmada = (
        ruptura
        and
        fuerza
        and
        distancia_atr
        >= CONTINUACION_ATR_MIN
    )

    return confirmada, nivel


# ============================================================
# ENTRADA TARDÍA COMPRA
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
        precio - zona
    )

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

    if (
        zona is None
        or
        atr <= 0
    ):

        return False

    distancia = (
        zona - precio
    )

    distancia_atr = (
        distancia / atr
    )

    return (
        distancia_atr
        >
        MAX_DISTANCIA_ENTRADA_ATR
    )


# ============================================================
# SCORE COMPRA
# ============================================================

def calcular_score_compra_v4(
    estructura,
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
    zona,
    contexto15
):

    score = 0

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    if estructura["direccion"] == "ALCISTA":
        score += 20

    if estructura["hh"]:
        score += 5

    if estructura["hl"]:
        score += 5

    if estructura["bos"] == "ALCISTA":
        score += 5

    # --------------------------------------------------------
    # CONTEXTO 15M
    # --------------------------------------------------------

    if contexto15 == "ALCISTA":
        score += 8

    elif contexto15 == "NEUTRAL":
        score += 3

    # --------------------------------------------------------
    # IMPULSO
    # --------------------------------------------------------

    if impulso is not None:

        score += 12

        if (
            impulso["desplazamiento_atr"]
            >= IMPULSO_ATR_FUERTE
        ):

            score += 5

    # --------------------------------------------------------
    # PULLBACK
    # --------------------------------------------------------

    if pullback is not None:

        score += 12

        if (
            pullback["retroceso_atr"]
            <= 1.20
        ):

            score += 4

    # --------------------------------------------------------
    # CONTINUACIÓN
    # --------------------------------------------------------

    if continuacion:
        score += 15

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    if rsi >= 50:
        score += 3

    if adx >= ADX_MINIMO:
        score += 2

    if di_plus > di_minus:
        score += 3

    # --------------------------------------------------------
    # EMA COMO CONTEXTO
    # --------------------------------------------------------

    if ema20 > ema50:
        score += 2

    if precio > ema20:
        score += 2

    # --------------------------------------------------------
    # UBICACIÓN
    # --------------------------------------------------------

    if zona is not None:

        distancia = (
            precio - zona
        )

        distancia_atr = (
            distancia / atr
            if atr > 0
            else 999
        )

        if (
            0
            <= distancia_atr
            <= 0.70
        ):

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
    zona,
    contexto15
):

    score = 0

    if estructura["direccion"] == "BAJISTA":
        score += 20

    if estructura["lh"]:
        score += 5

    if estructura["ll"]:
        score += 5

    if estructura["bos"] == "BAJISTA":
        score += 5

    if contexto15 == "BAJISTA":
        score += 8

    elif contexto15 == "NEUTRAL":
        score += 3

    if impulso is not None:

        score += 12

        if (
            impulso["desplazamiento_atr"]
            >= IMPULSO_ATR_FUERTE
        ):

            score += 5

    if pullback is not None:

        score += 12

        if (
            pullback["retroceso_atr"]
            <= 1.20
        ):

            score += 4

    if continuacion:
        score += 15

    if rsi <= 50:
        score += 3

    if adx >= ADX_MINIMO:
        score += 2

    if di_minus > di_plus:
        score += 3

    if ema20 < ema50:
        score += 2

    if precio < ema20:
        score += 2

    if zona is not None:

        distancia = (
            zona - precio
        )

        distancia_atr = (
            distancia / atr
            if atr > 0
            else 999
        )

        if (
            0
            <= distancia_atr
            <= 0.70
        ):

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

🏗️ Estructura: ALCISTA

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

✅ Estructura alcista
✅ Impulso detectado
✅ Pullback válido
✅ Continuación detectada
✅ Entrada dentro de zona válida
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

🏗️ Estructura: BAJISTA

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

✅ Estructura bajista
✅ Impulso detectado
✅ Pullback válido
✅ Continuación detectada
✅ Entrada dentro de zona válida
""".strip()

    return {
        "tipo": "VENTA",
        "mensaje": mensaje,
        "id": identificador
    }


# ============================================================
# ANALIZAR
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

        if len(df5) < 250:
            raise Exception(
                "Datos 5M insuficientes"
            )

        if len(df15) < 250:
            raise Exception(
                "Datos 15M insuficientes"
            )

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
                impulso_compra,
                pullback_compra
            )
        )

        continuacion_venta, zona_venta = (
            detectar_continuacion_bajista(
                df5,
                impulso_venta,
                pullback_venta
            )
        )

        # ----------------------------------------------------
        # ENTRADA TARDÍA
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
        # CONTEXTO 15M
        # ----------------------------------------------------

        contexto15 = (
            estructura15["direccion"]
        )

        contexto_compra_valido = (
            contexto15
            !=
            "BAJISTA"
        )

        contexto_venta_valido = (
            contexto15
            !=
            "ALCISTA"
        )

        # ----------------------------------------------------
        # POSIBLE COMPRA
        # ----------------------------------------------------

        posible_compra = (
            estructura5["direccion"]
            == "ALCISTA"

            and
            contexto_compra_valido

            and
            impulso_compra
            is not None

            and
            pullback_compra
            is not None

            and
            not tardia_compra
        )

        # ----------------------------------------------------
        # POSIBLE VENTA
        # ----------------------------------------------------

        posible_venta = (
            estructura5["direccion"]
            == "BAJISTA"

            and
            contexto_venta_valido

            and
            impulso_venta
            is not None

            and
            pullback_venta
            is not None

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
        )

        confirmada_venta = (
            posible_venta
            and
            continuacion_venta
        )

        # ----------------------------------------------------
        # SCORES
        # ----------------------------------------------------

        score_compra = (
            calcular_score_compra_v4(
                estructura5,
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
                zona_compra,
                contexto15
            )
        )

        score_venta = (
            calcular_score_venta_v4(
                estructura5,
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
                zona_venta,
                contexto15
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
        # CONFIRMAR COMPRA
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

            estado["direccion_pendiente"] = None
            estado["id_pendiente"] = None
            estado["ultima_confirmacion"] = time.time()

            return resultado

        # ====================================================
        # CONFIRMAR VENTA
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

            estado["direccion_pendiente"] = None
            estado["id_pendiente"] = None
            estado["ultima_confirmacion"] = time.time()

            return resultado

        # ====================================================
        # COMPRA PENDIENTE
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "COMPRA"
        ):

            if (
                estructura5["direccion"]
                == "BAJISTA"
                or
                estructura15["direccion"]
                == "BAJISTA"
            ):

                estado["direccion_pendiente"] = None
                estado["id_pendiente"] = None

                return {
                    "tipo": "DESCARTADA",
                    "mensaje": (
                        "🔴 PREALERTA COMPRA "
                        "DESCARTADA\n\n"
                        "La estructura dejó "
                        "de favorecer la compra."
                    )
                }

            if tardia_compra:

                estado["direccion_pendiente"] = None
                estado["id_pendiente"] = None

                return {
                    "tipo": "DESCARTADA",
                    "mensaje": (
                        "🔴 PREALERTA COMPRA "
                        "DESCARTADA\n\n"
                        "🚫 Entrada demasiado tarde."
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

            if (
                estructura5["direccion"]
                == "ALCISTA"
                or
                estructura15["direccion"]
                == "ALCISTA"
            ):

                estado["direccion_pendiente"] = None
                estado["id_pendiente"] = None

                return {
                    "tipo": "DESCARTADA",
                    "mensaje": (
                        "🟢 PREALERTA VENTA "
                        "DESCARTADA\n\n"
                        "La estructura dejó "
                        "de favorecer la venta."
                    )
                }

            if tardia_venta:

                estado["direccion_pendiente"] = None
                estado["id_pendiente"] = None

                return {
                    "tipo": "DESCARTADA",
                    "mensaje": (
                        "🟢 PREALERTA VENTA "
                        "DESCARTADA\n\n"
                        "🚫 Entrada demasiado tarde."
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

            ahora = time.time()

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
                        "⏳ Cooldown V4 compra..."
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

            estado["direccion_pendiente"] = (
                "COMPRA"
            )

            estado["id_pendiente"] = (
                resultado["id"]
            )

            estado["ultima_prealerta"] = (
                ahora
            )

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

            ahora = time.time()

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
                        "⏳ Cooldown V4 venta..."
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

            estado["direccion_pendiente"] = (
                "VENTA"
            )

            estado["id_pendiente"] = (
                resultado["id"]
            )

            estado["ultima_prealerta"] = (
                ahora
            )

            return resultado

        # ====================================================
        # SIN SEÑAL
        # ====================================================

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": "😴 Sin señal V4"
        }

    except Exception as e:

        print(
            f"❌ ERROR STRATEGY V4.0: {e}"
        )

        return {
            "tipo": "ERROR",
            "mensaje": (
                f"❌ Error estrategia V4: {e}"
            )
        }
