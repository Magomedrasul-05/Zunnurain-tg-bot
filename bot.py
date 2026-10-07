import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp_socks import ProxyConnector
from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL") # например: http://user:pass@ip:port

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация БД (Персональные данные хранятся локально в РФ)
def init_db():
    conn = sqlite3.connect('users_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            phone_number TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Настройка прокси для aiogram
async def create_bot_and_dp():
    connector = ProxyConnector.from_url(PROXY_URL)
    session = AiohttpSession(connector=connector)
    bot = Bot(token=TOKEN, session=session)
    dp = Dispatcher()
    return bot, dp

# --- Хэндлеры ---
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот, работающий через прокси. Введите свой номер телефона для регистрации.")
    # В реальности здесь должна быть кнопка request_contact или текстовый ввод

async def handle_phone(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    phone = message.text # Упрощенно, в реальности лучше использовать Contact KeyboardButton

    # Сохраняем ПДн в локальную БД
    conn = sqlite3.connect('users_data.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, username, full_name, phone_number) VALUES (?, ?, ?, ?)",
                   (user_id, username, full_name, phone))
    conn.commit()
    conn.close()

    await message.answer("Спасибо! Ваши данные успешно сохранены на серверах в РФ.")

# --- Запуск ---
async def main():
    init_db()
    bot, dp = await create_bot_and_dp()
    
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(handle_phone, F.text) # Упрощенный прием текста как номера

    # Пропускаем старые обновления, чтобы бот не спамил при перезапуске
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот успешно запущен через прокси!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
