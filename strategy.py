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
# MOTOR DE ESTRUCTURA + MOMENTUM + LIQUIDEZ
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
# UBICACIÓN
#     ↓
# SCORE
#     ↓
# PREALERTA
#     ↓
# CONFIRMACIÓN
#
# EMA / RSI / ADX / DI = CONTEXTO SECUNDARIO
#
# ============================================================


API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"

INTERVALO_5M = "5min"
INTERVALO_15M = "15min"

INTERVALO_ANALISIS = 100


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

IMPULSO_ATR_MIN = 0.70

IMPULSO_VELAS_MIN = 3


# ============================================================
# PULLBACK
# ============================================================

PULLBACK_MIN_ATR = 0.15

PULLBACK_MAX_ATR = 1.80

PULLBACK_MAX_VELAS = 7


# ============================================================
# CONTINUACIÓN
# ============================================================

CONTINUACION_ATR_MIN = 0.03

CUERPO_CONTINUACION_ATR = 0.10


# ============================================================
# ENTRADA TARDÍA
# ============================================================

MAX_DISTANCIA_ENTRADA_ATR = 1.50


# ============================================================
# SCORE
# ============================================================

SCORE_MIN_PREALERTA = 55

SCORE_MIN_CONFIRMACION = 68


# ============================================================
# ESTADO
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

    "nivel_continuacion": None,

    "pullback_maximo": None,

    "pullback_minimo": None,
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
        "outputsize": 1000,
        "apikey": API_KEY,
        "format": "JSON"
    }

    ultimo_error = None

    for intento in range(3):

        try:

            respuesta = requests.get(
                url,
                params=params,
                timeout=25
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

            print(
                f"📥 {intervalo}: "
                f"{len(df)} velas recibidas"
            )

            return df

        except Exception as e:

            ultimo_error = e

            print(
                f"⚠️ Twelve Data "
                f"{intervalo} intento "
                f"{intento + 1}/3: {e}"
            )

            if intento < 2:

                time.sleep(
                    2 + intento * 2
                )

    raise Exception(
        f"Twelve Data no respondió "
        f"correctamente para {intervalo}: "
        f"{ultimo_error}"
    )


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
        df["rango"]
        >
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

        atr_actual = float(
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
                "atr": atr_actual
            })

        if (
            low_actual <= bajos_izq.min()
            and
            low_actual <= bajos_der.min()
        ):

            lows.append({
                "index": i,
                "precio": low_actual,
                "atr": atr_actual
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
            highs[-2]["precio"]
        )

        resultado["lh"] = (
            highs[-1]["precio"] <
            highs[-2]["precio"]
        )

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
    # ESTRUCTURA PRINCIPAL
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
                atr * 0.40
            ):

                resultado["direccion"] = (
                    "ALCISTA"
                )

                resultado["fuerza"] = 1

            elif (
                desplazamiento <
                -atr * 0.40
            ):

                resultado["direccion"] = (
                    "BAJISTA"
                )

                resultado["fuerza"] = 1

    # --------------------------------------------------------
    # BOS
    #
    # Usamos swings confirmados anteriores.
    # No exigimos que el último swing sea el único nivel.
    # --------------------------------------------------------

    precio_actual = float(
        df.iloc[-1]["close"]
    )

    if len(highs) >= 1:

        for swing in reversed(highs):

            if (
                precio_actual >
                swing["precio"]
            ):

                resultado["bos"] = (
                    "ALCISTA"
                )

                break

    if resultado["bos"] is None:

        if len(lows) >= 1:

            for swing in reversed(lows):

                if (
                    precio_actual <
                    swing["precio"]
                ):

                    resultado["bos"] = (
                        "BAJISTA"
                    )

                    break

    # --------------------------------------------------------
    # CHoCH
    # --------------------------------------------------------

    if resultado["direccion"] == "ALCISTA":

        if (
            resultado["ultimo_low"]
            is not None
            and
            precio_actual <
            resultado["ultimo_low"]["precio"]
        ):

            resultado["choch"] = True

    elif resultado["direccion"] == "BAJISTA":

        if (
            resultado["ultimo_high"]
            is not None
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
    ].copy()

    atr = float(
        df.iloc[-1]["atr"]
    )

    if atr <= 0:

        return None

    inicio = float(
        ventana.iloc[0]["close"]
    )

    extremo_idx_local = (
        ventana["high"].idxmax()
    )

    extremo = float(
        ventana.loc[
            extremo_idx_local,
            "high"
        ]
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
        desplazamiento_atr
        >=
        IMPULSO_ATR_MIN
        and
        velas_alcistas
        >=
        IMPULSO_VELAS_MIN
    ):

        return {
            "direccion": "ALCISTA",

            "inicio": inicio,

            "extremo": extremo,

            "indice_extremo": int(
                extremo_idx_local
            ),

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
    ].copy()

    atr = float(
        df.iloc[-1]["atr"]
    )

    if atr <= 0:

        return None

    inicio = float(
        ventana.iloc[0]["close"]
    )

    extremo_idx_local = (
        ventana["low"].idxmin()
    )

    extremo = float(
        ventana.loc[
            extremo_idx_local,
            "low"
        ]
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
        desplazamiento_atr
        >=
        IMPULSO_ATR_MIN
        and
        velas_bajistas
        >=
        IMPULSO_VELAS_MIN
    ):

        return {
            "direccion": "BAJISTA",

            "inicio": inicio,

            "extremo": extremo,

            "indice_extremo": int(
                extremo_idx_local
            ),

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

    extremo = float(
        impulso["extremo"]
    )

    inicio = float(
        impulso["inicio"]
    )

    indice_extremo = int(
        impulso["indice_extremo"]
    )

    # --------------------------------------------------------
    # BUSCAMOS EL RETROCESO DESPUÉS DEL MÁXIMO DEL IMPULSO
    # --------------------------------------------------------

    despues_extremo = df[
        df.index > indice_extremo
    ].copy()

    if despues_extremo.empty:

        return None

    despues_extremo = despues_extremo.tail(
        PULLBACK_MAX_VELAS
    )

    minimo = float(
        despues_extremo["low"].min()
    )

    indice_minimo = int(
        despues_extremo["low"].idxmin()
    )

    precio = float(
        df.iloc[-1]["close"]
    )

    # --------------------------------------------------------
    # PROFUNDIDAD DEL RETROCESO
    # --------------------------------------------------------

    retroceso = (
        extremo -
        minimo
    )

    retroceso_atr = (
        retroceso /
        atr
    )

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    highs, lows = detectar_swings(df)

    hl_protegido = False

    nivel_hl = None

    if len(lows) >= 1:

        ultimo_low = lows[-1]

        if (
            ultimo_low["index"]
            >=
            indice_extremo
        ):

            nivel_hl = float(
                ultimo_low["precio"]
            )

            if minimo >= (
                nivel_hl -
                atr * 0.20
            ):

                hl_protegido = True

    # --------------------------------------------------------
    # FALLBACK ESTRUCTURAL
    #
    # Si todavía no existe swing confirmado posterior,
    # usamos el inicio del impulso como referencia secundaria.
    # --------------------------------------------------------

    estructura_valida = (
        minimo >
        inicio -
        atr * 0.75
    )

    if hl_protegido:

        estructura_valida = True

    # --------------------------------------------------------
    # EL RETROCESO DEBE EXISTIR
    # --------------------------------------------------------

    if (
        retroceso_atr
        <
        PULLBACK_MIN_ATR
    ):

        return None

    if (
        retroceso_atr
        >
        PULLBACK_MAX_ATR
    ):

        return None

    if not estructura_valida:

        return None

    # --------------------------------------------------------
    # NIVEL DE CONTINUACIÓN
    #
    # No exigimos volver exactamente al extremo del impulso.
    # Buscamos recuperar el máximo de la zona de pullback.
    # --------------------------------------------------------

    maximo_pullback = float(
        despues_extremo["high"].max()
    )

    nivel_continuacion = maximo_pullback

    # Si el máximo del pullback es prácticamente el extremo,
    # dejamos un margen pequeño para facilitar la confirmación.
    if (
        nivel_continuacion >=
        extremo -
        atr * 0.05
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

        "indice_extremo":
            indice_extremo,

        "indice_minimo":
            indice_minimo,

        "minimo_pullback":
            minimo,

        "maximo_pullback":
            maximo_pullback,

        "nivel_hl":
            nivel_hl,

        "hl_protegido":
            hl_protegido,

        "retroceso":
            retroceso,

        "retroceso_atr":
            retroceso_atr,

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

    indice_extremo = int(
        impulso["indice_extremo"]
    )

    # --------------------------------------------------------
    # BUSCAMOS EL RETROCESO DESPUÉS DEL MÍNIMO DEL IMPULSO
    # --------------------------------------------------------

    despues_extremo = df[
        df.index > indice_extremo
    ].copy()

    if despues_extremo.empty:

        return None

    despues_extremo = despues_extremo.tail(
        PULLBACK_MAX_VELAS
    )

    maximo = float(
        despues_extremo["high"].max()
    )

    indice_maximo = int(
        despues_extremo["high"].idxmax()
    )

    precio = float(
        df.iloc[-1]["close"]
    )

    # --------------------------------------------------------
    # PROFUNDIDAD
    # --------------------------------------------------------

    retroceso = (
        maximo -
        extremo
    )

    retroceso_atr = (
        retroceso /
        atr
    )

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    highs, lows = detectar_swings(df)

    lh_protegido = False

    nivel_lh = None

    if len(highs) >= 1:

        ultimo_high = highs[-1]

        if (
            ultimo_high["index"]
            >=
            indice_extremo
        ):

            nivel_lh = float(
                ultimo_high["precio"]
            )

            if maximo <= (
                nivel_lh +
                atr * 0.20
            ):

                lh_protegido = True

    estructura_valida = (
        maximo <
        inicio +
        atr * 0.75
    )

    if lh_protegido:

        estructura_valida = True

    if (
        retroceso_atr
        <
        PULLBACK_MIN_ATR
    ):

        return None

    if (
        retroceso_atr
        >
        PULLBACK_MAX_ATR
    ):

        return None

    if not estructura_valida:

        return None

    # --------------------------------------------------------
    # NIVEL DE CONTINUACIÓN
    # --------------------------------------------------------

    minimo_pullback = float(
        despues_extremo["low"].min()
    )

    nivel_continuacion = (
        minimo_pullback
    )

    if (
        nivel_continuacion <=
        extremo +
        atr * 0.05
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

        "indice_extremo":
            indice_extremo,

        "indice_maximo":
            indice_maximo,

        "maximo_pullback":
            maximo,

        "minimo_pullback":
            minimo_pullback,

        "nivel_lh":
            nivel_lh,

        "lh_protegido":
            lh_protegido,

        "retroceso":
            retroceso,

        "retroceso_atr":
            retroceso_atr,

        "nivel_continuacion":
            nivel_continuacion,

        "precio_actual":
            precio
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

    if atr <= 0:

        return False, None

    actual = df.iloc[-1]

    anterior = df.iloc[-2]

    precio = float(
        actual["close"]
    )

    apertura = float(
        actual["open"]
    )

    high = float(
        actual["high"]
    )

    low = float(
        actual["low"]
    )

    cuerpo = abs(
        precio -
        apertura
    )

    rango = (
        high -
        low
    )

    vela_alcista = (
        precio >
        apertura
    )

    cuerpo_minimo = max(
        atr * CONTINUACION_ATR_MIN,
        rango * 0.20
    )

    cuerpo_fuerte = (
        cuerpo >=
        max(
            atr * CUERPO_CONTINUACION_ATR,
            cuerpo_minimo
        )
    )

    nivel = float(
        pullback[
            "nivel_continuacion"
        ]
    )

    # --------------------------------------------------------
    # RECUPERACIÓN DEL NIVEL
    # --------------------------------------------------------

    ruptura_nivel = (
        precio >
        nivel
    )

    # --------------------------------------------------------
    # RUPTURA DEL MÁXIMO DE LA VELA ANTERIOR
    # --------------------------------------------------------

    maximo_anterior = float(
        anterior["high"]
    )

    ruptura_anterior = (
        precio >
        maximo_anterior
    )

    # --------------------------------------------------------
    # MOMENTUM DE CONTINUACIÓN
    # --------------------------------------------------------

    cierre_superior = (
        precio >
        float(actual["close"]) -
        atr * 0.25
    )

    confirmacion = (
        vela_alcista
        and
        cuerpo_fuerte
        and
        (
            ruptura_nivel
            or
            ruptura_anterior
        )
        and
        cierre_superior
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

    anterior = df.iloc[-2]

    precio = float(
        actual["close"]
    )

    apertura = float(
        actual["open"]
    )

    high = float(
        actual["high"]
    )

    low = float(
        actual["low"]
    )

    cuerpo = abs(
        precio -
        apertura
    )

    rango = (
        high -
        low
    )

    vela_bajista = (
        precio <
        apertura
    )

    cuerpo_minimo = max(
        atr * CONTINUACION_ATR_MIN,
        rango * 0.20
    )

    cuerpo_fuerte = (
        cuerpo >=
        max(
            atr * CUERPO_CONTINUACION_ATR,
            cuerpo_minimo
        )
    )

    nivel = float(
        pullback[
            "nivel_continuacion"
        ]
    )

    ruptura_nivel = (
        precio <
        nivel
    )

    minimo_anterior = float(
        anterior["low"]
    )

    ruptura_anterior = (
        precio <
        minimo_anterior
    )

    cierre_inferior = (
        precio <
        float(actual["close"]) +
        atr * 0.25
    )

    confirmacion = (
        vela_bajista
        and
        cuerpo_fuerte
        and
        (
            ruptura_nivel
            or
            ruptura_anterior
        )
        and
        cierre_inferior
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
        estructura15["direccion"]
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
# ZONA DE UBICACIÓN
# ============================================================

def obtener_zona_compra(
    estructura,
    pullback
):

    if pullback is not None:

        if pullback.get(
            "nivel_hl"
        ) is not None:

            return float(
                pullback["nivel_hl"]
            )

        return float(
            pullback["minimo_pullback"]
        )

    if (
        estructura["ultimo_low"]
        is not None
    ):

        return float(
            estructura[
                "ultimo_low"
            ]["precio"]
        )

    return None


def obtener_zona_venta(
    estructura,
    pullback
):

    if pullback is not None:

        if pullback.get(
            "nivel_lh"
        ) is not None:

            return float(
                pullback["nivel_lh"]
            )

        return float(
            pullback["maximo_pullback"]
        )

    if (
        estructura["ultimo_high"]
        is not None
    ):

        return float(
            estructura[
                "ultimo_high"
            ]["precio"]
        )

    return None


# ============================================================
# SCORE COMPRA V4
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

    if contexto15 == "ALCISTA":
        score += 10

    elif contexto15 == "NEUTRAL":
        score += 5

    elif contexto15 == "BAJISTA":
        score -= 6

    if impulso is not None:

        score += 12

        if (
            impulso[
                "desplazamiento_atr"
            ] >= 1.20
        ):

            score += 4

    if pullback is not None:

        score += 12

        if (
            pullback[
                "retroceso_atr"
            ] <= 1.20
        ):

            score += 4

        if pullback.get(
            "hl_protegido",
            False
        ):

            score += 3

    if continuacion:
        score += 15

    if rsi >= RSI_COMPRA_MIN:
        score += 3

    if rsi >= RSI_CONFIRMACION_COMPRA:
        score += 2

    if adx >= ADX_MINIMO:
        score += 3

    if adx >= 25:
        score += 2

    if di_plus > di_minus:
        score += 4

    if ema20 > ema50:
        score += 3

    if precio > ema20:
        score += 2

    if (
        ema20 > ema50
        and
        precio > ema20
    ):

        score += 2

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
            distancia_atr
            <= 0.80
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

    if contexto15 == "BAJISTA":
        score += 10

    elif contexto15 == "NEUTRAL":
        score += 5

    elif contexto15 == "ALCISTA":
        score -= 6

    if impulso is not None:

        score += 12

        if (
            impulso[
                "desplazamiento_atr"
            ] >= 1.20
        ):

            score += 4

    if pullback is not None:

        score += 12

        if (
            pullback[
                "retroceso_atr"
            ] <= 1.20
        ):

            score += 4

        if pullback.get(
            "lh_protegido",
            False
        ):

            score += 3

    if continuacion:
        score += 15

    if rsi <= RSI_VENTA_MAX:
        score += 3

    if rsi <= RSI_CONFIRMACION_VENTA:
        score += 2

    if adx >= ADX_MINIMO:
        score += 3

    if adx >= 25:
        score += 2

    if di_minus > di_plus:
        score += 4

    if ema20 < ema50:
        score += 3

    if precio < ema20:
        score += 2

    if (
        ema20 < ema50
        and
        precio < ema20
    ):

        score += 2

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
            distancia_atr
            <= 0.80
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

    retroceso = (
        pullback[
            "retroceso_atr"
        ]
        if pullback
        else 0
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

📐 Retroceso:
{retroceso:.2f} ATR

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
Precio → estructura → impulso
→ pullback → esperando continuación

⏳ Tiempo máximo:
{MINUTOS_VIDA_PREALERTA} minutos
""".strip()

    return {
        "tipo":
            "POSIBLE_COMPRA",

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

    retroceso = (
        pullback[
            "retroceso_atr"
        ]
        if pullback
        else 0
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

📐 Retroceso:
{retroceso:.2f} ATR

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
Precio → estructura → impulso
→ pullback → esperando continuación

⏳ Tiempo máximo:
{MINUTOS_VIDA_PREALERTA} minutos
""".strip()

    return {
        "tipo":
            "POSIBLE_VENTA",

        "mensaje":
            mensaje,

        "id":
            identificador
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

🧠 V4:
Estructura → impulso → pullback → continuación

✅ Entrada confirmada
""".strip()

    return {
        "tipo":
            "COMPRA",

        "mensaje":
            mensaje,

        "id":
            identificador
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

🧠 V4:
Estructura → impulso → pullback → continuación

✅ Entrada confirmada
""".strip()

    return {
        "tipo":
            "VENTA",

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

    estado["nivel_continuacion"] = None

    estado["pullback_maximo"] = None

    estado["pullback_minimo"] = None


# ============================================================
# DESCARTADA COMPRA
# ============================================================

def descartada_compra(
    razon
):

    identificador = (
        estado["id_pendiente"]
        or
        "------"
    )

    limpiar_pendiente()

    return {
        "tipo":
            "DESCARTADA",

        "id":
            identificador,

        "mensaje":
            (
                "🔴 PREALERTA COMPRA "
                "DESCARTADA\n\n"
                f"🆔 ID: {identificador}\n\n"
                f"{razon}"
            )
    }


# ============================================================
# DESCARTADA VENTA
# ============================================================

def descartada_venta(
    razon
):

    identificador = (
        estado["id_pendiente"]
        or
        "------"
    )

    limpiar_pendiente()

    return {
        "tipo":
            "DESCARTADA",

        "id":
            identificador,

        "mensaje":
            (
                "🟢 PREALERTA VENTA "
                "DESCARTADA\n\n"
                f"🆔 ID: {identificador}\n\n"
                f"{razon}"
            )
    }


# ============================================================
# ANALIZAR
# ============================================================

def analizar():

    try:

        print("")
        print("===================================")
        print("🔍 ANALIZANDO XAU/USD...")
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
        # ACTUAL
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

        # ----------------------------------------------------
        # ESTRUCTURA
        # ----------------------------------------------------

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
            f"Contexto 15M: "
            f"{contexto15}"
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
        # SI HAY PREALERTA PENDIENTE
        # USAMOS SU NIVEL DE CONTINUACIÓN
        # ----------------------------------------------------

        if (
            estado["direccion_pendiente"]
            == "COMPRA"
        ):

            if (
                estado[
                    "nivel_continuacion"
                ]
                is not None
            ):

                zona_compra = (
                    estado[
                        "nivel_continuacion"
                    ]
                )

                # Si el pullback nuevo desapareció por
                # cambio de ventana, reconstruimos una
                # referencia mínima con el estado guardado.

                if pullback_compra is None:

                    pullback_compra = {
                        "direccion":
                            "ALCISTA",

                        "extremo_impulso":
                            estado[
                                "impulso_extremo"
                            ],

                        "inicio_impulso":
                            estado[
                                "impulso_inicio"
                            ],

                        "minimo_pullback":
                            estado[
                                "pullback_minimo"
                            ]
                            or
                            precio,

                        "maximo_pullback":
                            precio,

                        "nivel_continuacion":
                            estado[
                                "nivel_continuacion"
                            ],

                        "retroceso_atr":
                            0.50,

                        "hl_protegido":
                            True
                    }

                continuacion_compra, _ = (
                    detectar_continuacion_alcista(
                        df5,
                        pullback_compra
                    )
                )

        if (
            estado["direccion_pendiente"]
            == "VENTA"
        ):

            if (
                estado[
                    "nivel_continuacion"
                ]
                is not None
            ):

                zona_venta = (
                    estado[
                        "nivel_continuacion"
                    ]
                )

                if pullback_venta is None:

                    pullback_venta = {
                        "direccion":
                            "BAJISTA",

                        "extremo_impulso":
                            estado[
                                "impulso_extremo"
                            ],

                        "inicio_impulso":
                            estado[
                                "impulso_inicio"
                            ],

                        "maximo_pullback":
                            estado[
                                "pullback_maximo"
                            ]
                            or
                            precio,

                        "minimo_pullback":
                            precio,

                        "nivel_continuacion":
                            estado[
                                "nivel_continuacion"
                            ],

                        "retroceso_atr":
                            0.50,

                        "lh_protegido":
                            True
                    }

                continuacion_venta, _ = (
                    detectar_continuacion_bajista(
                        df5,
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
        # ZONAS
        # ----------------------------------------------------

        if zona_compra is None:

            zona_compra = (
                obtener_zona_compra(
                    estructura5,
                    pullback_compra
                )
            )

        if zona_venta is None:

            zona_venta = (
                obtener_zona_venta(
                    estructura5,
                    pullback_venta
                )
            )

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # POSIBLES SETUPS
        #
        # PREALERTA:
        # IMPULSO + PULLBACK + SCORE
        #
        # NO exigimos continuación todavía.
        # ----------------------------------------------------

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

        if pullback_compra is not None:

            print(
                "📐 Pullback compra: "
                f"{pullback_compra['retroceso_atr']:.2f} ATR"
            )

            print(
                "🛡️ HL protegido compra: "
                f"{pullback_compra.get('hl_protegido', False)}"
            )

            print(
                "🎯 Nivel continuación compra: "
                f"{pullback_compra['nivel_continuacion']:.2f}"
            )

        if pullback_venta is not None:

            print(
                "📐 Pullback venta: "
                f"{pullback_venta['retroceso_atr']:.2f} ATR"
            )

            print(
                "🛡️ LH protegido venta: "
                f"{pullback_venta.get('lh_protegido', False)}"
            )

            print(
                "🎯 Nivel continuación venta: "
                f"{pullback_venta['nivel_continuacion']:.2f}"
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
            f"📈 RSI: "
            f"{rsi:.1f}"
        )

        print(
            f"📊 ADX: "
            f"{adx:.1f}"
        )

        print(
            f"DI+: "
            f"{di_plus:.1f}"
        )

        print(
            f"DI-: "
            f"{di_minus:.1f}"
)


        # ====================================================
        # PREALERTA PENDIENTE
        # ====================================================

        if (
            estado["direccion_pendiente"]
            is not None
        ):

            tiempo_viva = (
                ahora -
                estado["inicio_pendiente"]
            )

            # ------------------------------------------------
            # EXPIRACIÓN
            # ------------------------------------------------

            if (
                tiempo_viva
                >=
                MINUTOS_VIDA_PREALERTA * 60
            ):

                print(
                    "⏳ PREALERTA EXPIRADA"
                )

                if (
                    estado[
                        "direccion_pendiente"
                    ]
                    == "COMPRA"
                ):

                    return descartada_compra(
                        "⏳ Tiempo de confirmación agotado.\n\n"
                        "El movimiento no produjo una "
                        "continuación válida dentro del "
                        f"límite de "
                        f"{MINUTOS_VIDA_PREALERTA} minutos."
                    )

                return descartada_venta(
                    "⏳ Tiempo de confirmación agotado.\n\n"
                    "El movimiento no produjo una "
                    "continuación válida dentro del "
                    f"límite de "
                    f"{MINUTOS_VIDA_PREALERTA} minutos."
                )

            # ------------------------------------------------
            # PREALERTA COMPRA PENDIENTE
            # ------------------------------------------------

            if (
                estado[
                    "direccion_pendiente"
                ]
                == "COMPRA"
            ):

                contexto_contrario = (
                    estructura5[
                        "direccion"
                    ]
                    == "BAJISTA"
                    and
                    estructura5[
                        "fuerza"
                    ]
                    >= 2
                    and
                    contexto15
                    == "BAJISTA"
                )

                if contexto_contrario:

                    return descartada_compra(
                        "📉 La estructura cambió "
                        "claramente a bajista en 5M "
                        "y 15M."
                    )

                # --------------------------------------------
                # CONFIRMACIÓN
                # --------------------------------------------

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
                    "⏳ Compra pendiente..."
                )

                return {
                    "tipo":
                        "SIN_SEÑAL",

                    "mensaje":
                        "🔎 Compra V4 pendiente..."
                }

            # ------------------------------------------------
            # PREALERTA VENTA PENDIENTE
            # ------------------------------------------------

            if (
                estado[
                    "direccion_pendiente"
                ]
                == "VENTA"
            ):

                contexto_contrario = (
                    estructura5[
                        "direccion"
                    ]
                    == "ALCISTA"
                    and
                    estructura5[
                        "fuerza"
                    ]
                    >= 2
                    and
                    contexto15
                    == "ALCISTA"
                )

                if contexto_contrario:

                    return descartada_venta(
                        "📈 La estructura cambió "
                        "claramente a alcista en 5M "
                        "y 15M."
                    )

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
                    "⏳ Venta pendiente..."
                )

                return {
                    "tipo":
                        "SIN_SEÑAL",

                    "mensaje":
                        "🔎 Venta V4 pendiente..."
                }

        # ====================================================
        # NUEVA PREALERTA COMPRA
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
                    "pullback_minimo"
                ] = (
                    pullback_compra[
                        "minimo_pullback"
                    ]
                )

                estado[
                    "pullback_maximo"
                ] = (
                    pullback_compra[
                        "maximo_pullback"
                    ]
                )

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

                estado[
                    "pullback_nivel"
                ] = (
                    pullback_venta[
                        "maximo_pullback"
                    ]
                )

                estado[
                    "pullback_minimo"
                ] = (
                    pullback_venta[
                        "minimo_pullback"
                    ]
                )

                estado[
                    "pullback_maximo"
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
                "SIN_SEÑAL",

            "mensaje":
                "😴 Sin señal V4"
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
                f"❌ Error V4:\n{e}"
                }
