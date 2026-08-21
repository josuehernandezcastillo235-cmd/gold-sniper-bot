import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from strategy import analizar


# =========================================================
# XAU SNIPER AI V3.4
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

INTERVALO = 100


# =========================================================
# ESTADO
# =========================================================

bot_encendido = False
ultima_senal = None


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

async def inicio(application):

    global bot_encendido

    bot_encendido = False

    print(
        "🚀 XAU SNIPER AI V3.4 iniciado correctamente"
    )

    await application.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "🚀 XAU Sniper AI V3.4 iniciado correctamente.\n\n"
            "✅ Conexión Telegram: OK\n"
            "✅ Motor de análisis: OK\n"
            "📊 Mercado: XAU/USD\n"
            "⏱ Revisión: cada 100 segundos\n"
            "🕯️ Análisis: velas cerradas\n\n"
            "🔴 Estado: APAGADO\n"
            "▶️ Pulsa ENCENDER para comenzar."
        ),
        reply_markup=teclado()
    )

    print(
        "✅ Mensaje de inicio enviado"
    )

    print(
        "⏱️ Analizador programado cada 100 segundos"
    )


# =========================================================
# ANÁLISIS PROGRAMADO
# =========================================================

async def ejecutar_analisis(
    context: ContextTypes.DEFAULT_TYPE
):

    global ultima_senal

    if not bot_encendido:

        print(
            "⏸️ Bot apagado. No se analiza."
        )

        return

    try:

        print("===================================")
        print("🔍 Analizando XAU/USD...")

        resultado = analizar()

        # -------------------------------------------------
        # VALIDAR RESULTADO
        # -------------------------------------------------

        if resultado is None:

            print(
                "⚠️ Strategy devolvió None"
            )

            return

        if not isinstance(resultado, dict):

            print(
                "⚠️ Resultado inesperado:"
            )

            print(resultado)

            return

        tipo = resultado.get(
            "tipo",
            "SIN_SEÑAL"
        )

        mensaje = resultado.get(
            "mensaje",
            "😴 Sin señal"
        )

        print(
            f"📩 Tipo: {tipo}"
        )

        print(
            mensaje
        )

        # -------------------------------------------------
        # SIN SEÑAL
        # -------------------------------------------------

        if tipo == "SIN_SEÑAL":

            print(
                "😴 Sin señal"
            )

            return

        # -------------------------------------------------
        # ERROR
        # -------------------------------------------------

        if tipo == "ERROR":

            print(
                "❌ Error de estrategia"
            )

            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=mensaje
            )

            return

        # -------------------------------------------------
        # EVITAR DUPLICADOS
        # -------------------------------------------------

        if mensaje == ultima_senal:

            print(
                "♻️ Señal idéntica. No se envía."
            )

            return

        # -------------------------------------------------
        # ENVIAR TELEGRAM
        # -------------------------------------------------

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=mensaje,
            reply_markup=teclado()
        )

        ultima_senal = mensaje

        print(
            f"✅ {tipo} enviada a Telegram"
        )

    except Exception as e:

        print(
            f"❌ ERROR EN ANÁLISIS: {e}"
        )

        try:

            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    "❌ Error en XAU Sniper AI V3.4\n\n"
                    f"{e}"
                )
            )

        except Exception as telegram_error:

            print(
                "❌ Error enviando error a Telegram: "
                f"{telegram_error}"
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

    # -----------------------------------------------------
    # ENCENDER
    # -----------------------------------------------------

    if query.data == "encender":

        bot_encendido = True

        await query.edit_message_text(
            text=(
                "🟢 XAU SNIPER AI V3.4\n\n"
                "▶️ BOT ENCENDIDO\n\n"
                "🔍 Analizando XAU/USD\n"
                "⏱ Cada 100 segundos\n"
                "🕯️ Usando velas cerradas\n"
                "🎯 Pullback + continuación ACTIVOS"
            ),
            reply_markup=teclado()
        )

        print(
            "🟢 BOT ENCENDIDO"
        )

    # -----------------------------------------------------
    # APAGAR
    # -----------------------------------------------------

    elif query.data == "apagar":

        bot_encendido = False

        await query.edit_message_text(
            text=(
                "🔴 XAU SNIPER AI V3.4\n\n"
                "⏹ BOT APAGADO\n\n"
                "El análisis está detenido.\n"
                "Pulsa ▶️ ENCENDER para continuar."
            ),
            reply_markup=teclado()
        )

        print(
            "🔴 BOT APAGADO"
        )


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
            "🥇 XAU SNIPER AI V3.4\n\n"
            "🟢 Bot encendido\n"
            "📊 Mercado: XAU/USD\n"
            "⏱ Análisis: cada 100 segundos\n"
            "🕯️ Análisis con velas cerradas\n"
            "🎯 Pullback + continuación ACTIVOS\n\n"
            "🔍 Buscando oportunidades..."
        ),
        reply_markup=teclado()
    )

    print(
        "🟢 /start recibido"
    )


# =========================================================
# /STATUS
# =========================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if bot_encendido:

        estado_actual = "🟢 ENCENDIDO"

    else:

        estado_actual = "🔴 APAGADO"

    await update.message.reply_text(
        (
            "📊 XAU SNIPER AI V3.4\n\n"
            f"Estado: {estado_actual}\n"
            "📈 Mercado: XAU/USD\n"
            "⏱ Intervalo: 100 segundos\n"
            "🕯️ Velas cerradas: ACTIVAS\n"
            "🎯 Pullback + continuación: ACTIVOS\n"
            "📊 ADX mínimo confirmación: 20"
        ),
        reply_markup=teclado()
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
        "🚀 Iniciando XAU SNIPER AI V3.4..."
    )

    print(
        "📊 Mercado: XAU/USD"
    )

    print(
        "⏱ Intervalo: 100 segundos"
    )

    print(
        "🕯️ Análisis con velas cerradas"
    )

    print(
        "🎯 Pullback + continuación ACTIVOS"
    )

    print(
        "📊 ADX mínimo confirmación: 20"
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
    # JOBQUEUE
    # -----------------------------------------------------

    if application.job_queue is None:

        raise RuntimeError(
            "❌ JobQueue no disponible. "
            "Instala python-telegram-bot[job-queue]."
        )

    application.job_queue.run_repeating(
        ejecutar_analisis,
        interval=INTERVALO,
        first=5,
        name="analizador_xau"
    )

    print(
        "✅ Analizador programado correctamente"
    )

    print(
        "▶️ Primer análisis en 5 segundos"
    )

    # -----------------------------------------------------
    # POLLING
    # -----------------------------------------------------

    application.run_polling()


# =========================================================
# EJECUTAR
# =========================================================

if __name__ == "__main__":

    main()
