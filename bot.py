from telegram import Bot
import asyncio
import os

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

async def main():
    bot = Bot(token=TOKEN)

    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="🚀 Prueba: Gold Sniper Bot conectado en Railway."
        )
        print("✅ Mensaje enviado a Telegram")

    except Exception as e:
        print("❌ Error Telegram:", e)

if __name__ == "__main__":
    asyncio.run(main())
