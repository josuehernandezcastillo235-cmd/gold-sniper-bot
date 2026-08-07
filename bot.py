from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes
)

import asyncio
import os
import json
from datetime import datetime

from strategy import analizar
print("🔥 BOT.PY V3.0 CARGADO")


TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

ARCHIVO = "historial.json"


ultima_senal = ""


def cargar_historial():

    try:
        with open(ARCHIVO, "r") as f:
            return json.load(f)

    except:
        return []



def guardar_historial(datos):

    with open(ARCHIVO, "w") as f:
        json.dump(
            datos,
            f,
            indent=4
        )



def guardar_senal(texto):

    historial = cargar_historial()

    registro = {
        "fecha": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "senal": texto,
        "estado": "pendiente"
    }

    historial.append(registro)

    guardar_historial(historial)



async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()


    historial = cargar_historial()


    if historial:

        if query.data == "tomar":

            historial[-1]["estado"] = "TOMADA"


        elif query.data == "ignorar":

            historial[-1]["estado"] = "IGNORADA"



        guardar_historial(historial)



    await query.edit_message_reply_markup(
        reply_markup=None
    )



    await query.message.reply_text(
        f"✅ Señal marcada como: {historial[-1]['estado']}"
    )



async def analizar_loop(app):

    global ultima_senal


    while True:

        try:

            senal = analizar()


            if (
                ("COMPRA" in senal or "VENTA" in senal)
                and senal != ultima_senal
            ):


                teclado = [
                    [
                        InlineKeyboardButton(
                            "✅ Tomar operación",
                            callback_data="tomar"
                        ),

                        InlineKeyboardButton(
                            "❌ Ignorar",
                            callback_data="ignorar"
                        )
                    ]
                ]


                mensaje = await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text=senal,
                    reply_markup=InlineKeyboardMarkup(
                        teclado
                    )
                )


                guardar_senal(senal)


                ultima_senal = senal



            elif "😴 Sin señal" in senal:

                ultima_senal = ""



        except Exception as e:


            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=f"❌ Error:\n{e}"
            )



        await asyncio.sleep(30)




async def inicio(app):

    await app.bot.send_message(
        chat_id=CHAT_ID,
        text="""🚀 XAU Sniper AI V3.0 iniciado correctamente.

✅ Conexión Telegram: OK
✅ Estrategia V3.0 cargada
📊 Mercado: XAU/USD
🧠 Historial activado"""
    )

print("🚀 INICIANDO XAU SNIPER")

async def main():

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CallbackQueryHandler(botones)
    )

    await app.initialize()
    await app.start()

    await inicio(app)

    asyncio.create_task(
        analizar_loop(app)
    )

    await app.updater.start_polling()

    # Mantener vivo el bot
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
