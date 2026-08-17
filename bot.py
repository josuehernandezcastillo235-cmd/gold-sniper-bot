import asyncio
import os
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from strategy import analizar


# =========================================================
# CONFIGURACIÓN
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


# =========================================================
# VALIDACIÓN
# =========================================================

if not BOT_TOKEN:
    raise Exception("❌ Falta la variable BOT_TOKEN")

if not CHAT_ID:
    raise Exception("❌ Falta la variable CHAT_ID")


# =========================================================
# VARIABLES DE CONTROL
# =========================================================

ultima_senal = None
ultima_alerta_tiempo = None


# =========================================================
# COMANDO /START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🚀 XAU Sniper AI V3.3 activo.\n\n"
        "✅ Telegram conectado\n"
        "✅ Motor de análisis conectado\n"
        "📊 Mercado: XAU/USD\n"
        "⏱ Análisis: cada 5 minutos"
    )


# =========================================================
# ANALIZAR MERCADO
# =========================================================

async def analizar_mercado(app):

    global ultima_senal
    global ultima_alerta_tiempo

    print("🔍 Analizando...")

    try:

        resultado = analizar()

        print("📩 Resultado:")
        print(resultado)

        # =================================================
        # SI NO HAY SEÑAL
        # =================================================

        if resultado == "😴 Sin señal":

            print("😴 Sin señal")
            return

        # =================================================
        # EVITAR DUPLICADOS
        # =================================================

        ahora = datetime.now()

        if (
            resultado == ultima_senal
            and ultima_alerta_tiempo is not None
            and (ahora - ultima_alerta_tiempo).total_seconds() < 300
        ):

            print("⚠️ Señal duplicada ignorada")
            return

        # =================================================
        # GUARDAR SEÑAL
        # =================================================

        ultima_senal = resultado
        ultima_alerta_tiempo = ahora

        # =================================================
        # ENVIAR TELEGRAM
        # =================================================

        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=resultado
        )

        print("📨 Señal enviada a Telegram")

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
# CICLO PRINCIPAL
# =========================================================

async def ciclo_analisis(app):

    print("🚀 CICLO DE ANÁLISIS INICIADO")

    while True:

        try:

            await analizar_mercado(app)

        except Exception as e:

            print(
                f"❌ ERROR EN CICLO: {e}"
            )

        print("⏳ Esperando 5 minutos...")

        await asyncio.sleep(300)


# =========================================================
# INICIO DEL BOT
# =========================================================

async def inicio(app):

    print("===================================")
    print("🔥 XAU SNIPER AI V3.3")
    print("🚀 BOT.PY CARGADO")
    print("===================================")

    try:

        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                "🚀 XAU Sniper AI V3.3 iniciado correctamente.\n\n"
                "✅ Conexión Telegram: OK\n"
                "✅ Motor de análisis: OK\n"
                "📊 Mercado: XAU/USD\n"
                "⏱ Revisión: cada 5 minutos"
            )
        )

        print("✅ Mensaje inicial enviado a Telegram")

    except Exception as e:

        print(
            f"❌ No se pudo enviar mensaje inicial: {e}"
        )

    asyncio.create_task(
        ciclo_analisis(app)
    )

    print("🔍 Analizador automático iniciado")


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
