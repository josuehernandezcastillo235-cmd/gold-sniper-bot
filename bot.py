import os
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from strategy import analizar


# =========================================================
# XAU SNIPER AI V4.0
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
    format=(
        "%(asctime)s - "
        "%(name)s - "
        "%(levelname)s - "
        "%(message)s"
    ),
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
        "🚀 XAU SNIPER AI V4.0 "
        "iniciado correctamente"
    )

    await application.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "🚀 XAU SNIPER AI V4.0\n\n"
            "✅ Conexión Telegram: OK\n"
            "✅ Motor de análisis: OK\n"
            "📊 Mercado: XAU/USD\n"
            "⏱ Revisión: cada 100 segundos\n\n"
            "🔴 Estado: APAGADO\n\n"
            "🧠 Motor:\n"
            "Estructura + Impulso + "
            "Pullback + Continuación\n\n"
            "⚠️ Modo: PAPER / ESCÁNER"
        ),
        reply_markup=teclado()
    )

    print(
        "✅ Mensaje de inicio enviado"
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
            "⏸️ Bot apagado. "
            "No se analiza."
        )

        return

    try:

        print(
            "==================================="
        )

        print(
            "🔍 Analizando XAU/USD..."
        )

        resultado = analizar()

        if resultado is None:

            print(
                "⚠️ Strategy devolvió None"
            )

            return

        if not isinstance(
            resultado,
            dict
        ):

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

            return

        # -------------------------------------------------
        # ERROR
        # -------------------------------------------------

        if tipo == "ERROR":

            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=mensaje,
                reply_markup=teclado()
            )

            return

        # -------------------------------------------------
        # EVITAR DUPLICADOS
        # -------------------------------------------------

        if mensaje == ultima_senal:

            print(
                "♻️ Señal idéntica. "
                "No se envía."
            )

            return

        # -------------------------------------------------
        # TELEGRAM
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
                    "❌ ERROR XAU SNIPER V4.0\n\n"
                    f"{e}"
                ),
                reply_markup=teclado()
            )

        except Exception as telegram_error:

            print(
                "❌ Error enviando error "
                f"a Telegram: {telegram_error}"
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

        if bot_encendido:

            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    "🟢 XAU SNIPER AI V4.0\n\n"
                    "▶️ El bot ya está ENCENDIDO.\n\n"
                    "🔍 El escáner continúa "
                    "analizando XAU/USD."
                ),
                reply_markup=teclado()
            )

            return

        bot_encendido = True

        # NUEVO MENSAJE.
        # NO editamos el anterior.

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                "🟢 XAU SNIPER AI V4.0\n\n"
                "▶️ BOT ENCENDIDO\n\n"
                "🔍 Analizando XAU/USD\n"
                "⏱ Cada 100 segundos\n\n"
                "🧠 Lectura principal:\n"
                "Estructura → Impulso → "
                "Pullback → Continuación\n\n"
                "⚠️ Modo: PAPER / ESCÁNER"
            ),
            reply_markup=teclado()
        )

        print(
            "🟢 BOT ENCENDIDO"
        )

    # =====================================================
    # APAGAR
    # =====================================================

    elif query.data == "apagar":

        if not bot_encendido:

            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    "🔴 XAU SNIPER AI V4.0\n\n"
                    "⏹ El bot ya está APAGADO.\n\n"
                    "El análisis permanece detenido."
                ),
                reply_markup=teclado()
            )

            return

        bot_encendido = False

        # NUEVO MENSAJE.
        # NO editamos el anterior.

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                "🔴 XAU SNIPER AI V4.0\n\n"
                "⏹ BOT APAGADO\n\n"
                "El análisis está detenido.\n\n"
                "Pulsa ▶️ ENCENDER "
                "para continuar."
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
            "🥇 XAU SNIPER AI V4.0\n\n"
            "🟢 Bot encendido\n"
            "📊 Mercado: XAU/USD\n"
            "⏱ Análisis: cada 100 segundos\n\n"
            "🧠 Estructura + Movimiento\n"
            "🚀 Impulso + Pullback\n"
            "💥 Continuación\n\n"
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
            "📊 XAU SNIPER AI V4.0\n\n"
            f"Estado: {estado_actual}\n"
            "📈 Mercado: XAU/USD\n"
            "⏱ Intervalo: 100 segundos\n\n"
            "🧠 Motor:\n"
            "Estructura + Impulso + "
            "Pullback + Continuación\n\n"
            "⚠️ Modo: PAPER / ESCÁNER"
        ),
        reply_markup=teclado()
    )


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # VARIABLES
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
        "🚀 Iniciando XAU SNIPER AI V4.0..."
    )

    print(
        "📊 Mercado: XAU/USD"
    )

    print(
        "⏱ Intervalo: 100 segundos"
    )

    print(
        "🧠 Motor V4: estructura y movimiento"
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
    # JOB QUEUE
    # -----------------------------------------------------

    if application.job_queue is None:

        raise RuntimeError(
            "❌ JobQueue no disponible.\n"
            "Instala:\n"
            "python-telegram-bot[job-queue]==22.2"
        )

    application.job_queue.run_repeating(
        ejecutar_analisis,
        interval=INTERVALO,
        first=5,
        name="analizador_xau_v4"
    )

    print(
        "✅ Analizador programado"
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
