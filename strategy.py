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
# ============================================================
#
# CEREBRO PRINCIPAL:
#
# Estructura
#      ↓
# Impulso
#      ↓
# Pullback
#      ↓
# Continuación
#      ↓
# Ubicación
#      ↓
# Señal
#
# Las EMAs / RSI / ADX / DI son filtros secundarios.
#
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

RSI_COMPRA_MIN = 50
RSI_VENTA_MAX = 50

ATR_SL = 1.3
ATR_TP = 2.2


# ============================================================
# ESTRUCTURA
# ============================================================

# Número de velas utilizadas para encontrar swings.
SWING_LEFT = 2
SWING_RIGHT = 2

# Un swing debe tener cierta separación mínima.
# Se expresa como múltiplo del ATR.
SWING_ATR_MIN = 0.25


# ============================================================
# IMPULSO
# ============================================================

# Movimiento mínimo del impulso expresado en ATR.
IMPULSO_ATR_MIN = 1.0

# Máximo de velas que consideramos para buscar impulso.
IMPULSO_VELAS = 8


# ============================================================
# PULLBACK
# ============================================================

# Retroceso mínimo para considerar que realmente existe
# un pullback.
PULLBACK_MIN_ATR = 0.30

# Retroceso máximo permitido.
PULLBACK_MAX_ATR = 1.80


# ============================================================
# CONTINUACIÓN
# ============================================================

# La continuación debe superar el extremo del pullback
# por al menos esta cantidad de ATR.
CONTINUACION_ATR_MIN = 0.10


# ============================================================
# ANTI-ENTRADA TARDÍA
# ============================================================

# Si el precio ya se alejó demasiado de la zona del
# pullback, NO se persigue la entrada.
MAX_DISTANCIA_ENTRADA_ATR = 1.20


# ============================================================
# SCORE
# ============================================================

SCORE_MIN_PREALERTA = 55
SCORE_MIN_CONFIRMACION = 70


# ============================================================
# ESTADO
# ============================================================

