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
        text="""🚀 Gold Sniper Bot iniciado correctamente en Railway.

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
                text=f"🥇 Gold Sniper Alert\n\n{señal}"
            )

        # Cada 12 ciclos (12 × 5 min = 60 min)
        contador += 1
        if contador >= 12:
            await bot.send_message(
                chat_id=CHAT_ID,
                text="🤖 Gold Sniper sigue activo.\n😴 Sin señales por el momento.\n⏰ El sistema continúa monitoreando GOLD."
            )
            contador = 0

        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())
