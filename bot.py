from telegram import Bot
import asyncio
import os
from strategy import analizar

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

async def main():
    bot = Bot(token=TOKEN)

    while True:
        señal = analizar()

        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"🥇 Gold Sniper Bot\n\n{señal}"
        )

        await asyncio.sleep(300)  # espera 5 minutos

if __name__ == "__main__":
    asyncio.run(main())
