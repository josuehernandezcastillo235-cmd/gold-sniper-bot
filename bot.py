from telegram import Bot
import asyncio
import os
from strategy import analizar

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


async def main():

    bot = Bot(token=TOKEN)

    await bot.send_message(
        chat_id=CHAT_ID,
        text="""🚀 XAU Sniper AI V3.0 iniciado correctamente.

✅ Conexión Telegram: OK
✅ Estrategia V3.0 cargada
📊 Mercado: XAU/USD
⚡ Revisión rápida activada"""
    )

    ultima_senal = ""
    contador = 0

    while True:

        try:

            senal = analizar()

            if (
                ("COMPRA" in senal or "VENTA" in senal)
                and senal != ultima_senal
            ):

                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=senal
                )

                ultima_senal = senal

            elif "😴 Sin señal" in senal:
                ultima_senal = ""

            contador += 1

            if contador >= 120:

                await bot.send_message(
                    chat_id=CHAT_ID,
                    text="""🤖 XAU Sniper AI sigue activo.

📈 Monitoreando XAU/USD
😴 Sin oportunidades por el momento."""
                )

                contador = 0

        except Exception as e:

            await bot.send_message(
                chat_id=CHAT_ID,
                text=f"❌ Error:\n{e}"
            )

        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
