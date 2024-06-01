import sqlite3
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import Router
from aiogram.fsm.storage.memory import MemoryStorage
from config import API_TOKEN

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Функция для подключения к базе данных
def connect_db():
    return sqlite3.connect('users.db')

# Функция для создания таблицы пользователей
def create_user_table():
    conn = connect_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                (id INTEGER PRIMARY KEY, telegram_id INTEGER, correct_answers INTEGER, total_answers INTEGER)''')
    conn.commit()
    conn.close()

# Функция для регистрации пользователя
def register_user(telegram_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute('INSERT INTO users (telegram_id, correct_answers, total_answers) VALUES (?, ?, ?)', (telegram_id, 0, 0))
    conn.commit()
    conn.close()

# Хэндлер для команды /start
@router.message(Command("start"))
async def send_welcome(message: Message):
    telegram_id = message.from_user.id
    conn = connect_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE telegram_id=?', (telegram_id,))
    user = c.fetchone()
    if user is None:
        register_user(telegram_id)
        await message.reply("Привет! Я бот-тренажер. Ты зарегистрирован.")
    else:
        await message.reply("Привет! Ты уже зарегистрирован.")

if __name__ == '__main__':
    create_user_table()
    dp.run_polling(bot, skip_updates=True)
