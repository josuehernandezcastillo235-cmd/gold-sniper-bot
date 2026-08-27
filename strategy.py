# ============================================================
# XAU SNIPER AI V4.2
# MOTOR DE ESTRUCTURA + MOMENTUM + LIQUIDEZ
# PARTE 1/9
# ============================================================

import os
import time
import uuid
import logging
from datetime import datetime, timezone

import requests
import pandas as pd
import numpy as np

from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange


# ============================================================
# CONFIGURACIÓN
# ============================================================

API_KEY = os.getenv("API_KEY")

SYMBOL = "XAU/USD"

INTERVALO_5M = "5min"
INTERVALO_15M = "15min"

VELAS_5M = 300
VELAS_15M = 200

TIMEOUT_API = 15

# El bot corre cada 100 segundos desde bot.py.
INTERVALO_ANALISIS = 100

# ------------------------------------------------------------
# VALIDACIÓN TEMPORAL
# ------------------------------------------------------------

# Tolerancia máxima para datos realmente futuros.
# No se utiliza para considerar "vieja" una vela que simplemente
# todavía pertenece al intervalo actual de 15M.
FUTURO_TOLERANCIA_MIN = 2

# Una vela cerrada debe tener una antigüedad razonable.
# Se permite margen porque el proveedor puede tardar unos segundos.
MAX_EDAD_5M = 10
MAX_EDAD_15M = 20


# ============================================================
# ESTRUCTURA
# ============================================================

SWING_LOOKBACK = 3

MIN_BOS_DIST_ATR = 0.12
MIN_STRUCTURE_SCORE = 2


# ============================================================
# MOMENTUM
# ============================================================

RSI_COMPRA = 52
RSI_VENTA = 48

RSI_CONFIRMACION_COMPRA = 55
RSI_CONFIRMACION_VENTA = 45

ADX_MINIMO = 18
ADX_CONFIRMACION = 20


# ============================================================
# ATR / RIESGO
# ============================================================

ATR_SL = 1.30
ATR_TP = 2.20

RR_MINIMO = 1.50


# ============================================================
# SCORE
# ============================================================

SCORE_PREALERTA = 58
SCORE_CONFIRMACION = 72


# ============================================================
# COOLDOWNS
# ============================================================

MINUTOS_REPETICION = 15
MINUTOS_COOLDOWN_CONFIRMADA = 15

ultima_senal_id = None
ultima_direccion = None
ultima_confirmacion_ts = None

ultimo_error_ts = 0
ultimo_timestamp_5m = None
ultimo_timestamp_15m = None


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("xau_sniper_v42")

if not logger.handlers:

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s - "
            "%(levelname)s - "
            "%(message)s"
        )
    )


# ============================================================
# UTILIDADES BÁSICAS
# ============================================================

def ahora_utc():
    """
    Devuelve la hora UTC actual con timezone.
    """
    return datetime.now(timezone.utc)


def numero(valor, default=np.nan):
    """
    Convierte cualquier valor numérico a float de forma segura.
    """
    try:

        if valor is None:
            return default

        if isinstance(valor, str):
            valor = valor.replace(",", "").strip()

        resultado = float(valor)

        if not np.isfinite(resultado):
            return default

        return resultado

    except Exception:
        return default


def redondear_precio(valor):
    """
    Oro normalmente se muestra con 2 decimales en Telegram.
    """
    try:
        return round(float(valor), 2)
    except Exception:
        return 0.0


def fmt(valor, decimales=2):
    """
    Formato numérico seguro para mensajes.
    """
    try:
        return f"{float(valor):.{decimales}f}"
    except Exception:
        return "N/D"


def normalizar_timestamp(valor):
    """
    Convierte timestamps de Twelve Data a UTC.

    Regla importante:
    - Si vienen con timezone, se convierten a UTC.
    - Si vienen sin timezone, se interpretan como UTC porque
      la petición solicita timezone=UTC.
    """

    try:

        ts = pd.Timestamp(valor)

        if ts.tzinfo is None:

            ts = ts.tz_localize("UTC")

        else:

            ts = ts.tz_convert("UTC")

        return ts

    except Exception:

        return pd.NaT


def intervalo_minutos(intervalo):
    """
    Convierte 5min / 15min a minutos.
    """

    if intervalo == "5min":
        return 5

    if intervalo == "15min":
        return 15

    raise ValueError(
        f"Intervalo no soportado: {intervalo}"
    )


# ============================================================
# FIN PARTE 1/9
# ============================================================
