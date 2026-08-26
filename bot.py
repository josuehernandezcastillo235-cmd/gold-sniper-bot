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
# XAU SNIPER AI V4.1
# TELEGRAM + MOTOR DE ESTRUCTURA
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
# BOTONES
# =========================================================

async def botones(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global bot_encendido

    query = update.callback_query

    await query.answer()

    if query.data == "encender":

        bot_encendido = True

        await query.message.reply_text(
            (
                "🟢 XAU SNIPER AI V4.1\n\n"
                "▶️ BOT ENCENDIDO\n\n"
                "🔍 Analizando XAU/USD...\n\n"
                "🧠 Estructura\n"
                "🚀 Impulso\n"
                "🔄 Pullback\n"
                "💥 Continuación\n\n"
                "📡 Proveedor: BiQuote\n"
                "⏱ Próximo análisis automático."
            ),
            reply_markup=teclado()
        )

        print("🟢 BOT ENCENDIDO")

        return

    if query.data == "apagar":

        bot_encendido = False

        await query.message.reply_text(
            (
                "🔴 XAU SNIPER AI V4.1\n\n"
                "⏹ BOT APAGADO\n\n"
                "El análisis automático "
                "queda detenido.\n\n"
                "Pulsa ▶️ ENCENDER "
                "para continuar."
            ),
            reply_markup=teclado()
        )

        print("🔴 BOT APAGADO")


# =========================================================
# INICIO
# =========================================================

async def inicio(application):

    global bot_encendido

    bot_encendido = False

    print(
        "🚀 XAU SNIPER AI V4.1 "
        "iniciado correctamente"
    )

    await application.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "🚀 XAU SNIPER AI V4.1\n\n"
            "✅ Telegram: OK\n"
            "✅ Motor V4.1: OK\n"
            "📊 Mercado: XAU/USD\n"
            "📡 Datos: BiQuote\n"
            "⏱ Revisión: cada 100 segundos\n\n"
            "🔴 Estado: APAGADO\n\n"
            "🧠 Motor:\n"
            "Estructura → Impulso → "
            "Pullback → Continuación\n\n"
            "⚠️ Modo: PAPER / ESCÁNER"
        ),
        reply_markup=teclado()
    )

    print("✅ Mensaje de inicio enviado")


# =========================================================
# ANÁLISIS
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

        print("")
        print("===================================")
        print("🔍 ANALIZANDO XAU/USD...")
        print("===================================")

        resultado = analizar()

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

        print(f"📩 Tipo: {tipo}")
        print(mensaje)

        if tipo == "SIN_SEÑAL":

            return

        if tipo == "ERROR":

            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=mensaje,
                reply_markup=teclado()
            )

            return

        identificador = resultado.get("id")

        if (
            identificador
            and identificador == ultima_senal
        ):

            print(
                "♻️ Señal duplicada. "
                "No se envía."
            )

            return

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=mensaje,
            reply_markup=teclado()
        )

        if identificador:

            ultima_senal = identificador

        print(
            "📨 Señal enviada a Telegram"
        )

    except Exception as e:

        logger.exception(
            "❌ Error en ejecutar_analisis"
        )

        print(
            f"❌ ERROR BOT: {e}"
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
            "🥇 XAU SNIPER AI V4.1\n\n"
            "🟢 BOT ENCENDIDO\n\n"
            "📊 Mercado: XAU/USD\n"
            "📡 Datos: BiQuote\n"
            "⏱ Análisis: cada 100 segundos\n\n"
            "🧠 Estructura + Movimiento\n"
            "🚀 Impulso + Pullback\n"
            "💥 Continuación\n\n"
            "🔍 Buscando oportunidades..."
        ),
        reply_markup=teclado()
    )

    print("🟢 /start recibido")


# =========================================================
# /STATUS
# =========================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    estado_actual = (
        "🟢 ENCENDIDO"
        if bot_encendido
        else "🔴 APAGADO"
    )

    await update.message.reply_text(
        (
            "📊 XAU SNIPER AI V4.1\n\n"
            f"Estado: {estado_actual}\n"
            "📈 Mercado: XAU/USD\n"
            "📡 Datos: BiQuote\n"
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

    if not BOT_TOKEN:

        raise ValueError(
            "❌ Falta BOT_TOKEN en Railway"
        )

    if not CHAT_ID:

        raise ValueError(
            "❌ Falta CHAT_ID en Railway"
        )

    print(
        "🚀 Iniciando XAU SNIPER AI V4.1..."
    )

    print(
        "📊 Mercado: XAU/USD"
    )

    print(
        "📡 Proveedor: BiQuote"
    )

    print(
        "⏱ Intervalo: 100 segundos"
    )

    print(
        "🧠 Motor V4.1: "
        "estructura + movimiento"
    )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(inicio)
        .build()
    )

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

    application.add_handler(
        CallbackQueryHandler(
            botones
        )
    )

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

    application.run_polling()


# =========================================================
# EJECUTAR
# =========================================================

if __name__ == "__main__":

    main()
