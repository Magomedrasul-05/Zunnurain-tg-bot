import asyncio
import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL")  # например: socks5h://user:pass@ip:port

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# Состояния FSM для пошагового ввода
# ============================================
class UserRegistration(StatesGroup):
    waiting_for_phone = State()      # Ожидание номера телефона
    waiting_for_birthplace = State() # Ожидание места рождения


# ============================================
# Инициализация базы данных (ПДн хранятся локально в РФ)
# ============================================
def init_db():
    """Создаёт таблицу пользователей, если её нет."""
    conn = sqlite3.connect('users_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            phone_number TEXT,
            birthplace TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")


# ============================================
# Создание бота с прокси
# ============================================
async def create_bot_and_dp():
    """Создаёт экземпляр бота с подключением через прокси."""
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=TOKEN, session=session)
    # MemoryStorage хранит состояния в памяти (для продакшена лучше Redis)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    return bot, dp


# ============================================
# Обработчики команд
# ============================================
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start - начинает регистрацию."""
    await message.answer(
        "Привет! 👋\n\n"
        "Я бот для регистрации пользователей.\n"
        "Ваши персональные данные хранятся локально в соответствии с 152-ФЗ.\n\n"
        "📱 Введите свой номер телефона:"
    )
    # Устанавливаем состояние ожидания номера телефона
    await state.set_state(UserRegistration.waiting_for_phone)


async def handle_phone(message: types.Message, state: FSMContext):
    """Обработчик номера телефона - сохраняет и запрашивает место рождения."""
    phone = message.text
    
    # Сохраняем номер во временное хранилище FSM
    await state.update_data(phone_number=phone)
    
    logger.info(f"Получен номер телефона от пользователя {message.from_user.id}")
    
    # Запрашиваем место рождения
    await message.answer(
        "✅ Номер получен!\n\n"
        "🏠 Теперь введите ваше место рождения (город, страна):"
    )
    
    # Переключаем состояние на ожидание места рождения
    await state.set_state(UserRegistration.waiting_for_birthplace)


async def handle_birthplace(message: types.Message, state: FSMContext):
    """Обработчик места рождения - сохраняет все данные в БД."""
    birthplace = message.text
    
    # Получаем данные из FSM
    data = await state.get_data()
    phone_number = data.get('phone_number')
    
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    full_name = message.from_user.full_name or "unknown"
    
    # Сохраняем все ПДн в локальную БД
    try:
        conn = sqlite3.connect('users_data.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, username, full_name, phone_number, birthplace) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, full_name, phone_number, birthplace)
        )
        conn.commit()
        conn.close()
        
        logger.info(f"Сохранены данные пользователя {user_id}: {phone_number}, {birthplace}")
        
        await message.answer(
            "✅ Спасибо! Ваши данные успешно сохранены на серверах в РФ.\n\n"
            f"📱 Номер: {phone_number}\n"
            f"🏠 Место рождения: {birthplace}\n\n"
            "Если нужно изменить данные, отправьте /start"
        )
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")
        await message.answer("❌ Произошла ошибка при сохранении данных. Попробуйте позже.")
    finally:
        # Завершаем состояние FSM
        await state.clear()


# ============================================
# Главная функция запуска
# ============================================
async def main():
    """Точка входа в приложение."""
    # Проверка наличия необходимых переменных окружения
    if not TOKEN:
        logger.error("BOT_TOKEN не найден в .env файле!")
        return
    if not PROXY_URL:
        logger.error("PROXY_URL не найден в .env файле!")
        return

    # Инициализация БД
    init_db()

    # Создание бота и диспетчера
    bot, dp = await create_bot_and_dp()

    # Регистрация обработчиков (порядок важен!)
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(handle_phone, UserRegistration.waiting_for_phone)
    dp.message.register(handle_birthplace, UserRegistration.waiting_for_birthplace)

    # Удаляем webhook и пропускаем старые обновления
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Бот успешно запущен через прокси!")
    logger.info(f"Прокси: {PROXY_URL}")

    # Запуск polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


# ============================================
# Запуск приложения
# ============================================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем")
