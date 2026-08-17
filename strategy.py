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
# PREALERTA + CONFIRMACIÓN + CONTROL DE REPETICIONES
# ============================================================

API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"

# ------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------

INTERVALO_5M = "5min"
INTERVALO_15M = "15min"

MINUTOS_REPETICION = 15

ADX_MINIMO_CONFIRMACION = 15

RSI_COMPRA_MIN = 55
RSI_VENTA_MAX = 45

ATR_SL = 1.3
ATR_TP = 2.2


# ============================================================
# ESTADO DE LA ESTRATEGIA
# ============================================================

estado = {
    "direccion_pendiente": None,
    "id_pendiente": None,
    "ultima_prealerta": 0,
    "ultima_confirmacion": 0,
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
        "outputsize": 200,
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
            f"Sin datos para {intervalo}"
        )

    # --------------------------------------------------------
    # Convertir columnas
    # --------------------------------------------------------

    columnas = [
        "open",
        "high",
        "low",
        "close"
    ]

    for columna in columnas:

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

    return df


# ============================================================
# INDICADORES
# ============================================================

def calcular_indicadores(df):

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

    df = df.dropna()

    return df


# ============================================================
# TENDENCIA
# ============================================================

def obtener_tendencia(row):

    if (
        row["ema20"] > row["ema50"]
        and row["ema50"] > row["ema200"]
        and row["close"] > row["ema20"]
    ):
        return "ALCISTA"

    if (
        row["ema20"] < row["ema50"]
        and row["ema50"] < row["ema200"]
        and row["close"] < row["ema20"]
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

    # Tendencia 5M
    if tendencia5 == "ALCISTA":
        score += 25

    # Tendencia 15M
    if tendencia15 == "ALCISTA":
        score += 25

    # Precio sobre EMA50
    if precio > ema50:
        score += 15

    # EMA20 sobre EMA50
    if ema20 > ema50:
        score += 15

    # Momentum
    if rsi >= 55:
        score += 10

    # DI
    if di_plus > di_minus:
        score += 5

    # ADX
    if adx >= ADX_MINIMO_CONFIRMACION:
        score += 5

    return min(
        score,
        100
    )


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

    return min(
        score,
        100
    )


# ============================================================
# PREALERTA COMPRA
# ============================================================

def es_posible_compra(
    tendencia5,
    tendencia15,
    precio,
    ema50,
    rsi,
    di_plus,
    di_minus
):

    return (
        tendencia5 == "ALCISTA"
        and
        tendencia15 == "ALCISTA"
        and
        precio > ema50
        and
        rsi >= 50
        and
        di_plus >= di_minus
    )


# ============================================================
# PREALERTA VENTA
# ============================================================

def es_posible_venta(
    tendencia5,
    tendencia15,
    precio,
    ema50,
    rsi,
    di_plus,
    di_minus
):

    return (
        tendencia5 == "BAJISTA"
        and
        tendencia15 == "BAJISTA"
        and
        precio < ema50
        and
        rsi <= 50
        and
        di_minus >= di_plus
    )


# ============================================================
# CONFIRMACIÓN COMPRA
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
    di_minus
):

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
    )


# ============================================================
# CONFIRMACIÓN VENTA
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
    di_minus
):

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
    )


# ============================================================
# INVALIDACIÓN DE COMPRA
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
# INVALIDACIÓN DE VENTA
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
# GENERAR PREALERTA COMPRA
# ============================================================

