import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import Message
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

# Функция для подключения к базе данных вопросов
def connect_questions_db():
    return sqlite3.connect('questions.db')

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

# Функция для получения случайного вопроса из базы данных
def get_random_question():
    conn = connect_questions_db()
    c = conn.cursor()
    c.execute('SELECT id, question FROM questions ORDER BY RANDOM() LIMIT 1')
    question = c.fetchone()
    conn.close()
    return question

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

# Хэндлер для команды /question
@router.message(Command("question"))
async def send_question(message: Message):
    question = get_random_question()
    if question:
        question_id, question_text = question
        await message.reply(f"Вопрос: {question_text}")
    else:
        await message.reply("В базе данных нет вопросов.")

# Хэндлер для обработки текстовых сообщений (ответов)
@router.message()
async def handle_answer(message: Message):
    answer_text = message.text
    telegram_id = message.from_user.id

    # Здесь можно добавить логику проверки ответа
    # Пример: считаем ответ всегда правильным для демонстрации
    correct = True  # или False в зависимости от проверки

    conn = connect_db()
    c = conn.cursor()
    if correct:
        c.execute('UPDATE users SET correct_answers = correct_answers + 1, total_answers = total_answers + 1 WHERE telegram_id=?', (telegram_id,))
        await message.reply("Правильно! Продолжайте в том же духе.")
    else:
        c.execute('UPDATE users SET total_answers = total_answers + 1 WHERE telegram_id=?', (telegram_id,))
        await message.reply("Неправильно. Попробуйте еще раз.")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_user_table()
    dp.run_polling(bot, skip_updates=True)
