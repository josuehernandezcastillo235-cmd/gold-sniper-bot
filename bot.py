import os
import asyncio
import logging
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from strategy import analizar


# =========================================================
# CONFIGURACIÓN
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

INTERVALO = 100


# =========================================================
# ESTADO
# =========================================================

bot_encendido = True

ultima_alerta_tipo = None
ultima_alerta_precio = None
ultima_alerta_tiempo = 0

ciclo_iniciado = False


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# =========================================================
# TECLADO
# =========================================================

def teclado():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "▶️ ENCENDER",
                callback_data="encender"
            ),
            InlineKeyboardButton(
                "⏹ APAGAR",
                callback_data="apagar"
            )
        ]
    ])


# =========================================================
# INICIO
# =========================================================

async def inicio(app):

    global bot_encendido
    global ciclo_iniciado

    bot_encendido = True

    print("🚀 XAU SNIPER AI V3.3 iniciado correctamente")

    await app.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "🚀 XAU Sniper AI V3.3 iniciado correctamente.\n\n"
            "✅ Conexión Telegram: OK\n"
            "✅ Motor de análisis: OK\n"
            "📊 Mercado: XAU/USD\n"
            "⏱ Revisión: cada 100 segundos\n\n"
            "🟢 Estado: ENCENDIDO\n"
            "⚠️ Advertencias anticipadas: ACTIVADAS"
        ),
        reply_markup=teclado()
    )

    # Evitar iniciar dos ciclos
    if not ciclo_iniciado:

        ciclo_iniciado = True

        asyncio.create_task(
            ciclo_analisis(app)
        )


# =========================================================
# BOTONES
# =========================================================

async def botones(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global bot_encendido

    query = update.callback_query

    await query.answer()

    # =====================================================
    # ENCENDER
    # =====================================================

    if query.data == "encender":

        bot_encendido = True

        await query.edit_message_text(
            text=(
                "🟢 XAU SNIPER AI V3.3\n\n"
                "▶️ BOT ENCENDIDO\n\n"
                "🔍 Analizando XAU/USD\n"
                "⏱ Cada 100 segundos\n"
                "⚠️ Advertencias anticipadas ACTIVAS"
            ),
            reply_markup=teclado()
        )

        print("🟢 BOT ENCENDIDO")


    # =====================================================
    # APAGAR
    # =====================================================

    elif query.data == "apagar":

        bot_encendido = False

        await query.edit_message_text(
            text=(
                "🔴 XAU SNIPER AI V3.3\n\n"
                "⏹ BOT APAGADO\n\n"
                "El análisis está detenido.\n"
                "Pulsa ▶️ ENCENDER para continuar."
            ),
            reply_markup=teclado()
        )

        print("🔴 BOT APAGADO")


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global bot_encendido

    bot_encendido = True

    await update.message.reply_text(
        (
            "🥇 XAU SNIPER AI V3.3\n\n"
            "🟢 Bot encendido\n"
            "📊 Mercado: XAU/USD\n"
            "⏱ Análisis: cada 100 segundos\n\n"
            "⚠️ Advertencias anticipadas: ACTIVAS\n\n"
            "🔍 Buscando oportunidades..."
        ),
        reply_markup=teclado()
    )


# =========================================================
# /STATUS
# =========================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if bot_encendido:
        estado = "🟢 ENCENDIDO"
    else:
        estado = "🔴 APAGADO"

    await update.message.reply_text(
        (
            "📊 XAU SNIPER AI V3.3\n\n"
            f"Estado: {estado}\n"
            "📈 Mercado: XAU/USD\n"
            "⏱ Intervalo: 100 segundos\n"
            "⚠️ Advertencias anticipadas: ACTIVADAS"
        ),
        reply_markup=teclado()
    )


# =========================================================
# ENVIAR ALERTA
# =========================================================

async def enviar_alerta(app, resultado):

    global ultima_alerta_tipo
    global ultima_alerta_precio
    global ultima_alerta_tiempo

    tipo = resultado.get("tipo")
    mensaje = resultado.get("mensaje")

    if not mensaje:
        mensaje = "😴 Sin señal"

    # -----------------------------------------------------
    # SIN SEÑAL
    # -----------------------------------------------------

    if tipo == "SIN_SEÑAL":

        print("📩 Tipo: SIN_SEÑAL")
        print(mensaje)

        return

    # -----------------------------------------------------
    # ERROR
    # -----------------------------------------------------

    if tipo == "ERROR":

        print("❌ Error de estrategia")

        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=mensaje
        )

        return

    # -----------------------------------------------------
    # PRECIO PARA CONTROL DE DUPLICADOS
    # -----------------------------------------------------

    precio = None

    try:

        precio = resultado.get("precio")

    except Exception:
        pass

    ahora = time.time()

    # -----------------------------------------------------
    # EVITAR REPETIR EXACTAMENTE LA MISMA ALERTA
    # DURANTE 5 MINUTOS
    # -----------------------------------------------------

    misma_alerta = (
        tipo == ultima_alerta_tipo
        and precio == ultima_alerta_precio
        and ahora - ultima_alerta_tiempo < 300
    )

    if misma_alerta:

        print(
            "♻️ Alerta repetida. No se envía."
        )

        return

    # -----------------------------------------------------
    # ENVIAR
    # -----------------------------------------------------

    await app.bot.send_message(
        chat_id=CHAT_ID,
        text=mensaje,
        reply_markup=teclado()
    )

    ultima_alerta_tipo = tipo
    ultima_alerta_precio = precio
    ultima_alerta_tiempo = ahora

    print(
        f"✅ ALERTA ENVIADA: {tipo}"
    )


