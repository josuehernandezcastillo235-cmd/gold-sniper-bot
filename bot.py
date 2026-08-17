import os
import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from strategy import analizar


# =========================================================
# CONFIGURACIÓN
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

INTERVALO = 100

encendido = True

ultima_alerta = None


# =========================================================
# BOTONES
# =========================================================

def teclado():

    keyboard = [
        [
            InlineKeyboardButton(
                "🟢 ENCENDER",
                callback_data="encender"
            ),
            InlineKeyboardButton(
                "🔴 APAGAR",
                callback_data="apagar"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# BOTÓN
# =========================================================

async def botones(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global encendido

    query = update.callback_query

    await query.answer()

    if query.data == "encender":

        encendido = True

        await query.edit_message_text(
            "🟢 XAU SNIPER AI V3.3\n\n"
            "Estado: ENCENDIDO 🟢\n\n"
            "🔍 Analizando cada 100 segundos...",
            reply_markup=teclado()
        )

        print("🟢 BOT ENCENDIDO")

    elif query.data == "apagar":

        encendido = False

        await query.edit_message_text(
            "🔴 XAU SNIPER AI V3.3\n\n"
            "Estado: APAGADO 🔴\n\n"
            "Pulsa ENCENDER para continuar.",
            reply_markup=teclado()
        )

        print("🔴 BOT APAGADO")


# =========================================================
# COMANDO /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🥇 XAU SNIPER AI V3.3\n\n"
        "Control del escáner:",
        reply_markup=teclado()
    )


# =========================================================
# ANALIZADOR
# =========================================================

async def ciclo():

    global ultima_alerta

    while True:

        try:

            if encendido:

                print("🔍 Analizando...")

                resultado = analizar()

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

                print(mensaje)

                # =========================================
                # EVITAR REPETICIONES
                # =========================================

                if tipo != "SIN_SEÑAL":

                    clave = (
                        tipo,
                        mensaje
                    )

                    if clave != ultima_alerta:

                        ultima_alerta = clave

                        await enviar_alerta(
                            mensaje
                        )

                    else:

                        print(
                            "⏭️ Alerta repetida, no se envía."
                        )

                else:

                    print(
                        "😴 Sin señal"
                    )

            else:

                print(
                    "⏸️ Bot apagado..."
                )

        except Exception as e:

            print(
                f"❌ ERROR EN CICLO: {e}"
            )

        print(
            f"⏳ Esperando {INTERVALO} segundos..."
        )

        await asyncio.sleep(
            INTERVALO
        )


# =========================================================
# ENVIAR ALERTA
# =========================================================

async def enviar_alerta(mensaje):

    try:

        chat_id = int(CHAT_ID)

        await application.bot.send_message(
            chat_id=chat_id,
            text=mensaje,
            reply_markup=teclado()
        )

        print(
            "📩 Alerta enviada a Telegram"
        )

    except Exception as e:

        print(
            f"❌ ERROR TELEGRAM: {e}"
        )


# =========================================================
# INICIO
# =========================================================

async def inicio():

    global application

    print(
        "==================================="
    )

    print(
        "🔥 BOT.PY V3.3 CARGADO"
    )

    print(
        "🚀 XAU SNIPER AI V3.3 ACTIVO"
    )

    print(
        "⏱️ Intervalo: 100 segundos"
    )

    print(
        "==================================="
    )

    await application.bot.send_message(
        chat_id=int(CHAT_ID),
        text=(
            "🚀 XAU Sniper AI V3.3 "
            "iniciado correctamente.\n\n"
            "✅ Conexión Telegram: OK\n"
            "✅ Motor de análisis: OK\n"
            "📊 Mercado: XAU/USD\n"
            "⏱ Revisión: cada 100 segundos"
        ),
        reply_markup=teclado()
    )

    asyncio.create_task(
        ciclo()
    )


# =========================================================
# MAIN
# =========================================================

application = None


def main():

    global application

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
        CallbackQueryHandler(
            botones
        )
    )

    print(
        "🚀 Iniciando XAU SNIPER AI V3.3..."
    )

    application.run_polling()


if __name__ == "__main__":
    main()
