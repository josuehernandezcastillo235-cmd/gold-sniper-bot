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
# XAU SNIPER AI V4.2
# TELEGRAM + MOTOR DE ESTRATEGIA
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

INTERVALO = 100


# =========================================================
# ESTADO DEL BOT
# =========================================================

bot_encendido = False

# Guardamos ID + tipo.
#
# Esto es MUY importante:
#
# PREALERTA ID123
#      ↓
# CONFIRMADA ID123
#
# Son el mismo setup, pero son DOS estados distintos.
#
# Con el sistema anterior se podía bloquear la confirmación
# porque el ID era exactamente el mismo.
# =========================================================

ultima_senal_id = None
ultimo_tipo_senal = None


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

    # -----------------------------------------------------
    # ENCENDER
    # -----------------------------------------------------

    if query.data == "encender":

        bot_encendido = True

        await query.message.reply_text(
            (
                "🟢 XAU SNIPER AI V4.2\n\n"
                "▶️ BOT ENCENDIDO\n\n"
                "🔍 Analizando XAU/USD...\n\n"
                "🧠 Estructura\n"
                "⚡ Momentum\n"
                "💧 Liquidez\n"
                "🚀 Impulso + Pullback\n"
                "💥 Continuación\n\n"
                "🟡 Prealertas ACTIVAS\n"
                "🟢 Confirmaciones ACTIVAS\n"
                "🔴 Invalidaciones ACTIVAS\n\n"
                "⏱ Próximo análisis automático."
            ),
            reply_markup=teclado()
        )

        print("🟢 BOT ENCENDIDO")

        return

    # -----------------------------------------------------
    # APAGAR
    # -----------------------------------------------------

    if query.data == "apagar":

        bot_encendido = False

        await query.message.reply_text(
            (
                "🔴 XAU SNIPER AI V4.2\n\n"
                "⏹ BOT APAGADO\n\n"
                "El análisis automático "
                "queda detenido.\n\n"
                "Pulsa ▶️ ENCENDER "
                "para continuar."
            ),
            reply_markup=teclado()
        )

        print("🔴 BOT APAGADO")

        return


# =========================================================
# INICIO DE APLICACIÓN
# =========================================================

async def inicio(application):

    global bot_encendido
    global ultima_senal_id
    global ultimo_tipo_senal

    bot_encendido = False

    ultima_senal_id = None
    ultimo_tipo_senal = None

    print(
        "🚀 XAU SNIPER AI V4.2 "
        "iniciado correctamente"
    )

    await application.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "🚀 XAU SNIPER AI V4.2\n\n"
            "✅ Telegram: OK\n"
            "✅ Motor V4: OK\n"
            "✅ Proveedor: BiQuote\n"
            "📊 Mercado: XAU/USD\n"
            "⏱ Revisión: cada 100 segundos\n\n"
            "🔴 Estado: APAGADO\n\n"
            "🧠 Motor:\n"
            "Estructura → Impulso → "
            "Pullback → Continuación\n\n"
            "🟡 Prealertas: ACTIVAS\n"
            "🟢 Confirmaciones: ACTIVAS\n"
            "🔴 Invalidaciones: ACTIVAS\n\n"
            "⚠️ Modo: PAPER / ESCÁNER"
        ),
        reply_markup=teclado()
    )

    print("✅ Mensaje de inicio enviado")


# =========================================================
# ANÁLISIS PROGRAMADO
# =========================================================

async def ejecutar_analisis(
    context: ContextTypes.DEFAULT_TYPE
):

    global ultima_senal_id
    global ultimo_tipo_senal

    # -----------------------------------------------------
    # BOT APAGADO
    # -----------------------------------------------------

    if not bot_encendido:

        print(
            "⏸️ Bot apagado. "
            "No se analiza."
        )

        return

    try:

        print("")
        print(
            "==================================="
        )
        print(
            "🔍 ANALIZANDO XAU/USD..."
        )
        print(
            "==================================="
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

        identificador = resultado.get(
            "id"
        )

        print(
            f"📩 Tipo: {tipo}"
        )

        if identificador:
            print(
                f"🆔 ID: {identificador}"
            )

        print(mensaje)

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
        # DUPLICADOS
        #
        # Ya NO comparamos solamente el ID.
        #
        # PREALERTA ABC
        # CONFIRMADA ABC
        #
        # deben poder enviarse ambas.
        # -------------------------------------------------

        if (
            identificador
            and
            identificador == ultima_senal_id
            and
            tipo == ultimo_tipo_senal
        ):

            print(
                "♻️ Evento duplicado. "
                "No se envía."
            )

            return

        # -------------------------------------------------
        # ENVIAR EVENTO
        # -------------------------------------------------

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=mensaje,
            reply_markup=teclado()
        )

        ultima_senal_id = identificador
        ultimo_tipo_senal = tipo

        print(
            "📨 Evento enviado a Telegram"
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
            "🥇 XAU SNIPER AI V4.2\n\n"
            "🟢 BOT ENCENDIDO\n\n"
            "📊 Mercado: XAU/USD\n"
            "📡 Datos: BiQuote\n"
            "⏱ Análisis: cada 100 segundos\n\n"
            "🧠 Estructura + Movimiento\n"
            "⚡ Momentum\n"
            "💧 Liquidez\n"
            "🚀 Impulso + Pullback\n"
            "💥 Continuación\n\n"
            "🟡 Buscando prealertas...\n"
            "🟢 Esperando confirmaciones..."
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

    if bot_encendido:
        estado_actual = "🟢 ENCENDIDO"
    else:
        estado_actual = "🔴 APAGADO"

    await update.message.reply_text(
        (
            "📊 XAU SNIPER AI V4.2\n\n"
            f"Estado: {estado_actual}\n"
            "📈 Mercado: XAU/USD\n"
            "📡 Datos: BiQuote\n"
            "⏱ Intervalo: 100 segundos\n\n"
            "🧠 Motor:\n"
            "Estructura + Momentum + "
            "Liquidez\n"
            "Impulso + Pullback + "
            "Continuación\n\n"
            "🟡 Prealertas: ACTIVAS\n"
            "🟢 Confirmaciones: ACTIVAS\n"
            "🔴 Invalidaciones: ACTIVAS\n\n"
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
        "🚀 Iniciando XAU SNIPER AI V4.2..."
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
        "🧠 Motor V4: estructura + movimiento"
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
    
