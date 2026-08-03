from telegram import Bot
import asyncio
import os
from strategy import analizar

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


async def main():

    bot = Bot(token=TOKEN)

    # Mensaje al iniciar
    await bot.send_message(
        chat_id=CHAT_ID,
        text="""🚀 XAU Sniper AI iniciado correctamente en Railway.

✅ Conexión Telegram: OK
✅ Motor de análisis: OK
📊 Mercado: XAU/USD
⏱ Revisión: cada 5 minutos"""
    )

    contador = 0

    while True:

        señal = analizar()

        # Envía alerta solo si hay compra o venta
        if "COMPRA" in señal or "VENTA" in señal:

            await bot.send_message(
                chat_id=CHAT_ID,
                text=f"""🥇 XAU Sniper Alert

{señal}"""
            )


        # Mensaje de estado cada hora
        contador += 1

        if contador >= 12:

            await bot.send_message(
                chat_id=CHAT_ID,
                text="""🤖 XAU Sniper AI sigue activo.

😴 Sin señales por el momento.
⏰ El sistema continúa monitoreando XAU/USD."""
            )

            contador = 0


        await asyncio.sleep(300)


if __name__ == "__main__":
    asyncio.run(main())