estado = {
    "direccion_pendiente": None,
    "id_pendiente": None,
    "ultima_prealerta": 0,
    "ultima_confirmacion": 0,

    # Información del setup actual.
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

    url = "https://api.twelvedata.com/time_series"

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
    # EXPANSIÓN DEL RANGO
    # --------------------------------------------------------

    df["rango_medio"] = (
        df["rango"]
        .rolling(20)
        .mean()
    )

    df["expansion"] = (
        df["rango"] >
        df["rango_medio"] * 1.15
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

    for i in range(inicio, final):

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
            i + 1:i + 1 + SWING_RIGHT
        ]["high"]

        bajos_izq = df.iloc[
            i - SWING_LEFT:i
        ]["low"]

        bajos_der = df.iloc[
            i + 1:i + 1 + SWING_RIGHT
        ]["low"]

        if (
            high_actual >= altos_izq.max()
            and
            high_actual >= altos_der.max()
        ):

            highs.append({
                "index": i,
                "precio": high_actual
            })

        if (
            low_actual <= bajos_izq.min()
            and
            low_actual <= bajos_der.min()
        ):

            lows.append({
                "index": i,
                "precio": low_actual
            })

    return highs, lows


# ============================================================
# CLASIFICAR ESTRUCTURA
# ============================================================

def analizar_estructura(df):

    highs, lows = detectar_swings(df)

    resultado = {
        "direccion": "NEUTRAL",
        "ultimo_high": None,
        "ultimo_low": None,
        "prev_high": None,
        "prev_low": None,
        "bos": None,
        "choch": False
    }

    if len(highs) >= 2:

        ultimo_high = highs[-1]
        prev_high = highs[-2]

        resultado["ultimo_high"] = ultimo_high
        resultado["prev_high"] = prev_high

    if len(lows) >= 2:

        ultimo_low = lows[-1]
        prev_low = lows[-2]

        resultado["ultimo_low"] = ultimo_low
        resultado["prev_low"] = prev_low

    if (
        len(highs) >= 2
        and
        len(lows) >= 2
    ):

        hh = (
            highs[-1]["precio"]
            >
            highs[-2]["precio"]
        )

        hl = (
            lows[-1]["precio"]
            >
            lows[-2]["precio"]
        )

        lh = (
            highs[-1]["precio"]
            <
            highs[-2]["precio"]
        )

        ll = (
            lows[-1]["precio"]
            <
            lows[-2]["precio"]
        )

        if hh and hl:
            resultado["direccion"] = "ALCISTA"

        elif lh and ll:
            resultado["direccion"] = "BAJISTA"

    # --------------------------------------------------------
    # BOS
    # --------------------------------------------------------

    precio_actual = float(
        df.iloc[-1]["close"]
    )

    if (
        resultado["ultimo_high"] is not None
        and
        precio_actual >
        resultado["ultimo_high"]["precio"]
    ):

        resultado["bos"] = "ALCISTA"

    elif (
        resultado["ultimo_low"] is not None
        and
        precio_actual <
        resultado["ultimo_low"]["precio"]
    ):

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
        (ventana["direccion_vela"] == 1)
        .sum()
    )

    expansion = int(
        ventana["expansion"].sum()
    )

    desplazamiento_atr = (
        desplazamiento / atr
    )

    if (
        desplazamiento_atr >= IMPULSO_ATR_MIN
        and
        velas_alcistas >= 3
    ):

        return {
            "direccion": "ALCISTA",
            "inicio": inicio,
            "extremo": maximo,
            "desplazamiento": desplazamiento,
            "desplazamiento_atr": desplazamiento_atr,
            "velas_alcistas": velas_alcistas,
            "expansion": expansion
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
        (ventana["direccion_vela"] == -1)
        .sum()
    )

    expansion = int(
        ventana["expansion"].sum()
    )

    desplazamiento_atr = (
        desplazamiento / atr
    )

    if (
        desplazamiento_atr >= IMPULSO_ATR_MIN
        and
        velas_bajistas >= 3
    ):

        return {
            "direccion": "BAJISTA",
            "inicio": inicio,
            "extremo": minimo,
            "desplazamiento": desplazamiento,
            "desplazamiento_atr": desplazamiento_atr,
            "velas_bajistas": velas_bajistas,
            "expansion": expansion
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

    extremo = impulso["extremo"]

    minimo_reciente = float(
        df.iloc[-5:]["low"].min()
    )

    retroceso = (
        extremo - minimo_reciente
    )

    retroceso_atr = (
        retroceso / atr
    )

    if (
        retroceso_atr >= PULLBACK_MIN_ATR
        and
        retroceso_atr <= PULLBACK_MAX_ATR
    ):

        return {
            "direccion": "ALCISTA",
            "extremo_impulso": extremo,
            "minimo_pullback": minimo_reciente,
            "retroceso": retroceso,
            "retroceso_atr": retroceso_atr
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

    extremo = impulso["extremo"]

    maximo_reciente = float(
        df.iloc[-5:]["high"].max()
    )

    retroceso = (
        maximo_reciente - extremo
    )

    retroceso_atr = (
        retroceso / atr
    )

    if (
        retroceso_atr >= PULLBACK_MIN_ATR
        and
        retroceso_atr <= PULLBACK_MAX_ATR
    ):

        return {
            "direccion": "BAJISTA",
            "extremo_impulso": extremo,
            "maximo_pullback": maximo_reciente,
            "retroceso": retroceso,
            "retroceso_atr": retroceso_atr
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

    nivel = (
        pullback["minimo_pullback"]
    )

    maximo_local = float(
        df.iloc[-2:]["high"].max()
    )

    precio = float(
        df.iloc[-1]["close"]
    )

    ruptura = (
        maximo_local >
        nivel
    )

    fuerza = (
        precio >
        df.iloc[-1]["open"]
    )

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
        distancia_atr >= CONTINUACION_ATR_MIN
    )

    return confirmada, nivel


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

    nivel = (
        pullback["maximo_pullback"]
    )

    minimo_local = float(
        df.iloc[-2:]["low"].min()
    )

    precio = float(
        df.iloc[-1]["close"]
    )

    ruptura = (
        minimo_local <
        nivel
    )

    fuerza = (
        precio <
        df.iloc[-1]["open"]
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
        distancia_atr >= CONTINUACION_ATR_MIN
    )

    return confirmada, nivel


# ============================================================
# FILTRO ENTRADA TARDÍA COMPRA
# ============================================================

def entrada_tardia_compra(
    precio,
    zona,
    atr
):

    if zona is None or atr <= 0:
        return True

    distancia = (
        precio - zona
    )

    distancia_atr = (
        distancia / atr
    )

    return (
        distancia_atr >
        MAX_DISTANCIA_ENTRADA_ATR
    )


# ============================================================
# FILTRO ENTRADA TARDÍA VENTA
# ============================================================

def entrada_tardia_venta(
    precio,
    zona,
    atr
):

    if zona is None or atr <= 0:
        return True

    distancia = (
        zona - precio
    )

    distancia_atr = (
        distancia / atr
    )

    return (
        distancia_atr >
        MAX_DISTANCIA_ENTRADA_ATR
    )


# ============================================================
# SCORE V4 COMPRA
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
    zona
):

    score = 0

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    if estructura["direccion"] == "ALCISTA":
        score += 20

    if estructura["bos"] == "ALCISTA":
        score += 5

    # --------------------------------------------------------
    # IMPULSO
    # --------------------------------------------------------

    if impulso is not None:

        score += 15

        if impulso["desplazamiento_atr"] >= 1.5:
            score += 5

    # --------------------------------------------------------
    # PULLBACK
    # --------------------------------------------------------

    if pullback is not None:
        score += 15

        if (
            pullback["retroceso_atr"]
            <= 1.20
        ):
            score += 5

    # --------------------------------------------------------
    # CONTINUACIÓN
    # --------------------------------------------------------

    if continuacion:
        score += 20

    # --------------------------------------------------------
    # MOMENTUM SECUNDARIO
    # --------------------------------------------------------

    if rsi >= 50:
        score += 3

    if adx >= ADX_MINIMO:
        score += 2

    if di_plus > di_minus:
        score += 3

    # --------------------------------------------------------
    # CONTEXTO EMA
    # --------------------------------------------------------

    if ema20 > ema50:
        score += 2

    if precio > ema20:
        score += 2

    # --------------------------------------------------------
    # ANTI-ENTRADA TARDÍA
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

        if distancia_atr <= 0.70:
            score += 3

    return min(
        int(score),
        100
    )


# ============================================================
# SCORE V4 VENTA
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
    zona
):

    score = 0

    if estructura["direccion"] == "BAJISTA":
        score += 20

    if estructura["bos"] == "BAJISTA":
        score += 5

    if impulso is not None:

        score += 15

        if impulso["desplazamiento_atr"] >= 1.5:
            score += 5

    if pullback is not None:
        score += 15

        if (
            pullback["retroceso_atr"]
            <= 1.20
        ):
            score += 5

    if continuacion:
        score += 20

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

        if distancia_atr <= 0.70:
            score += 3

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

        if len(df5) < 50:
            raise Exception(
                "Datos 5M insuficientes"
            )

        if len(df15) < 50:
            raise Exception(
                "Datos 15M insuficientes"
            )

        actual5 = df5.iloc[-1]
        actual15 = df15.iloc[-1]

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
            f"5M: {estructura5['direccion']}"
        )

        print(
            f"15M: {estructura15['direccion']}"
        )

        print(
            f"BOS 5M: {estructura5['bos']}"
        )

        # ----------------------------------------------------
        # IMPULSOS
        # ----------------------------------------------------

        impulso_compra = (
            detectar_impulso_alcista(df5)
        )

        impulso_venta = (
            detectar_impulso_bajista(df5)
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
        # ENTRADA TARDÍA
        # ----------------------------------------------------

        tardia_compra = entrada_tardia_compra(
            precio,
            zona_compra,
            atr
        )

        tardia_venta = entrada_tardia_venta(
            precio,
            zona_venta,
            atr
        )

        # ----------------------------------------------------
        # CONTEXTO 15M
        # ----------------------------------------------------

        contexto_compra = (
            estructura15["direccion"]
            == "ALCISTA"
        )

        contexto_venta = (
            estructura15["direccion"]
            == "BAJISTA"
        )

        # ----------------------------------------------------
        # POSIBLE COMPRA
        # ----------------------------------------------------

        posible_compra = (
            estructura5["direccion"]
            == "ALCISTA"
            and
            contexto_compra
            and
            impulso_compra is not None
            and
            pullback_compra is not None
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
            contexto_venta
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
        )

        confirmada_venta = (
            posible_venta
            and
            continuacion_venta
        )

        # ----------------------------------------------------
        # SCORES
        # ----------------------------------------------------

        score_compra = calcular_score_compra_v4(
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
            zona_compra
        )

        score_venta = calcular_score_venta_v4(
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
            zona_venta
        )

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

        # ====================================================
        # CONFIRMACIÓN COMPRA
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "COMPRA"
            and
            confirmada_compra
            and
            score_compra >= SCORE_MIN_CONFIRMACION
        ):

            resultado = crear_compra_confirmada(
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

            estado["direccion_pendiente"] = None
            estado["id_pendiente"] = None
            estado["ultima_confirmacion"] = time.time()

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
            score_venta >= SCORE_MIN_CONFIRMACION
        ):

            resultado = crear_venta_confirmada(
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

            # Si la estructura dejó de ser alcista,
            # descartamos el setup.

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
                        "La estructura alcista "
                        "dejó de ser válida."
                    )
                }

            # Si el precio se fue demasiado lejos,
            # NO perseguimos.

            if tardia_compra:

                estado["direccion_pendiente"] = None
                estado["id_pendiente"] = None

                return {
                    "tipo": "DESCARTADA",
                    "mensaje": (
                        "🔴 PREALERTA COMPRA "
                        "DESCARTADA\n\n"
                        "🚫 Entrada demasiado tarde.\n\n"
                        "El precio se alejó demasiado "
                        "de la zona válida."
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
                        "La estructura bajista "
                        "dejó de ser válida."
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
                        "🚫 Entrada demasiado tarde.\n\n"
                        "El precio se alejó demasiado "
                        "de la zona válida."
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
            score_compra >= SCORE_MIN_PREALERTA
        ):

            ahora = time.time()

            if (
                ahora -
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

            resultado = crear_prealerta_compra(
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

            estado["direccion_pendiente"] = "COMPRA"
            estado["id_pendiente"] = resultado["id"]
            estado["ultima_prealerta"] = ahora

            return resultado

        # ====================================================
        # NUEVA PREALERTA VENTA
        # ====================================================

        if (
            posible_venta
            and
            score_venta >= SCORE_MIN_PREALERTA
        ):

            ahora = time.time()

            if (
                ahora -
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

            resultado = crear_prealerta_venta(
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

            estado["direccion_pendiente"] = "VENTA"
            estado["id_pendiente"] = resultado["id"]
            estado["ultima_prealerta"] = ahora

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
