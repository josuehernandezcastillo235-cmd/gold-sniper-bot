import requests
import pandas as pd
import os
import uuid
import time

from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


# ============================================================
# XAU SNIPER AI V3.4.1
# ============================================================

API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"

INTERVALO_5M = "5min"
INTERVALO_15M = "15min"

MINUTOS_REPETICION = 15
MINUTOS_EXPIRACION = 8

ADX_MINIMO_CONFIRMACION = 15

RSI_COMPRA_MIN = 55
RSI_VENTA_MAX = 45

ATR_SL = 1.3
ATR_TP = 2.2

# Distancia máxima permitida desde la entrada confirmada
MAX_ENTRADA_ATR = 0.35


# ============================================================
# ESTADO
# ============================================================

estado = {
    "direccion_pendiente": None,
    "id_pendiente": None,
    "ultima_prealerta": 0,
    "ultima_confirmacion": 0,

    "confirmacion_activa": None,
    "entrada_confirmada": None,
    "atr_confirmacion": None,
    "hora_confirmacion": 0
}


# ============================================================
# OBTENER DATOS
# ============================================================

def obtener_datos(intervalo):

    if not API_KEY:
        raise Exception("API_KEY no configurada")

    respuesta = requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": SYMBOL,
            "interval": intervalo,
            "outputsize": 500,
            "apikey": API_KEY,
            "format": "JSON"
        },
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
    ).reset_index(
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
        df["close"],
        20
    ).ema_indicator()

    df["ema50"] = EMAIndicator(
        df["close"],
        50
    ).ema_indicator()

    df["ema200"] = EMAIndicator(
        df["close"],
        200
    ).ema_indicator()

    df["rsi"] = RSIIndicator(
        df["close"],
        14
    ).rsi()

    df["atr"] = AverageTrueRange(
        df["high"],
        df["low"],
        df["close"],
        14
    ).average_true_range()

    adx = ADXIndicator(
        df["high"],
        df["low"],
        df["close"],
        14
    )

    df["adx"] = adx.adx()

    df["di_plus"] = adx.adx_pos()

    df["di_minus"] = adx.adx_neg()

    df = df.dropna().reset_index(
        drop=True
    )

    print(
        f"📊 Velas útiles: {len(df)}"
    )

    return df


# ============================================================
# TENDENCIA
# ============================================================

def obtener_tendencia(row):

    if (
        row["ema20"] > row["ema50"]
        and
        row["ema50"] > row["ema200"]
        and
        row["close"] > row["ema20"]
    ):

        return "ALCISTA"

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
# POSIBLE COMPRA
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
# POSIBLE VENTA
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
# PULLBACK REAL
# ============================================================

def pullback_compra(df):

    actual = df.iloc[-2]
    previa1 = df.iloc[-3]
    previa2 = df.iloc[-4]

    retroceso = (
        previa1["low"] <= previa1["ema20"]
        or
        previa2["low"] <= previa2["ema20"]
    )

    continuacion = (
        actual["close"] > previa1["high"]
    )

    return bool(
        retroceso and continuacion
    )


def pullback_venta(df):

    actual = df.iloc[-2]
    previa1 = df.iloc[-3]
    previa2 = df.iloc[-4]

    retroceso = (
        previa1["high"] >= previa1["ema20"]
        or
        previa2["high"] >= previa2["ema20"]
    )

    continuacion = (
        actual["close"] < previa1["low"]
    )

    return bool(
        retroceso and continuacion
    )


# ============================================================
# INVALIDACIONES
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
# PREALERTA COMPRA
# ============================================================