# =========================================================
# CICLO DE ANÁLISIS
# =========================================================

async def ciclo_analisis(app):

    await asyncio.sleep(3)

    while True:

        try:

            # -------------------------------------------------
            # BOT APAGADO
            # -------------------------------------------------

            if not bot_encendido:

                print("⏸ Bot apagado")

                await asyncio.sleep(5)

                continue


            # -------------------------------------------------
            # ANALIZAR
            # -------------------------------------------------

            print("")
            print("🔍 Analizando...")

            resultado = analizar()


            # -------------------------------------------------
            # VALIDAR RESULTADO
            # -------------------------------------------------

            if not isinstance(resultado, dict):

                print(
                    "⚠️ Resultado inesperado de strategy.py"
                )

                resultado = {
                    "tipo": "ERROR",
                    "mensaje": "❌ Resultado inválido de estrategia"
                }


            tipo = resultado.get(
                "tipo",
                "SIN_SEÑAL"
            )

            mensaje = resultado.get(
                "mensaje",
                "😴 Sin señal"
            )


            # -------------------------------------------------
            # LOG
            # -------------------------------------------------

            print(
                f"📩 Tipo: {tipo}"
            )

            print(
                mensaje
            )


            # -------------------------------------------------
            # TELEGRAM
            # -------------------------------------------------

            await enviar_alerta(
                app,
                resultado
            )


            # -------------------------------------------------
            # ESPERA
            # -------------------------------------------------

            print(
                f"⏳ Esperando {INTERVALO} segundos..."
            )

            await asyncio.sleep(
                INTERVALO
            )


        except Exception as e:

            print(
                f"❌ ERROR EN CICLO: {e}"
            )

            try:

                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text=(
                        "❌ Error en XAU Sniper AI V3.3\n\n"
                        f"{e}"
                    )
                )

            except Exception as telegram_error:

                print(
                    f"❌ Error Telegram: {telegram_error}"
                )

            await asyncio.sleep(
                INTERVALO
            )


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # VALIDAR VARIABLES
    # -----------------------------------------------------

    if not BOT_TOKEN:

        raise ValueError(
            "❌ Falta BOT_TOKEN en Railway"
        )

    if not CHAT_ID:

        raise ValueError(
            "❌ Falta CHAT_ID en Railway"
        )


    print(
        "🚀 Iniciando XAU SNIPER AI V3.3..."
    )


    # -----------------------------------------------------
    # APPLICATION
    # -----------------------------------------------------

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(inicio)
        .build()
    )


    # -----------------------------------------------------
    # COMANDOS
    # -----------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            status
        )
    )


    # -----------------------------------------------------
    # BOTONES
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            botones
        )
    )


    # -----------------------------------------------------
    # INICIAR
    # -----------------------------------------------------

    print(
        "✅ Telegram configurado"
    )

    print(
        "✅ Motor de análisis configurado"
    )

    print(
        "⏱ Intervalo: 100 segundos"
    )

    print(
        "⚠️ Advertencias anticipadas: ACTIVADAS"
    )


    application.run_polling()


# =========================================================
# EJECUTAR
# =========================================================

if __name__ == "__main__":

    main()
