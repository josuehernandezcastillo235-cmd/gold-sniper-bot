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
        text="""🚀 XAU Sniper AI V2.0 iniciado correctamente.

✅ Conexión Telegram: OK
✅ Estrategia V2.0 cargada
📊 Mercado: XAU/USD
⏱ Revisión: cada 5 minutos"""
    )

    contador = 0
    ultima_senal = ""

    while True:

        senal = analizar()

        # Solo enviar si es una señal NUEVA
        if (
            ("COMPRA" in senal or "VENTA" in senal)
            and senal != ultima_senal
        ):

            await bot.send_message(
                chat_id=CHAT_ID,
                text=f"""🥇 XAU Sniper Alert

{senal}"""
            )

            ultima_senal = senal

        # Si ya no hay señal, reinicia para permitir una futura alerta
        elif "😴 Sin señal" in senal:
            ultima_senal = ""

        contador += 1

        # Mensaje de estado cada hora
        if contador >= 12:

            await bot.send_message(
                chat_id=CHAT_ID,
                text="""🤖 XAU Sniper AI sigue activo.

😴 Sin señales por el momento.
⏰ Monitoreando XAU/USD."""
            )

            contador = 0

        await asyncio.sleep(300)


if __name__ == "__main__":
    asyncio.run(main())