def prealerta_compra(
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

    sl = round(
        precio - atr * ATR_SL,
        2
    )

    tp = round(
        precio + atr * ATR_TP,
        2
    )

    identificador = uuid.uuid4().hex[:6]

    mensaje = f"""
🥇 XAU SNIPER AI V3.4.1

ID: {identificador}

🟡 POSIBLE COMPRA ANTICIPADA

⚠️ AÚN SIN CONFIRMACIÓN

⭐ Score: {score}/100

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

📋 REFERENCIA

Precio: {precio:.2f}

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
# PREALERTA VENTA
# ============================================================

def prealerta_venta(
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

    sl = round(
        precio + atr * ATR_SL,
        2
    )

    tp = round(
        precio - atr * ATR_TP,
        2
    )

    identificador = uuid.uuid4().hex[:6]

    mensaje = f"""
🥇 XAU SNIPER AI V3.4.1

ID: {identificador}

🟡 POSIBLE VENTA ANTICIPADA

⚠️ AÚN SIN CONFIRMACIÓN

⭐ Score: {score}/100

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

📋 REFERENCIA

Precio: {precio:.2f}

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
# COMPRA CONFIRMADA
# ============================================================

def confirmacion_compra(
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

    sl = round(
        precio - atr * ATR_SL,
        2
    )

    tp = round(
        precio + atr * ATR_TP,
        2
    )

    distancia = round(
        atr * MAX_ENTRADA_ATR,
        2
    )

    zona_min = round(
        precio - distancia,
        2
    )

    zona_max = round(
        precio + distancia,
        2
    )

    identificador = (
        estado["id_pendiente"]
        or
        uuid.uuid4().hex[:6]
    )

    mensaje = f"""
🥇 XAU SNIPER AI V3.4.1

ID: {identificador}

🟢 COMPRA CONFIRMADA

⭐ Score: {score}/100

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

📋 ENTRADA IDEAL

Precio: {precio:.2f}

📏 ZONA VÁLIDA:
{zona_min:.2f} - {zona_max:.2f}

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

⚠️ Si el precio actual está fuera
de la zona, NO ENTRAR.

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
# VENTA CONFIRMADA
# ============================================================

def confirmacion_venta(
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

    sl = round(
        precio + atr * ATR_SL,
        2
    )

    tp = round(
        precio - atr * ATR_TP,
        2
    )

    distancia = round(
        atr * MAX_ENTRADA_ATR,
        2
    )

    zona_min = round(
        precio - distancia,
        2
    )

    zona_max = round(
        precio + distancia,
        2
    )

    identificador = (
        estado["id_pendiente"]
        or
        uuid.uuid4().hex[:6]
    )

    mensaje = f"""
🥇 XAU SNIPER AI V3.4.1

ID: {identificador}

🔴 VENTA CONFIRMADA

⭐ Score: {score}/100

📊 Tendencia:
5M: {tendencia5}
15M: {tendencia15}

📋 ENTRADA IDEAL

Precio: {precio:.2f}

📏 ZONA VÁLIDA:
{zona_min:.2f} - {zona_max:.2f}

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

⚠️ Si el precio actual está fuera
de la zona, NO ENTRAR.

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
# LIMPIAR ESTADOS
# ============================================================

def limpiar_pendiente():

    estado["direccion_pendiente"] = None
    estado["id_pendiente"] = None


def limpiar_confirmacion():

    estado["confirmacion_activa"] = None
    estado["entrada_confirmada"] = None
    estado["atr_confirmacion"] = None
    estado["hora_confirmacion"] = 0

    limpiar_pendiente()


def reiniciar_estado():

    estado["direccion_pendiente"] = None
    estado["id_pendiente"] = None
    estado["ultima_prealerta"] = 0
    estado["ultima_confirmacion"] = 0
    estado["confirmacion_activa"] = None
    estado["entrada_confirmada"] = None
    estado["atr_confirmacion"] = None
    estado["hora_confirmacion"] = 0


# ============================================================
# REVISAR CONFIRMACIÓN ACTIVA
# ============================================================

def revisar_confirmacion(precio):

    direccion = estado["confirmacion_activa"]

    entrada = estado["entrada_confirmada"]

    atr = estado["atr_confirmacion"]

    hora = estado["hora_confirmacion"]

    if (
        not direccion
        or
        not entrada
        or
        not atr
        or
        not hora
    ):

        return None

    limite = (
        atr * MAX_ENTRADA_ATR
    )

    distancia = abs(
        precio - entrada
    )

    tiempo_excedido = (
        time.time() - hora
        >
        MINUTOS_EXPIRACION * 60
    )

    distancia_excedida = (
        distancia > limite
    )

    if (
        tiempo_excedido
        or
        distancia_excedida
    ):

        if tiempo_excedido:

            motivo = (
                f"superó "
                f"{MINUTOS_EXPIRACION} minutos"
            )

        else:

            motivo = (
                f"se alejó "
                f"{distancia:.2f} puntos; "
                f"límite {limite:.2f}"
            )

        if direccion == "COMPRA":

            icono = "🟢"

        else:

            icono = "🔴"

        mensaje = f"""
⚠️ SEÑAL VENCIDA

{icono} {direccion}

Entrada original:
{entrada:.2f}

Precio actual:
{precio:.2f}

❌ NO ENTRAR

La señal {motivo}.
""".strip()

        limpiar_confirmacion()

        return {
            "tipo": "DESCARTADA",
            "mensaje": mensaje
        }

    return None


# ============================================================
# ANALIZAR
# ============================================================

def analizar():

    try:

        print("")
        print(
            "==================================="
        )
        print(
            "🔍 Analizando XAU/USD V3.4.1"
        )
        print(
            "==================================="
        )

        # ----------------------------------------------------
        # DATOS
        # ----------------------------------------------------

        df5 = calcular_indicadores(
            obtener_datos(
                INTERVALO_5M
            )
        )

        df15 = calcular_indicadores(
            obtener_datos(
                INTERVALO_15M
            )
        )

        if len(df5) < 4:

            raise Exception(
                f"Datos insuficientes 5M: "
                f"{len(df5)}"
            )

        if len(df15) < 4:

            raise Exception(
                f"Datos insuficientes 15M: "
                f"{len(df15)}"
            )

        # ----------------------------------------------------
        # ÚLTIMA VELA CERRADA
        # ----------------------------------------------------

        actual5 = df5.iloc[-2]

        actual15 = df15.iloc[-2]

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

        print("")
        print("📊 DATOS ACTUALES")
        print("-----------------------------------")

        print(
            f"💰 Precio: {precio:.2f}"
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
        # REVISAR SEÑAL CONFIRMADA ACTIVA
        # ----------------------------------------------------

        vencida = revisar_confirmacion(
            precio
        )

        if vencida:

            print(
                "⚠️ CONFIRMACIÓN VENCIDA"
            )

            return vencida

        # Si hay una confirmación activa
        # no se genera otra señal.

        if estado["confirmacion_activa"]:

            print(
                "⏳ Confirmación activa."
            )

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "⏳ Confirmación activa..."
                )
            }

        # ----------------------------------------------------
        # CONDICIONES
        # ----------------------------------------------------

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

        pullback_c = pullback_compra(
            df5
        )

        pullback_v = pullback_venta(
            df5
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

        print(
            f"📈 Pullback compra: "
            f"{pullback_c}"
        )

        print(
            f"📉 Pullback venta: "
            f"{pullback_v}"
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
            pullback_c
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

            resultado = confirmacion_compra(
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

            estado["confirmacion_activa"] = (
                "COMPRA"
            )

            estado["entrada_confirmada"] = (
                precio
            )

            estado["atr_confirmacion"] = (
                atr
            )

            estado["hora_confirmacion"] = (
                time.time()
            )

            estado["ultima_confirmacion"] = (
                time.time()
            )

            estado["direccion_pendiente"] = (
                None
            )

            estado["id_pendiente"] = (
                None
            )

            print(
                "🟢 COMPRA CONFIRMADA + PULLBACK"
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
            and
            pullback_v
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

            resultado = confirmacion_venta(
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

            estado["confirmacion_activa"] = (
                "VENTA"
            )

            estado["entrada_confirmada"] = (
                precio
            )

            estado["atr_confirmacion"] = (
                atr
            )

            estado["hora_confirmacion"] = (
                time.time()
            )

            estado["ultima_confirmacion"] = (
                time.time()
            )

            estado["direccion_pendiente"] = (
                None
            )

            estado["id_pendiente"] = (
                None
            )

            print(
                "🔴 VENTA CONFIRMADA + PULLBACK"
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

                limpiar_pendiente()

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

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "🔎 Compra pendiente..."
                )
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

                limpiar_pendiente()

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

            return {
                "tipo": "SIN_SEÑAL",
                "mensaje": (
                    "🔎 Venta pendiente..."
                )
            }

        # ====================================================
        # NUEVA PREALERTA COMPRA
        # ====================================================

        ahora = time.time()

        if (
            posible_compra
            and
            ahora -
            estado["ultima_prealerta"]
            >=
            MINUTOS_REPETICION * 60
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

            resultado = prealerta_compra(
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

            estado["direccion_pendiente"] = (
                "COMPRA"
            )

            estado["id_pendiente"] = (
                resultado["id"]
            )

            estado["ultima_prealerta"] = (
                ahora
            )

            print(
                "🟡 NUEVA PREALERTA COMPRA"
            )

            return resultado

        # ====================================================
        # NUEVA PREALERTA VENTA
        # ====================================================

        if (
            posible_venta
            and
            ahora -
            estado["ultima_prealerta"]
            >=
            MINUTOS_REPETICION * 60
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

            resultado = prealerta_venta(
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

            estado["direccion_pendiente"] = (
                "VENTA"
            )

            estado["id_pendiente"] = (
                resultado["id"]
            )

            estado["ultima_prealerta"] = (
                ahora
            )

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
            f"❌ ERROR STRATEGY V3.4.1: {e}"
        )

        return {
            "tipo": "ERROR",
            "mensaje": (
                f"❌ Error estrategia: {e}"
            )
    }
