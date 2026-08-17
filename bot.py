import asyncio
import os

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes
)

from strategy import analizar


# =========================================================
# CONFIGURACIÓN
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

INTERVALO = 100


if not BOT_TOKEN:
    raise Exception("❌ Falta BOT_TOKEN")

if not CHAT_ID:
    raise Exception("❌ Falta CHAT_ID")


# =========================================================
# ESTADO
# =========================================================

bot_activo = False
tarea_analisis = None

ultima_alerta = None


# =========================================================
# BOTONES
# =========================================================

def teclado_principal():

    keyboard = [
        [
            InlineKeyboardButton(
                "▶️ ENCENDER",
                callback_data="encender"
            ),
            InlineKeyboardButton(
                "⏹️ APAGAR",
                callback_data="apagar"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 ESTADO",
                callback_data="estado"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# /START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🥇 XAU SNIPER AI V3.3\n\n"
        "🤖 Panel de control\n\n"
        "⏱️ Intervalo: 100 segundos\n"
        "🟡 Advertencias anticipadas: ACTIVAS\n"
        "📈 EMA20 no bloquea la advertencia anticipada\n\n"
        "Selecciona una opción:",
        reply_markup=teclado_principal()
    )


# =========================================================
# ESTADO
# =========================================================

async def mostrar_estado(query):

    if bot_activo:

        texto = (
            "🟢 BOT ACTIVO\n\n"
            "🔍 Analizando XAU/USD\n"
            "⏱️ Cada 100 segundos\n"
            "🟡 Advertencias anticipadas: ACTIVAS"
        )

    else:

        texto = (
            "🔴 BOT APAGADO\n\n"
            "El escáner está detenido.\n"
            "Pulsa ▶️ ENCENDER para comenzar."
        )

    await query.answer()

    await query.message.reply_text(
        texto,
        reply_markup=teclado_principal()
    )


# =========================================================
# ENCENDER
# =========================================================

async def encender(app, query):

    global bot_activo
    global tarea_analisis

    if bot_activo:

        await query.answer(
            "⚠️ El bot ya está encendido."
        )

        return

    bot_activo = True

    tarea_analisis = asyncio.create_task(
        ciclo_analisis(app)
    )

    await query.answer(
        "🟢 Bot encendido"
    )

    await query.message.reply_text(
        "🟢 XAU SNIPER AI V3.3 ENCENDIDO\n\n"
        "🔍 Comenzando análisis...\n"
        "⏱️ Próximas revisiones cada 100 segundos.\n"
        "🟡 Advertencias anticipadas activas.",
        reply_markup=teclado_principal()
    )


# =========================================================
# APAGAR
# =========================================================

async def apagar(query):

    global bot_activo
    global tarea_analisis

    if not bot_activo:

        await query.answer(
            "⚠️ El bot ya está apagado."
        )

        return

    bot_activo = False

    if tarea_analisis:

        tarea_analisis.cancel()
        tarea_analisis = None

    await query.answer(
        "🔴 Bot apagado"
    )

    await query.message.reply_text(
        "🔴 XAU SNIPER AI V3.3 APAGADO\n\n"
        "El análisis automático está detenido.",
        reply_markup=teclado_principal()
    )


# =========================================================
# CALLBACKS
# =========================================================

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if query.data == "encender":

        await encender(
            context.application,
            query
        )

    elif query.data == "apagar":

        await apagar(query)

    elif query.data == "estado":

        await mostrar_estado(query)


# =========================================================
# ANALIZAR
# =========================================================

async def analizar_mercado(app):

    global ultima_alerta

    print("🔍 Analizando...")

    try:

        resultado = analizar()

        tipo = resultado.get("tipo")
        mensaje = resultado.get("mensaje")

        print(f"📩 Tipo: {tipo}")

        if tipo == "SIN_SEÑAL":

            print("😴 Sin señal")
            return

        if tipo == "ERROR":

            print(mensaje)

            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=mensaje
            )

            return

        # =================================================
        # EVITAR REPETIR LA MISMA ADVERTENCIA
        # =================================================

        clave = mensaje

        if (
            tipo.startswith("ADVERTENCIA")
            and clave == ultima_alerta
        ):

            print("⚠️ Advertencia repetida ignorada")
            return

        # =================================================
        # LAS SEÑALES CONFIRMADAS SIEMPRE PUEDEN AVISAR
        # =================================================

        if tipo in [
            "COMPRA",
            "VENTA"
        ]:

            ultima_alerta = None

            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=mensaje
            )

            print("📨 SEÑAL CONFIRMADA ENVIADA")

            return

        # =================================================
        # ADVERTENCIA
        # =================================================

        ultima_alerta = clave

        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=mensaje
        )

        print("📨 ADVERTENCIA ENVIADA")

    except Exception as e:

        print(
            f"❌ ERROR BOT: {e}"
        )

        try:

            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=f"❌ Error XAU Sniper AI:\n{e}"
            )

        except Exception as telegram_error:

            print(
                f"❌ Error enviando Telegram: {telegram_error}"
            )


# =========================================================
# CICLO
# =========================================================

async def ciclo_analisis(app):

    print("🚀 CICLO DE ANÁLISIS INICIADO")

    try:

        while bot_activo:

            await analizar_mercado(app)

            if not bot_activo:
                break

            print(
                "⏳ Esperando 100 segundos..."
            )

            await asyncio.sleep(INTERVALO)

    except asyncio.CancelledError:

        print(
            "⏹️ CICLO DE ANÁLISIS DETENIDO"
        )

    except Exception as e:

        print(
            f"❌ ERROR CICLO: {e}"
        )


# =========================================================
# INICIO
# =========================================================

async def inicio(app):

    print("===================================")
    print("🔥 XAU SNIPER AI V3.3")
    print("🚀 BOT.PY CARGADO")
    print("===================================")

    await app.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "🚀 XAU Sniper AI V3.3 iniciado correctamente.\n\n"
            "✅ Conexión Telegram: OK\n"
            "✅ Motor de análisis: OK\n"
            "📊 Mercado: XAU/USD\n"
            "⏱️ Intervalo: 100 segundos\n\n"
            "🔴 El escáner está APAGADO.\n"
            "Pulsa ▶️ ENCENDER para comenzar."
        ),
        reply_markup=teclado_principal()
    )

    print("✅ Panel enviado a Telegram")


# =========================================================
# MAIN
# =========================================================

def main():

    print("🟡 INICIANDO BOT.PY...")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(inicio)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CallbackQueryHandler(botones)
    )

    print("✅ Aplicación Telegram preparada")
    print("🚀 Iniciando polling...")

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# EJECUTAR
# =========================================================

if __name__ == "__main__":
    main()
