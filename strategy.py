import requests
import pandas as pd
import os
import uuid
import time

from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


# ============================================================
# XAU SNIPER AI V3.4
# ============================================================

API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"

INTERVALO_5M = "5min"
INTERVALO_15M = "15min"

# Tiempo mínimo entre nuevas prealertas
MINUTOS_REPETICION = 15

# Confirmación
ADX_MINIMO_CONFIRMACION = 20

RSI_COMPRA_MIN = 55
RSI_VENTA_MAX = 45

# SL / TP
ATR_SL = 1.3
ATR_TP = 2.2

# ============================================================
# PULLBACK
# ============================================================

# Distancia máxima aproximada respecto a EMA20 para considerar
# que el precio está trabajando una zona de pullback.
PULLBACK_ATR_MAX = 0.60

# Número de velas recientes utilizadas para detectar pullback.
VELAS_PULLBACK = 3


# ============================================================
# ESTADO
# ============================================================

estado = {
    "direccion_pendiente": None,
    "id_pendiente": None,
    "ultima_prealerta": 0,
    "ultima_confirmacion": 0
}


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

    df = pd.DataFrame(data["values"])

    if df.empty:
        raise Exception(
            f"Datos vacíos para {intervalo}"
        )

    # --------------------------------------------------------
    # Convertir precios
    # --------------------------------------------------------

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

    # Orden cronológico
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

    # EMA 20
    df["ema20"] = EMAIndicator(
        close=df["close"],
        window=20
    ).ema_indicator()

    # EMA 50
    df["ema50"] = EMAIndicator(
        close=df["close"],
        window=50
    ).ema_indicator()

    # EMA 200
    df["ema200"] = EMAIndicator(
        close=df["close"],
        window=200
    ).ema_indicator()

    # RSI
    df["rsi"] = RSIIndicator(
        close=df["close"],
        window=14
    ).rsi()

    # ATR
    df["atr"] = AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    ).average_true_range()

    # ADX
    adx = ADXIndicator(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    df["adx"] = adx.adx()
    df["di_plus"] = adx.adx_pos()
    df["di_minus"] = adx.adx_neg()

    # Eliminar filas incompletas
    df = df.dropna().reset_index(
        drop=True
    )

    print(
        f"📊 Velas útiles después de indicadores: "
        f"{len(df)}"
    )

    return df


# ============================================================
# TENDENCIA
# ============================================================

def obtener_tendencia(row):

    # ALCISTA
    if (
        row["ema20"] > row["ema50"]
        and
        row["ema50"] > row["ema200"]
        and
        row["close"] > row["ema20"]
    ):
        return "ALCISTA"

    # BAJISTA
    if (
        row["ema20"] < row["ema50"]
        and
        row["ema50"] < row["ema200"]
        and
        row["close"] < row["ema20"]
    ):
        return "BAJISTA"

    return "NEUTRAL"


# ============================================================
# SCORE COMPRA
# ============================================================

def calcular_score_compra(
    tendencia5,
    tendencia15,
    precio,
    ema20,
    ema50,
    rsi,
    adx,
    di_plus,
    di_minus
):

    score = 0

    if tendencia5 == "ALCISTA":
        score += 25

    if tendencia15 == "ALCISTA":
        score += 25

    if precio > ema50:
        score += 15

    if ema20 > ema50:
        score += 15

    if rsi >= 55:
        score += 10

    if di_plus > di_minus:
        score += 5

    if adx >= ADX_MINIMO_CONFIRMACION:
        score += 5

    return min(score, 100)


# ============================================================
# SCORE VENTA
# ============================================================

def calcular_score_venta(
    tendencia5,
    tendencia15,
    precio,
    ema20,
    ema50,
    rsi,
    adx,
    di_plus,
    di_minus
):

    score = 0

    if tendencia5 == "BAJISTA":
        score += 25

    if tendencia15 == "BAJISTA":
        score += 25

    if precio < ema50:
        score += 15

    if ema20 < ema50:
        score += 15

    if rsi <= 45:
        score += 10

    if di_minus > di_plus:
        score += 5

    if adx >= ADX_MINIMO_CONFIRMACION:
        score += 5

    return min(score, 100)


# ============================================================
# DETECTAR PULLBACK COMPRA
# ============================================================

def detectar_pullback_compra(
    df,
    indice_actual
):

    if indice_actual < VELAS_PULLBACK:
        return False

    actual = df.iloc[indice_actual]

    inicio = indice_actual - VELAS_PULLBACK

    recientes = df.iloc[
        inicio:indice_actual + 1
    ]

    # Debe existir una aproximación del precio a EMA20
    # durante las últimas velas.
    distancia_minima = (
        recientes["low"] -
        recientes["ema20"]
    ).abs().min()

    atr = float(actual["atr"])

    if atr <= 0:
        return False

    cerca_ema20 = (
        distancia_minima <=
        atr * PULLBACK_ATR_MAX
    )

    # El precio actual debe seguir sobre EMA50.
    estructura_sigue_alcista = (
        actual["close"] > actual["ema50"]
    )

    return (
        cerca_ema20
        and
        estructura_sigue_alcista
    )


# ============================================================
# DETECTAR PULLBACK VENTA
# ============================================================

def detectar_pullback_venta(
    df,
    indice_actual
):

    if indice_actual < VELAS_PULLBACK:
        return False

    actual = df.iloc[indice_actual]

    inicio = indice_actual - VELAS_PULLBACK

    recientes = df.iloc[
        inicio:indice_actual + 1
    ]

    distancia_minima = (
        recientes["high"] -
        recientes["ema20"]
    ).abs().min()

    atr = float(actual["atr"])

    if atr <= 0:
        return False

    cerca_ema20 = (
        distancia_minima <=
        atr * PULLBACK_ATR_MAX
    )

    estructura_sigue_bajista = (
        actual["close"] < actual["ema50"]
    )

    return (
        cerca_ema20
        and
        estructura_sigue_bajista
    )


# ============================================================
# POSIBLE COMPRA
# ============================================================

def es_posible_compra(
    tendencia5,
    tendencia15,
    precio,
    ema20,
    ema50,
    rsi,
    di_plus,
    di_minus,
    df5,
    indice_actual
):

    pullback = detectar_pullback_compra(
        df5,
        indice_actual
    )

    return (
        tendencia5 == "ALCISTA"
        and
        tendencia15 == "ALCISTA"
        and
        precio > ema50
        and
        precio >= ema20
        and
        rsi >= 50
        and
        di_plus >= di_minus
        and
        pullback
    )


# ============================================================
# POSIBLE VENTA
# ============================================================

def es_posible_venta(
    tendencia5,
    tendencia15,
    precio,
    ema20,
    ema50,
    rsi,
    di_plus,
    di_minus,
    df5,
    indice_actual
):

    pullback = detectar_pullback_venta(
        df5,
        indice_actual
    )

    return (
        tendencia5 == "BAJISTA"
        and
        tendencia15 == "BAJISTA"
        and
        precio < ema50
        and
        precio <= ema20
        and
        rsi <= 50
        and
        di_minus >= di_plus
        and
        pullback
    )


# ============================================================
# COMPRA CONFIRMADA
# ============================================================

def compra_confirmada(
    tendencia5,
    tendencia15,
    precio,
    ema20,
    ema50,
    rsi,
    adx,
    di_plus,
    di_minus,
    vela_actual,
    vela_anterior
):

    # Continuación alcista:
    # la vela cerrada actual debe estar sobre EMA20
    # y mostrar recuperación respecto a la vela anterior.
    continuacion = (
        vela_actual["close"] > vela_actual["ema20"]
        and
        vela_actual["close"] > vela_anterior["close"]
    )

    return (
        tendencia5 == "ALCISTA"
        and
        tendencia15 == "ALCISTA"
        and
        precio > ema20
        and
        ema20 > ema50
        and
        rsi >= RSI_COMPRA_MIN
        and
        adx >= ADX_MINIMO_CONFIRMACION
        and
        di_plus > di_minus
        and
        continuacion
    )


# ============================================================
# VENTA CONFIRMADA
# ============================================================

def venta_confirmada(
    tendencia5,
    tendencia15,
    precio,
    ema20,
    ema50,
    rsi,
    adx,
    di_plus,
    di_minus,
    vela_actual,
    vela_anterior
):

    continuacion = (
        vela_actual["close"] < vela_actual["ema20"]
        and
        vela_actual["close"] < vela_anterior["close"]
    )

    return (
        tendencia5 == "BAJISTA"
        and
        tendencia15 == "BAJISTA"
        and
        precio < ema20
        and
        ema20 < ema50
        and
        rsi <= RSI_VENTA_MAX
        and
        adx >= ADX_MINIMO_CONFIRMACION
        and
        di_minus > di_plus
        and
        continuacion
    )


# ============================================================
# INVALIDAR COMPRA
# ============================================================

def compra_invalida(
    tendencia5,
    tendencia15,
    precio,
    ema50
):

    return (
        tendencia5 == "BAJISTA"
        or
        tendencia15 == "BAJISTA"
        or
        precio < ema50
    )


# ============================================================
# INVALIDAR VENTA
# ============================================================

def venta_invalida(
    tendencia5,
    tendencia15,
    precio,
    ema50
):

    return (
        tendencia5 == "ALCISTA"
        or
        tendencia15 == "ALCISTA"
        or
        precio > ema50
    )


# ============================================================
# CREAR PREALERTA COMPRA
# ============================================================

def crear_prealerta_compra(
    precio,
    atr,
    score,
    tendencia5,
    tendencia15,
    rsi,
    adx,
    di_plus,
    di_minus,
    ema20,
    ema50
):

    entrada = round(precio, 2)

    sl = round(
        entrada - atr * ATR_SL,
        2
    )

    tp = round(
        entrada + atr * ATR_TP,
        2
    )

    identificador = uuid.uuid4().hex[:6]

    mensaje = f"""
🥇 XAU SNIPER AI V3.4

ID: {identificador}

🟡 POSIBLE COMPRA ANTICIPADA

⚠️ AÚN SIN CONFIRMACIÓN

⭐ Score: {score}/100

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

📋 REFERENCIA

Precio: {entrada:.2f}

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

🧠 Pullback alcista detectado
📈 Precio sobre EMA50

🔎 PREALERTA GUARDADA
⏳ Esperando confirmación real
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
    tendencia5,
    tendencia15,
    rsi,
    adx,
    di_plus,
    di_minus,
    ema20,
    ema50
):

    entrada = round(precio, 2)

    sl = round(
        entrada + atr * ATR_SL,
        2
    )

    tp = round(
        entrada - atr * ATR_TP,
        2
    )

    identificador = uuid.uuid4().hex[:6]

    mensaje = f"""
🥇 XAU SNIPER AI V3.4

ID: {identificador}

🟡 POSIBLE VENTA ANTICIPADA

⚠️ AÚN SIN CONFIRMACIÓN

⭐ Score: {score}/100

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

📋 REFERENCIA

Precio: {entrada:.2f}

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

🧠 Pullback bajista detectado
📉 Precio bajo EMA50

🔎 PREALERTA GUARDADA
⏳ Esperando confirmación real
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
    tendencia5,
    tendencia15,
    rsi,
    adx,
    di_plus,
    di_minus,
    ema20,
    ema50
):

    entrada = round(precio, 2)

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
        or
        uuid.uuid4().hex[:6]
    )

    mensaje = f"""
🥇 XAU SNIPER AI V3.4

ID: {identificador}

🟢 COMPRA CONFIRMADA

⭐ Score: {score}/100

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

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

✅ Precio sobre EMA20
✅ EMA20 sobre EMA50
✅ Tendencia 5M alcista
✅ Tendencia 15M alcista
✅ Pullback + continuación
✅ Momentum confirmado
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
    tendencia5,
    tendencia15,
    rsi,
    adx,
    di_plus,
    di_minus,
    ema20,
    ema50
):

    entrada = round(precio, 2)

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
        or
        uuid.uuid4().hex[:6]
    )

    mensaje = f"""