def generar_prealerta_compra(
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

🧠 Momentum alcista
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
# GENERAR PREALERTA VENTA
# ============================================================

def generar_prealerta_venta(
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

🧠 Momentum bajista
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
# GENERAR COMPRA CONFIRMADA
# ============================================================

def generar_compra_confirmada(
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

    identificador = estado["id_pendiente"]

    if identificador is None:
        identificador = uuid.uuid4().hex[:6]

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
✅ Momentum confirmado
""".strip()

    return {
        "tipo": "COMPRA",
        "mensaje": mensaje,
        "id": identificador
    }


# ============================================================
# GENERAR VENTA CONFIRMADA
# ============================================================

def generar_venta_confirmada(
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

    identificador = estado["id_pendiente"]

    if identificador is None:
        identificador = uuid.uuid4().hex[:6]

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
        print("🔍 Analizando XAU/USD...")
        print("")

        # ====================================================
        # DATOS
        # ====================================================

        df5 = obtener_datos(
            INTERVALO_5M
        )

        df15 = obtener_datos(
            INTERVALO_15M
        )

        print("✅ Datos 5M y 15M recibidos")

        # ====================================================
        # INDICADORES
        # ====================================================

        df5 = calcular_indicadores(
            df5
        )

        df15 = calcular_indicadores(
            df15
        )

        if len(df5) < 5 or len(df15) < 5:

            raise Exception(
                "No hay suficientes datos"
            )

        # ====================================================
        # ÚLTIMA VELA
        # ====================================================

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

        tendencia5 = obtener_tendencia(
            actual5
        )

        tendencia15 = obtener_tendencia(
            actual15
        )

        print(
            f"💰 Precio: {precio:.2f}"
        )

        print(
            f"📊 5M: {tendencia5}"
        )

        print(
            f"📊 15M: {tendencia15}"
        )

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

        # ====================================================
        # CONDICIONES
        # ====================================================

        posible_compra = es_posible_compra(
            tendencia5,
            tendencia15,
            precio,
            ema50,
            rsi,
            di_plus,
            di_minus
        )

        posible_venta = es_posible_venta(
            tendencia5,
            tendencia15,
            precio,
            ema50,
            rsi,
            di_plus,
            di_minus
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
            di_minus
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
            di_minus
        )

        # ====================================================
        # DEBUG
        # ====================================================

        print(
            f"🟡 Posible compra: {posible_compra}"
        )

        print(
            f"🟡 Posible venta: {posible_venta}"
        )

        print(
            f"🟢 Compra confirmada: {confirmada_compra}"
        )

        print(
            f"🔴 Venta confirmada: {confirmada_venta}"
        )

        # ====================================================
        # 1. CONFIRMACIÓN DE COMPRA
        # ====================================================

        if (
            estado["direccion_pendiente"] == "COMPRA"
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

            resultado = generar_compra_confirmada(
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
        # 2. CONFIRMACIÓN DE VENTA
        # ====================================================

        if (
            estado["direccion_pendiente"] == "VENTA"
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

            resultado = generar_venta_confirmada(
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
        # 3. INVALIDAR COMPRA
        # ====================================================

        if estado["direccion_pendiente"] == "COMPRA":

            if compra_invalida(
                tendencia5,
                tendencia15,
                precio,
                ema50
            ):

                print(
                    "🔴 PREALERTA COMPRA INVALIDADA"
                )

                estado["direccion_pendiente"] = None
                estado["id_pendiente"] = None

                return {
                    "tipo": "DESCARTADA",
                    "mensaje": (
                        "🔴 PREALERTA COMPRA DESCARTADA\n"
                        "Las condiciones alcistas "
                        "dejaron de cumplirse."
                    )
                }

            # ------------------------------------------------
            # Si sigue pendiente, NO mandar otra alerta
            # ------------------------------------------------

            print(
                "🔎 COMPRA PENDIENTE - "
                "SIN NUEVA ALERTA"
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": "🔎 Compra pendiente..."
            }

        # ====================================================
        # 4. INVALIDAR VENTA
        # ====================================================

        if estado["direccion_pendiente"] == "VENTA":

            if venta_invalida(
                tendencia5,
                tendencia15,
                precio,
                ema50
            ):

                print(
                    "🟢 PREALERTA VENTA INVALIDADA"
                )

                estado["direccion_pendiente"] = None
                estado["id_pendiente"] = None

                return {
                    "tipo": "DESCARTADA",
                    "mensaje": (
                        "🟢 PREALERTA VENTA DESCARTADA\n"
                        "Las condiciones bajistas "
                        "dejaron de cumplirse."
                    )
                }

            print(
                "🔎 VENTA PENDIENTE - "
                "SIN NUEVA ALERTA"
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": "🔎 Venta pendiente..."
            }

        # ====================================================
        # 5. NUEVA PREALERTA COMPRA
        # ====================================================

        if posible_compra:

            ahora = time.time()

            if (
                ahora - estado["ultima_prealerta"]
                < MINUTOS_REPETICION * 60
            ):

                print(
                    "⏳ Prealerta compra bloqueada "
                    "por cooldown"
                )

                return {
                    "tipo": "SIN_SEÑAL",
                    "mensaje": "⏳ Esperando confirmación..."
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

            resultado = generar_prealerta_compra(
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
        # 6. NUEVA PREALERTA VENTA
        # ====================================================

        if posible_venta:

            ahora = time.time()

            if (
                ahora - estado["ultima_prealerta"]
                < MINUTOS_REPETICION * 60
            ):

                print(
                    "⏳ Prealerta venta bloqueada "
                    "por cooldown"
                )

                return {
                    "tipo": "SIN_SEÑAL",
                    "mensaje": "⏳ Esperando confirmación..."
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

            resultado = generar_prealerta_venta(
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