🥇 XAU SNIPER AI V3.4

ID: {identificador}

🔴 VENTA CONFIRMADA

⭐ Score: {score}/100

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

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

✅ Precio bajo EMA20
✅ EMA20 bajo EMA50
✅ Tendencia 5M bajista
✅ Tendencia 15M bajista
✅ Pullback + continuación
✅ Momentum confirmado
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
        print("🔍 XAU SNIPER AI V3.4")
        print("🔍 Analizando XAU/USD...")
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

        print(
            "✅ Datos 5M y 15M recibidos"
        )

        # ----------------------------------------------------
        # INDICADORES
        # ----------------------------------------------------

        df5 = calcular_indicadores(
            df5
        )

        df15 = calcular_indicadores(
            df15
        )

        print(
            f"📊 Filas útiles 5M: {len(df5)}"
        )

        print(
            f"📊 Filas útiles 15M: {len(df15)}"
        )

        # ----------------------------------------------------
        # COMPROBAR DATOS
        # ----------------------------------------------------

        if len(df5) < 10:

            raise Exception(
                f"No hay suficientes datos 5M: {len(df5)}"
            )

        if len(df15) < 10:

            raise Exception(
                f"No hay suficientes datos 15M: {len(df15)}"
            )

        # ----------------------------------------------------
        # USAR ÚLTIMA VELA CERRADA
        # ----------------------------------------------------

        indice5 = len(df5) - 2
        indice15 = len(df15) - 2

        actual5 = df5.iloc[indice5]
        anterior5 = df5.iloc[indice5 - 1]

        actual15 = df15.iloc[indice15]

        print(
            f"🕯️ Vela 5M analizada: "
            f"{actual5['datetime']}"
        )

        print(
            f"🕯️ Vela 15M analizada: "
            f"{actual15['datetime']}"
        )

        # ----------------------------------------------------
        # VALORES 5M
        # ----------------------------------------------------

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
        # TENDENCIAS
        # ----------------------------------------------------

        tendencia5 = obtener_tendencia(
            actual5
        )

        tendencia15 = obtener_tendencia(
            actual15
        )

        # ----------------------------------------------------
        # DEBUG
        # ----------------------------------------------------

        print("")
        print("📊 DATOS ACTUALES")
        print("-----------------------------------")

        print(
            f"💰 Precio cerrado: {precio:.2f}"
        )

        print(
            f"EMA20: {ema20:.2f}"
        )

        print(
            f"EMA50: {ema50:.2f}"
        )

        print(
            f"EMA200: {ema200:.2f}"
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
            f"5M: {tendencia5}"
        )

        print(
            f"15M: {tendencia15}"
        )

        # ----------------------------------------------------
        # PULLBACK
        # ----------------------------------------------------

        pullback_compra = detectar_pullback_compra(
            df5,
            indice5
        )

        pullback_venta = detectar_pullback_venta(
            df5,
            indice5
        )

        print("")
        print("🔄 PULLBACK")
        print("-----------------------------------")

        print(
            f"🟢 Pullback compra: "
            f"{pullback_compra}"
        )

        print(
            f"🔴 Pullback venta: "
            f"{pullback_venta}"
        )

        # ----------------------------------------------------
        # CONDICIONES
        # ----------------------------------------------------

        posible_compra = es_posible_compra(
            tendencia5,
            tendencia15,
            precio,
            ema20,
            ema50,
            rsi,
            di_plus,
            di_minus,
            df5,
            indice5
        )

        posible_venta = es_posible_venta(
            tendencia5,
            tendencia15,
            precio,
            ema20,
            ema50,
            rsi,
            di_plus,
            di_minus,
            df5,
            indice5
        )

        confirmada_compra = compra_confirmada(
            tendencia5,
            tendencia15,
            precio,
            ema20,
            ema50,
            rsi,
            adx,
            di_plus,
            di_minus,
            actual5,
            anterior5
        )

        confirmada_venta = venta_confirmada(
            tendencia5,
            tendencia15,
            precio,
            ema20,
            ema50,
            rsi,
            adx,
            di_plus,
            di_minus,
            actual5,
            anterior5
        )

        print("")
        print("📋 CONDICIONES")
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
            f"🟢 Compra confirmada: "
            f"{confirmada_compra}"
        )

        print(
            f"🔴 Venta confirmada: "
            f"{confirmada_venta}"
        )

        # ====================================================
        # CONFIRMACIÓN COMPRA
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "COMPRA"
            and
            confirmada_compra
        ):

            score = calcular_score_compra(
                tendencia5,
                tendencia15,
                precio,
                ema20,
                ema50,
                rsi,
                adx,
                di_plus,
                di_minus
            )

            resultado = crear_compra_confirmada(
                precio,
                atr,
                score,
                tendencia5,
                tendencia15,
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

            print(
                "🟢 COMPRA CONFIRMADA"
            )

            return resultado

        # ====================================================
        # CONFIRMACIÓN VENTA
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "VENTA"
            and
            confirmada_venta
        ):

            score = calcular_score_venta(
                tendencia5,
                tendencia15,
                precio,
                ema20,
                ema50,
                rsi,
                adx,
                di_plus,
                di_minus
            )

            resultado = crear_venta_confirmada(
                precio,
                atr,
                score,
                tendencia5,
                tendencia15,
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

            print(
                "🔴 VENTA CONFIRMADA"
            )

            return resultado

        # ====================================================
        # COMPRA PENDIENTE
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "COMPRA"
        ):

            if compra_invalida(
                tendencia5,
                tendencia15,
                precio,
                ema50
            ):

                print(
                    "🔴 PREALERTA COMPRA DESCARTADA"
                )

                estado["direccion_pendiente"] = None
                estado["id_pendiente"] = None

                return {
                    "tipo": "DESCARTADA",
                    "mensaje": (
                        "🔴 PREALERTA COMPRA "
                        "DESCARTADA\n\n"
                        "Las condiciones "
                        "alcistas dejaron de "
                        "cumplirse."
                    )
                }

            print(
                "🔎 COMPRA PENDIENTE"
            )

            print(
                "⏳ Esperando confirmación..."
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": "🔎 Compra pendiente..."
            }

        # ====================================================
        # VENTA PENDIENTE
        # ====================================================

        if (
            estado["direccion_pendiente"]
            == "VENTA"
        ):

            if venta_invalida(
                tendencia5,
                tendencia15,
                precio,
                ema50
            ):

                print(
                    "🟢 PREALERTA VENTA DESCARTADA"
                )

                estado["direccion_pendiente"] = None
                estado["id_pendiente"] = None

                return {
                    "tipo": "DESCARTADA",
                    "mensaje": (
                        "🟢 PREALERTA VENTA "
                        "DESCARTADA\n\n"
                        "Las condiciones "
                        "bajistas dejaron de "
                        "cumplirse."
                    )
                }

            print(
                "🔎 VENTA PENDIENTE"
            )

            print(
                "⏳ Esperando confirmación..."
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": "🔎 Venta pendiente..."
            }

        # ====================================================
        # NUEVA PREALERTA COMPRA
        # ====================================================

        if posible_compra:

            ahora = time.time()

            if (
                ahora -
                estado["ultima_prealerta"]
                <
                MINUTOS_REPETICION * 60
            ):

                print(
                    "⏳ Prealerta compra bloqueada "
                    "por cooldown"
                )

                return {
                    "tipo": "SIN_SEÑAL",
                    "mensaje": (
                        "⏳ Esperando confirmación..."
                    )
                }

            score = calcular_score_compra(
                tendencia5,
                tendencia15,
                precio,
                ema20,
                ema50,
                rsi,
                adx,
                di_plus,
                di_minus
            )

            resultado = crear_prealerta_compra(
                precio,
                atr,
                score,
                tendencia5,
                tendencia15,
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

            print(
                "🟡 NUEVA PREALERTA COMPRA"
            )

            return resultado

        # ====================================================
        # NUEVA PREALERTA VENTA
        # ====================================================

        if posible_venta:

            ahora = time.time()

            if (
                ahora -
                estado["ultima_prealerta"]
                <
                MINUTOS_REPETICION * 60
            ):

                print(
                    "⏳ Prealerta venta bloqueada "
                    "por cooldown"
                )

                return {
                    "tipo": "SIN_SEÑAL",
                    "mensaje": (
                        "⏳ Esperando confirmación..."
                    )
                }

            score = calcular_score_venta(
                tendencia5,
                tendencia15,
                precio,
                ema20,
                ema50,
                rsi,
                adx,
                di_plus,
                di_minus
            )

            resultado = crear_prealerta_venta(
                precio,
                atr,
                score,
                tendencia5,
                tendencia15,
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

            print(
                "🟡 NUEVA PREALERTA VENTA"
            )

            return resultado

        # ====================================================
        # SIN SEÑAL
        # ====================================================

        print(
            "😴 Sin señal"
        )

        return {
            "tipo": "SIN_SEÑAL",
            "mensaje": "😴 Sin señal"
        }

    # ========================================================
    # ERROR
    # ========================================================

    except Exception as e:

        print(
            f"❌ ERROR STRATEGY V3.4: {e}"
        )

        return {
            "tipo": "ERROR",
            "mensaje": (
                f"❌ Error estrategia: {e}"
            )
            }
